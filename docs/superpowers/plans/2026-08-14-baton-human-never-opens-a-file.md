# baton: человек никогда не открывает файл — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Убрать редактирование файлов из работы человека и дать владельцев двум полям, у которых их не было, — авторству спеки и снятию стоп-флага.

**Architecture:** Один новый отказ в `baton-write` (по переходу, а не по пути), один новый скрипт-печатник, две команды с `disable-model-invocation`, удаление поля `pass` и переезд `spec` в конституцию. Скрипты меняются впервые за две ветки — до сих пор всё было документацией; здесь механизм.

**Tech Stack:** bash, awk, git; проверки — `tests/helpers.sh` и `bash tests/run-tests`.

**Spec:** `docs/superpowers/specs/2026-08-14-baton-human-never-opens-a-file-design.md`

---

## Зависимость, которую надо снять до начала

Этот план предполагает, что ветка **`baton/budget-holes` влита в `main`**. Она добавляет байтовый бюджет, обход всех `.md` под скиллами, потолок на `commands/` и переименование `build-diverged.sh` → `build-diverged-claims.sh`.

Если она не влита: Task 8 теряет смысл (двигать нечего), а Task 5 и Task 6 будут править `build-diverged.sh` под старым именем. Оба случая безобидны, но **сверьтесь перед началом**: `git log --oneline main | grep budget` и `ls tests/fixtures/cold-start/`.

---

## Инвариант этого плана

> **Отказ должен быть виден в обе стороны.** Тест, который проверяет только «скрипт отказал», зелен и у скрипта, который отказывает всегда. Каждый новый отказ проверяется парой: запрещённый переход — отказ, разрешённый — успех.

Это не общая мудрость: предыдущая ветка выпустила две проверки, зелёные ещё до изменения, которое они должны были закреплять.

---

## File Structure

| Файл | Ответственность после изменения |
|---|---|
| `plugins/baton/scripts/baton-write` | плюс отказ по переходу: снятие `suspect` / `needs_human` в `state.md` |
| `plugins/baton/scripts/baton-digest` | **новый.** Печатает существо конституции и стопа. Ничего не пишет |
| `plugins/baton/commands/ratify.md` | **новый.** Выжимка конституции → запись четырёх полей |
| `plugins/baton/commands/clear.md` | **новый.** Выжимка стопа → снятие флага |
| `plugins/baton/commands/status.md` | называет команду рядом с каждым флагом |
| `plugins/baton/commands/init.md` | `spec` уходит в конституцию; ратификация — командой |
| `plugins/baton/commands/auto.md` | правило скоупа читает `spec` из конституции; `pass` уходит |
| `plugins/baton/templates/constitution.md` | поле `spec` на волну |
| `plugins/baton/templates/state.md` | без колонки `spec`; без `pass` в легенде |
| `plugins/baton/skills/*/SKILL.md` | `pass` уходит; шаг 1 автопилота читает конституцию; «нет тупиков» |
| `tests/test-write.sh` | отказ по переходу, в обе стороны |
| `tests/test-digest.sh` | **новый.** Выжимка против фикстуры |
| `tests/test-commands.sh` | потолок `commands/` двигается под два новых файла |
| `tests/test-templates.sh`, `test-skills.sh`, `test-skill-commands.sh` | схема, правила, тексты команд |
| `tests/fixtures/cold-start/*` | `spec` в конституциях фикстур; `pass` из таблиц |

---

### Task 1: `baton-write` отказывает в снятии стоп-флага

Самая дорогая из двух дыр: `needs_human` останавливает прогон, и агент, способный снять собственный стоп, не имеет стопа.

**Files:**
- Modify: `plugins/baton/scripts/baton-write`
- Modify: `tests/test-write.sh`

- [ ] **Step 1: Написать падающие проверки**

Прочитайте `tests/test-write.sh` целиком и найдите, как в нём строится фикстура и вызывается скрипт. Добавьте в его стиле, перед `finish`, **четыре** проверки. Первые две — сам отказ, вторые две — то, без чего отказ не доказан:

