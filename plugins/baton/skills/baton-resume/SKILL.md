---
name: baton-resume
description: Use when the human's first message of a session is "continue", "where were we" or "pick up where we left off", when a session starts in a repository containing docs/baton/, or right after a context compaction or clear - restores the run state and verifies it against the repository before any work continues, however complete the summary you woke up with reads
---

# baton Resume

Recover the run. Nothing else happens until this finishes.

**Announce at start:** "Restoring baton state before doing anything else."

This skill writes — repairing observed fields, and raising a divergence it
finds — both through `baton-write` under the writer lease. It is idempotent:
run it again after nothing has changed and `baton-write` has nothing to
commit, like `baton-checkpoint`'s idle case. If you are unsure whether you
already resumed, resume again.

## The Process

```dot
digraph resume {
    "docs/baton/state.md exists?" [shape=diamond];
    "Not a baton run - say so, suggest /baton:init, stop" [shape=doublecircle];
    "Read constitution.md and state.md" [shape=box];
    "baton-observe; check merge-base ancestry" [shape=box];
    "Read .baton/precompact-facts if present" [shape=box];
    "suspect or needs_human already on disk?" [shape=diamond];
    "Resolve that first - report to the human" [shape=doublecircle];
    "Acquire the writer lease" [shape=box];
    "Write what you found - repairs always, suspect if diverged" [shape=box];
    "Divergence found by this resume?" [shape=diamond];
    "Release the lease, report it - stop" [shape=doublecircle];
    "Execute Next action in the restored operating mode" [shape=doublecircle];

    "docs/baton/state.md exists?" -> "Not a baton run - say so, suggest /baton:init, stop" [label="no"];
    "docs/baton/state.md exists?" -> "Read constitution.md and state.md" [label="yes"];
    "Read constitution.md and state.md" -> "baton-observe; check merge-base ancestry";
    "baton-observe; check merge-base ancestry" -> "Read .baton/precompact-facts if present";
    "Read .baton/precompact-facts if present" -> "suspect or needs_human already on disk?";
    "suspect or needs_human already on disk?" -> "Resolve that first - report to the human" [label="yes"];
    "suspect or needs_human already on disk?" -> "Acquire the writer lease" [label="no"];
    "Acquire the writer lease" -> "Write what you found - repairs always, suspect if diverged";
    "Write what you found - repairs always, suspect if diverged" -> "Divergence found by this resume?";
    "Divergence found by this resume?" -> "Release the lease, report it - stop" [label="yes"];
    "Divergence found by this resume?" -> "Execute Next action in the restored operating mode" [label="no"];
}
```

## Steps

**0. Is this a baton run at all?** If `docs/baton/state.md` does not exist,
this repository is not a baton run: say so, suggest `/baton:init`, stop.
Create nothing — not the directory, not a state file, not a constitution. This
skill fires on every session start and on the word "continue", in every
repository on the machine, so a missing state file is the ordinary case, not a
fault to report at length.

**1. Read both files.** First pin the working directory to the repository
root:

```bash
cd "$(git rev-parse --show-toplevel)"
```

Every path here — `docs/baton/state.md`, `.baton/precompact-facts` — is
relative to that root; from a monorepo subdirectory they resolve against
`packages/foo/`, find nothing, and this resume concludes there is no run.
Every script and both hooks re-resolve for the same reason:
`hooks/pre-compact` records a lease that landed in a subdirectory and left two
sessions each believing it held it alone.

Then read `docs/baton/constitution.md` first, `docs/baton/state.md` second.
Three things from it, none optional: the goal, your operating mode, the
non-negotiables. Without the constraints, a run correctly serves the current
request while violating the original brief. The operating mode is who you are
for the rest of the session, and step 7 means it literally: orchestrator means
you delegate rather than implement here.

Check `status` in its frontmatter before acting on any of it: anything other
than `ratified` means the human has not finished writing it — stop and ask for
ratification rather than guessing at intent.

A `REPLACE-WITH` placeholder means the same — but match a *frontmatter field
whose value begins with the token*, not the string anywhere in the file. The
template ships `REPLACE-WITH` inside a frontmatter *comment* explaining the
ratification rule, which survives untouched into a perfectly ratified
constitution; a substring match then halts every resume of that run,
permanently, over a line of documentation.

