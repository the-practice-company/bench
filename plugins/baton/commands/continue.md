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

Do not let it run past that point. Resume now has its own gate right after —
whether to carry the run onward — but it decides that by reading the session
source this conversation started from: an automatic pickup, a compaction or a
plain resume, continues; a fresh start, a `/clear`, or a fork waits for a
human. It has no way to see that a human is sitting here having just typed
`/baton:continue`, which is exactly the fact that should override a "wait" —
so treat resume as finished once it has written what it found, and do the
rest — reading the grant, deciding whether to carry on — here instead, where
that fact is available.

## 2. Stop if resume already stopped

`baton-resume` stops for more than one reason — not a baton run, an
unratified constitution, `suspect` or `needs_human` already on disk, another
session's live lease, a divergence this resume found itself — and the action
here is the same regardless of which one fired: report what resume reported
and go no further. A pat nobody has resolved does not stop being a pat
because a human typed `continue`, and resolving it, whichever kind it is, is
the human's decision, not this command's.

Resume releases the lease on every one of those paths except one: if its own
final write fails, its error handling — `baton-checkpoint`'s "If the write
fails" table — reports and stops without releasing, because most of those
failures need a human to look at the repository before anything writes under
that lease again. If you land here holding a lease you did not expect to be
holding, do not release it and do not write through it: report the write
failure by name — the exit code and the message — and stop. Whether that
lease is still good is a human's call, not a guess this command makes for
them.

## 3. Check there is a grant, and that it is safe to act on

Read `autopilot` from the state step 1 just verified, normalized the same way
the session-start hook already does before comparing it — trim whitespace,
strip a trailing `\r`, strip one layer of matching quotes, fold case —
because `state.md` is written by an agent, not validated input, and the
unsafe direction here is a false positive: carrying an unattended run forward
on a value that only looks like a grant is worse than stopping on one that is
not.

**Absent or unrecognized reads as `off`.** A run initialised before this field
existed has no `autopilot` key at all; treat that the same as `off` rather
than as a value to interpret — the session-start hook makes the same choice,
for the same reason.

**A grant with no journal entry behind it is not a grant.** If `autopilot` is
not `off` but `autopilot_grant` is `—` or otherwise names no entry, that is a
claim pointing at nothing. Refuse to act on it the same as `off`, but say so
plainly rather than folding it into the ordinary case: the two fields
disagreeing is itself something the human needs to know, not only that the
run happens to be unattended or not right now.

**The tree has to be clean too.** `baton-autopilot`'s dirty-tree handling
reasons that any dirt it finds mid-run is the run's own doing, because
`/baton:auto` refuses to hand a run over with a dirty tree in the first
place. That premise does not hold here: `baton-resume`'s own dirty-tree
handling, back in step 1, reports what it finds and continues regardless — it
does not stop for it. Check it here, the same way `/baton:auto` does:

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/baton-observe"
```

`tree_clean` must be `true`; `dirty_count` names how much is outstanding if it
is not.

If any of the three is not satisfied — no grant, an ungrounded one, or a
dirty tree — release the lease step 1 took:

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

| Exit | Meaning | What to do |
|---|---|---|
| 0 | Still ours. | Continue. |
| 3 | Another session holds it live — the loudest of the three, not the lease being gone: someone is actively writing right now. | Stop and report. Do not take over a live session from a command nobody is watching run. |
| 4 | It expired — stale long enough that another session could have taken it over, though none did. | Stop and report; re-run `/baton:continue` rather than silently re-acquiring here, which would carry the run on without the fresh verification step 1 exists to require. |
| 5 | No lease file at all. | Stop and report the same way. |

Report in two or three lines where the run stopped and what comes next, then
use the `baton-autopilot` skill and continue.
