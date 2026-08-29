# Покрытие критериев выхода волны 1

Зелёный `./check` не доказывает, что проверка работает. Он доказывает только,
что на неизменённом дереве она молчит, — а молчать умеет и слепая. Волну 1 один
раз уже объявляли закрытой на зелёном наборе; посаженные следом мутации
оставили его зелёным по четырём критериям из пяти. Доказательство здесь: под
каждый критерий заведены мутации, каждая сажается в одноразовую копию
репозитория, и каждая обязана покраснеть.

Оснастка — `dev/mutate.py`, запускается руками: `python3 dev/mutate.py`. В
`./check` она не входит намеренно: семнадцать копий дерева с прогоном
тестового модуля в каждой стоят на порядок дороже самого `./check`, который
обязан оставаться дешёвым. Выжившая мутация — находка, а не повод её ослабить.

Критерии — дословно из `docs/roadmap.md`, раздел «Волна 1».

| критерий | чем атакован | чем доказан |
|---|---|---|
| 1. Each gate shall report exactly the findings asserted by the broken-fixture test, by class and by count. | `dead-allow: две причины схлопнуты в одну`; `wikilink: запрещённый откат на basename`; `глоб снова считается конкретным путём`; `шаблон уходит из-под проверки корня` | все четыре роняют `tests.test_fixtures`. Первые две — на `test_every_link_finding_sits_on_its_own_specimen`. Две последние заведены под правило про глоб и атакуют его с разных сторон: «глоб — конкретный путь» роняет зелёную фикстуру, где `.claude/settings.json` каркаса обязан молчать; «шаблон уходит из-под проверки корня» — битую, где глоб наружу репозитория обязан оставаться `escapes-root`. Ни одна не ловит обе половины: правило двустороннее, и мутации к нему тоже |
| 2. Gate reports shall be byte-identical regardless of checkout location, and every time-dependent value shall arrive as an explicit date parameter. | `часы: import datetime в гейте ссылок`; `Report молча теряет переданную дату` | обе роняют `tests.test_fixtures`: `test_no_module_in_scripts_reads_the_clock` и `test_today_is_carried_on_the_report` |
| 3. The package check shall exit non-zero on any hook type, event or matcher outside its closed list, on any absolute path anywhere in the package, and on any skill lacking a description or a trigger eval. | `матчер: любой принимается за известный`; `absolute-path: пять префиксов, без Windows и UNC`; `shebang: исключение снимает строку целиком`; `скан: файл с недекодируемым байтом пропускается`; `скан пакета: фильтр по списку расширений`; `периметр снова слеп к .gitignore`; `SKIP_AT_ROOT: все восемь имён зон обратно`; `skill-without-eval удалён из проверки` | все восемь роняют `tests.test_check_package`; каждая — на своём тесте, от `test_matcher_typo_is_caught` до `test_skill_without_trigger_eval_fails`. Три из них заведены вместе с починкой дыр, найденных ревью: исключение для shebang гасило всю первую строку, один недекодируемый байт уводил файл из-под скана целиком, а периметр не читал `.gitignore` вовсе — и вердикт о пакете зависел от неотслеживаемого локального состояния (`python3 -m venv .venv` красил `./check` на чистом коммите). Мутировать все три было нечего, пока кода не было |
| 4. Every gate shall carry either an executable fixture test or a recorded reason for having none, and an empty reason shall fail. | `удалён тест, на который ссылается таблица`; `цитата в таблице заменена прозой` | обе роняют `tests.test_gate_coverage` на `test_the_real_table_is_sound` |
| 5. The eight zones shall be defined in exactly one module, and a test shall fail if a second definition appears in the package. | `второе определение зон: hooks/zones.py` | роняет `tests.test_zones` на `test_no_second_zone_table_in_package` |

Мутации именованы так же, как в таблице `MUTATIONS` в `dev/mutate.py`; таблицы
обязаны сходиться. Что именно мутация делает с копией — читается там же.

**Состояние на 2026-08-29.** Семнадцать мутаций, семнадцать убито, ноль
выжило, ноль не легло; прогон занимает около тринадцати секунд.

Три исхода различаются намеренно. **Убита** — набор покраснел, проверка видит.
**Выжила** — набор остался зелёным, критерий держится на честном слове.
**Не легла** — образца замены в файле уже нет: устарела таблица мутаций, а не
гейт. Смешать последние два значит спрятать оба: пустая замена «выживает»
тривиально, потому что мутировать было нечего.
</content>
