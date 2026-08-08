---
schema: baton/state/v1
writer: f4ebcdf4-3884-4cc2-b31d-77161c8355a5
updated_at: 2026-08-08T11:07:18Z
observed_sha: e87b4b5ea6e9146e409882049a728d0245fd1b8d
observed_branch: main
tree_clean: true
suspect: false
needs_human: false
autopilot: all
autopilot_grant: DEC-0001
---

# State

**Goal:** Плагин собран, ставится из маркетплейса, проходит проверку пакета; на новом репозитории прожит полный цикл CREATE. ADOPT и MAINTAIN реализованы и покрыты фикстурами, но на настоящем чужом дереве не гоняются.

**Operating mode:** Оркестратор: реализацию отдаёт субагентам и workflow, в основной сессии код не пишет. Перед каждым workflow читается `launching-workflows`, модель названа явно на каждом `agent()`, маршрут проверяется по транскриптам после запуска.

**Non-negotiables:**

1. **Линия ответственности.** Форму правит плагин молча, содержимое не трогает без автора. Ни одна волна не расширяет плагину права на содержимое.
2. **Нет проверки — нет гейта.** Правило существует, только будучи выражено исполняемой проверкой. Объявить проверку, за которой нет кода, нельзя.
3. **Эффективность, а не маскарад.** Механизм не заводится, пока не предъявлена наблюдённая поломка, которую он чинит.
4. **Запрет молчаливых заглушек.** Невосстановимое значение либо помечается синтетическим, либо уходит в отчёт. Никогда не подставляется тихо — ни в полях записей, ни в ответах за автора.
5. **Ноль зависимостей.** Python stdlib, git, файловая система. Ни MCP, ни внешних движков, ни сети — ни в гейтах, ни в хуках, ни в скриптах.
6. **Граница рабочего каталога.** Плагин не пишет и не двигает ничего вне корня репозитория. Исключения ровно два, оба названы в секции 15 спеки.
7. **Спека — источник истины.** Разошлись реализация и спека — правится спека отдельным коммитом, а не код втихую.

## Waves

| # | name | status | branch/worktree | spec | plan | closed_at_sha | gate |
|---|------|--------|-----------------|------|------|---------------|------|
| 1 | Гейты и проверка пакета | todo | — | umbrella §13,14,16 | `docs/superpowers/plans/2026-08-08-wave-1-gates-and-package-check.md` | — | — |
| 2 | Хуки | todo | — | — | — | — | — |
| 3 | Каркас и CREATE | todo | — | — | — | — | — |
| 4 | ADOPT | todo | — | — | — | — | — |
| 5 | MAINTAIN и расширение | todo | — | — | — | — | — |

**Status:** `todo | doing | done | blocked`.
`blocked` waits on a dependency; `needs_human: true` (frontmatter) stops the whole run.

**Gate:** `—` nothing produced a verdict; `auto` closed under the autopilot,
verdict in `docs/baton/gates/`; `pass` a human confirmed it.

**Current wave:** 1 — Гейты и проверка пакета

## Now

- **Next action:** Выполнить Task 1 плана волны 1 («Скелет пакета и `./check`»): написать `tests/test_smoke.py`, убедиться что падает, создать `.claude-plugin/plugin.json`, `scripts/__init__.py`, `tests/__init__.py` и исполняемый `check`, прогнать `python3 -m unittest tests.test_smoke -v` до зелёного, коммит.
- **In flight:** ничего
- **Suspect:** Конституция ратифицирована устно, поля заполнил агент по поручению автора — см. поправку в конституции и DEC-0001. Отказ `baton-write` на её путь цел, но обычным редактором не связан: «конституцию агент не пишет» здесь соглашение, не механика.
- **Open questions:** Пять мест неуверенности по волнам предъявлены автору до гранта, см. DEC-0001. Плюс три решения спеки, оспоренные аудитом и намеренно не тронутые: скелет CLAUDE.md (§9), нечем фальсифицировать рецепт (§27), отказ от сигналов протухания (§24, §27).

## Pointers

- Constitution: docs/baton/constitution.md
- Umbrella spec: docs/superpowers/specs/2026-08-08-context-repo-plugin-design.md
- Autopilot grant: docs/baton/journal/0001-autopilot-grant.md
- Recent decisions: docs/baton/journal/
