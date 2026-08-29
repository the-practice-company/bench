# Покрытие классов находок

Правило секции 16: у каждого гейта либо исполняемая проверка на фикстуре,
либо обязательное поле с объяснением, почему её нет. Пустым оставить нельзя.
Таблицу держит `tests/test_gate_coverage.py`.

Строк больше, чем классов, и это намеренно: у класса с несколькими причинами
— своя строка на причину, и у каждой строки свой тест. Одна строка на класс
скрывала вторую половину проверки: `unparseable` числился доказанным блочным
скаляром во frontmatter, а форму `hooks.json` тем же классом проверяет
совсем другой код, о котором таблица не говорила ничего.

Что проверяется механически: цитата ведёт на существующий тест
(`_problems`) и заявленное число находок совпадает с тем, что гейт даёт на
битой фикстуре сейчас (`_miscounts`). **Прозу не проверяет никто:** строка
может назвать верное число и при этом описывать не тот механизм — так и
случилось со строкой `gate-not-read-only`, которая полгейта описывала хешем
фикстуры, тогда как код давно хеширует весь корень.

| класс | чем доказан | тест |
|---|---|---|
| `unresolved` | битая фикстура, 5 находок: несуществующая заметка, `scripts/move.py`, `areas/hiring/items/` и `scripts/rename.py` в rule-файле, `[[projects/dup]]` — путь не существует, откат на basename запрещён | `tests/test_fixtures.py::TestExactFindings::test_every_link_finding_sits_on_its_own_specimen` |
| `md-link-to-file` | битая фикстура, 1 находка | `tests/test_fixtures.py::TestExactFindings::test_every_link_finding_sits_on_its_own_specimen` |
| `link-to-transient` | битая фикстура, 1 находка | `tests/test_fixtures.py::TestExactFindings::test_every_link_finding_sits_on_its_own_specimen` |
| `escapes-root` | битая фикстура, 3 находки: абсолютный путь, `..` выше корня и глоб наружу (`~/vault/**/*.md`: шаблон границы не отменяет) | `tests/test_fixtures.py::TestExactFindings::test_every_link_finding_sits_on_its_own_specimen` |
| `dead-allow` | битая фикстура, 2 находки: строка без причины и мёртвая строка | `tests/test_fixtures.py::TestExactFindings::test_every_link_finding_sits_on_its_own_specimen` |
| `broad-allow` | битая фикстура, 1 находка: `*тень*` — подстрока в глоб-написании, гасит обе ссылки `areas/hiring/broad.md` и потому считается использованной, так что `dead-allow` о ней молчит | `tests/test_fixtures.py::TestExactFindings::test_every_link_finding_sits_on_its_own_specimen` |
| `broad-allow` | четыре написания одной семантики (`*a*`, `*`, `?*`, `[a-z]*`), одной погашенной цели довольно, и обратная сторона: якорный `черновики/*` — законная «строка на паттерн» секции 13, а не находка | `tests/test_check_links.py::TestOverBroadAllowEntry::test_a_substring_wearing_glob_syntax_is_over_broad` |
| `ambiguous` | битая фикстура, 1 находка при двух `dup.md` | `tests/test_fixtures.py::TestExactFindings::test_every_link_finding_sits_on_its_own_specimen` |
| `orphan` | битая фикстура, 1 находка в `sources` | `tests/test_fixtures.py::TestExactFindings::test_every_link_finding_sits_on_its_own_specimen` |
| `undecodable` | битая фикстура, 1 находка: `areas/hiring/cp1251.md`. Ссылка внутри него в счёт `unresolved` не входит — вернётся чтение с заменой байта, и она войдёт | `tests/test_fixtures.py::TestExactFindings::test_every_link_finding_sits_on_its_own_specimen` |
| `undecodable` | вторая половина того же: две кодировки одной ссылки не дают двух вердиктов, файл в UTF-16 не исчезает молча, а `.gitignore`, `.link-allow` и `settings.json` называются каждый со своим последствием | `tests/test_check_links.py::TestUndecodableFileIsAFinding::test_the_same_link_in_two_encodings_never_becomes_a_target_nobody_typed` |
| `undecodable` | второй производитель: гейт frontmatter. Замещающий знак в **значении** поля давал `value-outside-vocabulary` на значении, которого автор не писал | `tests/test_check_frontmatter.py::TestUndecodableFileIsAFinding::test_every_unreadable_file_is_named_and_none_is_judged` |
| `undecodable` | третий производитель: проверка пакета на нечитаемом `.gitignore`. Периметр сужался до умолчаний молча, а вердикт обещан не зависящим от неотслеживаемого состояния | `tests/test_check_package.py::TestPackageCheck::test_an_unreadable_gitignore_is_named_rather_than_narrowed_silently` |
| `undecodable` | там же — `hooks.json` и `SKILL.md`: замена байта делала находки `unknown-matcher Ed?it` и `skill-name-mismatch 'nam?e' != 'name'` про текст, которого автор не писал. Граница проходит по вопросу, а не по файлу: скан абсолютных путей читает с заменой и дальше, потому что `�` ни на один префикс не похож | `tests/test_check_package.py::TestPackageCheck::test_an_unreadable_hooks_json_never_invents_a_matcher` |
| `missing-required` | битая фикстура, 3 находки: дважды поле `created` стартового набора и `status`, обязательный архетипу `pipeline` (архетипу, а не виду: вид требует своё третьим списком) | `tests/test_fixtures.py::TestExactFindings::test_every_frontmatter_finding_sits_on_its_own_specimen` |
| `missing-required` | граница послабления волны 3: собственный README коллекции с перечисления записей снят, а `projects/<имя>/README.md` записью остался. Послабление привязано к **своему** виду, а не к соседству с любым `views.base`: заведи проект свою коллекцию — широкое прочтение сняло бы его карточку с проверки вовсе | `tests/test_check_frontmatter.py::TestCollectionOwnReadme::test_a_project_readme_is_still_a_record` |
| `value-outside-vocabulary` | битая фикстура, 1 находка: `status: активно` вне объявленного словаря | `tests/test_fixtures.py::TestExactFindings::test_every_frontmatter_finding_sits_on_its_own_specimen` |
| `value-outside-vocabulary` | обратная сторона того же послабления: снятый с перечисления README продолжает **питать словарь**, и значение вне него у записи остаётся находкой. Снять файл с перечисления и снять его с чтения — две разные правки, и вторая молча обесценила бы весь класс | `tests/test_check_frontmatter.py::TestCollectionOwnReadme::test_the_declaration_still_feeds_the_vocabulary` |
| `unparseable` | битая фикстура, 1 находка: блочный скаляр в поле с потребителем | `tests/test_fixtures.py::TestExactFindings::test_every_frontmatter_finding_sits_on_its_own_specimen` |
| `unparseable` | второй производитель: временный пакет, семь неверных форм `hooks.json` — по одной на каждый уровень, от «верхний уровень не объект» до «`hooks[0].hooks[0]` не объект». Валидный JSON неверной формы ронял всю проверку исключением | `tests/test_check_package.py::TestPackageCheck::test_every_wrong_shape_of_hooks_json_is_named` |
| `unparseable` | третий производитель: `hooks.json` без верхнего ключа `hooks` — файл валиден, а контракт не объявлен, и Claude Code не запускает ни одного хука молча | `tests/test_check_package.py::TestPackageCheck::test_hooks_json_without_the_top_level_key_is_a_finding` |
| `unknown-hook-event` | временный пакет с `OnFullMoon` | `tests/test_check_package.py::TestPackageCheck::test_unknown_hook_event_fails` |
| `unknown-hook-type` | тип вне закрытого списка | `tests/test_check_package.py::TestPackageCheck::test_unknown_hook_type_fails` |
| `unknown-matcher` | матчер вне закрытого множества, включая опечатку `Bahs` | `tests/test_check_package.py::TestPackageCheck::test_matcher_typo_is_caught` |
| `absolute-path` | двадцать пять форм в тесте. Корней в `_ABSOLUTE_PREFIXES` тридцать два, и одиннадцать из них в тесте не встречаются ни разу (`/opt/`, `/etc/`, `/root/`, `/srv/`, `/mnt/`, `/media/`, `/Applications/`, `/Library/`, `/System/`, `/workspace/`, `/workspaces/`): проверено, что ветка списка работает, а не что список полон. Кроме списка в регулярке три ветки — домашний каталог свой и чужой, буква диска Windows, UNC, — и все три в тесте есть | `tests/test_check_package.py::TestPackageCheck::test_every_absolute_form_is_caught` |
| `relative-path-in-skill` | пять форм вызова в скилле: без запускающего слова, через `-m`, через `uv run`, а также вызов в `hooks/`, а не только в `scripts/` — каталогов пакета в проверке два | `tests/test_check_package.py::TestPackageCheck::test_every_relative_call_form_in_a_skill_is_caught` |
| `relative-path-in-skill` | написания через `./` и законная форма `${CLAUDE_PLUGIN_ROOT}`, которая обязана остаться тихой | `tests/test_check_package.py::TestPackageCheck::test_the_dot_slash_spellings_are_caught_and_plugin_root_still_is_not` |
| `relative-path-in-skill` | второй периметр: команда в `hooks.json`. Это такой же путь и такой же чужой, а проверялись раньше только скиллы | `tests/test_check_package.py::TestPackageCheck::test_a_relative_command_in_hooks_json_is_caught` |
| `destructive-example` | одиннадцать форм в инструкциях ADOPT: `mv`, `rm`, `rmdir`, `git clean`, `git checkout --`, `git reset --hard`, `find -delete`, `rmtree`, `rsync --delete`, `truncate -s 0`, усекающее перенаправление | `tests/test_check_package.py::TestPackageCheck::test_every_destructive_form_is_caught` |
| `destructive-example` | ещё четырнадцать форм: перечисление было короче того, что перечисляет. `git restore` вместо устаревшего `checkout --`, `rm` в хвосте конвейера через `xargs`, `os.remove` и `unlink`, форма усечения, продавливающая `noclobber`, семейство «переписать на месте» — `sed -i`, `tee`, `cp`, `dd`, `install`, `shred`, `chmod`, `git worktree remove`. Веток в `DESTRUCTIVE` двадцать | `tests/test_check_package.py::TestPackageCheck::test_the_sibling_spelling_of_every_listed_form_is_caught_too` |
| `gate-not-read-only` | хеш **всего корня репозитория** до и после прогона гейта. Хеш одной фикстуры был слеп по построению: посаженный образец писал файл двумя уровнями выше, `counts()` оставался пустым, а файл появлялся | `tests/test_check_package.py::TestGateNotReadOnlyMechanism::test_a_gate_that_writes_outside_the_fixture_is_caught` |
| `gate-not-read-only` | тот же хеш на гейте, который пишет внутрь фикстуры | `tests/test_check_package.py::TestGateNotReadOnlyMechanism::test_mutating_gate_is_caught` |
| `tests-touched-product` | тот же приём вокруг прогона тестов: тест, пишущий в `scripts/`, обязан быть виден | `tests/test_check_package.py::TestTestsTouchedProductMechanism::test_test_run_that_writes_to_scripts_is_caught` |
| `tests-touched-product` | снимок берётся со всех отгружаемых каталогов, а не с одного: `hooks/` и `skills/` в нём не было, хотя docstring называл его «единственным, чего тесты не вправе трогать» | `tests/test_check_package.py::TestTestsTouchedProductMechanism::test_every_shipped_directory_is_watched` |
| `skill-without-description` | SKILL.md без поля `description` | `tests/test_check_package.py::TestPackageCheck::test_skill_without_description_fails` |
| `skill-without-description` | вторая причина: каталог скилла без SKILL.md вовсе | `tests/test_check_package.py::TestPackageCheck::test_a_directory_without_any_manifest_is_still_a_finding` |
| `skill-without-description` | заполнено по существу, а не по признаку «не None»: описание из закавыченных пробелов | `tests/test_check_package.py::TestPackageCheck::test_a_quoted_whitespace_description_is_empty` |
| `skill-without-description` | то же для всех написаний «ничего» в YAML | `tests/test_check_package.py::TestPackageCheck::test_the_yaml_spellings_of_nothing_are_an_empty_description` |
| `skill-without-eval` | скилл без `eval.txt` | `tests/test_check_package.py::TestPackageCheck::test_skill_without_trigger_eval_fails` |
| `skill-without-eval` | вторая причина: `eval.txt` есть, но пуст — включая файл из одних пробелов и табуляций | `tests/test_check_package.py::TestPackageCheck::test_an_empty_trigger_eval_is_not_a_trigger_eval` |
| `skill-without-eval` | третья причина: `eval.txt` из одних комментариев — текст в файле есть, фразы срабатывания нет; там же одинокая BOM, которая не пробельный знак и проверку проходила | `tests/test_check_package.py::TestPackageCheck::test_an_eval_of_only_comments_is_not_a_trigger_eval` |
| `skill-name-mismatch` | имя не совпало с папкой | `tests/test_check_package.py::TestPackageCheck::test_skill_name_must_match_directory` |

