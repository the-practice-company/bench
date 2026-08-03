# baton

Keeps goal and state coherent across multi-day autonomous agent runs.

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
/plugin marketplace add artemkononov/baton
/plugin install baton@baton
/plugin install superpowers@baton
```

`baton@baton` is not a typo: the marketplace this repository ships
(`.claude-plugin/marketplace.json`) is itself named `baton`, and it lists a
plugin also named `baton` — the syntax is `<plugin-name>@<marketplace-name>`.
The same marketplace re-exports superpowers, so the one `marketplace add`
covers both installs. Start a fresh session afterwards: a plugin's hooks,
skills and commands only take effect in a session that starts after it was
installed, not the one you installed it from.

## Use

```
/baton:init          # once: decompose the umbrella spec, write the constitution
/baton:checkpoint    # before compacting context by hand
/baton:status        # where the run stands, deviations first
```

Between those, the agent works on its own. Skills fire on their own
triggers, and two hooks — one just before compaction, one at the start of
the session that follows — make recovery automatic rather than something
the agent has to remember to do.

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
```

Committed, markdown, readable without any tool.

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

There is no gate. `baton-verify` — run the verification command, scan for
placeholders, check the tree — and the `baton-gate` skill that would judge
the result against the constitution don't exist yet; that's separate, later
work, along with the verdict records under `docs/baton/gates/`. Nothing here
mechanically stops an agent from declaring a wave done that isn't.

Until the gate exists, closing a wave runs on an interim rule instead: every
exit criterion checked one by one against the repository, and a human
confirms it before the wave moves to `done`. That is prose the agent is
asked to follow, not enforcement, and it's worth saying plainly rather than
letting it surface as a surprise. The constitution's `verify_cmd` field is
reserved for the gate that will eventually read it — until then, nothing
runs it automatically.

## Requirements

`git`, `bash`, and the standard Unix text tools that ship with any Linux or
macOS install — `grep`, `sed`, `head`, `tr`, `find`, `sort`, `dirname`,
`basename`, `date`, `wc`. No language runtime, no package manager, no
server. (`python3` is used by the test suite only; it never runs as part of
the plugin itself.)

## Licence

MIT — see [LICENSE](LICENSE).