**2. Verify rather than trust.**

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/baton-observe"
```

Three frontmatter fields in `state.md` describe the repository rather than
claiming anything about the work: `observed_sha`, `observed_branch`,
`tree_clean`. Repair all three silently where they disagree with what came
back — stale reading, and the repository is right. Note the repairs; you do
not hold the lease yet, so nothing is written until step 6.

Compare `observed_sha` against this run's `work_sha`, not its `sha`. `sha` is
raw `HEAD` and moves on every checkpoint commit, so it could never equal a
baseline the checkpoint before it recorded; `work_sha` is the last commit
outside `docs/baton/`, which checkpoint commits never touch, so it holds
across checkpoints and moves when work lands. Empty `work_sha` is not a
failure — nothing outside `docs/baton/` is reachable from `HEAD` yet. Then
compare `observed_branch`.

`tree_clean: false` matters most on a resume: uncommitted work in the tree,
most often from a session that died mid-edit — the one you are picking up.
Find out what it is before touching anything:

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/baton-observe" --changed-since "<observed_sha>"
```

That lists every path changed since the last checkpoint's baseline, untracked
included. Reconcile against `In flight`: the same work means you have found
the interrupted edit and `In flight` says what it was for. If `In flight` says
`nothing` and the list is not empty, say so — that is work nobody wrote down,
and `Next action` was written for a clean tree; running it over a tree of
unknown provenance tangles the two together.

A wave marked `done` whose `closed_at_sha` is not an ancestor of `HEAD` is a
different finding: `closed_at_sha` is claimed, so it is a divergence, never
repaired silently. Check every wave marked `done`, not only the most recent —
a run on day three has several, and the older claim is likelier to have been
rebased out from under. Skip any whose `closed_at_sha` is the template's `—`
placeholder: it means "not closed here", and `merge-base` answers it with exit
128, which reads as history moving when nothing did.

Capture the exit code and the message together — the table below keys one row
on what the command printed:

```bash
rc=0
out="$(git merge-base --is-ancestor <closed_at_sha> HEAD 2>&1)" || rc=$?
printf 'exit=%s message=%s\n' "$rc" "$out"
```

| Exit | Meaning |
|---|---|
| 0 | `<closed_at_sha>` is an ancestor of `HEAD`. The claim holds. |
| 1 | It is not an ancestor. The claim diverged from the repository. |
| 128, message starts `fatal:` | `<closed_at_sha>` is not a valid commit at all — a placeholder never filled in, or history rewritten out from under it. |

Any non-zero exit, 1 or 128 alike, is the same finding: the claimed field
diverged and the run stops for it — 128 is not a crash to report and move
past. But record which code, and which wave, in step 6's `Suspect` line: 1
says the commit exists and history moved past it, 128 says there is no such
commit at all.

**3. Check what happened after the last checkpoint.** If
`.baton/precompact-facts` exists, the PreCompact hook recorded the repository
as it stood at compaction time.

If it carries `observe_failed=true`, stop reading there: the hook writes that
line, and deliberately no `work_sha` at all, when `baton-observe` failed at
compaction time. An absent field reads back as an empty string, unequal to
every real `observed_sha`, so comparing anyway manufactures a divergence on a
healthy run — the one case the hook went to trouble to prevent. Say no
staleness check was possible this resume, and go to step 4.

Otherwise check direction first. If the precompact `work_sha` is an ancestor
of *both* the current `work_sha` and `observed_sha` — the `merge-base` call
from step 2 — the file is left over from an earlier compaction already
checkpointed past, and establishes nothing. `.baton/` is gitignored and
nothing prunes it, so a spent file is the normal case here; treating one as a
mismatch raises a divergence on a healthy run at every resume to the end of
the run.

Otherwise compare the file's `work_sha` — not its `sha` — against the
`observed_sha` you read *from disk* in step 1, before step 2's repair: step 2
sets that field from the same `baton-observe` output, so the repaired value
would be compared against itself and never fire. Three outcomes:

- **Equal.** The checkpoint was current when the compaction hit. Nothing
  follows.
