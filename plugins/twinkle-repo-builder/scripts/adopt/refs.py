#!/usr/bin/env python3
"""`find-refs`: кто ссылается на путь, и сколько из них не переживут переезда.

Резолвер здесь не живёт. Он один на пакет и стоит в гейте ссылок; сюда он
приходит импортом, и тождество этого имени утверждается тестом — иначе
второй резолвер заводится незаметно и расходится молча.

Markdown-ссылки инвариант R не видит: §13 делает их ошибкой всегда, и
`rewrite-refs` их не трогает. Переезд их всё равно ломает, поэтому здесь
они и находятся, и показываются отдельным числом — молчать про них значит
показать автору инвариант, который сошёлся мимо поломки.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts import paths as pathlib_rules
from scripts.check_links import occurrences
from scripts.findings import EXIT_OK

COLUMNS = ("file", "line", "kind", "raw")


def _under(child, parent):
    return child == parent or child.startswith(parent + "/")


def find(root, target):
    """`(вхождения, нечитаемые)` для этого пути и всего, что под ним.

    Каталог допустим и обязателен: переезжает папка — ломаются ссылки на
    каждый файл внутри, и спрашивать про них по одному значит промахнуться
    ровно там, где переезд крупный.

    Нечитаемые возвращаются, а не отбрасываются. Ответ «вхождений 0» про
    дерево, часть которого не прочитана, — невосстановимое значение,
    подставленное молча; незыблемое №4 запрещает это и здесь. Чужие
    деревья — ровно то место, где такие файлы и водятся.
    """
    target = pathlib_rules.normalise(target).rstrip("/")
    occs, unreadable = occurrences(root)
    return ([o for o in occs if any(_under(c, target) for c in o.candidates)],
            unreadable)


def render(root, target):
    target = pathlib_rules.normalise(target).rstrip("/")
    hits, unreadable = find(root, target)
    markdown = [h for h in hits if h.kind == "mdlink"]
    out = ["# find-refs %s: вхождений %d, из них markdown-ссылок %d"
           % (target, len(hits), len(markdown)),
           "\t".join(COLUMNS)]
    for hit in hits:
        out.append("\t".join((hit.path, str(hit.line), hit.kind, hit.raw)))
    for rel, _, consequence in unreadable:
        out.append("# не прочитан: %s — %s" % (rel, consequence))
    return "\n".join(out) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description="who links to this path")
    parser.add_argument("root")
    parser.add_argument("target")
    args = parser.parse_args(argv)
    sys.stdout.write(render(args.root, args.target))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
