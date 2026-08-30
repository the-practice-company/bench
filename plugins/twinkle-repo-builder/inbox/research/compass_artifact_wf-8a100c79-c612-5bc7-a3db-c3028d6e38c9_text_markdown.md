# Шаблонизация репозиториев и управление дрейфом инстансов (R2)

## TL;DR
- Для семейства markdown-репозиториев-контекста, редактируемых человеком в Obsidian, единственный инструмент, покрывающий полный цикл «сгенерировать → обновить живой инстанс → измерить дрейф», — **Copier** (`.copier-answers.yml` + git 3-way merge + `copier update --check` в CI). Cookiecutter одноразов; cruft добавляет к нему отслеживание, но наследует хрупкость патча; GitHub template repositories и Backstage рвут связь с шаблоном в момент создания.
- Разделяйте `core/` не как монолит, а на **три слоя по способу управления**: (1) managed-блоки внутри маркеров `<!-- BEGIN MANAGED -->`, перезаписываемые автоматически; (2) свободные зоны, которых шаблон никогда не касается (`_skip_if_exists`); (3) явный реестр намеренных расхождений (`.template-exceptions.yml`), чтобы отчёт о дрейфе не шумел. Всё, что требует ручной дисциплины, деградирует — поэтому дрейф должен проверяться машиной (`copier update --check` / `cruft check --strict` в CI), а не памятью человека.
- Насильственная унификация в полирепо — известный способ отказа: команды «обходят» путь, если он медленнее workaround, а механизм update молча ломается, как только инстанс изменил ту же строку, что и шаблон. Стройте на PR-фан-ауте с правом инстанса сказать «нет» (opt-out как первоклассная запись), а не на forced-push из шаблона.

## Key Findings

