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
| `ambiguous` | битая фикстура, 1 находка при двух `dup.md` | `tests/test_fixtures.py::TestExactFindings::test_every_link_finding_sits_on_its_own_specimen` |
| `orphan` | битая фикстура, 1 находка в `sources` | `tests/test_fixtures.py::TestExactFindings::test_every_link_finding_sits_on_its_own_specimen` |
| `missing-required` | битая фикстура, 3 находки: дважды поле `created` стартового набора и `status`, обязательный архетипу `pipeline` (архетипу, а не виду: вид требует своё третьим списком) | `tests/test_fixtures.py::TestExactFindings::test_every_frontmatter_finding_sits_on_its_own_specimen` |
| `value-outside-vocabulary` | битая фикстура, 1 находка: `status: активно` вне объявленного словаря | `tests/test_fixtures.py::TestExactFindings::test_every_frontmatter_finding_sits_on_its_own_specimen` |
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
