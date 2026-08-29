---
description: Zone rules for decisions
paths: ["decisions/**"]
---
# decisions

**Belongs here** only if all three hold: there was a named rejected
alternative; reversing costs more than taking it; it will bear on choices made
later by someone who does not remember it.

The practical form of the test: if in three months someone proposes the
opposite, do I want the agent to object by pointing at this record?

**Rules.**

- A record is added, never edited. A choice that changed is superseded by a
  new record linking back to the one it replaces.
- How something was done is work, not a decision. The zone fills with process
  notes the moment that line is crossed.
- The status vocabulary is declared in the zone README. Read it there; do not
  restate it anywhere else.
- A record that names a review trigger carries its date as a field, so that a
  view can compare it. What can be computed is not stored.

Held by gates: frontmatter gate — the starter fields on every record and the
status value from the vocabulary the zone README declares; write hook — a
warning when an existing record here is edited rather than superseded.