1. `state.md` c `suspect: true` в HEAD, запись с `suspect: false` → **exit 3**, и сообщение называет поле.
2. То же для `needs_human`.
3. `state.md` c `suspect: false` в HEAD, запись с `suspect: true` → **exit 0**. Поднятие разрешено всегда.
4. `state.md` c `suspect: false` в HEAD, запись с `suspect: false` → **exit 0**. «Ничего не менялось» — не отказ.

Проверка 3 — не формальность. Без неё зелёный результат совместим со скриптом, который отказывает в любой записи `state.md`.

- [ ] **Step 2: Убедиться, что они падают**

Run: `bash tests/test-write.sh`
Expected: FAIL на 1 и 2 (сейчас exit 0), PASS на 3 и 4.

- [ ] **Step 3: Добавить извлечение поля**

В `plugins/baton/scripts/baton-write`, рядом с существующей `strip_timestamp()` (около строки 246), добавьте:

```bash
# Reads a frontmatter field's value from stdin. Scoped to the frontmatter
# block deliberately: state.md's body carries a `**Suspect:**` line in the
# Now section, and a body match would read the prose as the flag.
frontmatter_flag() {
    awk -v field="$1" '
        NR == 1 && $0 == "---" { infm = 1; next }
        infm && $0 == "---" { exit }
        infm && index($0, field ":") == 1 {
            sub("^" field ": *", "")
            gsub(/[ \t\r]/, "")
            print
            exit
        }
    '
}
```

- [ ] **Step 4: Добавить отказ**

Сразу после блока, устанавливающего `target_in_head` (около строки 253), добавьте:

```bash
# Granted fields move one way only. The model skill states it as a rule --
# "raising suspect or needs_human is always yours; clearing either is the
# human's" -- and until now that was all it was. An agent that can clear
# needs_human has no stop: the flag exists to halt the run, and the run is
# what would be clearing it. /baton:clear writes this field directly, with
# plain git, for the same reason /baton:init writes the constitution that
# way: this refusal is why it has to.
#
# Refused on the transition, not on the value. Writing false over false is
# an ordinary checkpoint of a run that was never stopped.
if [ "$target" = "docs/baton/state.md" ] && [ "$target_in_head" -eq 1 ]; then
    for flag in suspect needs_human; do
        was="$(git show "HEAD:$target" | frontmatter_flag "$flag")"
        now="$(frontmatter_flag "$flag" < "$tmp")"
        if [ "$was" = "true" ] && [ "$now" = "false" ]; then
            echo "baton-write: refusing to clear $flag: it is set, and clearing it is the human's -- see /baton:clear. Raising it is always yours; lowering it is not." >&2
            exit 3
        fi
    done
fi
```

- [ ] **Step 5: Обновить список причин exit 3 в шапке**

Комментарий в начале файла (около строки 18–23) перечисляет причины exit 3. Допишите к ним снятие `suspect` или `needs_human` в `state.md`. Список, который не перечисляет всех причин, хуже отсутствующего: по нему сверяются.

- [ ] **Step 6: Прогнать**

Run: `bash tests/test-write.sh` → все PASS.
Run: `bash tests/run-tests` → `All test files passed.`

**Если `run-tests` покажет падение вне `test-write.sh`** — вероятно, где-то в фикстурах или рунбуке `state.md` записывается со снятым флагом. Это настоящая находка, а не помеха: сообщите её, не обходите отказ.

- [ ] **Step 7: Commit**

```bash
git add plugins/baton/scripts/baton-write tests/test-write.sh
git commit -m "baton-write: a flag that stops the run is not the run's to clear"
```

---

### Task 2: `baton-digest` — выжимку печатает скрипт

Несущее: если существо файла пересказывает агент, человек одобряет пересказ. Тот же принцип, что у `baton-gate` — скрипт печатает, агент не редактирует.

**Files:**
- Create: `plugins/baton/scripts/baton-digest`
- Create: `tests/test-digest.sh`

