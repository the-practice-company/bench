# bench

A Claude Code plugin marketplace for long-running agent work.

It ships one plugin today:

- **[baton](plugins/baton)** — keeps goal and state coherent across
  multi-day autonomous agent runs.

The rest of this file is about baton, since it is currently the only thing
here. When a second plugin arrives, this page becomes an index and baton's
own detail moves to `plugins/baton/README.md`.

## baton

An agent working one task for days will have its context compacted many
times over. Each time, it loses the thread: what it already finished, what
it was doing next, and what it was told never to do. baton makes that
recoverable in one step — and makes the recovery verifiable against the
repository, not trusted from a summary the model wrote about itself.

State lives in `docs/baton/`, committed to git. Git history is the event
log. A decision journal records why choices were made, not just what they
were. Checkpointing persists state before context is lost; resuming reads
it back and checks it against the repository rather than taking the file's
word for it.

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

The syntax is `<plugin-name>@<marketplace-name>`: `baton` is the plugin,
`bench` is the marketplace this repository ships in
`.claude-plugin/marketplace.json`.

To work against a local checkout instead, point the first command at the
directory rather than the repository:

```
/plugin marketplace add /path/to/this/checkout
```

superpowers comes from `claude-plugins-official`, the marketplace Claude Code
already knows about, rather than from a copy re-exported here. Anthropic's
entry pins the exact commit it installs. A re-export in this repository would
either have to drop that pin — handing whoever controls that repository's
default branch a say in what lands on your machine at install time and at
every version bump — or carry a second pin that someone has to keep in step
with the first by hand. Neither is worth owning to save a word.

Start a fresh session afterwards: a plugin's hooks, skills and commands only
take effect in a session that starts after it was installed, not the one you
installed it from.

## Use

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
remember to do. The second one is deliberately not limited to sessions that
follow a compaction: day two of a multi-day run begins by `startup` or
`resume`, with the least surviving context and the most need for state to be
put back deterministically.

A human can go further and hand the run over entirely. `/baton:auto` runs a
readiness review, then the agent carries waves to closure with nobody
watching — gating each one against the constitution's `verify_cmd` and a
placeholder scan before filing a verdict. `/baton:continue` is the one word
that restarts that on a fresh session, deliberately not automatic: a session
started to check one thing has not agreed to an hour of unattended work, and
only a human typing the command can say otherwise.

## What lands in your repository

```
docs/baton/
  constitution.md    ratified by you; baton-write -- the tool every
                      checkpoint and resume uses to write durably -- refuses
                      this path outright. /baton:init places the initial
                      file directly, with plain git, once, before
                      ratification, which is the one way around that
  state.md           where the run is now; capped at 60 lines, and
                      baton-write refuses to write anything longer
  journal/           decisions, append-only, never edited
  gates/             verdicts filed when a wave closes under the autopilot --
                      baton-gate's mechanical evidence, plus the agent's own
                      walk through the exit criteria, one file per attempt
```

Committed, markdown, readable without any tool.

That one way around the refusal is closed to the agent: `/baton:init` is
declared user-only, so it runs when you type it and cannot be called by the
model mid-run. A refusal reachable through a command the agent can invoke on
itself would not be a refusal at all. `/baton:auto` and `/baton:continue` are
user-only for the same reason: granting unattended work, and resuming it on a
fresh session, are the human's calls to make, not the agent's to make for
itself. `/baton:checkpoint` and `/baton:status` are left open to the model,
because neither writes anything the run is judged against.

A separate `.baton/` directory holds the writer lease and a snapshot taken
just before compaction. `/baton:init` adds it to `.gitignore`: it describes
the current session, not the run, and has no business in history.

## How it stays honest

- **The repository is the source of truth about facts.** Observed fields —
  the commit, the branch, whether the tree is clean — are re-derived every
  time, never remembered. A claim that disagrees with the repository (a
  wave marked done that the repository doesn't back up) is flagged, never
  quietly corrected.
- **One writer.** The writer role is held under a lock for the whole
  session, not re-acquired per write.
- **No state outside the log.** Every checkpoint is a commit, so
  `git log -p docs/baton/state.md` is the full history. A checkpoint with
  nothing to say writes nothing.

## What's not built yet

- **`baton-verify`** — an independent gate. `baton-gate` now gathers the
  mechanical evidence (the constitution's `verify_cmd`, a placeholder scan
  over what the wave touched) and the agent walks the exit criteria and files
  a verdict under `docs/baton/gates/`. What is still missing is the second
  party: today the verdict is written by the same agent that did the work,
  which is why a wave closed unattended reads `auto` in the gate column and
  not `pass`. Turning `auto` into `pass` is a human's job.

A wave can still close the way it always could, with no autopilot involved:
every exit criterion checked one by one against the repository, and a human
confirms it before the wave moves to `done`. `/baton:auto` is what adds the
second path — `baton-gate`'s evidence plus the agent's own walk through the
criteria, filed as a verdict rather than confirmed on the spot — for the
stretches where no human is there to do the confirming.

## Requirements

`git`, `bash`, and the standard Unix text tools that ship with any Linux or
macOS install — `grep`, `sed`, `head`, `tr`, `sort`, `dirname`,
`basename`, `date`, `wc`. No language runtime, no package manager, no
server. (`python3` is used by the test suite only; it never runs as part of
the plugin itself.)

## Licence

MIT — see [LICENSE](LICENSE).
