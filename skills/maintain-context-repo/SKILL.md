---
name: maintain-context-repo
description: Keep an existing context repository in shape — fix the form without asking, show what is declared and unused, and never touch content. Use when a directory already carries the recipe marker and the work is upkeep rather than creation.
---
# Maintain a context repository

The plugin fixes form silently and does not touch content without the author —
not the body of a record, not the value of a field that is already there, not
the prose of a README. Everything below stands on that line, and the run proves
it about itself before it commits anything.

## Which mode is this

| marker file | material in the tree | mode |
|---|---|---|
| absent | none | create — another skill |
| absent | some | adopt — another skill |
| present | — | **maintain** — this skill |

The marker is `.twinkle-repo-builder` in the root.

## What one run does

1. **Form, mechanically.** Both gates run. What the recipe owns whole is
   restored from the scaffold — the rule files under `.claude/rules/` — and the
   form sections of `CLAUDE.md` are restored section by section, because the
   domain description in the same file is the author's. A path that carries
   uncommitted work is not fixed: it is skipped and named, because a fix there
   would take somebody's unsaved work with it. Whatever the gates still find is
   reported, not guessed at.
2. **Form, in substance.** A missing zone folder is created — the eight zones
   are fixed, so there is nothing to judge. Everything else here is shown: a
   top-level folder the zone map does not know, a direction with no row in
   `areas/README.md`, a declared archetype against how the records actually
   behave, a binary outside git that nothing refers to.
3. **Demand.** Numbers and dates: what was declared and never filled, an
   empty collection, a view whose folder holds no records, the committed date
   of every submodule pin. No verdict is attached. "Stale" and "time to" are
   the author's words; the layer supplies the numbers they are made of.

An empty collection that has been empty past the threshold is the one thing
this run deletes. There is no content in it by definition, which is why the
deletion does not cross the line — and the fact is established by the command
itself, not accepted as a claim from the caller.

## The date is mandatory

`--today YYYY-MM-DD`. It does not shape a single line of the report: it
decides one thing only, whether an empty collection has crossed the threshold.
Reading the system clock instead would put back into a mutating mode the
dependency this package has already pulled out twice.

## The run checks itself and takes itself back

A snapshot is taken before the first fix and compared with the tree afterwards
against the form surface — the closed list of what the plugin may write. One
`content-modified` finding and the whole run is reverted: every path it
touched returns to `HEAD`.

Paths that were already dirty before the run are **not** reverted, and they
are named in the report. Quietly discarding a parallel edit of the author's is
exactly what the rollback exists to prevent, so it stops at their work rather
than tidying over it.

## The commit

Fixes land in a commit of their own, over paths named one by one, never over
the whole index — the index belongs to the person, and it holds whatever they
were preparing for themselves. Two reasons for the separate commit, and the
second is easy to miss: without it the next session reads the fixes as the
author's own work, and there is nothing left to measure a disputed fix
against.

## What this skill does not do

- it does not repair an unresolved link in the body of a record: a guessed
  target is rewritten authorial text, and the gate then goes green pointing at
  a file the author never meant;
- it does not bring an archetype in line with the records: that choice is the
  author's judgement, and a silent switch would make `status` mandatory — a
  fix of the form producing N new errors of the gate;
- it does not delete a view: the predicate "selects nothing" needs a filter
  engine, and this package does not build one; the statically decidable case
  is shown instead;
- it does not delete anything non-empty — not a zone, not a direction, not a
  collection holding a record, not a row of `areas/README.md`;
- it does not write `.link-allow` and does not convert markdown links into
  wikilinks;
- it does not fill in a missing field: `backfill` is asked for by name, from
  the extend skill, and never runs here by itself;
- it never calls `drain-inbox`. Sorting the inbox is a judgement about
  content, and this run is unattended by design.

## What is left for the author

Two places, and neither of them dies with the session: the report on stdout,
and `OPEN-THREADS.md`, where every suggestion is appended once under a stable
key. A second run over an unchanged tree appends nothing and changes not a
byte.

Two things go to the author always, and neither has a command behind it:

- **a demand that reads like a need.** Demand is not need: the need is content
  that does not exist yet, and only the author knows whether it does.
- **a divergence between the recipe and the tree that a fix would settle by
  choosing for the author.** Bring the divergence and a proposal; the choice
  is theirs.

## Command

```sh
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/maintain/run.py" . --today 2026-08-30
```

Exit code 2 means one thing only: the run broke its own promise and took
itself back. Findings left for the author do not colour it — the gates are run
by the end-of-turn hook, while this run fixes the form and shows the rest.

Operations are named here by their command tokens, never by the commands they
wrap. The package check forbids a destructive example anywhere in this
directory, for the same reason it forbids one in the adoption: an example
written into instructions is executed literally, on a tree full of somebody's
work.
