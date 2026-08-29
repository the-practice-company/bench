# Волны

**Цель прогона.** Плагин собран, ставится из маркетплейса и проходит
собственную проверку пакета; на новом репозитории прожит полный цикл CREATE —
от пустого каталога до живого дерева, зелёного на обоих гейтах. ADOPT и
MAINTAIN реализованы и покрыты фикстурами, но на настоящем чужом репозитории
в этом прогоне не гоняются.

Порядок продиктован самой спекой: «нет проверки — нет гейта», поэтому проверки
раньше того, что они проверяют. Параллельность одна — волны 2 и 3, — и она
безопасна ровно потому, что всё общее принадлежит волне 1 и обе только читают
его. Спека измерила цену обратного: в изученном аналоге три разошедшиеся
таблицы зон и две копии парсера JSON, одна из которых не исполняется никогда.

| # | волна | зависит от | статус |
|---|---|---|---|
| 1 | Гейты и проверка пакета | — | **закрыта** после переоткрытия: 40 находок трёх зондов, 17 мутаций на пять критериев — все убиты |
| 2 | Хуки | 1 | **закрыта**: восемь задач, восемь дыр контракта, пять мутаций на пять критериев |
| 3 | Каркас и CREATE | 1 | **закрыта**: десять задач, семь новых мутаций — семь убиты; половина суждения в критерии 3 машиной не проверяется и названа вслух |
| 4 | ADOPT | 2, 3 | не начата |
| 5 | MAINTAIN и расширение | 4 | не начата |

Критерии выхода записаны по-английски намеренно: это утверждения вида
«shall», которые проверяются буквально, и перевод их размывает.

---

## Волна 1. Гейты и проверка пакета

План: `docs/superpowers/plans/2026-08-08-wave-1-gates-and-package-check.md`

**Критерии выхода:**

1. Each gate shall report exactly the findings asserted by the broken-fixture test, by class and by count.
2. Gate reports shall be byte-identical regardless of checkout location, and every time-dependent value shall arrive as an explicit date parameter.
3. The package check shall exit non-zero on any hook type, event or matcher outside its closed list, on any absolute path anywhere in the package, and on any skill lacking a description or a trigger eval.
4. Every gate shall carry either an executable fixture test or a recorded reason for having none, and an empty reason shall fail.
5. The eight zones shall be defined in exactly one module, and a test shall fail if a second definition appears in the package.

**Состояние на 2026-08-29. Волна переоткрыта в день закрытия.** Задачи 1–23
плана исполнены, набор на момент закрытия был зелёным, и этого оказалось
недостаточно: волну объявили закрытой на зелёном `./check` и семнадцати убитых
мутациях, а состязательный зонд построил входы, которые обязаны быть находками,
и получил `exit 0`. Девятнадцать слепых зон; текущее состояние каждой — в
`docs/tracker.md`, и волна остаётся открытой, пока критерии не подтверждены
заново.

**Критерий 3 опровергнут четырьмя входами:** `hooks.json` без ключа-обёртки
`hooks` (тогда не проверяются вообще ни события, ни матчеры, ни типы), пустой
`eval.txt`, описание из пробелов в кавычках и абсолютный путь в файле, который
git отслеживает, но который выпал из периметра из-за отрицания в `.gitignore`.

**Критерий 1 держится на своей фикстуре, но фикстура не всюду доходит:** до
ветки архетипа `registry` и до блочной формы словаря она не добирается, а код
за обеими был сломан. Критерии 4 и 5 зонд выдержали.

**Критерий 2 выдержал, и одна его половина держалась на честном слове дольше
всех.** Половина про дату: `--today` больше не молчаливая заглушка, отчёт
несёт принятое значение, и мутация, теряющая дату, роняет набор. Отчёты
побайтово совпали из путей с пробелом, кириллицей, CJK и через симлинк.
Половина про часы до 2026-08-29 проверялась поиском пяти подстрок, и
посаженное настоящее чтение часов (`st_mtime` внутри `scan()`) переживало её,
не уронив ни одного теста. Проверка переписана на разбор кода; та же мутация
теперь умирает. Разбор — в `docs/criteria-coverage.md`, строка критерия 2.

Общий признак всех девятнадцати — тот, которого оснастка мутаций не видит по
построению: код реализует правило у́же, чем комментарий или предложение спеки
рядом с ним. Мутировать нечего, пока кода нет.

Заходов до этого было два, и оба записаны здесь, чтобы не выглядело, будто
проверку не трогали. Первый: десять дыр, которыми мутации опровергли критерии
1, 3, 4 и 5, закрыты задачами 16–23, а ручная проверка мутациями заменена
оснасткой `dev/mutate.py` — она сажает нарушение в копию дерева и требует,
чтобы набор покраснел; в `./check` не входит, потому что копирует дерево на
каждую мутацию. Второй: состязательное ревью нашло пять **отсутствующих**
проверок, в их числе `#!/bin/sh`, которым начинается собственный `check` этого
репозитория, при том что спека рядом утверждала обратное. Все пять закрыты;
спека, утверждавшая неподкреплённое, поправлена.

Разведка волны 3 нашла блокер уже в волне 1: каркас, предписанный спекой,
не проходил гейт ссылок — глоб `**/knowledge/**` и правило доступа
`Edit(./knowledge/*/**)` гейт считал несуществующими путями. Глоб не путь;
правило и фальсификатор к нему сделаны. Последней работой волны они были ровно
до переоткрытия — эта строка стояла тут и после него.

**Отдаёт волнам 2 и 3:** `scripts/zones.py` — восемь зон, префиксы путей, права
записи, `DENY_PATTERNS`; `scripts/findings.py` — имена классов, `EXIT_OK` и
`EXIT_VIOLATION`; `scripts/paths.py` — признак пути и `escapes_root`; CLI обоих
гейтов: `python3 scripts/check_links.py <корень> [--today ГГГГ-ММ-ДД]`, код 2
при нарушении.

