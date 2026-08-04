---
description: Pick the run back up on a fresh session and carry on
disable-model-invocation: true
---

Resume this run.

After a compaction the `baton-resume` skill picks the run up on its own and,
if the autopilot is on, carries straight on — the grant is still live and it
is the same session. This command is for the other case: a fresh session, or
one after `/clear`, where continuing silently would mean that opening the
repository to check one thing started an hour of unattended work.

`disable-model-invocation: true`, because step 4 below carries the run on into
unattended work, and that decision is the human's to make, not the agent's to
make for itself.

Run these in order and stop at the first that says stop.

## 1. Verify the state

Use the `baton-resume` skill and follow it exactly, through the point it
writes what it found: read the constitution and `state.md`, verify them
against the repository with `baton-observe`, ancestry-check every wave marked
`done`, take the writer lease, and record repairs or raise `suspect`. Stop
wherever resume's own steps say stop — including before the lease is ever
taken, if `suspect` or `needs_human` was already set on disk. Nothing here is
skipped because the run "was fine an hour ago" — that is precisely the belief
`baton-resume` exists to check.

Do not let it run its own last step. `baton-resume` executes `Next action`
unconditionally once verification comes back clean; carrying the run on
without a grant is exactly what this command exists to gate, so treat resume
as finished once it has written what it found, and continue below instead.

## 2. Stop if the run is already stopped

If step 1 stopped — raised `suspect` itself, or found `suspect` or
`needs_human` already set and never reached the lease — this command's job is
done: report what resume reported and go no further. A pat nobody has
resolved does not stop being a pat because a human typed `continue`, and
clearing either flag is the human's decision, not this command's. Resume
released the lease itself if it ever took one, so there is nothing here to
clean up.

## 3. Check there is a grant

Read `autopilot` from the state step 1 just verified. If it is `off`, release
the lease step 1 took:

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/baton-lock" release "${CLAUDE_CODE_SESSION_ID:-$CLAUDE_SESSION_ID}"
```

Then report where the run stands, and wait. **This command does not grant
autonomy.** It uses a grant that already exists — turning the autopilot on is
`/baton:auto` and nothing else. Stopping here without releasing would leave a
lease held by a session about to do nothing with it, indistinguishable from
one abandoned mid-work.

## 4. Carry on

Confirm the lease is still the one step 1 took — nothing should have taken it
in between, but starting unattended work on that assumption unchecked is the
one mistake this step cannot recover from:

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/baton-lock" check "${CLAUDE_CODE_SESSION_ID:-$CLAUDE_SESSION_ID}"
```

Exit 0: it is still ours. Anything else: the lease is gone — stop and report
rather than starting unattended work without holding it.

Report in two or three lines where the run stopped and what comes next, then
use the `baton-autopilot` skill and continue.