## Классы волны 4 (ADOPT)

Семь классов, и ни одного на битой фикстуре: битая фикстура — контекстный
репозиторий, а эти классы производят команды усыновления на **чужом** дереве.
Поэтому доказывает их `fixtures/foreign/`, развёрнутая во временный каталог
(`tests/foreign.py`), а колонка «чем доказан» числа находок на битой фикстуре
не заявляет — заявила бы, и `_miscounts` обязан был бы покраснеть.

Пять из семи — ошибки, два — отчёты. Отчёт здесь не смягчение: `foreign-repo`
и `created-unrecoverable` сообщают о свойствах чужого дерева, которых ADOPT не
создавал и чинить не вправе. Ошибкой их сделать значило бы объявить чужое
дерево виноватым и остановить процедуру на том, что в ней не чинится.

**Чего в этой таблице нет — строки про read-only четырёх команд волны.**
Спека волны обещает, что `scan-tree`, `find-refs`, `read-plan` и `check-plan`
доказывают read-only хешем дерева, «как гейты». Механизм `check_read_only` в
проверке пакета зовёт гейт **одним** аргументом-корнем, и такую форму из
четырёх имеет только `scan-tree`: он и добавлен в кортеж третьим именем.
Остальным трём нужен второй аргумент — план либо путь, — а план, написанный
ради проверки, сам сдвинет тот хеш, который проверка сверяет. Позвать их с
несуществующим планом значило бы удостоверить read-only на ветке раннего
отказа. Обещание держится, но не на каждом `./check`: каждая из трёх меряет
то же самое в своём наборе — `tests/test_read_plan.py::TestReadOnly`,
`tests/test_refs.py::TestReadOnly`,
`tests/test_check_plan.py::TestCommandLine::test_the_check_names_the_finding_and_changes_nothing`
(последний манифестом дерева, а не хешем). Сказано вслух, а не сужено молча.