`EXIT_TOOL_FAILED` из этого списка убран: имя в `scripts/findings.py` объявлено
и не используется нигде — ветка «не смог запуститься» возвращает `EXIT_OK`
напрямую. Значения у обоих одинаковые (`0`), так что поведение верное, а
контракт держит другая константа, чем обещало это имя. Потребителю волны 2 или
3 брать нечего: имени, за которым стоит проверяемое поведение, здесь нет. Что
с ним делать — оставить как документирующий синоним или снять — решает тот, кто
следующим правит `scripts/findings.py`; здесь этот выбор не делается.

---

## Волна 2. Хуки

Зависит от 1, параллельна 3.

**Потребляет:** модуль зон волны 1; имена классов находок и CLI обоих гейтов;
паттерны `permissions.deny`.

**Производит:** `hooks/hooks.json` и единственную точку входа
`hook.sh -> hook.py`; контракт кодов возврата (2 — нарушение, 0 — гейт не
выполнился, с видимой причиной); проверку границы рабочего каталога,
вызываемую и волной 4.

**Критерии выхода:**

1. Every hook shall be exercised through a real subprocess run, never by calling its logic directly.
2. Hook tests shall assert both the exit code and the message.
3. When the gate tool cannot start, the hook shall exit 0 and print a visible line naming the reason, and a test shall cover this case.
4. When a write, move or delete resolves outside the repository root after normalisation, the hook shall exit 2 naming the boundary.
5. The Stop hook shall be synchronous and shall honour `stop_hook_active`.

---

## Волна 3. Каркас и CREATE

Зависит от 1, параллельна 2.

**Потребляет:** модуль зон волны 1; оба гейта как исполняемые команды — каркас
обязан проходить их зелёным; паттерны `permissions.deny` для `settings.json`
целевого репозитория.

**Производит:** `scaffold/` — каркас рецепта физической папкой, побайтово
одинаковый во всех инстансах; скелет `CLAUDE.md`, `.claude/rules/*.md`,
`.gitignore`, фрагмент `settings.json`; скилл `create-context-repo` и порядок
двух коммитов.

**Критерии выхода:**

1. The scaffold shall pass both gates with zero findings as the clean fixture, and shall still pass with the `.claude` directory removed.
2. CREATE shall produce a first commit whose tree contains the scaffold byte-for-byte identical to the scaffold shipped in the package.
3. CREATE shall not complete a structural unit without real content, and where no answer is available from brief or dialogue the unit shall not be created and the question shall be recorded in open threads.
4. The generated `CLAUDE.md` shall carry the zone map and the placement rule, and shall contain no file listing.

**Состояние на 2026-08-29. Волна закрыта.** Десять задач плана исполнены,
`./check` зелёный, и посаженные мутации краснеют: семь новых строк в
`dev/mutate.py`, каждая называет тест, который обязан упасть именно от неё, и
каждый упал. Четыре строки атакуют критерии по одной, три подписаны `в3 гейт`
— они правят гейт frontmatter и ни одного критерия выхода не доказывают, что
сказано меткой, а не умолчано. Чем закрыт каждый критерий —
`docs/criteria-coverage.md`, раздел «Волна 3».

**Половина критерия 3 машинной проверки не имеет, и это записано, а не
умолчано.** «Настоящая запись» — суждение о содержимом. Проверено то, что
проверяемо: каркас не везёт ни одной коллекции и ни одного образца, первый
коммит не заводит коллекцию, а скилл несёт запрет сочинять правдоподобное и
адрес несостоявшихся ответов (`OPEN-THREADS.md`). Что скилл этому следует, не
доказывает ничто, кроме прогона с человеком, и незыблемое №2 запрещает
называть это гейтом.

**Отдаёт волне 4:** `scaffold/` — объект сравнения при обновлении версии
(§21: каркас новой версии разворачивается и сравнивается с деревом);
`scripts/install_scaffold.py` — ADOPT дописывает недостающую форму тем же
кодом и тем же отказом писать поверх; `merge_settings` — слияние настроек без
потери чужих ключей; `scripts/boundary.py` — граница рабочего каталога и поиск
корня, теперь доступные из `scripts/` без импорта из `hooks/`. ADOPT спрашивает
границу, а не пишет свою: копий было бы три.

**Отдаёт волне 5:** порог «файла сверх размера» — наблюдение о дереве, и его
место в слое спроса MAINTAIN, где обход дерева уже есть. `.gitignore` размера
выразить не умеет, и волна 3 не делает вид, что правило существует. Плюс
`add-area` обязан обновлять `areas/README.md`, а не только `CLAUDE.md`.

---

## Волна 4. ADOPT

Зависит от 2 и 3.

**Критерии выхода:**

1. On the foreign fixture, revert shall restore the tree byte-for-byte.
2. The count of resolvable links shall be identical before and after any rename chain.
3. ADOPT shall not move a file before the author has agreed to the plan line covering it.
4. If the repository has no git and the author declines to initialise it, then ADOPT shall stop after writing the plan and shall modify no file.
5. Every unclassified path shall appear in the plan with an explicit question mark, and a silent classification shall fail the test.

---

## Волна 5. MAINTAIN и расширение

Зависит от 4.

**Критерии выхода:**

1. MAINTAIN shall fix form without asking and shall not modify content.
2. MAINTAIN shall show demand and shall not act on it.
3. `extend-structure` shall not create a structural unit without content.
4. `backfill` shall not write a synthetic value silently, and an unrecoverable value shall either be marked synthetic or sent to the report.
5. Every mass mutation shall emit a machine field-map and a diff of expected versus actual counts.
