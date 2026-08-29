---
name: drain-inbox
description: Triage the inbox of a context repository item by item — four outcomes, each agreed with the author before anything is moved or dropped. Use when the inbox zone has accumulated captures and somebody asks for them to be sorted.
---
# Drain the inbox

The inbox is the zone of capture: an item lying there is unsorted by
definition. This skill is the only one of the upkeep set that touches content,
and it touches it **only with the author**. The maintain skill never calls it.

## Four outcomes and the judgement each one costs

| outcome | the judgement it needs | the mechanism |
|---|---|---|
| it became a record | which zone and collection the placement rule sends it to, and which archetype | `move` into the collection, then `backfill` for what a rule can recover |
| it dissolved | what exactly to absorb, and into which existing records | editing existing records — authorship, done in the conversation, not by a command |
| it was raw material | it was received, not written | `move` into `sources`; whatever is derived from it later carries `source` |
| it was rejected | value | `drop` — out of the tree, still in the history |

## Without an interlocutor, two of the four are executed

"It dissolved" and "it was rejected" both need a conclusion about the value of
somebody's content, and the line of responsibility hands that to the author. In
a headless session the item **stays in the inbox** and goes into the report.

This breaks no invariant: an item lying in the inbox is unsorted by definition,
and this one was never sorted. The alternative — a headless run deleting what
it judged unnecessary — is the plugin deciding that content is not needed, and
it is refused.

## The plan is where the agreement lives

One line per item, agreed before anything moves, in `tmp/drain-plan.md`. The
same format the adoption uses, and the same reader: a line carries a cross when
the author has agreed to it, a target, and a body underneath saying why.

The reader checks the plan against the **whole tree**, not against the inbox
alone, so every top-level path needs a line. Everything that is not being
triaged gets the reserved target `stay`, which is executed by nothing:

```markdown
## Draining the inbox

- [ ] `areas` -> `stay`

  Not part of this triage.

- [ ] `inbox/README.md` -> `stay`

  The README of the zone, not an item in it.

- [x] `inbox/2026-08-20-call.md` -> `areas/work/journal/items/2026-08-20-call.md`

  Became a journal record: an event, and the date is in the name.

- [x] `inbox/2026-08-21-scratch.md` -> `git-history`

  Rejected by the author: no value; the content stays in the history.
```

A line with no cross is executed by nothing. A target carrying `?` is executed
by nothing. Both are the author's silence, and silence is not agreement.

## Order per item

1. `find-refs` — who points at this path today. References first, the path
   second: the rewriter reads the tree as it stands, and a path that has
   already travelled is a path it can no longer find.
2. `rewrite-refs` — the references, against the plan.
3. `move` — the path itself, against the plan. For a rejected item, `drop`
   instead: the file leaves the tree and stays in the history.
4. `backfill` for the collection it landed in, if a field is missing there.

`created` is recoverable: the capture rule guarantees the date in the file
name, and that is the rule `backfill` prefers over the date of the commit that
carried the file in. Anything no rule can recover is either marked with the
synthetic token or reported — never substituted quietly.

## The invariant, and how to see it holds

After a triaged item is dealt with: the file is not in the tree, and it is in
the history. Both halves, checked on the tree rather than assumed from the
report — a command that said it moved something is not evidence that it did.

An item left in the inbox is fine. An item that is neither in the inbox nor in
the history is the failure this order exists to make impossible: `drop`
refuses a path that is not in `HEAD`, because deleting an uncommitted file
deletes it for good.

## What this skill does not do

- it does not decide that content has no value. That is the whole of the
  fourth outcome, and it belongs to the author;
- it does not absorb an item into existing records on its own: the third
  outcome is editing somebody's text, and it happens in the conversation;
- it does not invent a collection to put an item into. If no collection fits,
  the extend skill creates one — with the record first, and with the author;
- it does not write a frontmatter value it cannot recover by a named rule;
- it does not act on a line without a cross, and it does not touch a path no
  line covers.

## Commands

```sh
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/adopt/refs.py" . inbox/2026-08-20-call.md
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/adopt/rewrite_refs.py" . inbox/2026-08-20-call.md areas/work/journal/items/2026-08-20-call.md --plan tmp/drain-plan.md
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/adopt/move.py" . inbox/2026-08-20-call.md areas/work/journal/items/2026-08-20-call.md --plan tmp/drain-plan.md
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/adopt/drop.py" . inbox/2026-08-21-scratch.md --plan tmp/drain-plan.md
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/maintain/backfill.py" . areas/work/journal created
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/adopt/revert.py" . inbox areas
```

Every mutation takes the plan as a required argument and refuses on a line
that is not there. That is a door closed by argument parsing rather than by
discipline.

Operations are named here by their command tokens — `find-refs`,
`rewrite-refs`, `move`, `drop`, `backfill`, `revert` — and never by the
commands they wrap. The package check forbids a destructive example anywhere
in this directory: an example written into instructions is executed literally,
on somebody's captures.