- **`observed_sha` is an ancestor of the precompact `work_sha`.** Work landed
  after the last checkpoint and nothing captured it. The sha repair is
  routine, step 2 covers it — but `Next action`, `In flight` and the wave
  statuses were written alongside the old value and describe a repository that
  has since moved. They are claimed fields, nobody has corrected them, and
  *that* stops the run: not the sha, the narrative written against it.
- **Neither is an ancestor of the other, or `merge-base` exits 128.** History
  moved — a rebase, a force-push, a branch that is not the branch it was. A
  genuine divergence, and the same stop.

Once the file has been acted on — step 6's write has landed, or you
established above that it was spent — delete it:

```bash
rm -f .baton/precompact-facts
```

The next compaction writes a fresh one. Left behind, it makes the next resume
re-litigate a question this one already answered, and the answer only gets
more wrong as the run goes on.

**4. Handle the flags that were already on disk.** Steps 0 to 3 are all reads;
this is the first step that decides anything. `suspect: true` in the
`state.md` from step 1 means a claim already diverged, caught by an earlier
session's checkpoint or resume; `needs_human: true` means the run is already
stopped. Either one, found already set, is the whole job until resolved:
report it and stop rather than working around it. What steps 2 and 3 just
found themselves is different — that is step 6, once you hold the lease.

Resolution is not yours alone. `suspect` marks a claimed field that disagrees
with the repository, and which of the two is wrong is a question about intent
— was the wave actually finished, or was the commit lost? — so it takes the
human's decision, not your judgement. Put the specifics in front of them:
which field, what it claims, what the repository shows, what the `Suspect`
line says about how it was caught. Then record what they decide: a journal
entry with the decision and why, then a `baton-write` of `state.md` with the
claimed field set to what they said and `suspect: false`. That write is the
only thing that clears the flag: it does not expire, and no checkpoint clears
it for you. Clearing it without that conversation is silently correcting a
claim, the exact thing the flag exists to prevent.

**5. Take the writer lease.**

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/baton-lock" acquire "${CLAUDE_CODE_SESSION_ID:-$CLAUDE_SESSION_ID}"
```

Both names, in that order, deliberately: `CLAUDE_CODE_SESSION_ID` is what
Claude Code actually exports, and neither name is a documented contract, so
the fallback keeps this working if the exported name changes again.
`baton-lock` refuses an empty id rather than granting a shared lease, so exit
64 — the session id must not be empty — means the environment gave neither
name; report that and stop rather than inventing an id.

Exit 3 means another session holds an unexpired lease — do not write state;
say so, and stop. If you have good reason to believe that session is gone,
take it over instead; that always succeeds:

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/baton-lock" takeover "${CLAUDE_CODE_SESSION_ID:-$CLAUDE_SESSION_ID}"
```

Either way, whenever the script prints `takeover=<previous session>` — which
`acquire` also prints when it displaces an expired lease — record a journal
entry of type `takeover`, so an overlap of two sessions cannot pass unnoticed.
Its shape is not here: read `baton-checkpoint`'s step 5, "Journal anything
that crossed the threshold", which you will not have loaded this session. What
you need from it: `${CLAUDE_PLUGIN_ROOT}/scripts/baton-journal <slug>` hands
back the id and the path — never invent either — the frontmatter is the
standard envelope with `type: takeover`, the required sections are
`## Who was displaced` and `## Why it was believed safe`, and the entry
reaches disk through `baton-write` at the path `baton-journal` printed. Name
the displaced session id the script actually printed, not "a previous
session".

**6. Write what you found.** This step always runs: you hold the lease now,
and everything steps 2 and 3 turned up exists only in your head.

**Always:** the observed-field repairs from step 2 — `observed_sha` set from
`baton-observe`'s `work_sha`, `observed_branch` and `tree_clean` set from what
it reported.

**And, if steps 2 or 3 found a divergence** that step 4's on-disk flags did
not already cover — a `closed_at_sha` no longer an ancestor of `HEAD`, or a
precompact `work_sha` whose narrative fields describe an older repository:

- set `suspect: true`;
- describe the specifics in the `Suspect` line: which check failed, what each
  side said, which wave, and, for the ancestry check, whether it exited 1 or
  128;
