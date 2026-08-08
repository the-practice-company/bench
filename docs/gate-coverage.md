# Покрытие классов находок

Правило секции 16: у каждого гейта либо исполняемая проверка на фикстуре,
либо обязательное поле с объяснением, почему её нет. Пустым оставить нельзя.
Таблицу держит `tests/test_gate_coverage.py`.

| класс | чем доказан |
|---|---|
| `unresolved` | битая фикстура, 4 находки, `tests/test_fixtures.py` |
| `md-link-to-file` | битая фикстура, 1 находка |
| `link-to-transient` | битая фикстура, 1 находка |
| `escapes-root` | битая фикстура, 2 находки: абсолютный путь и `..` выше корня |
| `dead-allow` | битая фикстура, 2 находки: строка без причины и мёртвая строка |
| `ambiguous` | битая фикстура, 1 находка при двух `dup.md` |
| `orphan` | битая фикстура, 1 находка в `sources` |
| `missing-required` | битая фикстура, запись без `status` при `groupBy: status` |
| `value-outside-vocabulary` | битая фикстура, `status: активно` вне словаря |
| `unparseable` | битая фикстура, блочный скаляр в поле с потребителем |
| `unknown-hook-event` | `tests/test_check_package.py`, временный пакет с `OnFullMoon` |
| `unknown-hook-type` | `tests/test_check_package.py`, тип вне закрытого списка |
| `unknown-matcher` | `tests/test_check_package.py`, матчер вне закрытого множества |
| `absolute-path` | `tests/test_check_package.py`, `/Users/` в прозе скилла |
| `relative-path-in-skill` | `tests/test_check_package.py`, вызов `scripts/*` без `${CLAUDE_PLUGIN_ROOT}` |
| `destructive-example` | `tests/test_check_package.py`, пример `mv` в инструкциях ADOPT |
| `gate-not-read-only` | `check_read_only`: хеш дерева фикстуры до и после прогона гейта |
| `tests-touched-product` | тот же приём вокруг прогона тестов, хеш по `scripts/` и `.claude-plugin/` |
| `skill-without-description` | `tests/test_check_package.py`, SKILL.md без описания |
| `skill-without-eval` | `tests/test_check_package.py`, скилл без `eval.txt` |
| `skill-name-mismatch` | `tests/test_check_package.py`, имя не совпало с папкой |
