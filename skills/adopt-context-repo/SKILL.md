---
name: adopt-context-repo
description: Adopt an existing folder of notes as a context repository — inventory it, agree every change with the author as a line of a plan, and touch nothing that no line covers. Use when a directory already holds material of its own and carries no recipe marker.
---
# Adopt an existing tree

Somebody else built this tree. The plugin fixes form and never touches content
without the author, so every change here is agreed in advance by a line of the
plan, and every change can be taken back byte for byte.

## Which mode is this

| marker file | material in the tree | mode |
|---|---|---|
| present | — | already on the recipe: maintain, extend |
| absent | none | create — the other skill |
| absent | some | **adopt** — this skill |

The marker is `.twinkle-repo-builder` in the root. Material means content, not
files: a settings directory, a git directory and OS droppings do not count. The
marker is written by the last commit of the adoption, not the first: set early
it would declare a half-adopted tree ready, while an interrupted run has to
stay an adoption and read its own plan on the next start.

## Three questions, asked before the plan

The answers decide how the rest of the tree is read, so they come first.

| question | what it decides |
|---|---|
| 1. Do we put this tree under git? | whether anything may be changed at all |
| 2. What is kept here — a company, a project, hiring, a life? | which zones the plan aims at |
| 3. Which folders may not be touched? | the lines whose target is `stay` |

A "no" to the first question is an answer, not a failure: the run becomes an
inventory and a plan, and stops there. Record that refusal in the header of the
plan, where the next run reads it, so the author is asked once and not again.
In a headless session with no brief, git is set up — the first commit is
additive, and without it nothing else can be undone.

## Order

1. `init-tree` — the tree becomes revertible: git, the commit that records it
   as found, and nested foreign repositories excluded before that commit.
2. `scan-tree` — one line per directory: files, weight, dates, kinds. Weight
   goes to the author **before** the commit, not after: a 4.8 GB export travels
   into history and does not travel back out of it.
3. **The plan**, `tmp/adopt-plan.md`. One line per inventory path, a body under
   every line, and `?` wherever the answer is missing. This file is the only
   place where agreement lives; a path nobody wrote a line about is a finding,
   not a default.
4. **The scaffold**, and it is purely additive: every name it would write over
   stops the whole run before the first byte, with every occupied name listed
   at once. The two the plan agreed to merge are named to the installer, which
   then leaves them where they are and says so. This is a commit of its own.
5. `read-plan` — what the author agreed to and what is still not done. While
   the plan carries findings it prints them and nothing else.
6. Per agreed line, in this order: `find-refs` → `rewrite-refs` → `move`.
   References first, the path second: the rewriter reads the tree as it stands,
   and a path that has already travelled is a path it can no longer find.
   Reserved targets have their own commands — `drop` for `git-history`, `merge`
   for the two files the recipe shares with the tree — while `stay`,
   `foreign-repo` and any target carrying `?` are executed by nothing.
   `rewrite-refs` is a mass mutation and answers as one: a machine table in
   `tmp/` naming every rewrite by file, line and text, and a token for every
   reference it left alone — the bare name that still leads, the markdown link
   §13 defers to a mutation of its own, the path in backticks or in a
   permission rule that nothing will rewrite for you. A reference it can
   neither rewrite nor explain is a finding, and the run exits red.
7. `check-plan` before the commit of the stage: it reads the tree against the
   commit that recorded it as found and names every path that changed outside
   an agreed line, whoever changed it.
8. Red — `revert` over the paths of the stage, then read the plan again.

A stage ends in a commit or in a `revert`. It does not end with a dirty tree: a
clean tree is the only thing that tells "the adoption broke this" from "this
was broken before the adoption".

## The commits

| # | commit | what is inside | whose it is |
|---|---|---|---|
| 0 | as found | the tree exactly as it was | the author's |
| 1 | the recipe scaffold | additive only | the package's |
| 2 | stage 1 | the agreed moves, drops and merges | mechanical |
| 3 | stage 1b | records written from what the tree already said | the author's |

Split by origin, not by time. When the recipe version is updated later, a diff
against commit 1 shows what the author changed and what arrived from the
package; without the split the two are indistinguishable.

Stage the paths by name, one by one. Staging everything picks up a nested
foreign repository as a pointer to an object this repository does not have, and
a clone of it then has no content at all.

## The two files the recipe shares with the tree

`CLAUDE.md` and `.gitignore` usually exist before the adoption, so they fall
under the same rule as everything else: a line of the plan first, with the
reserved target `merge`. The installer is told which of them to leave alone; it
writes every other scaffold file, and names the ones it skipped. The merge then
appends the recipe under a marker — the author's text stays where it was, and
`.gitignore` gains only the patterns it lacks. A second run changes nothing:
the marker is what says the line is done.

## What this skill does not do

- it does not act on a line without a cross, and it does not act on a line
  whose target carries `?`, cross or no cross;
- it does not write `.link-allow`: every line of an allowlist needs a reason,
  and reasons belong to the author;
- it does not convert markdown links into wikilinks — that is a separate mass
  mutation with a plan of its own; until then such links are counted and shown,
  not changed;
- it does not reach inside a folder that carries a git directory of its own:
  what that folder is belongs to its owner, and where it should live goes into
  the open threads;
- it does not end with a green gate. It ends with measured debt: the number of
  resolving references did not change, and the number of findings of severity
  `error` did not grow.

## Commands

```sh
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/adopt/init_tree.py" .
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/adopt/inventory.py" .
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/install_scaffold.py" . --merging CLAUDE.md
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/adopt/read_plan.py" . tmp/adopt-plan.md
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/adopt/refs.py" . journal
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/adopt/rewrite_refs.py" . journal areas/work/journal --plan tmp/adopt-plan.md
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/adopt/move.py" . journal areas/work/journal --plan tmp/adopt-plan.md
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/adopt/merge.py" . CLAUDE.md --plan tmp/adopt-plan.md
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/adopt/drop.py" . archive --plan tmp/adopt-plan.md
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/adopt/check_plan.py" . tmp/adopt-plan.md
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/adopt/revert.py" . journal areas
```

Every mutation takes the plan as a required argument, and refuses on a line
that is not there. That is the door closed by argument parsing rather than by
discipline: the same invariant is held three times over — by what `read-plan`
prints, by what each command agrees to do, and by what `check-plan` finds
afterwards.

Operations are named here by their command tokens — `move`, `drop`, `merge`,
`revert`, `init-tree`, `scan-tree`, `find-refs`, `read-plan`, `check-plan`,
`rewrite-refs` — and never by the commands they wrap. Knowledge comes from the
mechanism that holds it: the package check forbids a destructive example
anywhere in this directory, because an example written into the instructions of
an adoption is executed literally on somebody else's tree sooner or later.
