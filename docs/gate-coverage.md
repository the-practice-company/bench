# Покрытие классов находок

Правило секции 16: у каждого гейта либо исполняемая проверка на фикстуре,
либо обязательное поле с объяснением, почему её нет. Пустым оставить нельзя.
Таблицу держит `tests/test_gate_coverage.py`.

| класс | чем доказан | тест |
|---|---|---|
| `unresolved` | битая фикстура, 4 находки | `tests/test_fixtures.py::TestExactFindings::test_every_link_finding_sits_on_its_own_specimen` |
| `md-link-to-file` | битая фикстура, 1 находка | `tests/test_fixtures.py::TestExactFindings::test_every_link_finding_sits_on_its_own_specimen` |
| `link-to-transient` | битая фикстура, 1 находка | `tests/test_fixtures.py::TestExactFindings::test_every_link_finding_sits_on_its_own_specimen` |
| `escapes-root` | битая фикстура, 2 находки: абсолютный путь и `..` выше корня | `tests/test_fixtures.py::TestExactFindings::test_every_link_finding_sits_on_its_own_specimen` |
| `dead-allow` | битая фикстура, 2 находки: строка без причины и мёртвая строка | `tests/test_fixtures.py::TestExactFindings::test_every_link_finding_sits_on_its_own_specimen` |
| `ambiguous` | битая фикстура, 1 находка при двух `dup.md` | `tests/test_fixtures.py::TestExactFindings::test_every_link_finding_sits_on_its_own_specimen` |
| `orphan` | битая фикстура, 1 находка в `sources` | `tests/test_fixtures.py::TestExactFindings::test_every_link_finding_sits_on_its_own_specimen` |
| `missing-required` | битая фикстура, запись без `status` при `groupBy: status` | `tests/test_fixtures.py::TestExactFindings::test_every_frontmatter_finding_sits_on_its_own_specimen` |
| `value-outside-vocabulary` | битая фикстура, `status: активно` вне словаря | `tests/test_fixtures.py::TestExactFindings::test_every_frontmatter_finding_sits_on_its_own_specimen` |
| `unparseable` | битая фикстура, блочный скаляр в поле с потребителем | `tests/test_fixtures.py::TestExactFindings::test_every_frontmatter_finding_sits_on_its_own_specimen` |
| `unknown-hook-event` | временный пакет с `OnFullMoon` | `tests/test_check_package.py::TestPackageCheck::test_unknown_hook_event_fails` |
| `unknown-hook-type` | тип вне закрытого списка | `tests/test_check_package.py::TestPackageCheck::test_unknown_hook_type_fails` |
| `unknown-matcher` | матчер вне закрытого множества, включая опечатку `Bahs` | `tests/test_check_package.py::TestPackageCheck::test_matcher_typo_is_caught` |
| `absolute-path` | двадцать пять форм абсолютного пути, включая Windows, UNC и чужой домашний каталог | `tests/test_check_package.py::TestPackageCheck::test_every_absolute_form_is_caught` |
| `relative-path-in-skill` | вызов `scripts/*` без `${CLAUDE_PLUGIN_ROOT}` | `tests/test_check_package.py::TestPackageCheck::test_relative_script_call_in_a_skill_fails` |
| `destructive-example` | пример `mv` в инструкциях ADOPT | `tests/test_check_package.py::TestPackageCheck::test_destructive_example_in_adopt_instructions_fails` |
| `gate-not-read-only` | хеш дерева фикстуры до и после прогона гейта | `tests/test_check_package.py::TestGateNotReadOnlyMechanism::test_mutating_gate_is_caught` |
| `tests-touched-product` | тот же приём вокруг прогона тестов | `tests/test_check_package.py::TestTestsTouchedProductMechanism::test_test_run_that_writes_to_scripts_is_caught` |
| `skill-without-description` | SKILL.md без описания | `tests/test_check_package.py::TestPackageCheck::test_skill_without_description_fails` |
| `skill-without-eval` | скилл без `eval.txt` | `tests/test_check_package.py::TestPackageCheck::test_skill_without_trigger_eval_fails` |
| `skill-name-mismatch` | имя не совпало с папкой | `tests/test_check_package.py::TestPackageCheck::test_skill_name_must_match_directory` |