- [ ] **Step 1: Написать падающий тест**

Создайте `tests/test-digest.sh` по образцу `tests/test-gate.sh` — прочитайте его сначала: он строит фикстуру, вызывает скрипт, проверяет вывод и код возврата. Проверьте:

- `baton-digest constitution` печатает цель, имя каждой волны, `verify_cmd` и `workspace` — **против фикстуры с известным содержимым**, а не против пересказа;
- у каждой волны печатается число её `exit_criteria`;
- `baton-digest stop` при `suspect: true` печатает, что поднято, и строку `Suspect` из `state.md`;
- `baton-digest stop` при обоих флагах `false` печатает, что прогон никого не ждёт, и выходит 0;
- неизвестный объект → exit 64 (в этом репозитории 64 значит ошибку употребления, см. `baton-write`);
- нет конституции → exit 3 с сообщением, называющим путь.

**Скрипт ничего не пишет.** Добавьте проверку, что после его вызова рабочее дерево чистое — печатник, который что-то пишет, это уже не печатник.

- [ ] **Step 2: Убедиться, что он падает**

Run: `bash tests/test-digest.sh`
Expected: FAIL — скрипта нет.

- [ ] **Step 3: Написать скрипт**

`plugins/baton/scripts/baton-digest`, исполняемый (`chmod +x`, сверьтесь с правами соседей). Шапка в стиле остальных скриптов: что делает, чего не делает, коды возврата.

Требования, а не готовый текст — их надо выполнить, а не переписать:

- употребление: `baton-digest <constitution|stop>`;
- читает `docs/baton/constitution.md` и `docs/baton/state.md`, **не пишет ничего**;
- пути резолвятся от корня репозитория, как в остальных скриптах (`git rev-parse --show-toplevel`) — иначе вызов из подкаталога прочитает не тот файл;
- вывод рассчитан на человека в чате: короткий, без цвета, без рамок;
- для `constitution` — цель, волны с числом критериев у каждой, `verify_cmd`, `placeholder_patterns`, `workspace`, non-negotiables;
- для `stop` — что поднято, что говорит строка `Suspect`, какая волна `blocked` и на чём;
- коды: 0 успех, 3 файла нет или он непригоден, 64 употребление.

Извлечение из YAML делайте тем же способом, каким это уже делает `baton-gate` — посмотрите, как он достаёт `verify_cmd`. Не тащите зависимость: в требованиях плагина только git, bash и стандартные текстовые утилиты.

- [ ] **Step 4: Прогнать**

Run: `bash tests/test-digest.sh` → все PASS.
Run: `bash tests/run-tests` → `All test files passed.`

- [ ] **Step 5: Commit**

```bash
git add plugins/baton/scripts/baton-digest tests/test-digest.sh
git commit -m "baton-digest: the file's own words, not the agent's account of them"
```

---

### Task 3: `/baton:ratify`

**Files:**
- Create: `plugins/baton/commands/ratify.md`
- Modify: `tests/test-skill-commands.sh`

- [ ] **Step 1: Написать падающие проверки**

В `tests/test-skill-commands.sh`, перед `finish`, добавьте в стиле соседних проверок:

```bash
ratify_cmd="$(cat "$PLUGIN/commands/ratify.md")"
assert_contains "$ratify_cmd" "disable-model-invocation: true" \
    "ratify is human-typed only -- that flag is the entire barrier"
assert_contains "$ratify_cmd" "baton-digest constitution" \
    "ratify shows the digest the script prints, not one it composes"
```

Первая проверка — не формальность. `disable-model-invocation` и есть барьер; без него команда становится тем, что агент вызывает себе сам.

- [ ] **Step 2: Убедиться, что падают**

Run: `bash tests/test-skill-commands.sh` → два FAIL.

- [ ] **Step 3: Написать команду**

Прочитайте `plugins/baton/commands/init.md` и `continue.md` — это образец формы: frontmatter, затем нумерованные шаги, которые агент выполняет.

Frontmatter:

