# Cold-start runbook

## What this is testing

`baton` is a Claude Code plugin for autonomous agent runs that last for days
across repeated context compaction (the point where a long session's history
gets summarized and most of the fine detail is gone). Its central claim is
that an agent which wakes up with no memory, in a repository it has been
working in for days, can restore where the work stands, who it is meant to
be, and what to do next — in one step, from files on disk alone.

Those files live under `docs/baton/`:

- `constitution.md` — the goal, the agent's role for this run ("operating
  mode"), and the rules no wave may break ("non-negotiables"). Written once
  at the start of a run and rarely touched after.
- `state.md` — the live picture: which "waves" (units of work, defined in
  the constitution) are done, which is in progress, and exactly what to do
  next. Rewritten on every checkpoint.

`test-cold-start.sh` (in this same directory's parent) builds a fixture
repository and checks, by script, that everything a resuming agent would
need is actually present in those two files and that a wave marked "done" is
verifiable against the repository's real commit history rather than merely
claimed. That is as far as a script can go. It cannot prove an agent
actually reads and uses what's there instead of, say, re-deriving the state
from scratch or guessing — proving that takes a real agent, in a real
session, doing the real thing. A scripted stand-in for that step would turn
a green checkmark into no evidence at all, which is why this half is a
runbook for a human to run by hand, not a test file.

Run this by hand before each release.

## Setup

Build the fixture — a small repository holding two commits (a finished
wave and a partially-done one) plus `docs/baton/constitution.md` and
`docs/baton/state.md` describing that exact situation:

```bash
bash tests/fixtures/cold-start/build.sh /tmp/baton-cold-start
cd /tmp/baton-cold-start
claude
```

The fixture directory is outside this repo, so Claude Code does not yet know
`baton` is a plugin it can use there. Inside this first session, tell it
about the local marketplace and install the plugin (`<repo-root>` is the
absolute path to the root of this checkout — the directory that contains
`.claude-plugin/marketplace.json`):

```
/plugin marketplace add <repo-root>
/plugin install baton@baton
```

(`baton@baton` is not a typo — the marketplace declared in
`.claude-plugin/marketplace.json` is itself named `baton`, and it lists a
plugin also named `baton`; the syntax is `<plugin-name>@<marketplace-name>`.)

When prompted for a scope, pick "user" — that enables it for every future
`claude` session on this machine, not just this one, so you will not repeat
this step for the next release's run. Then leave this session (`/exit` or
Ctrl-D) and start a fresh one in the same directory. This matters: the
plugin's `session-start` hook — the thing that hands the agent its first
orientation — only fires when a session *starts*, and this session already
started before the plugin was installed.

```bash
claude
```

Before running the actual test, confirm the install took:

```
/plugin list --enabled
```

`baton` should be in that list. Checking this separately from the real test
below means a failed install reads as a failed install, not a false failure
of the resume behavior you actually came here to check.

## The test

Say exactly this and nothing more:

> continue

## Pass conditions

All seven must hold. Each is something you can point to in the transcript —
if you and someone else watching the same session would disagree about
whether one of these happened, that condition has failed to do its job, not
the agent.

1. **It announces the resume before doing anything else.** Near the very
   start of its reply, before any tool call, it says something equivalent to
   "restoring baton state before doing anything else." A reply that jumps
   straight into editing code, or that never mentions resuming or recovering
   state, is a fail.

2. **It reads the constitution before the state, and both before the code.**
   Its first two tool calls are reads of `docs/baton/constitution.md` and
   then `docs/baton/state.md`, in that order — not a grep or directory
   listing of `src/`. Order matters here: the constitution carries the
   constraints state.md does not repeat in full, and reading it second risks
   already having decided what to do before those constraints are in view.

3. **It verifies wave 1's "done" claim instead of accepting it.** Before
   treating wave 1 as finished, it checks it against the repository —
   running the plugin's `baton-observe` script, or a
   `git merge-base --is-ancestor` check against the commit `state.md` names
   as where wave 1 closed, or both. `state.md` *claims* wave 1 is done at a
   specific commit; the pass condition is that the agent checks that claim
   against real git history rather than reading "done" in a table and moving
   on.

4. **It states the non-negotiable unprompted.** At some point before or
   while starting the fix, it says — in its own words or as a quote — that
   the token format must not change, without being asked first to summarize
   the constitution. This is the concrete, checkable sign that the
   constraint was actually carried forward, not silently dropped in favor of
   the goal alone.

5. **It does exactly what `Next action` says.** It edits `renew()` in
   `src/session.js` so a renewed token preserves its subject. Different but
   reasonable work — refactoring `login()`, writing tests first, changing
   the token format itself — is a fail here even if it is good work, because
   it is not what `state.md` said was next.

6. **It does not ask where things stand.** One clarifying question about how
   to implement the fix (for example, where the preserved subject should
   come from) is fine. A question that reveals it does not know what was
   being worked on — "what were we working on?", "what's the current state
   of this repo?" — is a fail: recovering that answer without asking is the
   entire problem this plugin exists to solve.

7. **It leaves wave 1 alone.** No edits to `src/auth.js`, no
   re-implementing or second-guessing `login()`. Wave 1 is closed and
   already verified in condition 3; touching it again is a sign the
   verification did not actually inform what happened next.

## Recording the result

Note which of the seven failed, and what the agent did instead of the
passing behavior. A failure here points at a defect in `docs/baton/state.md`
or `docs/baton/constitution.md`'s format, the `session-start` hook, or the
`baton-resume` skill — not at the model. `test-cold-start.sh` already proved
the fixture holds everything a resuming agent needs on disk, so anything
missed here was not made findable enough, and that is fixable.
