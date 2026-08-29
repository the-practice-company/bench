---
description: What a collection view must hold to
paths: ["**/*.base"]
---
# views

**This file is the views of one collection.** It is the navigation layer, and
it lives one level above the records.

**Rules.**

- The filter names the folder the records are in, and that folder has to
  exist. Nothing reports it if it does not: a filter on a renamed folder draws
  an empty table, and an empty table is also what a young collection draws.
  Check this one by looking.
- A view may only read fields the records carry. A field mentioned in a
  filter, a sort or a grouping becomes required for every record of the
  collection — that is where the contract comes from, not from a schema.
- What can be computed is not stored: keep the date, and let the view compute
  whether it has gone stale.
- A second view appears when a question arrives that the first cannot answer.
- Editing this file through the Obsidian UI drops its comments. Edit it as
  text.

Held by gates: frontmatter gate — every field this view reads is required of
every record the filter reaches, and a record lacking one is a finding.
