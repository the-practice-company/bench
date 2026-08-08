---
schema: baton/constitution/v1
run_id: twinkle-repo-builder-v1
status: ratified
ratified_by: Артём
ratified_at: 2026-08-08T10:31:39Z
git_anchor: 160d9e4761b25be1fcdf4d2f04b5594dc2304a39
umbrella_spec: docs/superpowers/specs/2026-08-08-context-repo-plugin-design.md
verify_cmd: "./check"
placeholder_patterns: "TODO|FIXME|NotImplemented|unimplemented|raise NotImplementedError"
---

# twinkle-repo-builder v1

## Goal

Плагин Claude Code для контекстных репозиториев собран, ставится из маркетплейса
и проходит собственную проверку пакета; на новом репозитории прожит полный цикл
CREATE — от пустого каталога до живого дерева, зелёного на обоих гейтах. ADOPT
и MAINTAIN реализованы и покрыты фикстурами, но на настоящем чужом репозитории
в этом прогоне не гоняются.

## Operating mode

Оркестратор. Реализацию отдаёт субагентам и workflow, в основной сессии код
не пишет, отвечает за доведение работы до конца.

Сверх дефолта — жёсткое условие по моделям, оплаченное этим же проектом:
перед каждым запуском workflow читается скилл `launching-workflows`; на каждом
вызове `agent()` модель названа явно; после запуска маршрут проверяется по
транскриптам (`grep '"model"' <transcript-dir>/agent-*.jsonl | sort | uniq -c`),
а не по параметру в скрипте. Причина записана: в сессии проектирования 1026
вызовов молча унаследовали модель оркестратора, потому что этот шаг пропустили.

## Non-negotiables

1. **Линия ответственности.** Форму правит плагин молча, содержимое не трогает
   без автора. Ни одна волна не расширяет плагину права на содержимое.
2. **Нет проверки — нет гейта.** Правило существует, только будучи выражено
   исполняемой проверкой. Объявить проверку, за которой нет кода, нельзя.
3. **Эффективность, а не маскарад.** Механизм не заводится, пока не предъявлена
   наблюдённая поломка, которую он чинит.
4. **Запрет молчаливых заглушек.** Невосстановимое значение либо помечается
   синтетическим, либо уходит в отчёт. Никогда не подставляется тихо — ни в
   полях записей, ни в ответах за автора.
5. **Ноль зависимостей.** Python stdlib, git, файловая система. Ни MCP, ни
   внешних движков, ни сети — ни в гейтах, ни в хуках, ни в скриптах.
6. **Граница рабочего каталога.** Плагин не пишет и не двигает ничего вне корня
   репозитория. Исключения ровно два, оба названы в секции 15 спеки.
7. **Спека — источник истины.** Разошлись реализация и спека — правится спека
   отдельным коммитом, а не код втихую.

## Waves

