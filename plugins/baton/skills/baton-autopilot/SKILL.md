---
name: baton-autopilot
description: Use when docs/baton/state.md has autopilot set to anything but off - carries waves to closure with no human present, files a verdict for each one, and stops the right way when it cannot
---

# baton Autopilot

The run continues while nobody is watching. This skill is what that permits
and, more importantly, what it does not.

**Announce at start:** "Autopilot is on for <scope> — carrying waves without
stopping for confirmation."

**Prerequisite:** `autopilot` in `state.md` is not `off`, and you hold the
writer lease. That field is also the scope: `all` is every wave in the run, a
number is that wave and no other. If it reads `off`, this skill does not
apply — closing a wave then needs a human, and `baton-checkpoint` says how.

## The grant is asymmetric

A human turns the autopilot on, by typing `/baton:auto` — a command the model
cannot invoke. You may always turn it off, and never on.

This is the same direction as `suspect` and `needs_human`, where you raise the
flag and a human clears it. In both cases you are free to move toward more
human involvement and not free to move toward less. An agent that could grant
itself autonomy is bounded by nothing, and the grant would stop meaning
anything the first time one did.

So: writing `autopilot: off` is always available to you. Writing anything else
into that field is not, whatever the reason seems to be. Leave `autopilot_grant`
holding whatever the human put there — it records what was authorised, which is
not the same thing as the authority, and the morning reads it to find out what
the run was allowed to do before it stopped.

## The loop

For each wave in scope, in Waves-table order:

1. **Spec.** If the wave's `spec` cell in the Waves table names a file, that
   spec is the human's and you work to it. If it reads `—`, derive one from
   the constitution: the wave's `exit_criteria`, its `produces` and `consumes`,
   and the non-negotiables. Deriving is narrowing what the human already
   ratified, not inventing scope — if it feels like invention, that is the
   signal to stop, not to be bolder.
2. **Plan.** `superpowers:writing-plans` against that spec.
3. **Work.** Delegate it. You are the orchestrator; the rule that you do not
   write code in the primary session is not suspended by the human's absence —
   it is more load-bearing without them, since context is the only resource
   the run cannot refill and nobody is around to notice you spending it.
4. **Gate.** `baton-gate`, then your own verdict. See below.
5. **Close or block.** Then the next wave.

Checkpoint between waves, always. A wave closed and not checkpointed is a
wave that did not happen, as far as the next session can tell.

## The gate

