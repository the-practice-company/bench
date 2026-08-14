# baton

Keeps goal and state coherent across multi-day autonomous agent runs.

An agent working one task for days will have its context compacted many
times over. Each time, it loses the thread: what it already finished, what
it was doing next, and what it was told never to do. baton makes that
recoverable in one step — and makes the recovery verifiable against the
repository, not trusted from a summary the model wrote about itself.

State lives in `docs/baton/`, committed to git. Git history is the event
log. A decision journal records why choices were made, not just what they
were. Checkpointing persists state before context is lost; resuming reads it
back and checks it against the repository rather than taking the file's word
for it.

It is a thin process layer on top of
[superpowers](https://github.com/obra/superpowers), not a replacement for
it. superpowers covers one unit of work end to end — spec, plan, TDD,
review. baton covers what sits above and between those units across days:
which unit is next, what has already closed, and what must not be broken
along the way.

## Install

```
/plugin marketplace add the-practice-company/bench
/plugin install baton@bench
/plugin install superpowers@claude-plugins-official
```

baton works without superpowers; you will just be writing the per-wave
specs, plans and tests by hand.

Start a fresh session afterwards — hooks, skills and commands only take
effect in a session that begins after the install, not the one you installed
from.

## A run, end to end

Say the task is **usage-based billing for an API** — too big for one sitting,
and you want it carried on while you sleep.

baton does not run the work. superpowers does. baton decides which wave is
next, records what closed, and keeps that recoverable when the context is
compacted. So the walkthrough below is mostly the ordinary superpowers flow
with four baton commands around it.

### 1. Design it, before baton exists

Use `superpowers:brainstorming` as you always would. It writes an umbrella
spec to `docs/superpowers/specs/2026-08-13-usage-billing-design.md`.

`/baton:init` refuses to start without one. baton decomposes a spec; it does
not replace the conversation that produces it.

### 2. Set the run up — `/baton:init`

Once per repository, and it is a conversation, not a form. It works out with
you: the goal, how the work splits into waves, what each depends on, what
"closed" means for each in EARS, what no wave may break, the command that
proves the repository works — and, per wave, **which document that wave builds
to**.

It also settles one thing once, so nobody has to answer it at 03:40: whether
this run works in your checkout as it stands, or in an isolated worktree of
its own. Working in place is the default — baton needs no separate tree for
anything of its own, and the declared preference is what stops
`using-git-worktrees` asking for consent mid-wave when there is nobody to give
it.

Out comes `docs/baton/constitution.md`:

```yaml
- wave: 1
  name: metering
  depends_on: []
  exit_criteria:
    - When a request is served, the system shall record one usage event
      against the calling account.

- wave: 2
  name: rating
  depends_on: [1]
  exit_criteria:
    - The system shall turn a period of usage events into priced invoice
      lines.
```

Then you ratify it by hand — `status: ratified`, `ratified_by`,
`ratified_at`, `git_anchor`. From that moment the file is read-only to the
agent, so the thresholds it is judged against sit outside its reach.

**Ratify before you compact.** Clearing a context filled by the decomposition
dialogue is a sensible thing to do here, and safe — the state file is already
written and committed. But an unratified constitution is a guess about what
you wanted, so a session that comes back to one will stop and ask, and you
will have spent a compaction to arrive at the step you were on.

Waves whose spec cell in `state.md` is `—` are not startable. Most waves will
point at the umbrella spec, or at one section of it. A wave the umbrella
covers in a single line gets its own `brainstorming` pass — and that is a
decision you make here, at setup, not at midnight.

### 3. Hand it over — `/baton:auto`

```
/baton:auto            # every wave still todo
/baton:auto 2          # wave 2 and no other
```

It lays out which waves in what order, where each spec comes from, the exit
criteria quoted word for word, the command that will check them, and — the
useful part — where it is unsure. You correct it or say go. Then you leave.

### 4. What happens while you are gone

Per wave, in order:

| | |
|---|---|
| **Plan** | `superpowers:writing-plans` against that wave's spec |
| **Work** | `superpowers:subagent-driven-development` — a fresh subagent per task, spec-compliance review then code-quality review after each |
| **Gate** | `baton-gate` runs `verify_cmd` and scans for placeholder markers; the agent walks the exit criteria one at a time against the repository |
| **Record** | a verdict filed under `docs/baton/gates/`, the wave closed, a checkpoint committed |

Then the next wave. A wave that cannot close goes to `blocked`, with a journal
entry saying what stopped it, and the run moves on to one that can.

### 5. In the morning — `/baton:status`

Deviations first: what closed, what blocked, which decisions want your review.
Waves closed overnight read `auto` in the gate column, with the verdict file
named beside each one.

Nothing there is waiting to be countersigned. A run only waits on you in three
ways, and `/baton:status` leads with all three: `suspect: true` or
`needs_human: true` in the frontmatter, which stop it outright and which
`/baton:clear` lowers once you have looked; a wave sitting at `blocked`, which
waits on whatever its journal entry names, not on a mark from you; and an
unratified constitution, which `/baton:ratify` settles. Silence on all three
means the run is not asking for anything, and reading the verdicts is
something you do because you want to, not because a column is waiting for
your initials.

### 6. The next night — `/baton:continue`

One word restarts the run on a fresh session. Deliberately not automatic: a
session opened to check one thing has not agreed to six hours of unattended
work.

### 7. When the run is over

All waves `done`, and `superpowers:finishing-a-development-branch` asks the
question it always asks — merge, PR, or clean up. Once per run, not once per
wave, because that is a question only you can answer.

---

**The shape worth remembering:**

```
[where the run works — declared once, in the constitution]

    wave 1:  plan  work  →  gate  →  checkpoint
    wave 2:  plan  work  →  gate  →  checkpoint
    wave 3:  plan  work  →  gate  →  checkpoint

[you are back: merge? PR? clean up?]
```

baton is what happens before the first wave and after the last one, plus a
short record between waves. Inside a wave it is not there — `plan` and `work`
are superpowers' own skills, running exactly as they would without baton.

## First run

```
/baton:init
```

Once per repository. It is a conversation, not a form: it reads an umbrella
spec from `docs/superpowers/specs/`, works out with you how the work splits
into waves and what "closed" means for each, and writes
`docs/baton/constitution.md`. Then it hands the file back for you to ratify —
change `status: draft` to `status: ratified` and fill `ratified_by`,
`ratified_at` and `git_anchor` yourself.

That ratification is not paperwork. From that moment the constitution is
read-only to the agent: `baton-write`, the tool every checkpoint and resume
uses, refuses that one path unconditionally, so the thresholds the run is
judged against sit outside the reach of the thing being judged.

## Day to day

| Command | What it does |
|---|---|
| `/baton:init` | Once: decompose the umbrella spec, write the constitution. Human-typed only. |
| `/baton:checkpoint` | Persist run state now — before compacting context by hand. |
| `/baton:status` | Show where the run stands, deviations first. |
| `/baton:auto [wave] [--since <ref>]` | Hand the run over: readiness review, then work with no human present. Human-typed only. |
| `/baton:continue` | Pick an unattended run back up on a fresh session. Human-typed only. |

Between those, the agent works on its own. Skills fire on their own
triggers, and two hooks — one just before compaction, one at the start of
every session, whether it began by startup, resume, clear, compaction or
fork — make recovery automatic rather than something the agent has to
remember to do. The second is deliberately not limited to sessions that
follow a compaction: day two of a multi-day run begins by `startup` or
`resume`, with the least surviving context and the most need for state to be
put back deterministically.

Three of the five are human-typed only. `/baton:init` is the single way
around `baton-write`'s refusal to touch the constitution, and a refusal
reachable through a command the agent can invoke on itself would not be a
refusal at all. `/baton:auto` and `/baton:continue` grant unattended work and
resume it — the human's calls, not the agent's to make for itself.
`/baton:checkpoint` and `/baton:status` stay open to the model, because
neither writes anything the run is judged against.

## Working unattended

`/baton:auto` runs a readiness review — which waves in what order, what
closing each one means quoted from the constitution, and where the agent is
unsure — and then the agent carries waves to closure with nobody watching.

Each wave is gated before it closes: `baton-gate` runs the constitution's
`verify_cmd` and scans what the wave touched for placeholder markers, and the
agent walks the exit criteria one at a time against the repository. Both
halves are filed as a verdict under `docs/baton/gates/`. A wave closed this
way reads `auto` in the gate column — the column's way of saying that nobody
but the agent that did the work has looked at it.

`/baton:continue` is the one word that restarts an unattended run on a fresh
session, deliberately not automatic: a session started to check one thing has
not agreed to an hour of unattended work, and only a human typing the command
can say otherwise.

The gate's design turns on one distinction: "the tests failed" and "the tests
could not be run" arrive in the same shape, a number on a `verify_exit=` line.
`baton-gate` deliberately does not remap `127` or the signal deaths into
something tidier — a real test runner can propagate a `127` of its own, and
guessing which case this is would be worse than reporting the number. So the
exit codes keep the two apart at every other level: `3` and `4` both mean the
gate could not reach a verdict, and they hand you different jobs. A missing
`placeholder_patterns` is `3`, because `/baton:init` always writes that field
and its absence is a statement about the constitution. A missing `verify_cmd`
is `4`, reported as empty: there is simply nothing to run.

## What appears in your repository

```
docs/baton/
  constitution.md    ratified by you; baton-write refuses this path outright
  state.md           where the run is now; capped at 60 lines, and
                      baton-write refuses to write anything longer
  journal/           decisions, append-only, never edited
  gates/             verdicts filed when a wave closes under the autopilot --
                      baton-gate's mechanical evidence, plus the agent's own
                      walk through the exit criteria, one file per attempt
```

All committed markdown — `git log -p docs/baton/state.md` is the whole
history, readable without any tool. A separate `.baton/` holds the writer
lease and a snapshot taken just before compaction; it describes the current
session rather than the run, and `/baton:init` adds it to `.gitignore`.

## How it stays honest

- **The repository is the source of truth about facts.** Observed fields —
  the commit, whether the tree is clean — are re-derived every time, never
  remembered, and repaired in place when they disagree. A claim that
  disagrees with the repository (a wave marked done that the repository
  doesn't back up) is flagged, never quietly corrected.
- **The branch is neither.** It is observed, but it does not describe the
  tree the way the others do — it answers whether this is the tree at all. So
  a disagreement between the branch `state.md` names and the branch you are
  on is not repaired and not flagged: it stops the run where it stands, with
  both branches named and nothing written, because the `state.md` that would
  record the flag is the one that cannot be established as this run's.
- **One writer.** The writer role is held under a lock for the whole
  session, not re-acquired per write.
- **No state outside the log.** Every checkpoint is a commit, so
  `git log -p docs/baton/state.md` is the full history. A checkpoint with
  nothing to say writes nothing.
- **Resume verifies before it trusts.** A grant to work without a human is not
  a grant to work from an unverified state, so the divergence checks run on
  every resume including an autopilot one. The one input resume cannot observe
  is whether a human is in the session — the session source says how the
  session arrived, not who is in it — which is why `/baton:continue` exists as
  a separate word rather than a smarter guess.

## Worth knowing before you rely on it

**There is no second party yet.** `baton-gate` gathers the mechanical
evidence and the agent walks the exit criteria, but the verdict is written by
the same agent that did the work. That is exactly what `auto` in the gate
column records, and why the column has no value meaning "a human checked
this": an independent `baton-verify` is not built, and a mark nothing reads
is not a second party looking.

A wave can still close the way it always could, with no autopilot involved:
every exit criterion checked one by one against the repository, and a human
confirms it before the wave moves to `done`. That confirmation lives in the
conversation and in the commit, not in a column — such a wave's gate stays
`—`.

## Requirements

`git`, `bash`, and the standard Unix text tools that ship with any Linux or
macOS install — `grep`, `sed`, `head`, `tr`, `sort`, `dirname`, `basename`,
`date`, `wc`. No language runtime, no package manager, no server.

## Licence

MIT — see [LICENSE](LICENSE).
