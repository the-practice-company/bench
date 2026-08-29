---
archetype: pipeline
values:
  status: [open, decided, revisited]
---
# decisions

Closed questions, kept so that the agent does not reopen them.

**Membership test.** Three conditions, all of them required:

1. There was a named rejected alternative. No alternative means an action, not
   a decision.
2. Reversing it costs more than taking it. Free to undo — not written down.
3. It will bear on decisions taken later by someone who does not remember it.

In practice: if in three months someone proposes the opposite, do I want the
agent to object by pointing at this record? No — it does not belong here.

**Shape.** A collection: one file per decision, plus views.

**Writing.** Append only. A decision is not edited; it is superseded by a new
record that links back to the one it replaces.

**Status vocabulary.**

- open — the question is stated and not closed
- decided — the choice is made
- revisited — reopened and replaced by a later record

The machine-readable copy of these three words is this file's frontmatter;
there is no third place where they are written down.

**Nothing here yet.** There is no decision in this zone — ask before writing.

**By threshold.** A "due for review" view with the first record that carries a
review trigger. An `area` field for grouping once there are enough records to
group. A skill for keeping this zone once the filter rule has had to be
explained twice.
