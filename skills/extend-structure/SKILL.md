---
name: extend-structure
description: Add a collection, an area or a view to an existing context repository, and fill in a missing field — the record first, the unit second, so nothing empty is ever created. Use when the repository already carries the recipe marker and something new has to be added to its structure.
---
# Extend the structure

Four commands, and one rule above all four.

## Record first, unit second

A structural unit is never created without content. Not "create it and fill it
later" — the folder, the README and the views file do not reach the disk until
the first real record is in hand. Deploying the skeleton, then asking, then
rolling back was considered and rejected: the rollback is safe, but an
interrupted run leaves an empty collection behind, and an empty collection
looks like a working one while signalling nothing at all.

So the order is the reverse of how the recipe reads. The record comes first
because that is the only way the invariant holds mechanically rather than by
discipline.

## The four commands

| command | when | refuses when | with nothing to put inside |
|---|---|---|---|
| `add-collection` | a set of records of one kind has appeared | the name is taken, the archetype is outside the closed set, the path leaves the root | writes nothing, asks in the open threads |
| `add-area` | a direction of work has appeared and it has a purpose | the name is taken, it is not a folder name, `areas/README.md` has no listing heading | writes nothing, asks in the open threads |
| `add-view` | an existing collection needs another cut | the name is taken, the collection has no views file, the folder the filter names holds no records | refuses — a view over nothing is what the demand layer would show as dead the same day |
| `backfill` | a field is missing across a collection | — | writes what is computable, marks what is not, defers what belongs to the author |

`add-collection` takes the first record as an argument. Write it to `tmp/`
first, in the author's own words, and point the command at it; the record keeps
the name of the file it came from unless another one is given. A record file
that cannot be read is a named refusal, not an empty record: sending the author
a question about a record they have already written would be the substitution
this package forbids.

`add-area` writes the folder, its README and the row in `areas/README.md`. The
row is not optional and not deferred: a direction without a row in the listing
is drift created by construction.

`add-view` never evaluates the filter. Only the statically decidable case is
checked — the folder named by `file.inFolder(...)` holds no records. A filter
engine for Obsidian Bases is not built here, and deleting an author's view on
the strength of a guessed one would be the worst trade in this package.

## What `backfill` may and may not do

Three outcomes per record, and there is no fourth:

| outcome | when | what lands in the record |
|---|---|---|
| computed | a named rule produced a value | the real value, and the rule is named in the table |
| synthetic | no rule, and the field has no declared vocabulary | the token `unknown` |
| deferred | no rule, and the field has a declared vocabulary | **nothing**, and the record is named in the report |

The vocabulary is what separates the second outcome from the third. `unknown`
in a field with a declared vocabulary is a value outside it — a fix that
manufactures an error of the gate. `status` falls under this always, so
`backfill status` writes nothing and reports; not by a special case, but by the
general rule.

Every value that lands on disk is written into a table under `tmp/`, one row
per record, with the rule that produced it. The table is what makes a value
checkable afterwards without trusting this run's word for it.

`--silently` is the narrow mode: it writes only when **every** record is
computable, and on the first record that is not, it writes nothing at all and
says so. A pass with nobody watching has no right to stamp `unknown` across two
hundred files with no one to tell.

## What this skill does not do

- it does not invent the first record. No sample project, no `Example Person`,
  no plausible decision — a synthetic record is worse than an empty folder,
  because the empty folder is honest;
- it does not choose the archetype: the closed set is `journal`, `pipeline`,
  `registry`, and which one this is describes how the records behave, which
  the author knows and the tree does not yet;
- it does not write the purpose of a direction: without that phrase the
  direction is not created, and the question goes to the open threads;
- it does not group a new view by a field: grouping demands that field of
  every record, and nobody named one;
- it does not overwrite a value that is already there, not even an empty one.
  An empty value stays a finding of the gate, and it stays the author's.

## What goes to the author

Whatever could not be obtained goes to `OPEN-THREADS.md` — a file in git, not a
report that dies with the session. The question carries a stable key, so
refusing the same command twice asks once.

Escalate, do not decide: whether a collection is worth splitting, which
archetype fits, what the purpose of a direction is, and every value a rule
could not recover. All four are judgements about content.

## Commands

```sh
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/maintain/extend.py" . add-collection projects/leads --archetype pipeline --record-file tmp/first.md
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/maintain/extend.py" . add-area sales --purpose "Sales and the funnel"
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/maintain/extend.py" . add-view core/people "Everyone"
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/maintain/backfill.py" . areas/work/journal created
```

Exit code 2 is a refusal with a named reason, and a refusal has written
nothing: every command checks everything before the first byte. Read the
reason, fix the input or take the question to the author, and run it again.

Operations are named here by their command tokens, never by the commands they
wrap. The package check forbids a destructive example anywhere in this
directory: an example written into instructions is executed literally, on a
tree full of somebody's work.
