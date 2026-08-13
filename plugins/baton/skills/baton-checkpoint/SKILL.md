---
name: baton-checkpoint
description: Use when about to compact or clear context, when ending a stretch of work, after closing a meaningful chunk, or whenever asked to make sure nothing is lost - persists run state so the next session can pick it up
---

# baton Checkpoint

Persist the run so a session with no memory of this one can continue it.

**Announce at start:** "Checkpointing the run — writing it down so it survives without this context."

**Prerequisite:** `docs/baton/constitution.md`'s `status` is `ratified` with no
`REPLACE-WITH` token left. You also hold the writer lease:

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/baton-lock" check "${CLAUDE_CODE_SESSION_ID:-$CLAUDE_SESSION_ID}"
```

Read the exit code, not just whether it was zero:

| Exit | Meaning | What to do |
|---|---|---|
| 0 | The lease is already yours. | Continue. |
| 3 | Another session holds a live lease. | Stop, report it, write nothing — see `baton-resume`. |
| 4 | The lease expired. | Continue to `acquire`; it takes over an expired lease itself. |
| 5 | There is no lease at all. | Continue to `acquire`; it takes a free lease itself. |

Then `acquire`, before writing anything:

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/baton-lock" acquire "${CLAUDE_CODE_SESSION_ID:-$CLAUDE_SESSION_ID}"
```

Exit 64, session id must not be empty, means the environment gave neither name —
report it and stop; do not invent an id. If `acquire` prints
`takeover=<previous session>` — it does when it displaces the expired lease of
exit 4 — journal it as a `takeover` entry (step 5). For the holder, `acquire` is
the heartbeat, not a second acquisition: it pushes the expiry out. Checkpoint
regularly and the lease never lapses.

## Steps

**1. Read the current state, whole.** Read all of `docs/baton/state.md` first.
`baton-write` replaces the entire file with whatever you pipe into it, so every
section you did not deliberately change — Goal, Operating mode, Non-negotiables,
Waves table, Pointers — has to come through into your draft byte for byte. The
steps below name only the fields they update.

**2. Snapshot the repository.**

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/baton-observe"
```

**3. Reconcile.** Compare what `state.md` claims against what came back.
Observed fields — `observed_sha`, `tree_clean`, `writer`, `updated_at` — you
overwrite without ceremony. Take `observed_sha` from `baton-observe`'s
`work_sha`, not its `sha`: `sha` is raw `HEAD`, which this checkpoint is about
to move. `work_sha` is the last commit touching anything outside `docs/baton/` —
which a checkpoint commit never does.

`observed_branch` is not on that list: a disagreement is **a stop, not a
repair**. Name the branch `state.md` expects and the branch you are on, and stop
without writing — not even a flag.

`writer` and `updated_at` are both stale: nothing has written either since
`/baton:init`. Bump `updated_at` freely — `baton-write` strips that line before
deciding whether a checkpoint is idle.

```bash
printf 'writer: %s\n' "${CLAUDE_CODE_SESSION_ID:-$CLAUDE_SESSION_ID}"
printf 'updated_at: %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
```

A claimed field that diverged — a wave marked `done` whose work is not in the
repository — you never overwrite: set `suspect: true`, put the specifics in the
`Suspect` line, and say so in your reply. For every `done` row, run the check
`baton-resume` runs — `baton-observe` cannot make this call for you:

```bash
git merge-base --is-ancestor <closed_at_sha> HEAD
```

Any non-zero exit — 1 and 128 alike — is a divergence; the codes are tabulated
in `baton-resume`'s step 2. A `done` row whose `closed_at_sha` is still `—`
fails as exit 128: nothing recorded the sha, so the claim cannot be checked.

**4. Write the narrative fields.**

- `Next action` — one sentence, deterministic enough that a session with no
  memory of this one executes it without asking. "Continue the API work" is a
  failure. "Run `npm test -- auth.spec.ts` and fix the two failing assertions in
  `src/auth/session.ts`" is not.
- `In flight` — what was interrupted mid-way, or `nothing`. One exception: an
  autopilot attempt counter (`wave 2: attempt 2 of 3`) stays, even when nothing
  is mid-edit and `nothing` is otherwise the honest answer — it is the only copy
  of a ceiling. See `baton-autopilot`.
- `Open questions` — or `none`.

Write these from the repository, not from your recollection of the last hour:

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/baton-observe" --changed-since <observed_sha>
```