1. **Модель обновления — главный водораздел инструментов.** Cookiecutter по дизайну одноразовый: рендерит дерево и «забывает» связь; апстрим-фича «обновить проект из шаблона» отклонена/не реализована (issue #784, #1472). Copier хранит в инстансе `.copier-answers.yml` (версия шаблона `_commit`, `_src_path`, ответы) и на `copier update` выполняет git-3-way-merge. Cruft делает то же поверх cookiecutter, храня `.cruft.json` с commit-хэшем.
2. **Разрешение конфликтов сводится к трём практикам:** (а) 3-way merge с inline-маркерами (`_conflict: inline`) или `.rej`-файлами (`_conflict: rej`); (б) managed-блоки между маркерами `DO NOT EDIT`; (в) зоны, полностью исключённые из обновления (`_skip_if_exists`, cruft `skip`). Боли задокументированы в issue-трекерах.
3. **Каскадное наследование конфигурации плохо масштабируется по глубине.** ESLint отказался от файлового каскада `.eslintrc` из-за невидимого наследования, но вернул `extends` под давлением жалоб. `.editorconfig`: ближайший файл выигрывает, стоп на `root=true`. Kustomize: не строить глубокие overlay-цепочки.
4. **Разделение общего контента:** submodule (явная версия, операционная нагрузка) vs subtree (прозрачно, раздувает историю) vs sync-бот (PR-фан-аут). Для markdown-в-Obsidian каждый вариант имеет специфические ограничения.
5. **Дрейф измеряется как в IaC/GitOps** (Terraform `plan -detailed-exitcode`, ArgoCD `OutOfSync`); файловый эквивалент — `cruft check` / `copier update --check` в CI по расписанию + compliance-сканеры по флоту.
6. **Опыт платформенных команд:** forced standardization ломается социально и технически; в монорепо унификация даётся даром, в полирепо стоит недель координации.

## Details

### 1. Инструменты скаффолдинга и их модели обновления

**Cookiecutter — одноразовый по дизайну.** Рендерит Jinja2-дерево при `cookiecutter <url>` и не сохраняет версию шаблона/ответы в форме, привязанной к обновлению. Апстрим-запросы «обновить проект из его cookiecutter» (issue #784) и «обратная генерация шаблона» (issue #1472) остались нереализованными; сообщество решает это внешними обёртками (cookiecutter_project_upgrader, cruft). Практический вывод: cookiecutter годится только как движок рендера под cruft, не как основа живого семейства.

**Copier — единственный, спроектированный вокруг update.** Инстанс содержит `.copier-answers.yml` с `_commit` (git-тег/commit шаблона), `_src_path` и всеми ответами. На `copier update`:
1. checkout старой версии (из `_commit`), рендер с сохранёнными ответами → «старое сгенерированное»;
2. checkout новой версии, рендер (с до-запросом новых вопросов) → «новое сгенерированное»;
3. diff между ними;
4. наложение diff на рабочее дерево через git 3-way merge.

Локальные изменения сохраняются, пока не конфликтуют по тем же строкам. Условия применимости жёсткие: инстанс — git-репозиторий, `git status` чист, шаблон версионирован git-тегами (PEP 440), `.copier-answers.yml` **никогда не редактируется руками** (ломает smart-diff; апстрим прямо отказывает в поддержке таких кейсов: «This is an unsupported way to update. Please do not open issues if you updated this way»). Параметр `context_lines` (по умолчанию 3) управляет точностью: больше строк — точнее, но больше конфликтов.

**Cruft — надстройка над cookiecutter для отслеживания дрейфа.** Хранит `.cruft.json` с commit-хэшем шаблона на момент инстанцирования. `cruft update` вычисляет diff шаблона от этого хэша до HEAD и накладывает патчем; `cruft diff` показывает расхождение инстанс↔шаблон; `cruft check` (exit 1 при рассинхроне) ставится в CI; `cruft link` привязывает уже существующий проект. Известный способ отказа (cruft/cruft issue #47, cruft 2.2.0): при дрейфе, когда 3-way merge невозможен, cruft может отрапортовать успех, оставив мусор — дословно: «it fails but then marks it as a success… `error: repository lacks the necessary blob to fall back on 3-way merge`… `Good work! Project's cruft has been updated and is as clean as possible!` .orig files are messy, but it feels even worse to mark the project as updated when the update fully failed». То есть автоматический sync молча перестаёт работать ровно тогда, когда инстанс ушёл далеко.

**GitHub template repositories рвут связь.** «Create from template» делает снимок дерева без общей git-истории. Официальный ответ GitHub community (Discussion #168227): «GitHub templates are designed for one-time scaffolding. After generating a repo from a template, there's no built-in sync mechanism». Обходные пути (добавить `upstream` remote с `no_push`, `git-upstream-template`) — самодельные и хрупкие.

**Backstage software templates / golden paths.** Scaffolder генерирует репозиторий в момент создания (skeleton/ + Nunjucks, `publish:github`), регистрирует в каталоге, опционально открывает PR. Но обратной связи с уже созданными репозиториями нет: обновление `template.yaml` не докатывается до порождённых репозиториев. Markus Eisele (Red Hat Developer, «10 tips for better Backstage Software Templates», 17.03.2025) предупреждает: «Like regular software applications, you'll need to update your templates… Be sure to avoid scaffolding code repositories with outdated code or dependencies. An outdated template is a liability, not an asset». То есть Backstage решает задачу «правильный старт», но не «поддержание живого инстанса». Для R2 (дрейф) Backstage сам по себе бесполезен, его надо дополнять cruft/copier или sync-ботом.

### 2. Разрешение конфликтов при обновлении

- **Inline vs rej (copier).** `_conflict: inline` (по умолчанию) — git-маркеры `<<<<<<<`; `_conflict: rej` — рядом кладётся `.rej`. Рекомендация апстрима: pre-commit-хук `check-merge-conflict` (для inline) и запрет коммита `.rej`, иначе неразрешённый конфликт попадёт в историю. Баг #1833: в некоторых mergetool/IDE (VS Code, PyCharm, `git mergetool`) конфликт «исчезает», показывая только локальную версию — молчаливая потеря изменений шаблона.
- **Managed-блоки.** Паттерн «генерируемая секция между маркерами, всё вне маркеров сохраняется» реализован в buildout (`# START/END … Do not remove or edit`), controller-gen (`+kubebuilder:` маркеры), Ansible `blockinfile` (`# {mark} ANSIBLE MANAGED BLOCK`), npm template-oss («This file is partially managed by @npmcli/template-oss. Edits may be overwritten»). Это самый предсказуемый способ для markdown: агент и человек видят явную границу «моё / шаблонное».
- **«Шаблон всегда выигрывает» vs «инстанс всегда выигрывает».** template-oss — шаблон выигрывает внутри managed-зон (edits overwritten; версионируется без semver, «Major versions are reserved for breaking changes to files written to a repo by this package»); copier `_skip_if_exists` — инстанс выигрывает навсегда (файл не рендерится при update, даже если существует). Смешанная стратегия (managed-блоки внутри свободного файла) — то, что нужно для `core/`.
- **Боль «всегда конфликт».** copier Discussion #456: любой файл, эволюционировавший в шаблоне, помечается «conflict» на update, даже если инстанс его не трогал (это «файл, который надо обновить», а не настоящий конфликт; настоящие дают `.rej`) — источник шума, который надо гасить фильтрацией в CI/агенте.

### 3. Каскадное наследование как модель для разделяемого контекста

- **ESLint** — важнейший постмортем. Старый `.eslintrc` каскадировал по дереву каталогов (merge всех файлов вверх). Официальная формулировка проблемы: «A file deep in `src/api/handlers/` might be affected by `.eslintrc` files it couldn't see, creating behavior that was difficult to explain». Flat config убрал скрытое наследование (один `eslint.config.js`, всё явно), но пользователи жаловались, что расширять конфиги стало трудно («For beginners, the spread syntax is confusing… some plugins export config objects while others export config arrays»), и апстрим **вернул `extends`** в марте 2025 через `defineConfig()`. Вывод для R2: явная композиция > неявный каскад, но полное отсутствие механизма `extends` тоже отвергается людьми.
- **`.editorconfig`** — чистая модель «ближайший выигрывает + стоп-граница»: поиск вверх по дереву, «properties in closer files take precedence», поиск останавливается на `root=true`. Прямой аналог для репозитория: `CLAUDE.md` в корне = глобальные правила, папочные инструкции переопределяют по мере погружения, папка может объявить «стоп, дальше не наследуем». (Осторожно: некоторые инструменты, например Oxfmt, `root=true` игнорируют и берут только ближайший файл — семантика каскада не универсальна.)
- **tsconfig `extends`** — одиночное/списочное наследование с переопределением; проблема — относительные пути и `references` в монорепо.
- **Kustomize overlays** — критика сложности задокументирована: официальные примеры признают, что наивный overlay-на-overlay «does not scale well in more complex scenarios»; рекомендация — «start simple with single-level inheritance and add layers only when clear benefits emerge», глубокие цепочки overlay «hard to reason about». Helm-лагерь аргументирует, что тот же эффект достигается «without the extra complexity of Kustomize». Практический порог, за которым люди перестают понимать, — глубина 2–3 слоя.

### 4. Разделение общего контента между репозиториями

| Механизм | Явность версии | Скрытая связность | Офлайн | Пригодность для markdown/Obsidian |
|---|---|---|---|---|
| git submodule | Высокая (pinned commit) | Низкая (явный указатель) | Хорошо после `--recurse` | Работает (obsidian-git #93), но wiki-ссылки через границу vault ломаются; symlink через границу устройства не переносится Obsidian |
| git subtree | Средняя (в истории) | Средняя (код влит) | Отлично (всё в репо) | Прозрачно для читателя (нет init-шага), но раздувает историю и усложняет push обратно |
| Версионируемый пакет (npm/pip/OCI) | Высокая (semver) | Низкая | Зависит от реестра | Плохо: markdown-заметки не пакет, человек не может править «в пакете» |
| Sync-бот (PR-фан-аут) | Средняя (по коммиту) | Высокая (много копий) | Плохо (нужен CI/сеть) | Хорошо: файлы физически в каждом репо, редактируются в Obsidian; PR даёт право «последнего слова» |

Для контекста заказчика (markdown, человек правит в Obsidian, submodule внутри vault) ключевые ограничения: (1) Obsidian не двигает файлы через границу устройства/симлинка своим файловым менеджером; (2) wiki-ссылки `[[...]]` через границу submodule требуют «absolute path in vault» и всё равно хрупки; (3) obsidian-git поддерживает submodule, но на мобильном ограниченно. Sync-боты (repo-file-sync-action от BetaHuhn: `sync.yml`, per-repo override через `{owner}/{repo}/{file}`, лейбл `sync` для гашения PR-fatigue, «Create a pull request in the target repo so you have the last say on what gets merged»; Redocly-форк; «Sync Files to Multiple Repos via API» с централизованным JSON-конфигом; GitHub-паттерн gh-aw fan-out с `max`/`title-prefix`/`labels` для контроля ширины фан-аута) дают модель «источник → PR во все инстансы» с правом инстанса отклонить.

### 5. Обнаружение и измерение дрейфа

Переносимое из IaC/GitOps:
- **Terraform** `plan -detailed-exitcode` на расписании: exit 2 = дрейф. Урок Scalr («Terraform Drift Detection»): опасность «drift by silence» — пайплайн умирает без ошибки, дрейф всплывает через недели: «Across Scalr's own fleet we measured 121 broken VCS connections in a single 30-day window, 79 of them fully broken providers on paid accounts. Drift by silence is one of the most common patterns in Scalr's support queue: the GitOps pipeline dies without an error anyone sees, and the gap only surfaces weeks later when someone runs a plan by hand». Прямой аналог: если CI-крон `cruft check` перестал запускаться, вы не узнаете о дрейфе — мониторьте здоровье самого детектора.
- **ArgoCD** `OutOfSync` через семантический diff «рендер vs live»; уроки — ложные срабатывания (переформатирование, лишние поля), которые надо явно игнорировать (`ignoreDifferences`, `compareoptions`) — аналог реестра намеренных расхождений.
- **Файловые шаблоны:** `cruft check` (exit 1) / `copier update --check` в CI по расписанию (типовой пример — еженедельный cron «Template Compliance»: если шаблон дрейфует, проверка падает, и команда знает, что пора запускать update); OpenSSF Scorecard (Microsoft OSPO регулярно считает score для всех публичных и приватных репозиториев, «making historical information and trends available»; проект сканирует >1 млн репозиториев еженедельно), repolinter — как флот-уровневые compliance-сканеры/дашборды.

### 6. Опыт платформенных команд

- **Golden path → golden cage.** «On day one, golden paths and golden cages look exactly the same. You only really find out you're in a cage when the platform you use doesn't let you do something» (Steve Fenton). Критерий полезности (Rajabi, COO CloudBolt, в материале platformengineering.com «The Rise of the Golden Path»): «A good golden path is the fastest way to ship, not a fence. If the paved road is slower than the workaround, you built a speed bump».
- **Что нельзя централизовать.** Astronomer (Bas Harenslak): при сотнях команд повторять `cruft update` вручную не масштабируется, поэтому крон-бот раз в час запускает `cruft check` и авто-открывает PR; но forced-push из шаблона «requires the platform team to have a good understanding of the development team's repositories to avoid breaking things. This doesn't scale well to hundreds of development teams» — «the development teams are then given the choice to accept, change, or deny the pull request». Остаточная неустранимая боль — merge-конфликты, «when the same line of code is changed in both repositories».
- **Монорепо vs полирепо.** В монорепо унификация «даётся даром»: одна версия, cross-cutting change одним diff (Meta), «no v1.2 vs v1.3 vs v1.9 debates». В полирепо (AWS) — «the same CDK patterns rewritten across dozens of teams», version-pinning hell; миграция 15→1 репо у SID Technologies сократила deployment time на 82%. Block (Cash App) отмечает, что SHA-версионирование библиотек «removed the forcing function for backward compatibility». Вывод для R2: семейство markdown-репозиториев — это полирепо, и вы платите полирепо-налог; минимизируйте общий контент, обязанный быть синхронным.
- **Forced standardization откатывали.** Задокументированы кейсы, где мандат «все обязаны использовать шаблон» приводил к тому, что команды забрасывали общий путь и делали руками (один рассказ: «three different Postgres operators… none properly maintained… developers gave up and just installed Postgres manually»); и постмортемы, где именно scaffolding-дрейф (устаревший k8s-манифест, CI-галочка, не проверяющая то, что предполагалось, секреты, сделанные тремя способами в трёх сервисах) вызывал инциденты, а насильственный путь отвергали: «Teams routed around it… A platform that developers have to be forced onto is not a platform, it's a tax». Измеренная эмпирика адопшна (Tasrie IT): «teams that invest in well-designed golden paths see voluntary platform adoption rates above 80%, while those that skip them struggle to reach 20%».

## Рекомендуемая механика для разделения `core/`-контекста

**Базовое решение: Copier как движок шаблона всего репозитория + трёхслойная модель `core/` + CI-детектор дрейфа + PR-фан-аут с opt-out.**

Разбейте `core/` по способу управления, а не по теме:
1. **Managed-зоны** — блоки между `<!-- BEGIN TEMPLATE:principles -->` / `<!-- END TEMPLATE -->` внутри markdown-файлов. Только они перезаписываются на update. Вне маркеров — свободный текст инстанса, шаблон не трогает. (Модель buildout/template-oss/controller-gen.)
2. **Skip-зоны** — файлы в `_skip_if_exists` (описание субъекта, локальные принципы): рендерятся один раз, при update не трогаются никогда.
3. **Реестр расхождений** `.template-exceptions.yml` — явный список файлов/блоков, где инстанс намеренно разошёлся, чтобы детектор дрейфа их не считал шумом (аналог ArgoCD `ignoreDifferences` / Terraform `lifecycle.ignore_changes`).

### Сценарий (а): выкатка изменения принципов на десять инстансов
1. Правка в managed-блоке `core/principles.md` в репозитории-шаблоне; коммит; git-тег новой версии (PEP 440).
2. Sync-бот/CI (по крону) для каждого из 10 инстансов запускает `copier update --defaults --vcs-ref=<tag>` в чистом рабочем дереве.
3. Где managed-блок не тронут локально — 3-way merge проходит чисто, бот открывает PR «template vX.Y».
4. Где инстанс правил тот же блок — inline-конфликт/`.rej`; PR помечается лейблом `template-conflict`, назначается человеку.
5. CLAUDE.md-агент в каждом инстансе может сам разрешать тривиальные конфликты (по инструкции в папочном README), эскалируя человеку только настоящие семантические.
6. Merge PR обновляет `.copier-answers.yml` (`_commit`), закрывая цикл; `copier update --check` в CI снова зелёный.

Право «accept / change / deny» на уровне PR — это ровно то, что Astronomer называет масштабируемой альтернативой forced-push.

### Сценарий (б): инстанс отказывается от изменения
1. Человек/агент в PR решает не принимать новый принцип.
2. Вместо «просто закрыть PR» (тогда дрейф будет шуметь вечно) — добавляется запись в `.template-exceptions.yml`: файл/блок + причина + версия, до которой синхронизировано.
3. Детектор дрейфа (`cruft check`/`copier update --check`, обёрнутый скриптом, читающим реестр) исключает эти пути из diff → отчёт остаётся тихим.
4. Альтернатива для полного локального переопределения — вынести принцип из managed-зоны в skip-зону (перестаёт быть общим). Это фиксирует «намеренную дивергенцию» машиночитаемо, а не в памяти человека.

## Recommendations

1. **Сейчас (1 инстанс → шаблон).** Возьмите Copier, а не cookiecutter/GitHub template. Сконвертируйте текущий репозиторий в шаблон, положите `.copier-answers.yml.jinja`, версионируйте тегами. Порог отказа: если у вас не будет ≥3 инстансов, накладные расходы Copier не окупятся — оставайтесь на ручном копировании.
2. **`core/` разбейте на managed/skip/exceptions с первого дня.** Не кладите весь `core/` под перезапись — это гарантированный источник конфликтов на каждом update (Discussion #456).
3. **Дрейф — только машиной.** Поставьте `copier update --check` (или `cruft check --strict`) в CI по недельному крону в каждом инстансе + мониторинг, что сам крон жив (урок «drift by silence» от Scalr). Ручные ресинхронизации деградируют — это ваше главное ограничение.
4. **Общий контент минимизируйте.** Для `core/` предпочтите managed-блоки внутри Copier-шаблона, а не submodule (ломает wiki-ссылки) и не пакет (нельзя править в Obsidian). Submodule — только для истинно неизменяемых `sources/`, разделяемых как есть, если вообще.
5. **Opt-out — первоклассная запись, не «закрыть PR».** Реестр `.template-exceptions.yml` обязателен, иначе отчёт о дрейфе зашумится и его перестанут читать (деградация дисциплины).
6. **Каскад держите ≤2 уровней.** CLAUDE.md-корень + папочные переопределения (модель `.editorconfig`), без глубоких overlay-цепочек (урок Kustomize/ESLint).
7. **Не форсируйте унификацию.** Каждый инстанс должен мочь отклонить изменение шаблона без «наказания» отчётом (иначе — «routed around it… a tax»). Порог пересмотра: если >30% инстансов держат один и тот же exception — это сигнал, что принцип не должен быть в managed-зоне вовсе; вынесите его в skip-зону.

## Caveats
- Copier `update` требует git-чистого дерева и запрещает ручную правку `.copier-answers.yml`; нарушение делает smart-diff непредсказуемым (апстрим не поддерживает такие кейсы).
- 3-way merge и патчи хрупки на markdown с длинными похожими блоками (copier может «перемещать» строки при малом `context_lines`); managed-маркеры снижают, но не устраняют риск.
- cruft может молча отрапортовать успех при провале merge (issue #47, cruft 2.2.0) — не полагайтесь на его exit-code без дополнительной проверки на `.rej`/`.orig`.
- Obsidian: submodule внутри vault ограничен на мобильном, wiki-ссылки через границу репозитория хрупки, symlink через границу устройства не переносится файловым менеджером; семантика `.editorconfig`-каскада не универсальна между инструментами.
- Часть источников по «форсированной унификации» — опытные/анекдотические статьи и вендор-блоги (Astronomer, Tasrie, InfoWorld-колонка), а не аудированные постмортемы; проценты адопшна (80%+/20%, 85%) иллюстративны и/или self-reported, а не измерены на одном контролируемом развёртывании.
- Backstage/golden-path материалы преимущественно описывают генерацию, а не поддержание; переносить их выводы на задачу дрейфа надо с оговоркой.