# baton

Installed. Start a fresh session if you have not already — hooks, skills and
commands only take effect in a session that begins after the install, not the
one you installed from.

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
judged against sit outside the reach of the thing being judged. `/baton:init`
is the single exception, which is why it is the one command the model cannot
invoke on itself — only you can type it.

## Day to day

```
/baton:checkpoint    # before compacting context by hand
/baton:status        # where the run stands, deviations first
```

Between those, leave it alone. Two hooks do the work you would otherwise have
to remember: one saves repository facts just before context is compacted, and
one re-injects goal, operating mode, non-negotiables and next action at the
start of every session — whether it began by startup, resume, clear,
compaction or fork.

## What appears in your repository

```
docs/baton/
  constitution.md    yours, ratified by you, never written by the agent
  state.md           where the run is now; capped at 60 lines
  journal/           decisions, append-only, never edited
```

All committed markdown — `git log -p docs/baton/state.md` is the whole
history, readable without any tool. A separate `.baton/` describes the current
session rather than the run; `/baton:init` adds it to `.gitignore`.

## Worth knowing before you rely on it

There is no gate yet. Nothing mechanically stops an agent from declaring a
wave done that isn't — closing a wave runs on prose the agent is asked to
follow (every exit criterion checked against the repository, then a human
confirms) rather than on enforcement. The constitution's `verify_cmd` is
reserved for the gate that will eventually read it; until then nothing runs
it automatically.

baton assumes [superpowers](https://github.com/obra/superpowers) is installed
alongside it for per-wave specs, plans and TDD —
`/plugin install superpowers@claude-plugins-official`. It works without it;
you will just be writing those by hand.

Needs `git`, `bash` and the usual Unix text tools. No runtime, no package
manager, no server.

MIT — see [LICENSE](LICENSE).