takes the `observed_sha` you read in step 1 — the previous checkpoint's
baseline, not the one you just overwrote — and lists every file changed since,
untracked ones included.

`state.md` is capped at 60 lines. Detail that does not fit — a long "In flight",
a Suspect writeup worth keeping — goes to a journal entry, and `state.md` keeps
only a pointer to it (e.g. "see DEC-0008"). An autopilot attempt counter is the
one thing that never moves out: send the surrounding narrative to the entry and
keep `wave 2: attempt 2 of 3` on the line.

**5. Journal anything that crossed the threshold.** Write an entry only if at
least one holds:

- the decision is hard to reverse;
- it touches something outside the declared scope of the current wave;
- it reinterprets a rule from the constitution;
- the choice was between real alternatives and the loser was plausible.

Entries are immutable: superseding one means a new entry, never an edit.
Allocate the id, then write:

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/baton-journal" chose-postgres-over-sqlite
# id=DEC-0008
# path=docs/baton/journal/0008-chose-postgres-over-sqlite.md
```

Entry format:

```markdown
---
id: DEC-0008
type: decision
status: accepted
decided_by: agent
wave: 2
timestamp: 2026-08-03T14:20:00Z
sha: a1b2c3d
reversibility: two-way
blast_radius: low
needs_review: false
---
## Context
## Options
## Decision
## Why
## Invalidated if
```

Four other entry types are required elsewhere in these skills — same envelope,
same `baton-journal` allocation, different `type` and sections:

| Type | Written when | Envelope | Sections |
|---|---|---|---|
| `takeover` | a `baton-lock` call prints `takeover=<previous session>`: `baton-resume` displacing another session's lease, or the `acquire` above taking over an expired one | `type: takeover` | `## Who was displaced`, `## Why it was believed safe` |
| `incoming` | new input arrives mid-run (see the `baton` skill's "New input mid-run") | `type: incoming`, `needs_review: true` | `## What arrived`, `## From whom`, `## What it affects` |
| `autopilot` | `/baton:auto` grants the run — written by it, not by you, and named by `state.md`'s `autopilot_grant` | `type: autopilot`, plus **`base:` in the frontmatter** — the resolved sha of `--since <ref>`, or `—` when none was given, and nowhere else | `## Scope`, `## The readiness review`, `## The human's corrections` |
| `blocked` | a wave cannot close and moves to `blocked` (see `baton-autopilot`'s "The pat") | `type: blocked`, and no `needs_human` | `## What stopped`, `## The evidence`, `## What was tried`, `## Why each attempt did not move it` |

Two riders on `blocked`. Its `## Why each attempt did not move it` says why each
attempt failed, not only that it was made. This entry carries no `needs_human`:
that is a granted field in `state.md`, not part of any entry's envelope, and
under the autopilot a parked wave deliberately does **not** raise it.
`baton-autopilot`'s "The pat" says when it is raised.

Pipe it through `baton-write` so it lands atomically and gets committed:

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/baton-write" \
    -m "baton: DEC-0008 chose postgres over sqlite" \
    docs/baton/journal/0008-chose-postgres-over-sqlite.md < .baton/journal-entry.md
```

`.baton/` is the scratch directory for this write and the state draft below, not
`/tmp`; the lease you took at the top created it. Do not add `$$` to the
filename to make it unique: the tool that writes the draft and the shell that
reads it are different processes, and would not agree on the name.

**6. Check the draft against what is committed.** Write the draft to
`.baton/checkpoint-state.md` — step 7 pipes it from there anyway — and diff it
against the version in the log before anything is written:

```bash
diff <(git show HEAD:docs/baton/state.md) .baton/checkpoint-state.md
```

Every line on the `<` side is a line this checkpoint deletes. Take them one at a
time and name the step that decided each: an observed field from step 3, a `Now`
line from step 4, a wave row you closed. A difference you cannot name is a
section that fell out of a draft rebuilt from memory, and it aborts the
checkpoint: re-read the committed file, apply your changes to *that*, diff again.
Nothing downstream catches it.

**7. Write the state.** What you pipe into `baton-write` is the whole file you
just diffed, unchanged since you diffed it.

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/baton-write" \
    -m "baton: checkpoint at wave 2" docs/baton/state.md < .baton/checkpoint-state.md
```

If nothing of substance changed, the script writes nothing and exits 0. That is
correct, not a failure.

**8. Release the lease only if the session is over.** Mid-stretch, keep it.
"Over" has to be something you can point at, not a feeling: the human said they
are stopping, asked you to wrap up, or took the run back; or the last wave is
`done` with nothing left to pick up. A compaction is none of those.
Verify before you release, never after: a verification that fails once the lease
is gone is one you cannot act on. Run both checks below, then:

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/baton-lock" release "${CLAUDE_CODE_SESSION_ID:-$CLAUDE_SESSION_ID}"
```

## Closing a wave

There are two ways a wave closes, and which one applies is decided by the
`autopilot` field in `state.md`, not by whether a human happens to be answering
right now.

**While `autopilot` reads `off`** — the default — you are the only mechanism. A
wave moves to `done` only when every exit criterion the constitution lists for
it has been checked, one by one, against the repository rather than your
impression of the work, with the check recorded, **and** the human has confirmed
it. Either half missing means it stays where it is. Green tests are not a
confirmation; they are what makes asking for one worth the human's time.

**While `autopilot` names a scope**, a human handed the run over and is not here
to confirm anything. The confirmation is replaced — not waived — by
`baton-gate`'s evidence plus a verdict file under `docs/baton/gates/` that
records your walk through the criteria; `baton-autopilot` has the procedure. Do
not read this path as "close it yourself when nobody answers": it applies while
the flag is set and at no other time, and the flag is set by a human typing
`/baton:auto`.

Closing the wave is then four edits to this checkpoint's draft, and it is not
closed until all four are in:

- `status` → `done` in the Waves table;
- `closed_at_sha` → this run's `work_sha` from `baton-observe`, not its `sha`,
  for the reason step 3 gives;
- **Current wave** → whatever is now in progress;
- the `gate` column → `pass` or `auto`, per the table below.

The `gate` column takes one of three values:

| Value | What it says |
|---|---|
| `—` | Nothing produced a verdict. |
| `auto` | Closed under the autopilot: `baton-gate`'s evidence was green and you walked the criteria. The verdict is filed in `docs/baton/gates/`. |
| `pass` | A human confirmed it, or a future `baton-verify` did. |

Closing under the autopilot writes `auto`, not `pass`: `pass` claims a human saw
this, and turning `auto` into `pass` is the morning's work. The row above the one
you are filling in carries the previous run's value, not an instruction.

`closed_at_sha` is the one claim here checked mechanically: `baton-resume` and
step 3 above both run `git merge-base --is-ancestor` against it for every wave
marked `done`. Left at `—`, both checks can only read `done` as a divergence.

## If the write fails

Do not retry blindly; the response differs by exit code.

| Exit | Meaning | What to do |
|---|---|---|
| 1 | Not a git repository. Nothing was written. | Not something to work around: the lease, the log and every check here are git. Report it and stop. |
| 3 | Refused before touching anything — see the causes below. | Nothing was written, so nothing is lost. Resolve the named cause and checkpoint again. |
| 5 | Two causes, told apart by the message. "commit failed; the tree was restored" — a hook or signing failure rejected the mutation and the rollback ran, so the tree is as it was found. "commit landed but does not contain what this run wrote" — the commit *succeeded* with another writer's content in it; nothing was rolled back, the commit stands. | First: read the message, fix the cause, checkpoint again. Second: do not retry over it — the lease discipline failed upstream, two writers at once; report that rather than silently re-checkpointing. |
| 7, "rollback could not restore" | The commit failed **and** the rollback ran but left the tree dirty. State is sitting outside the log. | Stop. Only a human can resolve it. Set `needs_human: true` if you can still write, and say so plainly. |
| 7, "could not be verified" | The commit failed, the rollback ran, and `git status` itself failed, so whether the tree was restored is unknown. | Stop, the same way — but hand over the difference. "The tree is dirty" a human can look at and fix; "the repository could not answer what state it is in" is what they need to hear first. |
| 64 | Malformed invocation: no path, more than one path, or `-m` with nothing after it. Nothing was written. | Fix the call. The two forms this skill uses are the blocks in steps 5 and 7. |

| Exit 3's message says | What to do |
|---|---|
| an unresolved merge, or an unresolved rebase, is in progress | A partial commit of one path is impossible mid-merge or mid-rebase. Finish or abort it, then checkpoint again. |
| the path is excluded by `.gitignore` | The file could never be committed, so writing it would leave state `git status` never shows. Fix the ignore rule or the path. |
| empty-or-whitespace-only content over existing committed state | Your draft was empty or nothing but whitespace — a single newline counts, and that is what a failed command substitution or an empty heredoc usually produces. Rebuild it from the file you read in step 1. |
| does not resolve to a path inside the repository | Should never fire from this skill's own calls: `docs/baton/state.md` and the journal paths `baton-journal` hands back are always repo-root-relative. Something upstream built the wrong path. |
| refusing to write `docs/baton/constitution.md` | This skill only ever writes `state.md` and journal entries, so you targeted the wrong path. The constitution is never a checkpoint target. |
| over the 60-line cap | Move the excess detail into a journal entry (`baton-journal`), leave `state.md` holding only a pointer to it, and write again — except an autopilot attempt counter, which stays on the `In flight` line whatever else moves out (see step 4). |

Exit 0 with no commit is not a failure — see step 7.

## Verify before claiming success

**1. Every section is still in the committed file.**

```bash
git show HEAD:docs/baton/state.md | grep -nE '^(#|\*\*[A-Z]|\| [0-9])'
```

Goal, Operating mode, Non-negotiables, `## Waves` with one row per wave,
`## Now`, `## Pointers` — everything you read in step 1 has to be in that output.
Anything missing is already committed: recover the lost text from
`git show HEAD~1:docs/baton/state.md` and checkpoint again from a draft on it.

**2. `git status --porcelain docs/baton` is empty.** It proves nothing about the
first, but catches what the first cannot: a rollback that left the tree dirty
(exit 7), or a stray untracked file under `docs/baton/`. If it is not empty,
state is sitting outside the log and the checkpoint did not happen. Say so
rather than reporting success.

## Red Flags

| Thought | Reality |
|---|---|
| "Next action is obvious, I'll keep it short" | Obvious to you, with context. Write it for someone with none. |
| "I'll checkpoint after this one last thing" | The compaction does not wait for you. |
| "The wave is basically done, I'll mark it done" | `done` needs every exit criterion checked against the repository, one by one, plus the human's confirmation — or, while the autopilot is on, a filed verdict in its place. See Closing a wave. |
| "The human hasn't replied in an hour, that's the same as autonomy" | It is not. The second closing path is gated on the `autopilot` field, which only a human sets. Silence is not a grant. |
| "State didn't change, something is broken" | An idle checkpoint writing nothing is the designed behaviour. |
| "I'll note the divergence in my reply instead of the file" | Your reply dies with the context. The file does not. |
| "I'll write the fields that changed" | `baton-write` replaces the whole file. Anything not carried over is deleted, the commit lands, and the tree still looks clean — step 6's diff is the only thing that catches it. |
| "`done` is set, I'll fill `closed_at_sha` later" | There is no later. The next checkpoint and the next resume both read `—` as a claim they cannot verify, and have to raise `suspect`. |
