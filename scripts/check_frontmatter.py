#!/usr/bin/env python3
"""Гейт frontmatter: контракт выводится из видов, а не из схемы."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.basefile import parse_base
from scripts.check_links import _ignored, _in_perimeter, _read
from scripts.findings import Finding, Report
from scripts.frontmatter import FrontmatterError, parse as parse_frontmatter


# Секция 2: третий источник контракта наравне с видом и README коллекции.
# type и created — всегда; status и description приходят из архетипа,
# поэтому здесь их нет: у журнальной записи жизненного цикла не бывает,
# и требовать у неё статус — требовать поле, которого не существует.
STARTER_ALWAYS = ("type", "created")

# Архетип, которому `status` обязателен (секции 2, 5 и 14). Правило было
# записано в комментарии этого модуля и в спеке, а в коде его не было
# вовсе: `status` требовался побочным эффектом того, что его называл вид,
# и конвейерная коллекция с видом-карточками требования статуса не имела.
# Словарь архетипов спеки английский — как `REGISTRY_ARCHETYPE` в
# `check_links`; за каждым из двух ходит свой гейт, общей таблицы нет.
PIPELINE_ARCHETYPE = "pipeline"


def _filled(value):
    """Поле заполнено по существу, а не по признаку «не None».

    `name not in fields or fields[name] is None` пропускал и `created: ""`,
    и `type: "   "`: обязательное поле удовлетворялось пустотой. Тот же
    довод и тот же фикс, что у `check_package._nonblank` (критерий 4:
    пустая причина не считается причиной). Пустой список сюда добавлен
    отдельно: стёртое multi-value свойство Obsidian пишет как `[]`, и это
    не «поле есть», а «поле пустое».
    """
    if value is None:
        return False
    if isinstance(value, list):
        return any(_filled(item) for item in value)
    return str(value).strip() != ""


def required_fields(base, archetype):
    """Пары «поле, причина» — по одной на поле, в порядке старшинства.

    Один список, а не три проверки подряд: поле, которого требуют сразу
    два источника, — по-прежнему один факт об одной записи, и находка про
    него должна быть одна. Порядок — порядок секции 14: стартовый набор
    (включая его архетипную половину), затем вид. Автору чинить надо то,
    что глубже: требование архетипа переживёт правку вида, обратное — нет.
    """
    out = []
    seen = set()

    def take(name, reason):
        if name in seen:
            return
        seen.add(name)
        out.append((name, reason))

    for name in STARTER_ALWAYS:
        take(name, "стартовый набор: поле %s" % name)
    if archetype == PIPELINE_ARCHETYPE:
        take("status", "стартовый набор: поле status у архетипа %s"
             % PIPELINE_ARCHETYPE)
    for name in sorted(base.required):
        take(name, "поле %s читает вид" % name)
    return out


def check_record(rel, fields, base, vocabulary, archetype=None):
    out = []
    for name, reason in required_fields(base, archetype):
        if not _filled(fields.get(name)):
            out.append(Finding("missing-required", rel, 1, reason))
    for name, allowed in sorted(vocabulary.items()):
        value = fields.get(name)
        # Пустое значение уже сказано классом `missing-required`, если поле
        # обязательно; второй находкой о той же пустоте отчёт не станет
        # точнее, а чинится она одним и тем же движением.
        if _filled(value) and value not in allowed:
            out.append(Finding("value-outside-vocabulary", rel, 1,
                               "%s=%r вне словаря %s" % (name, value, allowed)))
    return out


def _declaration(root, readme, findings):
    """Объявление коллекции: `(архетип, словари)`. Отказ разбора — находка.

    Проглоченный `FrontmatterError` стоил здесь всего словаря сразу:
    `values:` с блочным списком — форма панели Properties — ронял разбор,
    гейт ловил исключение и продолжал с `declaration = {}`. Коллекция
    молча оставалась без перечислений, а класс `value-outside-vocabulary`
    не мог сработать вовсе. Незыблемое №4 дословно: невосстановимое
    значение уходит в отчёт, а не подменяется пустым.

    Парсер эту форму теперь понимает, но починки парсера мало: следующий
    кривой README найдётся, и исчезать он не имеет права.
    """
    if not readme.exists():
        return None, {}
    rel = readme.relative_to(root).as_posix()
    try:
        declaration = parse_frontmatter(_read(readme))
    except FrontmatterError as error:
        findings.append(Finding("unparseable", rel, error.line, str(error)))
        return None, {}
    values = declaration.get("values") or {}
    vocabulary = {}
    if isinstance(values, dict):
        vocabulary = {k: v for k, v in values.items() if isinstance(v, list)}
    return declaration.get("archetype"), vocabulary


def scan(root, today=None):
    root = Path(root)
    # Периметр — тот же и оттуда же, что у гейта ссылок: `check_package`
    # импортирует `_ignored` по той же причине. Здесь `rglob` не имел
    # фильтра вовсе, и два гейта расходились в том, что считать
    # репозиторием: `archive/`, исключённый ровно затем, чтобы первый
    # прогон ADOPT не был стеной находок, этим гейтом проверялся целиком.
    ignored = _ignored(root)
    findings = []
    for base_path in sorted(root.rglob("views.base")):
        rel_base = base_path.relative_to(root).as_posix()
        if not _in_perimeter(rel_base, ignored):
            continue
        collection = base_path.parent
        base = parse_base(_read(base_path))

        # README отсекается вместе со своим видом, а не отдельно: коллекция
        # внутри периметра, оставшаяся без объявления, — это снова пустой
        # словарь молча.
        archetype, vocabulary = _declaration(root, collection / "README.md",
                                             findings)

        for folder in base.folders:
            records_dir = root / folder
            if not records_dir.exists():
                continue
            for record in sorted(records_dir.rglob("*.md")):
                rel = record.relative_to(root).as_posix()
                if not _in_perimeter(rel, ignored):
                    continue
                try:
                    fields = parse_frontmatter(_read(record))
                except FrontmatterError as error:
                    findings.append(Finding("unparseable", rel, error.line, str(error)))
                    continue
                findings.extend(
                    check_record(rel, fields, base, vocabulary, archetype))
    return Report(findings, today=today)


def main(argv=None):
    parser = argparse.ArgumentParser(description="frontmatter gate")
    parser.add_argument("root")
    parser.add_argument("--today", default=None)
    args = parser.parse_args(argv)
    report = scan(args.root, today=args.today)
    rendered = report.render()
    if rendered:
        print(rendered)
    return report.exit_code()


if __name__ == "__main__":
    sys.exit(main())
