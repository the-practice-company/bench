---
description: Zone rules for tmp
paths: ["tmp/**"]
---
# tmp

**Belongs here** if it stops being needed when the task ends.

**Rules.**

- Nothing here is a source of truth. Anything relied on later moves out first,
  by the placement rule.
- Writing and deleting are both free.
- No long-lived zone links here. Those zones outlive this one, so such a link
  is a breakage on a delay rather than a risk.
- Session artefacts belong here rather than in context: what is held only in
  context is lost when the context is compacted.

Held by gates: link gate — a link from a long-lived zone into a transient one.