Run the evidence collector first:

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/baton-gate" --since "<the previous wave's closed_at_sha>"
```

`closed_at_sha` is the right cell to read: `baton-checkpoint` records that
run's `work_sha` there, not its `sha`, so it already names the last commit
that moved the work rather than the checkpoint commit that followed it.

`--since` does not move between attempts on the same wave. What is being gated
is the whole wave, not the part of it since the last failed attempt.

For the first wave in a run, `--since` is whatever base the human named at
`/baton:auto`, and otherwise the repository's root commit:

```bash
git rev-list --max-parents=0 HEAD | tail -1
```

That prints one line in a repository with one root, which is the ordinary
case. More than one line means the history has more than one root — an
unrelated history merged in — and `tail -1` then picks whichever of them has
the oldest commit date. A diff from a root cannot report what was already in
that root's own tree, so everything that arrived with the sibling root falls
outside the scan, and nothing in the output says so: a gate that quietly looked
at less than the wave. Count the lines before using it. More than one, with no
base named at `/baton:auto`, is a stop — `needs_human: true`, saying what
clears it, which is a `/baton:auto` that names a base.

Read the exit code before the output:

| Exit | Meaning | What to do |
|---|---|---|
| 0 | Evidence gathered. | Read `verify_exit` and `placeholder_hits`. This is the only row a verdict can come out of. |
| 1 | Not a git repository. | Stop and report; nothing here works without git. |
| 3 | The constitution is unfit to gate against: missing, not `ratified`, still carrying an unfilled placeholder marker, `placeholder_patterns` absent, or either it or `verify_cmd` opening a quote it never closes. | Stop, `needs_human: true`. The constitution is the human's and `baton-write` refuses that path, so this is not something to route around — least of all when the fix looks like one character. |
| 4 | The constitution reads fine and the gate could not gather evidence from it: `verify_cmd` absent, empty, or naming something that cannot be run; `placeholder_patterns` holding a pattern that does not compile; `.baton/` not preparable for the log; a changed path that could not be scanned; or `baton-observe` itself failed. | Stop and report the message, which names which of those it was. Do not substitute a command you think is equivalent — `verify_cmd` is in the constitution precisely so you do not choose it. Some causes here are the machine's rather than the constitution's, and a human can clear those without amending anything. |
| 64 | Usage, including a `--since` that is not a commit in this repository. | Fix the argument and rerun. It is checked before `verify_cmd` runs, so nothing was spent. |
| anything else | Not this script's own logic — awk or git failed underneath it. | Stop and report. A tooling failure, not a verdict: the gate did not decide against the wave, it never got to look. |

**Absence is not symmetric between those two fields**, and reading across from
one to the other is how this table gets misremembered. A missing
`placeholder_patterns` is exit 3 — `/baton:init` always writes that field, so
its absence means somebody removed it, which is a statement about the
constitution. A missing `verify_cmd` is exit 4, reported as "empty": there is
simply nothing to run. Both stop the run, and they hand the human different
jobs.

Exit 0 is not a pass. It means the evidence exists. A red gate is exit 0 with
`verify_exit` non-zero, and that distinction is the reason to read the code
first: exit 4 and a red `verify_exit` look similar in a summary and call for
opposite responses.

## Reading the evidence

Exit 0 prints ten keys, in this order:

| Key | Reads |
|---|---|
| `verify_cmd` | the constitution's command, as it was run. |
| `verify_exit` | 0 is green; non-zero is red, except for the codes below, which are not a verdict at all. |
| `verify_log` | `.baton/gate-verify.log` — relative to the repository root, not to your cwd. |
| `placeholder_hits` | **files that matched**, not markers. Three markers in one file is one hit. |
| `placeholder_files` | which files, comma-separated; empty when there were none. |
| `changed_files` | files this scan considered. |
| `since` | the `--since` you passed, resolved to a SHA. |
| `sha` | HEAD when the evidence was gathered — the tree `verify_cmd` actually ran against. |
| `work_sha` | the last commit outside `docs/baton/`. |
| `tree_clean` | whether the working tree was clean when the evidence was gathered. It qualifies `sha` — see below. |

`sha` and `work_sha` answer different questions, and the next wave needs the
second one: its `--since` resolves from `work_sha`, not from `sha`, because a
checkpoint commit moves `sha` without moving the work. Take `sha` and the next
wave's scan begins after your own checkpoint, so anything that landed between
the work and that checkpoint is never scanned at all.

`changed_files=0` is a real property, not a sign that nothing happened. A wave
whose only change was deleting files reports 0 — there is nothing left on disk
to scan. So does a stretch that touched only `docs/baton/`, which the scan
excludes as describing the work rather than being it.

`placeholder_hits=0` is only evidence if the scan was asked anything.
`placeholder_patterns: ""` is a legitimate constitution meaning scan nothing,
and the gate then exits 0 having looked at no file for markers at all. Read the
constitution's pattern list before treating a zero as a clean bill: a run whose
human turned the scan off gets the same `0` as one that searched every changed
file and found nothing.

## A dirty tree at gate time

`tree_clean=false` means the evidence describes a tree no `sha` names. The
suite ran against files that are not in the repository — an uncommitted fix, a
test a subagent wrote and never committed — so nothing a later session can
check out reproduces this run, and a green verdict filed on it is a claim about
a tree that exists nowhere. `/baton:auto` refuses to hand a run over with a
dirty tree, so any dirt here arrived during the run: it is the run's own doing,
and yours to resolve.

Which of two things it is decides what happens, and do not settle it from
recollection — that is precisely what the next compaction takes. Name the paths
first:

```bash
git status --porcelain
```

Then check each against what this wave declared it would touch: its `produces`
in the constitution, and the file list in its plan. That comparison is against
documents, not against your memory of the last hour, which is the only reason
it is worth anything at 03:40.

- **Every path is inside that set.** Ordinary work, not a pat. Commit it and
  gate again. Committing moves `HEAD`, so the evidence in your hands is already
  stale — `verify_cmd` has to run against the tree that will still be there in
  the morning. This does not count against the three-attempt ceiling: the gate
  never rendered a verdict, and finishing the work is not a fix for a red one.
  But if the tree comes back dirty on that next run, something is writing files
  nothing accounts for, and that is the case below rather than this one again.
- **A path is outside it** — something you cannot account for as this wave's
  work. `needs_human: true`, name the paths, stop. Committing a change you
  cannot explain into a wave is worse than stopping, and there is nobody awake
  to say what it is. Do not stash it either: stashing hides it from the next
  session as well as from the gate, which is strictly worse than leaving it
  where a human will see it.

**Some non-zero `verify_exit` values are not evidence about the code.**
`verify_exit=127` means the command was never found — it reports that the suite
did not run, not did not pass. `130`, `137` and `143` are deaths by signal — an
interrupt, an OOM-killed suite, a `SIGTERM` from something's timeout — and say
the same thing about the machine rather than about the work. Nothing in any of
them is a claim that the code is wrong.

`baton-gate` deliberately does not remap
them, because a real test runner can legitimately propagate a 127 of its own
and guessing which case this is would be worse than reporting the number. So
the reading belongs here: treat these as the tooling failing. Stop and report;
do not enter the fix-and-regate loop below. Every attempt spent fixing code to
satisfy a suite that never ran is an attempt against the ceiling, and three of
them close nothing.

The whole exit-code design exists to keep "the tests failed" apart from "the
tests could not be run". This is the last place they can still be confused,
because here they arrive in the same shape: a number on a `verify_exit=` line.

**Evidence red** — `verify_exit` non-zero for a reason that is about the code,
or `placeholder_hits` above zero — means the wave does not close. Go fix it,
then gate again.

**Evidence green** is a necessary condition and not a sufficient one. Walk the
wave's `exit_criteria` from the constitution, one at a time, against the
repository — not against your impression of the work. No script will ever do
this part: "the system shall preserve the subject when a token is renewed" is
a claim about behaviour, and only reading the behaviour settles it.

## The verdict file

`verify_log` is unbounded — a verbose suite produces tens of megabytes — so
tail it rather than reading it whole:

```bash
tail -50 "$(git rev-parse --show-toplevel)/.baton/gate-verify.log"
```

It is also **truncated on every run**: attempt 1's output is gone the moment
attempt 2 starts, and `.baton/` is gitignored, so nothing of it survives
anywhere else. That is why the failing tail goes *into* the verdict file below
rather than a reference to it. Left out, the morning's account of what broke at
03:40 is your recollection of it, and your recollection is what the next
compaction takes.

Write it through `baton-write`, to
`docs/baton/gates/wave-<N>-attempt-<K>-<short_sha>.md`:

```markdown
---
schema: baton/gate/v1
wave: 2
attempt: 1
verdict: auto
decided_by: <your session id>
decided_at: <ISO8601>
since: <the since= from the evidence>
sha: <the sha= from the evidence>
work_sha: <the work_sha= from the evidence>
verify_exit: 0
placeholder_hits: 0
tree_clean: true
---

