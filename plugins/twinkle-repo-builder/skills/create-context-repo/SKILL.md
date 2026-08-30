---
name: create-context-repo
description: Create a context repository from scratch — eight zones, the recipe scaffold, and the author's own first records. Use when a directory carries no recipe marker and no material of its own.
---
# Create a context repository

A context repository is markdown kept for a domain — a company, a project,
hiring, a life — with Obsidian as the human front end and Claude Code as the
agent. This skill turns an empty directory into one.

## Which mode is this

Two observable facts, no judgement:

| marker file | material in the tree | mode |
|---|---|---|
| present | — | already on the recipe: maintain, extend |
| absent | none | **create** — this skill |
| absent | some | **adopt** — stop and use the adopt skill |

The marker is `.twinkle-repo-builder` in the root. Material means content, not
files: a settings directory, a git directory and OS droppings do not count.
One README and nothing else is the disputed case — ask. If there is nobody to
answer, take adopt: its first step is additive, while a mistaken create writes
over somebody's work.

## Order

The order is the reason this is a skill. Getting it wrong is expensive.

1. `git init` — the first action, before anything is written. Everything after
   it becomes revertible, and the end-of-turn hook does not meet a directory
   without git. The installer refuses to run without it, and that refusal is
   the check behind this step.
2. Install the scaffold:
   `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/install_scaffold.py" .`
   It prints every path it wrote, one per line, and writes nothing over an
   existing file: an occupied name stops the whole run before the first byte,
   with every occupied name listed at once.
3. Run both gates on the repository:
   `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/check_links.py" .`
   `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/check_frontmatter.py" .`
   Red here is a defect of the package, not of this repository — the scaffold
   is identical in every instance. Stop and report it rather than editing the
   scaffold in place.
4. **Commit 1 — the scaffold.** Stage exactly the paths the installer printed,
   passing each of them to `git add` by name. Never stage everything: that
   would pick up submodule pointers and whatever the human is editing in
   Obsidian at that moment.
5. Ask the three questions below, or read their answers from the brief.
6. Write what the answers give, and only that.
7. Run both gates again.
8. **Commit 2 — everything that came from the author.**

The two commits are split by origin, not by time. When the recipe version is
updated later, a diff against commit 1 shows what the author changed and what
arrived from the package; without the split, the two are indistinguishable.

## The three questions

| question | what it becomes |
|---|---|
| 1. What is kept here? | the domain line in CLAUDE.md, the draft of core |
| 2. What already exists — work, material, people? | the starting collections and their archetypes |
| 3. What cannot be derived from files and cannot be checked by a machine? | the last section of CLAUDE.md |

Three, not a questionnaire over eight zones. A questionnaire gives a filled-in
repository in which the author cannot tell their own material from what was
dictated to them.

The third question usually yields nothing or one item, and that is the right
answer. Three to six items come from practice; invented on day one they are
rules nobody has broken.

## What is written from the answers

- **A zone is created always, even empty.** The scaffold already did this.
- **A collection is never created without a real record.** An empty collection
  looks like a working one and signals nothing, so it waits for content.
- `core` gets the answer to the first question: who this is, what this is —
  one page, in the author's words.
- `decisions` gets the conversation that just happened: which collections were
  chosen, which archetypes, what was rejected. This record exists whenever
  there was a conversation, because the choice was just made.
- `areas`, `projects` and `sources` get what the second answer named, and
  nothing else.

## Never generate the plausible

No invented project, no `Example Person`, no sample decision along the lines
of "chose X over Y". This is the failure mode of template generators: the tree
looks complete, the author cannot tell their own material from the decoration,
and they do not delete it in case it is needed. A synthetic record is worse
than an empty folder, because the empty folder is honest.

Whatever could not be obtained goes into `OPEN-THREADS.md` — a file in git,
not a report that dies with the session.

## Without a human

In a headless session the three questions are read from the brief. With no
brief, deploy the form: eight zones, no collection at all, and every question
recorded in the open threads. That is the correct result and **not a refusal**.

## Output

```
created: 8 zones, N collections, M records
empty: areas, sources — there was nothing to put there
gates: links ok  frontmatter ok
open threads: 5
```

## Out of scope

- A tree that already has material — that is the adopt skill, and it never
  moves anything before the author agrees to the plan line covering it.
- Keeping an existing repository in shape, including revising CLAUDE.md —
  the maintain skill.
- Adding a collection, an area or a view later — the extend skill, which will
  not finish a structural unit without real content either.
- Writing anything inside a connected knowledge base. Nobody does that.
