"""Классы находок, их тяжесть, детерминированный отчёт и коды возврата.

Коды взяты из секции 15: 2 — нарушение, 0 — всё остальное, включая
случай «инструмент не смог запуститься». Различие между «нашёл нарушение»
и «не смог проверить» несёт текст, а не код: молчащий отказ — та самая
поломка, что стоила чужому продукту трёх с половиной месяцев.
"""

EXIT_OK = 0
EXIT_VIOLATION = 2
EXIT_TOOL_FAILED = 0

LINK_CLASSES = (
    "unresolved",
    "md-link-to-file",
    "link-to-transient",
    "escapes-root",
    "dead-allow",
    "broad-allow",
    "ambiguous",
    "orphan",
    "undecodable",
)

FRONTMATTER_CLASSES = (
    "missing-required",
    "value-outside-vocabulary",
    "unparseable",
)

PACKAGE_CLASSES = (
    "unknown-hook-event",
    "unknown-hook-type",
    "unknown-matcher",
    "absolute-path",
    "relative-path-in-skill",
    "destructive-example",
    "gate-not-read-only",
    "tests-touched-product",
    "skill-without-description",
    "skill-without-eval",
    "skill-name-mismatch",
)

ADOPT_CLASSES = (
    "plan-unparseable",
    "uncovered-path",
    "overlapping-line",
    "unagreed-change",
    "line-state-conflict",
    "foreign-repo",
    "created-unrecoverable",
)

MAINTAIN_CLASSES = (
    "content-modified",
    "unexplained-count",
    "silent-substitution",
    "structure-without-content",
    "empty-collection",
    "declared-unused",
    "view-selects-nothing",
    "map-tree-divergence",
    "archetype-mismatch",
    "unreferenced-ignored-binary",
)

_SEVERITY = {
    "unresolved": "error",
    "md-link-to-file": "error",
    "link-to-transient": "error",
    "escapes-root": "error",
    "dead-allow": "error",
    # Правило аллоулиста, не привязанное ни к месту, ни к имени, — та же
    # тяжесть, что и мёртвое: спека делает `dead-allow` ошибкой потому, что
    # уцелевшее исключение бессрочно ослабляет гейт. Здесь ослабление шире
    # (гасит везде) и незаметнее (запись выглядит живой), так что мягче быть
    # не может. Класс отдельный от `dead-allow`, потому что утверждения у них
    # противоположные: «ничего не исключает» против «исключает что угодно»,
    # и назвать второе первым — сказать про правило неправду.
    "broad-allow": "error",
    "ambiguous": "warning",
    "orphan": "report",
    # Файл, который не декодируется, — **ошибка**, а не отчёт. Три довода,
    # каждый против одного из двух соседей помягче.
    #
    # Против `report` (как `orphan`): сирота — суждение о содержимом, и
    # плагин там не хозяин (незыблемое №1). Кодировка файла — форма, а форма
    # правится плагином и обязана быть верной. Автору есть что сделать
    # ровно одним движением: пересохранить в UTF-8.
    #
    # Против `warning` (как `ambiguous`): у неоднозначной ссылки отчёт
    # всё-таки полон — кандидаты перечислены, вердикта нет. Здесь отчёта
    # нет вовсе: ссылки этого файла не проверил никто. Пропустить это
    # предупреждением значит выпустить прогон зелёным при непроверенном
    # куске дерева — ровно то молчание, против которого написан модуль.
    #
    # И довод сверху: класс заведён взамен подстановки замещающего знака,
    # которая давала `unresolved` — ошибку. Понизить тяжесть заодно с
    # починкой правдивости — это тихо ослабить гейт под видом фикса.
    "undecodable": "error",
    "missing-required": "error",
    "value-outside-vocabulary": "error",
    "unparseable": "error",
    "unknown-hook-event": "error",
    "unknown-hook-type": "error",
    "unknown-matcher": "error",
    "absolute-path": "error",
    "relative-path-in-skill": "error",
    "destructive-example": "error",
    "gate-not-read-only": "error",
    "tests-touched-product": "error",
    "skill-without-description": "error",
    "skill-without-eval": "error",
    "skill-name-mismatch": "error",
    # Пять ошибок — про процедуру усыновления: план не разобрался, путь не
    # покрыт, строки перекрылись, дерево ушло с плана, состояние строки
    # противоречиво. Каждая означает, что дальше двигаться нельзя.
    "plan-unparseable": "error",
    "uncovered-path": "error",
    "overlapping-line": "error",
    "unagreed-change": "error",
    "line-state-conflict": "error",
    # Два отчёта — про свойства чужого дерева, которых ADOPT не создавал и
    # чинить не вправе: вложенный репозиторий и невосстановимая дата
    # создания. Ошибкой их сделать значило бы объявить чужое дерево
    # виноватым и остановить процедуру на том, что в ней не чинится.
    "foreign-repo": "report",
    "created-unrecoverable": "report",
    # Четыре ошибки — про нарушенное обещание плагина о себе: прогон тронул
    # содержимое, счётчики не сошлись, значение записано молча, единица
    # доведена до диска без записи. Каждая означает, что режиму нельзя
    # верить дальше, и потому останавливает его собственным откатом.
    "content-modified": "error",
    "unexplained-count": "error",
    "silent-substitution": "error",
    "structure-without-content": "error",
    # Шесть отчётов — наблюдения о дереве. Чинить их либо не плагину
    # (архетип, карта, бинарь), либо нечем детерминированно. Ошибкой их
    # сделать значило бы остановить режим на том, чего в нём не чинится, —
    # тот же довод, что у `foreign-repo` волной раньше.
    "empty-collection": "report",
    "declared-unused": "report",
    "view-selects-nothing": "report",
    "map-tree-divergence": "report",
    "archetype-mismatch": "report",
    "unreferenced-ignored-binary": "report",
}


def severity(cls):
    try:
        return _SEVERITY[cls]
    except KeyError:
        raise ValueError("неизвестный класс находки: %r" % (cls,))


class Finding:
    __slots__ = ("cls", "path", "line", "detail")

    def __init__(self, cls, path, line, detail):
        severity(cls)  # неизвестный класс падает здесь, а не в отчёте
        self.cls = cls
        self.path = str(path)
        self.line = int(line)
        self.detail = detail

    def key(self):
        return (self.path, self.line, self.cls, self.detail)

    def render(self):
        return "%s:%d %s %s" % (self.path, self.line, self.cls, self.detail)

    def __repr__(self):
        return "Finding(%r, %r, %r, %r)" % (self.cls, self.path, self.line, self.detail)

    def __eq__(self, other):
        return isinstance(other, Finding) and self.key() == other.key()

    def __hash__(self):
        return hash(self.key())


class Report:
    def __init__(self, findings, today=None):
        self.findings = list(findings)
        # Дата прогона, если её передали. Правил, зависящих от даты, в волне 1
        # нет; параметр несётся явно, чтобы принятое значение было наблюдаемо,
        # а не проглочено молча (незыблемое №4).
        self.today = today

    def counts(self):
        out = {}
        for f in self.findings:
            out[f.cls] = out.get(f.cls, 0) + 1
        return out

    def render(self):
        """Побайтово детерминирован: сортировка по ключу, пути относительные."""
        return "\n".join(f.render() for f in sorted(self.findings, key=Finding.key))

    def exit_code(self):
        for f in self.findings:
            if severity(f.cls) == "error":
                return EXIT_VIOLATION
        return EXIT_OK