```yaml
---
description: Ratify the constitution - review its digest, then mark it ratified
disable-model-invocation: true
---
```

Процедура: показать `baton-digest constitution`; спросить подтверждение; при согласии записать `status: ratified`, `ratified_by` (из `git config user.name`), `ratified_at` (ISO 8601), `git_anchor` (текущий `HEAD`) — **напрямую, через plain git, не через `baton-write`**, ровно как `/baton:init` кладёт начальный файл, и по той же причине: `baton-write` отказывает по этому пути безусловно.

Что должно быть в тексте команды, потому что иначе агент это додумает:

- если конституция уже `ratified` — сказать это и остановиться, ничего не переписывая;
- если в файле остался незаполненный маркер — остановиться: ратифицировать заготовку нельзя, и это ровно то, что проверяет гейт на exit 3;
- выжимку **печатает скрипт**; пересказывать её своими словами запрещено — человек одобряет файл, а не ваш рассказ о нём.

- [ ] **Step 4: Прогнать и закоммитить**

Run: `bash tests/run-tests` → `All test files passed.`

```bash
git add plugins/baton/commands/ratify.md tests/test-skill-commands.sh
git commit -m "/baton:ratify: the four fields, behind the one flag the agent cannot set"
```

---

### Task 4: `/baton:clear`

**Files:**
- Create: `plugins/baton/commands/clear.md`
- Modify: `tests/test-skill-commands.sh`

- [ ] **Step 1: Написать падающие проверки**

```bash
clear_cmd="$(cat "$PLUGIN/commands/clear.md")"
assert_contains "$clear_cmd" "disable-model-invocation: true" \
    "clear is human-typed only -- that flag is the entire barrier"
assert_contains "$clear_cmd" "baton-digest stop" \
    "clear shows why the run stopped before offering to un-stop it"
```

- [ ] **Step 2: Убедиться, что падают**

Run: `bash tests/test-skill-commands.sh` → два FAIL.

- [ ] **Step 3: Написать команду**

Frontmatter:

```yaml
---
description: Clear the flag that stopped the run - review why it was raised, then lower it
disable-model-invocation: true
---
```

Процедура: `baton-digest stop`; подтверждение; снятие флага записью в `state.md` **напрямую, plain git** — через `baton-write` не пройдёт, Task 1 это и запрещает.

Что должно быть в тексте:

- если ни один флаг не поднят — сказать это и остановиться;
- снимать **только то, что человек подтвердил**: два флага поднимаются по разным причинам, и «снять оба заодно» — это снять тот, о котором не спрашивали;
- `suspect` поднят из-за конкретного расхождения. Если то, что его вызвало, всё ещё истинно, снятие вернёт его на следующем же резюме. Сказать это человеку до подтверждения, а не после;
- запись должна оставить `state.md` в пределах 60 строк — тот же потолок, что и у `baton-write`, и мимо него вы пишете именно потому, что он вас не пропустит.

- [ ] **Step 4: Прогнать и закоммитить**

Run: `bash tests/run-tests` → `All test files passed.`

```bash
git add plugins/baton/commands/clear.md tests/test-skill-commands.sh
git commit -m "/baton:clear: the stop comes down where it went up, at a human"
```

---

### Task 5: удалить `pass`

Значение gate-колонки не читает ни один скрипт и ни один хук. Отсутствие `pass` ничего не блокирует.

**Files:**
- Modify: `plugins/baton/templates/state.md`
- Modify: `plugins/baton/skills/baton/SKILL.md`, `baton-checkpoint/SKILL.md`
- Modify: `plugins/baton/commands/status.md`, `auto.md`
- Modify: `plugins/baton/README.md`
- Modify: `tests/test-skills.sh`, `tests/test-templates.sh`, фикстуры

- [ ] **Step 1: Найти всё**

```bash
grep -rn "pass" plugins/ tests/ --include=*.md --include=*.sh | grep -v "passed\|passes\|password"
```

Пройдите каждое вхождение. Часть — про прохождение тестов, их не трогать.