| класс | чем доказан | тест |
|---|---|---|
| `plan-unparseable` | строка без тела: разбор её теряет и называет находкой с путём, строкой и деталью — то же правило, что у аллоулиста §13, и по той же причине | `tests/test_adopt_plan.py::TestRefusals::test_a_line_without_a_body_fails_the_parse` |
| `plan-unparseable` | вторая причина: строка с нулевой позиции, не разобранная вовсе. Молчаливый пропуск означал бы, что правка автора рукой тихо выносит строку из исполнения — то есть отменяет собственное согласие, не заметив | `tests/test_adopt_plan.py::TestRefusals::test_an_unrecognised_line_is_a_finding_not_a_skip` |
| `uncovered-path` | чужая фикстура без строки на `journal`: назван самый мелкий непокрытый путь и ровно один, а не все файлы под ним. Это и есть механизм критерия 5 — молчание наблюдаемо потому, что план обязан быть тотальным | `tests/test_adopt_plan.py::TestCoverage::test_an_unmentioned_directory_is_reported_once_at_its_top` |
| `uncovered-path` | обратная сторона: из дерева вычитается ровно одно имя — сам файл плана, а не каталог вокруг него. Сосед плана обязан быть назван, иначе под видом «вычесть план» из полноты выпадает целая папка | `tests/test_adopt_plan.py::TestCoverage::test_the_plan_file_itself_is_not_demanded_but_its_neighbour_is` |
| `overlapping-line` | источник одной строки — предок источника другой; находка встаёт на обеих, и в обоих порядках следования. Смысл плана не имеет права зависеть от порядка строк | `tests/test_adopt_plan.py::TestOverlap::test_a_source_that_is_an_ancestor_of_another_is_a_finding` |
| `unagreed-change` | чужой файл переписан мимо плана: строка `identity` согласована крестиком, но целью `stay`, которую не исполняет ничто. Вторая половина инварианта волны — ловит уход с плана, кем бы он ни был сделан | `tests/test_check_plan.py::TestCheck::test_a_change_outside_any_agreed_line_is_a_finding` |
| `line-state-conflict` | столкновение (источник и цель существуют оба) и потеря (не существует ни того, ни другого) по таблице состояний §«Частичное согласие»: состояние строки считается из дерева, и врать оно не умеет | `tests/test_adopt_plan.py::TestState::test_collision_and_loss_are_findings` |
| `foreign-repo` | отчёт: папка с `.git` внутри названа `init-tree` и не тронута — ни `git add -A` gitlink'ом, ни переездом | `tests/test_adopt_tree.py::TestInit::test_the_nested_repository_is_reported_not_touched` |
| `foreign-repo` | второй производитель: подметание `revert`. Неисключённый чужой репозиторий приезжает из `ls-files --others` каталогом; удалить его как файл — уронить откат посередине, удалить рекурсивно — снести чужое безвозвратно. Поэтому он называется и остаётся | `tests/test_revert.py::TestSweep::test_a_repository_that_appeared_after_the_base_commit_is_not_deleted` |
| `created-unrecoverable` | отчёт поимённо, а не одним числом: имя грепается, число — нет. Записи без восстановимой даты создания перечисляются, а в поле уезжает токен `unknown` — незыблемое №4 даёт две ветки, и здесь взяты обе | `tests/test_dates.py::TestReport::test_every_unrecoverable_record_is_named` |