# Gate: wave 2 — attempt 1

## Evidence

<the ten key=value lines, verbatim>

## Verify output

<the tail of the verify log: the failing block if you can find it, the last
fifty lines otherwise>

## Criteria

- **When a token is renewed, the system shall preserve its subject** — met.
  `src/session.js:12` carries the subject through; covered by
  `test/session.test.js:8`, green in the run above.

## Decision

Closed under the autopilot. No human confirmed this.
```

Both shas are in the frontmatter because they answer different questions
later: `sha` is the tree this verdict judged, `work_sha` is where the next
wave's scan starts. `tree_clean` is there because it qualifies `sha` — it is
what tells the morning whether `sha` names the tree the suite actually ran
against, and a verdict that records the first without the second cannot be
told apart from one filed over uncommitted work.

A red attempt gets a file too, with `verdict: fail`. What broke at 03:40 is
exactly what the morning needs, and it is gone by then if only successes are
written down. The attempt number is in the filename because two red attempts
without a commit between them share a `short_sha`, and the second would
otherwise overwrite the first.

Then close the wave the way `baton-checkpoint` describes, with one difference:
the `gate` column takes `auto`, not `pass`. `pass` says a human confirmed it,
and none did. The morning's job is turning `auto` into `pass` or into an
objection, and it cannot be done if the two were already conflated overnight.

Filing the verdict does not disturb the closure: it lands under `docs/baton/`,
which `work_sha` excludes, so `closed_at_sha` is the same whether the verdict
is written before the checkpoint or after it. Write it first anyway — it is
the evidence for a closure, and evidence that arrives after the claim it
supports leaves a window where the claim stands on nothing.

## When fixing stops being fixing

A red gate is work, not a stop. Fix it and gate again.

Stop when the evidence stops moving: the same `verify_exit` and the same set
of failing tests as the previous attempt. That is unchanged evidence, and
unchanged evidence after a fix means the fix did not address what is actually
broken — running it again is what a loop looks like from the inside.

There is also a ceiling: **three attempts** at closing one wave. It exists for
the case where the evidence shifts slightly each time while nothing actually
moves.

Keep the count in `state.md`'s **In flight** line — `wave 2: attempt 2 of 3` —
not in your head. A count held in context is reset by the next compaction, and
a ceiling that resets is not a ceiling. It belongs to the wave, not to this
session: `/baton:continue` does not reset it. The only thing that does is a
human clearing the `blocked` status.

## The pat

When a wave cannot close:

1. wave `status` → `blocked`;
2. `needs_human: true`;
3. a journal entry, `type: blocked` — what stopped, the evidence, what you
   tried, and why each attempt did not move it;
4. checkpoint;
5. look for another wave.

**A wave is available only if all three hold:**

1. its status is `todo` and it is inside the granted scope;
2. every wave in the **transitive** closure of its `depends_on` is `done`;
3. nothing in its `consumes` appears in the `produces` of any wave that is
   `blocked`.

The third condition is what makes moving on safe rather than merely fast. Two
waves can be independent in the dependency graph and still rest on one
contract that the blocked wave was supposed to define; building on a contract
nobody has defined yet produces work that has to be thrown away, which is
worse than the night of idling it was meant to avoid.

If no wave is available: checkpoint, write `autopilot: off`, and stop with a
report.

## What the autopilot never covers

Autonomy removes the need to confirm each step. It adds no authority. These
stop the run regardless of how many waves are left:

- **New input that contradicts the constitution.** Journal it as `incoming`,
  wave → `blocked`, `needs_human: true`. The amendment is the human's.
- **A claimed field that diverged.** `suspect: true` and stop. The autopilot
  is not permission to repair a claim; silently correcting one destroys the
  evidence that something went wrong.
- **`baton-lock` exit 3.** Another session holds a live lease. Stop, report,
  write nothing.
- **Anything that would weaken the gate.** `verify_cmd`, `placeholder_patterns`
  and the exit criteria live in the constitution and `baton-write` refuses that
  path. Editing tests so they pass instead of the code they cover is the same
  act by another route, and it is worse for being deniable.
- **A question whose answer changes the goal.** Not "how do I build this" but
  "is this the thing to build". `needs_human: true`.

## Red Flags

| Thought | Reality |
|---|---|
| "The human isn't here, so I decide what closing means" | Closing means the exit criteria in the constitution. Their absence changes who confirms, not what is required. |
| "The gate is red for an unrelated reason, this wave is fine" | Then the gate is the run's problem and it is now. A gate you are willing to interpret around has stopped being a gate. |
| "I'll set autopilot back on after this stop" | You cannot. Turning it on is the human's, always, and this is the exact moment that rule is for. |
| "Nobody will read a fail verdict, I'll just fix it" | The morning reads it. It is the only account of what happened at 03:40, and the log it came from is overwritten by the next attempt. |
| "The suite exited 127, so something is broken" | Nothing ran. That is not evidence about the code, and fixing code against it spends the ceiling on a machine problem. |
| "The tree is dirty but the gate is green, so it passed" | It passed against a tree no `sha` names, which nobody can check out in the morning. Account for every path, commit, gate again. |
| "This wave doesn't depend on the blocked one, I'll take it" | Check `consumes` against the blocked wave's `produces` too. The graph is not the whole dependency. |
| "It's faster if I write this bit myself" | It is faster, and speed is not the constraint. Nobody is here to notice the context going. |

## Related skills

- **baton** — the model this rides on: what is authoritative, the two logs,
  the divergence policy.
- **baton-checkpoint** — the write. Closing a wave under the autopilot is its
  "Closing a wave" section, second path.
- **baton-resume** — runs before this on every fresh or compacted session, and
  decides whether the autopilot continues silently or waits for a word.