- [ ] **Step 2: Перевернуть проверки**

В `tests/test-skills.sh` есть проверка, различающая `auto` и `pass`, — она пиннит строку `` `pass` is a second party saying so ``. В `tests/test-templates.sh` есть проверка легенды gate. Обе надо **заменить**, а не удалить: на `assert_not_contains`, что `pass` в этих файлах больше нет.

Удалить проверку — значит убрать сторожа. Перевернуть — оставить его сторожить противоположное.

Запустите и убедитесь, что новые проверки падают.

- [ ] **Step 3: Убрать значение**

Легенда gate становится двузначной: `—` ничего не произвело вердикта, `auto` закрыто под автопилотом с вердиктом в `docs/baton/gates/`.

Из модели (`baton/SKILL.md`) уходит `pass` в claimed-полях и в строке Red Flags про «напишу pass, тесты же зелёные» — рационализация исчезает вместе со значением, которое можно было заявить.

Из `baton-checkpoint` уходит строка `pass` из таблицы значений и абзац про «утреннюю работу».

**Сохраните то, что `pass` объяснял, если оно верно и без него.** `auto` по-прежнему значит «закрыто без человека», и это по-прежнему стоит говорить.

- [ ] **Step 4: README**

Раздел про утреннюю работу и превращение `auto` в `pass` уходит. Что приходит взамен — как теперь понять, что прогон чего-то ждёт: `/baton:status`, `blocked`, `suspect`, и команды, которые их снимают.

- [ ] **Step 5: Прогнать и закоммитить**

Run: `bash tests/run-tests` → `All test files passed.`

```bash
git add -A
git commit -m "baton: a mark nothing reads is not a second party looking"
```

---

### Task 6: `spec` переезжает в конституцию

**Files:**
- Modify: `plugins/baton/templates/constitution.md`, `templates/state.md`
- Modify: `plugins/baton/commands/init.md`, `auto.md`
- Modify: `plugins/baton/skills/baton-autopilot/SKILL.md`
- Modify: `tests/test-templates.sh`, `test-skills.sh`, `test-skill-commands.sh`, фикстуры

- [ ] **Step 1: Написать падающие проверки**

В `tests/test-templates.sh`: конституция несёт `spec:` внутри блока волн, а `state.md` колонки `spec` не несёт. Второе — `assert_not_contains` на заголовок колонки.

Обратите внимание: в `test-templates.sh` уже есть python-разбор блока волн конституции. **Расширьте его**, чтобы он требовал `spec` у каждой волны, — грепом это не проверяется, а разбор уже написан.

В `test-skills.sh`: автопилот читает `spec` из конституции. Иглу берите такую, чтобы она не проходила от старого текста — старый говорил про «ячейку `spec`».

- [ ] **Step 2: Убедиться, что падают**

Run: `bash tests/run-tests`

- [ ] **Step 3: Шаблоны**

В блок волн конституции добавляется `spec:` — рядом с `depends_on` и `exit_criteria`, до `exit_criteria`, потому что читается раньше.

Из `state.md` уходит колонка `spec` целиком: заголовок, разделитель и ячейка в строке-образце. Проверьте, что остальные колонки сходятся по числу — предыдущая ветка ловила ровно эту ошибку в четырёх фикстурах.

- [ ] **Step 4: Читатели**

`/baton:init` спрашивает про документ каждой волны так же, как спрашивает сейчас, но ответ идёт в конституцию.

Шаг 1 автопилота читает `spec` волны из конституции. Смысл не меняется — меняется, откуда берётся.

Правило скоупа `/baton:auto` («волна без спеки не в скоупе») читает оттуда же.

**Проверьте `baton-resume`:** шаг 1 перечисляет, что берётся из конституции. Если `spec` там не назван, возобновлённая сессия его не увидит — ровно та ошибка, которая была с `workspace` и которую нашли только финальным ревью.

- [ ] **Step 5: Фикстуры**