```yaml
- wave: 1
  name: Гейты и проверка пакета
  depends_on: []
  parallel_with: []
  exit_criteria:
    - "Each gate shall report exactly the findings asserted by the broken-fixture test, by class and by count."
    - "Gate reports shall be byte-identical regardless of checkout location, and every time-dependent value shall arrive as an explicit date parameter."
    - "The package check shall exit non-zero on any hook type, event or matcher outside its closed list, on any absolute path anywhere in the package, and on any skill lacking a description or a trigger eval."
    - "Every gate shall carry either an executable fixture test or a recorded reason for having none, and an empty reason shall fail."
    - "The eight zones shall be defined in exactly one module, and a test shall fail if a second definition appears in the package."

- wave: 2
  name: Хуки
  depends_on: [1]
  parallel_with: [3]
  consumes:
    - "Модуль зон из волны 1: восемь зон, префиксы путей, права записи."
    - "Имена классов находок и CLI-контракт обоих гейтов."
    - "Паттерны permissions.deny."
  produces:
    - "hooks/hooks.json и единственная точка входа hook.sh -> hook.py."
    - "Контракт кодов возврата: 2 — нарушение, 0 — гейт не выполнился, с видимой причиной."
    - "Проверка границы рабочего каталога, вызываемая и волной 4."
  exit_criteria:
    - "Every hook shall be exercised through a real subprocess run, never by calling its logic directly."
    - "Hook tests shall assert both the exit code and the message."
    - "When the gate tool cannot start, the hook shall exit 0 and print a visible line naming the reason, and a test shall cover this case."
    - "When a write, move or delete resolves outside the repository root after normalisation, the hook shall exit 2 naming the boundary."
    - "The Stop hook shall be synchronous and shall honour stop_hook_active."

- wave: 3
  name: Каркас и CREATE
  depends_on: [1]
  parallel_with: [2]
  consumes:
    - "Модуль зон из волны 1: восемь зон, префиксы путей, права записи."
    - "Оба гейта как исполняемые команды — каркас обязан проходить их зелёным."
    - "Паттерны permissions.deny для settings.json целевого репозитория."
  produces:
    - "scaffold/ — каркас рецепта физической папкой, побайтово одинаковый во всех инстансах."
    - "Скелет CLAUDE.md, .claude/rules/*.md, .gitignore, фрагмент settings.json."
    - "Скилл create-context-repo и порядок двух коммитов."
  exit_criteria:
    - "The scaffold shall pass both gates with zero findings as the clean fixture, and shall still pass with the .claude directory removed."
    - "CREATE shall produce a first commit whose tree contains the scaffold byte-for-byte identical to the scaffold shipped in the package."
    - "CREATE shall not complete a structural unit without real content, and where no answer is available from brief or dialogue the unit shall not be created and the question shall be recorded in open threads."
    - "The generated CLAUDE.md shall carry the zone map and the placement rule, and shall contain no file listing."

- wave: 4
  name: ADOPT
  depends_on: [2, 3]
  parallel_with: []
  exit_criteria:
    - "On the foreign fixture, revert shall restore the tree byte-for-byte."
    - "The count of resolvable links shall be identical before and after any rename chain."
    - "ADOPT shall not move a file before the author has agreed to the plan line covering it."
    - "If the repository has no git and the author declines to initialise it, then ADOPT shall stop after writing the plan and shall modify no file."
    - "Every unclassified path shall appear in the plan with an explicit question mark, and a silent classification shall fail the test."

- wave: 5
  name: MAINTAIN и расширение
  depends_on: [4]
  parallel_with: []
  exit_criteria:
    - "MAINTAIN shall fix form without asking and shall not modify content."
    - "MAINTAIN shall show demand and shall not act on it."
    - "extend-structure shall not create a structural unit without content."
    - "backfill shall not write a synthetic value silently, and an unrecoverable value shall either be marked synthetic or sent to the report."
    - "Every mass mutation shall emit a machine field-map and a diff of expected versus actual counts."
```

Порядок продиктован самой спекой: «нет проверки — нет гейта», поэтому проверки
раньше того, что они проверяют. Параллельность одна — волны 2 и 3, — и она
безопасна ровно потому, что всё общее принадлежит волне 1 и обе только читают
его. Спека измерила цену обратного: в изученном аналоге три разошедшиеся
таблицы зон и две копии парсера JSON, одна из которых не исполняется никогда.

## Decision authority

Обратимые решения с низким и средним радиусом поражения — за агентом, с записью
в журнал. Необратимые и всё с высоким радиусом — эскалация. Обратимое решение
принимается примерно на 70% информации, которую хотелось бы иметь, а не на 90%:
ждать полноты на обратимом решении — это медленно, а не осторожно.

Сверх дефолта, две вещи эскалируются всегда:

- **правка umbrella-спеки.** Незыблемое №7 требует править её, а не код, — но
  что именно поправить, решает автор. Агент приносит расхождение и предложение.
- **отказ от механизма, записанного в спеке, по мотиву «не понадобилось».**
  Это ровно тот ход, который принцип «эффективность, а не маскарад» разрешает
  в одну сторону и запрещает в другую: не заводить неизмеренное — можно,
  вынимать уже обоснованное — нельзя без автора.

## Amendments

Append only. Каждая поправка: дата, что изменилось, кто ратифицировал.

- **2026-08-08.** Ратификация. Артём ратифицировал прогон устно, в диалоге, и
  поручил агенту заполнить `status`, `ratified_by`, `ratified_at` и `git_anchor`
  за себя. Записано ради точности происхождения: подпись авторская, нажатие
  клавиш агентское. Следствие — «конституцию агент не пишет» в этом репозитории
  держится соглашением, а не механикой: отказ живёт в `baton-write`, обычный
  редактор им не связан. Изменены только четыре поля ратификации; `verify_cmd`
  и `placeholder_patterns` остались нетронутыми, что проверяемо диффом коммита.
