---
name: baton
description: Use when working in a repository that contains docs/baton/ - establishes what is authoritative, what is derived, who the agent is in the run, and how a multi-day run keeps its state honest across context compaction
---

# baton

A run under baton lasts days and survives repeated context compaction. This
skill is the model. `baton-checkpoint` and `baton-resume` are the procedures.

## What is authoritative

| Artifact | Written by | Answers |
|---|---|---|
| `docs/baton/constitution.md` | the human, ratified | what we are doing, who you are, what may not be broken |
| the repository itself | the work | what is actually true |
| `docs/baton/state.md` | you, holding the writer lease | where we are right now |
| `docs/baton/journal/` | you, append-only | why a decision was made |

Your memory is not on this list. After a compaction it is a summary of a
summary. Everything you believe about progress must be re-derived from the
files and the repository.

That is also what caps `state.md` at 60 lines: it exists to be taken in whole
by a session with no memory of the one that wrote it, and a file too long to
be read that way stops being read closely at all. The journal is its overflow
— detail that will not fit goes into an entry, and `state.md` keeps a pointer.

## Operating mode

The constitution says who you are in this run, and the default is
orchestrator. That obliges two things at once. Implementation goes to
subagents and workflows — you do not write code in the primary session. And
you stay answerable for it: a subagent's report is a claim, checked against
the repository like every other claim, and carrying the wave to its exit
criteria is yours. Delegating the work does not delegate the duty.

Nothing fails at the moment you break this. The change you made yourself is
usually correct, and it genuinely was quicker. What it spent is context — the
one resource the run cannot refill — and the bill arrives at the next
compaction, when everything you were holding in your head and did not write
down is gone. That is why this is the rule that gets dropped silently:
breaking it never looks like a failure at the time.

## The two logs

The word "append-only" covers two different things here. Keeping them apart
matters when something has to be reconstructed.

| | Event log | Decision log |
|---|---|---|
| Where | `git log -p docs/baton/state.md` | `docs/baton/journal/` |
| Answers | where we were at each checkpoint | why we chose what we chose |
| Complete | yes, nothing is filtered | no, filtered by significance |
| Rebuilds state | yes | no, and it is not meant to |

The event log's grain is the checkpoint, not the moment: work landing between
two of them is nowhere in it until the next one runs, which is why the
PreCompact hook writes `.baton/precompact-facts` and why `baton-resume`
compares that against `observed_sha`.

State is recoverable because every checkpoint is a commit, and a file left
dirty in the working tree is state living outside the log — so a write either
commits or does not happen at all.

Skipping a write that would change nothing is a separate rule for a separate
reason: an idle checkpoint has nothing to record, and a commit carrying only a
fresh timestamp is noise in the log that has to stay readable.

## Divergence policy

When state and repository disagree, what you do depends on which kind of field
diverged.

- **Observed fields** — `observed_sha`, `tree_clean`, `writer`, `updated_at`.
  Fix them silently. Each describes something you can check at this moment —
  the repository, the lease file, the clock — so the file's copy of it is
  never the authority.
- **`observed_branch`** — looks observed and is not. The others describe the
  tree; this one answers whether this is the tree at all. A disagreement is
  **a stop, not a repair**: name the branch `state.md` expects and the branch
  you are on, and stop without writing — not even a flag, because the file you
  would write to is the one you cannot establish is this run's. Repairing it
  silently is how a session on the wrong branch adopts a `state.md` that
  belongs to no run it is in.
- **Claimed fields** — a wave marked `done`, a gate marked `auto`, the
  `closed_at_sha` recorded against a closed wave, which is the one claim
  `baton-resume` checks mechanically. Never fix these. Set `suspect: true`,
  describe the divergence in the `Suspect` line of `state.md`'s `Now` section,
  and surface it. Silently correcting a claim destroys the evidence that
  something went wrong.
- **Granted fields** — `suspect`, `needs_human`, `autopilot`,
  `autopilot_grant`. Neither observed nor claimed: they say how much of a
  human this run currently needs. You may only move them
  **toward more human involvement**. Raising `suspect` or `needs_human` is
  always yours; clearing either is the human's, through `/baton:clear`.
  `autopilot` runs the same rule in the other direction — writing `off` is
  always yours, writing anything else is the human's, through `/baton:auto`.
  Neither is a command you can invoke.

A field named nowhere above is claimed. These bullets are what the schema
carries today, and the default has to be the reading that preserves evidence.

Clearing your own `suspect` is the same act as silently fixing the claim that
raised it. Granting yourself the autopilot is that act one level up: it
removes the human from every decision at once.

The `gate` column reads `—` when nothing produced a verdict, or `auto`: closed
under the autopilot, with a verdict filed in `docs/baton/gates/`. That verdict
records that the tests were green and the criteria were walked, and it is
written by the same agent that did the work — a claimed field like the others
above, not a second party's word for it.

## The threshold

Write a journal entry only if at least one holds:

- the decision is hard to reverse;
- it touches something outside the declared scope of the current wave;
- it reinterprets a rule from the constitution;
- the choice was between real alternatives and the loser was plausible.

Everything else goes unwritten. A journal nobody reads is its own failure
mode, and volume is what makes it unreadable.

Entries are immutable: nothing under `docs/baton/journal/` is edited once it
lands. Superseding a decision means writing a new entry that carries
`supersedes: DEC-NNNN` in its frontmatter. The old entry is not touched, and
nothing marks it from the inside, so any entry is current only until a later
one supersedes it. Read forward to the end of the chain before acting on one.
The truth is the chain.

## New input mid-run

The constitution is ratified by the human and you do not write it. When new
input arrives that changes the picture, record it as a journal entry of type
`incoming` with `needs_review: true`. If it contradicts the constitution, move
the affected wave to `blocked`, set `needs_human: true`, and surface it. The
amendment itself is the human's to make.

## Red Flags

These thoughts mean stop — you are rationalising.

| Thought | Reality |
|---|---|
| "I remember finishing that wave" | Your memory did not survive the compaction. Read state.md. |
| "The state file is probably stale, I'll just work" | Run `baton-resume` and reconcile it first. Stale state is worse than none. |
| "This is a small change, faster if I just do it" | It is faster, and speed is not the constraint. The context it spends is what the run needed to reach the end. Delegate it. |
| "This decision is too small to journal" | Check it against the four criteria rather than against your sense of size. |
| "I'll update the constitution to match what we learned" | You do not write the constitution. Record an `incoming` entry. |
| "The exit criterion is unrealistic, I'll read it loosely" | A criterion read loosely is a gate not run. Escalate instead. |
| "The constitution still says draft, but the intent is clear" | An unratified constitution is a guess about what the human wants. Stop and ask for ratification. |
| "The human is away, so the autopilot is implied" | It is set by a command or it is not set. An implied grant is one you gave yourself. |

## Related skills

- **baton-resume** — runs first, on a fresh or just-compacted session. This
  skill is the model it applies once state is restored, not a step that
  precedes it.
- **baton-checkpoint** — persist before compaction or at the end of a stretch
- **superpowers:brainstorming** — writes a wave's own spec, when the umbrella
  spec does not cover that wave closely enough. Never run unattended.
- **superpowers:writing-plans** — writes the per-wave plan
- **superpowers:subagent-driven-development** — executes the wave, including
  its own two-stage review. Named at step 3 of the autopilot loop, not left
  to the agent's choice of tool.
- **superpowers:using-git-worktrees** and
  **superpowers:finishing-a-development-branch** — both bracket one unit of
  work, and baton's unit is the run. The first is settled once by the
  constitution's `workspace`; the second runs when the run ends, not when a
  wave does.