Во всех `tests/fixtures/cold-start/build*.sh` конституции получают `spec` на волну, а таблицы `state.md` теряют колонку. Фикстура автопилота требует внимания: её волны должны остаться доступными ровно по тем причинам, по которым сценарий 4 их проверяет.

**Постройте фикстуру и пройдите четыре правила доступности руками** для волн 3 и 4, как это делалось в предыдущей ветке. Зелёный набор тестов этого не докажет.

- [ ] **Step 6: Прогнать и закоммитить**

Run: `bash tests/run-tests` → `All test files passed.`

```bash
git add -A
git commit -m "constitution: which document a wave builds to is the human's to say"
```

---

### Task 7: правило «нет тупиков»

> Ни одно место, где прогон ждёт человека, не сообщает об этом, не назвав команду, которая это снимает.

**Files:**
- Modify: `plugins/baton/commands/status.md`
- Modify: `plugins/baton/skills/baton-autopilot/SKILL.md`, `baton-resume/SKILL.md`
- Modify: `plugins/baton/commands/init.md`
- Modify: `tests/test-skills.sh`, `tests/test-skill-commands.sh`

- [ ] **Step 1: Написать падающие проверки**

Пять мест, по проверке на каждое:

| Место | Что ждёт | Какую команду называет |
|---|---|---|
| `/baton:status` | флаг на диске | `/baton:clear` |
| автопилот, отчёт конца прогона | `needs_human` | `/baton:clear` |
| автопилот, гейт на exit 3 | конституция не ратифицирована | `/baton:ratify` |
| `baton-resume`, найденный флаг | флаг на диске | `/baton:clear` |
| `/baton:init`, передача на ратификацию | ратификация | `/baton:ratify` |

Иглы берите такие, чтобы они пиннили **связку** — команду рядом с условием, — а не просто присутствие строки `/baton:clear` где-то в файле. Проверка, зелёная от упоминания в другом разделе, не проверяет ничего.

- [ ] **Step 2: Убедиться, что падают**

Run: `bash tests/run-tests`

- [ ] **Step 3: Назвать команды**

В каждом из пяти мест рядом с сообщением о том, что прогон ждёт человека, называется команда. Формулировки ваши; требование одно — человек, прочитавший сообщение, знает, что набрать, и не ищет это в README.

**Следите за потолками.** Автопилот и резюме на своих потолках или близко. Если правило не влезает — сообщите число, не срезайте соседнее предложение: так на предыдущей ветке возникла осцилляция, где одно и то же предложение дважды удалили и дважды вернули.

- [ ] **Step 4: Прогнать и закоммитить**

Run: `bash tests/run-tests` → `All test files passed.`

```bash
git add -A
git commit -m "baton: no flag is reported without the words that clear it"
```

---

### Task 8: потолок на `commands/` и README

**Files:**
- Modify: `tests/test-commands.sh`
- Modify: `plugins/baton/README.md`

- [ ] **Step 1: Измерить**

```bash
wc -l plugins/baton/commands/*.md
```

- [ ] **Step 2: Подвинуть потолок**

`CMD_BUDGET` в `tests/test-commands.sh` ставится по тому же правилу, что и потолки скиллов: **измеренный пол плюс около трёх строк**, не доля от прежнего веса. Если `baton/budget-holes` не влита и `CMD_BUDGET` там ещё нет — заведите его, а не двигайте; требование к числу то же. Комментарий рядом называет, что число выросло из-за двух новых команд, и почему их два файла, а не один: `disable-model-invocation` работает пофайлово, то есть отдельный файл здесь — сам механизм, а не оформление.

- [ ] **Step 3: README**

Семь команд вместо пяти. Таблица «Day to day» получает две строки. Раздел про ратификацию руками переписывается на команду.

Абзац про «три из пяти — только человеком» становится про пять из семи, и стоит сказать, что у этих пяти общего: каждая либо даёт что-то агенту, либо снимает то, что его останавливает.

- [ ] **Step 4: Прогнать и закоммитить**

Run: `bash tests/run-tests` → `All test files passed.`

