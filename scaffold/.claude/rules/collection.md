---
description: What a collection record must carry
paths: ["**/items/**"]
---
# collection records

**This folder holds the records of one collection and nothing else.** Anything
that does not read as markdown goes elsewhere: it clutters the view and the
frontmatter gate stumbles on it.

**A thing earns a file** when it has its own life cycle — it is created,
changes status, and is found separately from its neighbours. A checklist item,
a metric row or a paragraph inside a write-up is not a record; the sign is
that the only way to find it is to open its parent.

**Rules.**

- Every record carries the starter fields, plus whatever the collection's
  views read.
- The archetype and the status vocabulary are declared in the collection
  README. Refer to them there; a copy of a vocabulary diverges silently.
- A value that cannot be reconstructed six months later is written at creation
  even if no view reads it yet. A value that a script could backfill waits for
  a consumer.
- Attachments live in a sibling folder, not among the records. Records link to
  attachments, never the other way round.

Held by gates: frontmatter gate — a missing required field, a status value
outside the declared vocabulary, unparseable frontmatter.