- report it, and stop. A suspect run does not continue to `Next action`;
  resolving the divergence is the next thing that happens here, and step 4
  says what resolving it means.

Both cases go through one command:

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/baton-write" \
    -m "baton: resume verified state" docs/baton/state.md < .baton/resume-state.md
```

Pipe in the *whole file* — frontmatter, Goal, Operating mode, Non-negotiables,
the Waves table, Now, Pointers — everything you read in step 1, byte for byte,
with only the fields above changed on top. Not a diff, not just the fields
this resume touched. `baton-write` replaces the file with its stdin: it does
not merge and cannot know what you meant to keep. Two frontmatter lines piped
in leave a two-line `state.md` with the Waves table gone — exit 0, committed,
`git status --porcelain docs/baton` empty afterwards, and nothing downstream
will tell you it happened.

`state.md` is capped at 60 lines and `baton-write` refuses anything longer; a
`Suspect` writeup with real detail is what usually pushes it over. Put the
detail in a journal entry and leave a pointer ("see DEC-0008") in the line.
For any other non-zero exit, `baton-checkpoint`'s "If the write fails" table
says which situation you are in and what it needs; do not retry blindly.

If this write raised `suspect`, release the lease once it has succeeded:

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/baton-lock" release "${CLAUDE_CODE_SESSION_ID:-$CLAUDE_SESSION_ID}"
```

You are stopping, and the lease lives six hours. Held, the human's next
session finds a live lease and can only get past it with `takeover` —
manufacturing a journal entry for an overlap that never happened, noise in the
one log that has to stay signal. On the clean path, keep the lease: you are
about to work under it.

**7. Execute `Next action`, in the operating mode you restored in step 1.**
Reached only when step 6 found nothing that stops the run.

Exactly what it says — but that governs the work, not who does it. If step 1's
operating mode is orchestrator, delegating `Next action` to a subagent or a
workflow *is* executing it, and implementing it here, in the primary session,
is not. The mode came from the constitution and outranks the convenience of
doing the thing yourself.

If `Next action` is too vague to act on, that is a checkpoint-quality failure
— reconstruct from the repository and the wave's plan rather than guessing,
and write a sharper one at the next checkpoint.

## What you are working under from here

The procedure is over; the run is not. The rest of the session is governed by
the **baton** skill — read it now unless it is already in context. It is the
model these procedures implement: which fields are observed and which are
claimed, and why that decides what you may repair; the four criteria that make
a decision worth journaling; what to do when new input arrives mid-run.

**baton-checkpoint** is the other half. Checkpoint before the next compaction,
at the end of a stretch of work, and after closing anything meaningful — it
also carries the 60-line cap on `state.md`, the journal entry formats, and the
release of the lease when the session ends. A run that resumes cleanly and
then never checkpoints has only moved the loss to the next compaction.

## Before implementing anything

Check whether it already exists. Grep for the behaviour, not only for the name
you expect it to have; read the wave's plan and the closed waves' specs. On
fresh context you have no memory of what was built, and concluding "not
implemented" from one failed search is the documented way an agent overwrites
working code.

## Red Flags

| Thought | Reality |
|---|---|
| "I know roughly where we were" | You do not. That is what the compaction took. |
| "The summary I woke up with reads complete" | Summaries always read complete. That is the premise this whole skill is built on. |
| "state.md says done, good enough" | Claims are checked against the repository, not accepted. |
| "suspect is set but I can work around it" | Resolving it is the work, and only the human can resolve it. |
| "The lease is held, I'll write anyway" | Two writers is exactly the failure the lease exists to prevent. |
| "I'll pipe the fields I changed into `baton-write`" | It replaces the whole file with your stdin. Anything you did not carry over is deleted, the commit succeeds, and the tree looks clean. |
| "The tree is dirty, that's just leftovers" | It is uncommitted work from the session you are picking up. Find out what it is before you build on it. |
| "I'll re-read the constitution later if needed" | Later is after you have already drifted. |
| "This function is missing, I'll add it" | Search first, by behaviour. |
| "The lease expired, so I'll just take it" | Expired means unobserved, not abandoned. Take it deliberately with `takeover` and journal it. |
