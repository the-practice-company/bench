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
    "ambiguous",
    "orphan",
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

_SEVERITY = {
    "unresolved": "error",
    "md-link-to-file": "error",
    "link-to-transient": "error",
    "escapes-root": "error",
    "dead-allow": "error",
    "ambiguous": "warning",
    "orphan": "report",
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