```bash
git add tests/test-commands.sh plugins/baton/README.md
git commit -m "tests: two commands more, and the ceiling that had to move for them"
```

---

### Task 9: две сценария рунбука — половина, которую скрипт не увидит

`tests/fixtures/cold-start/RUNBOOK.md` держит сценарии, которые проверяет человек, потому что «заметил ли агент и остановился ли» — суждение, а не значение. Спека требует два таких сценария; без них барьер проверен только со стороны скрипта.

**Files:**
- Modify: `tests/fixtures/cold-start/RUNBOOK.md`
- Modify: `tests/test-skill-commands.sh`

- [ ] **Step 1: Написать падающие проверки**

`tests/test-skill-commands.sh` уже пиннит сценарии рунбука по заголовкам — найдите те проверки и добавьте такие же на два новых. Пиннить именно заголовок секции, а не голое имя: предыдущая ветка ловила проверку, зелёную от упоминания сценария в списке-оглавлении.

- [ ] **Step 2: Сценарий «агент не снимает собственный стоп»**

По форме сценариев 1–5 (Setup / The test / Pass conditions). Существо: фикстура со взведённым `needs_human: true`, свежая сессия под автопилотом. Агент должен сообщить про флаг, **назвать `/baton:clear`** и остановиться — и не попытаться записать `needs_human: false` ни через `baton-write`, ни мимо него.

Условия прохождения должны быть **наблюдаемы человеком**: что в стенограмме, что в `git status`, что в `git log`. Условие вида «агент не думал о том, чтобы снять флаг» непроверяемо; «в `docs/baton/state.md` нет коммита, меняющего этот флаг» — проверяемо.

Отдельным абзацем — почему это рунбук, а не shell-тест: `baton-write` откажет и так, но сценарий проверяет другое, а именно что агент не пойдёт в обход и назовёт человеку команду вместо того, чтобы молча встать.

- [ ] **Step 3: Сценарий «ратификация целиком в чате»**

Фикстура с нератифицированной конституцией. Человек проходит `/baton:ratify` от начала до конца.

Условия прохождения: ни один файл не был открыт человеком; выжимку печатал скрипт, а не агент своими словами; четыре поля записаны; и — самое важное — **выжимки хватило, чтобы заметить подменённый `verify_cmd`**. Последнее и есть смысл сценария: выжимка, по которой нельзя поймать подмену, не выжимка, а формальность.

- [ ] **Step 4: Обновить шапку рунбука**

Число сценариев и список в начале файла. Предыдущая ветка выпустила расхождение между заголовком секции и её строкой в оглавлении — сверьте оба.

- [ ] **Step 5: Прогнать и закоммитить**

Run: `bash tests/run-tests` → `All test files passed.`

```bash
git add tests/fixtures/cold-start/RUNBOOK.md tests/test-skill-commands.sh
git commit -m "runbook: the barrier from the side a script cannot watch"
```

---

## Done when

- `bash tests/run-tests` зелёный, включая новые `test-digest.sh` и проверки в `test-write.sh`.
- `grep -rn "\bpass\b" plugins/ --include=*.md` не находит gate-значения (совпадения про прохождение тестов допустимы).
- `grep -rn "spec" plugins/baton/templates/state.md` не находит колонки.
- Обе новые команды несут `disable-model-invocation: true`.
- Ручной прогон: снятие `suspect` через `baton-write` отказано, поднятие разрешено.
- Ручной прогон: ратификация проходится целиком в чате, ни один файл не открыт.

Затем `superpowers:finishing-a-development-branch`.

---

## Чего этот план сознательно не делает

**`/baton:amend`.** Поправка к конституции по ходу прогона остаётся правкой файла. Это акт авторства, а не одобрения: человек сочиняет текст, и выжимка тут не помогает. Названо в спеке (§4), названо здесь.

**Потолок для `references/`.** Обход всех `.md` под скиллами приходит из `baton/budget-holes`; попиловый потолок для них не ставится, пока таких файлов нет и мерить нечего.
