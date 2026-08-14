---
name: baton-autopilot
description: Use when baton-resume has decided the autopilot grant applies to this session, or when a human has just typed /baton:continue - carries waves to closure with no human present under an existing grant, files a verdict for each one, and stops the right way when it cannot. Not triggered by reading autopilot in state.md; that field is set for every session, including ones a human opened to check one thing
---

# baton Autopilot

**Announce at start:** "Autopilot is on for <scope> — carrying waves without
stopping for confirmation."

**Prerequisite:** not that `autopilot` reads something other than `off` — that
fact sits on disk for every session of a granted run. What this skill needs is
the *decision* that the grant applies to **this** session, made in exactly two
places:

- `baton-resume`'s step 7 reached its `compact`/`resume` row — same session,
  the human is still away;
- or a human typed `/baton:continue`.

Plus the writer lease. Reading the field yourself is not the decision.

Once one of those holds, the field is also the scope: `all` is every wave in
the run, a number is that wave and no other. If it reads `off`, this skill does
not apply at all — closing a wave then needs a human, and `baton-checkpoint`
says how.

## The grant is asymmetric

A human turns the autopilot on, by typing `/baton:auto` — a command the model
cannot invoke. You may always turn it off, and never on. Writing
`autopilot: off` is always available to you; writing anything else into that
field is not, whatever the reason seems to be. Leave `autopilot_grant` holding
whatever the human put there.

## The loop

Take waves in **the constitution's wave order, restricted to waves in scope**.
Do not sort by `depends_on`. If the constitution's own order violates its own
`depends_on`, stop — the constitution is wrong, and it is the human's.

Then, for each wave:

0. **Check it is available.** The conditions under [The pat](#the-pat) — in
   scope and `todo`, the whole transitive `depends_on` closure `done`, nothing
   in its `consumes` produced by a `blocked` wave, a constitution `spec` that
   names a document. Not available, and not blocked either — skip it and take
   the next; any wave you never come back to belongs in the end-of-run report,
   because nothing on disk will record that you passed it.
1. **Spec.** The wave's `spec` in the constitution names the document this
   wave builds to — the umbrella spec, one section of it, or a spec written
   for this wave alone. Work to that document.

   Never derive that document yourself; a `—`, or no `spec:` key at all, is
   step 0's refusal, not a licence here. `baton-write` refuses the
   constitution, so a spec you wrote could not reach the field this step
   reads, and it would be one you judged at your own gate —
   `superpowers:brainstorming` writes it, and needs a human.
2. **Plan.** `superpowers:writing-plans` against that spec.
3. **Work.** `superpowers:subagent-driven-development` against that plan, and
   no other procedure in its place.

   You are the orchestrator, and the rule that you do not write code in the
   primary session is not suspended by the human's absence.
4. **Gate.** `baton-gate`, then your own verdict. See below.
5. **Close or block.** Then the next wave.

Checkpoint between waves, always.
**And between attempts, not only between waves.**

## The gate

The gate records that a wave closed against the criteria the human ratified —
**not a second review of the code**: it opens no findings and starts no rounds.

Run the evidence collector first:

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/baton-gate" --since "<the previous wave's closed_at_sha>"
```

`closed_at_sha` holds that run's `work_sha`, not its `sha`: it already names
the last commit that moved the work.

`--since` does not move between attempts on the same wave.

For the first wave in a run, read the base off the grant. `/baton:auto` takes
`[wave] [--since <ref>]`, resolves the ref, and records it as **`base:`** in
the frontmatter of the `type: autopilot` journal entry that `autopilot_grant`
names. So:

- **`base:` is a sha** — that is the first wave's `--since`, and it outranks
  anything you would derive.
- **`base:` is `—`** — no base was named. Fall back to the repository's root
  commit, with the count and the stop below.
- **`base:` is absent entirely** — an older entry, or one that put the base in
  the body. Treat it as `—`, say so in the report, and do not go hunting for a
  sha in the prose.

```bash
git rev-list --max-parents=0 HEAD | tail -1
```

**Count the lines.** More than one means more than one root, and `tail -1`
picks by commit date, so which root's tree is exempt is arbitrary. That is a
stop: `needs_human: true`, name the roots, and say what clears it, which is
`/baton:auto --since <ref>`.

Read the exit code before the output. **0 is the only code a verdict can come
out of**, and even then it means the evidence exists, not that it is green:
read `verify_exit` and `placeholder_hits`. Any other code is a stop, and the
script's own message names the cause — report that rather than paraphrasing
it. `3` and `4` both mean the gate could not reach a verdict and hand the
human different jobs; `3` also takes `needs_human: true` — say `/baton:ratify`
when the script's message is the unratified constitution, and `/baton:clear`
for the flag once that is done. `64` is a bad argument, checked before
`verify_cmd` runs, so nothing was spent; anything else is git or awk failing
underneath, not a verdict against the wave.

**Absence is not symmetric between the two constitution fields the gate
needs**, so do not read one across to the other: a missing
`placeholder_patterns` is exit 3, a missing `verify_cmd` is exit 4, reported
as empty. Never substitute a command of your own for `verify_cmd`.

## Reading the evidence

Exit 0 prints eleven keys, one `key=value` line each. Six need a reading:

- **`sha` and `work_sha` answer different questions.** `sha` is HEAD when the
  evidence was gathered — the tree `verify_cmd` ran against, and the one the
  verdict judges. `work_sha` is the last commit outside `docs/baton/`, and the
  next wave's `--since` resolves from `work_sha`, not from `sha`: take `sha`
  instead and the next scan starts after your own checkpoint, missing
  everything between.
- **`placeholder_hits=0` is only evidence if the scan was asked anything.** An
  empty `placeholder_patterns` — what the scan was asked to look for — is a
  legitimate constitution meaning scan nothing, and produces the same `0`.
  Carry both into the verdict. A non-zero count is **files that matched**, not
  markers.

`changed_files=0` is a real property, not a sign nothing happened: a wave that
only deleted files reports it, as does one that touched only `docs/baton/`.

`tree_clean` qualifies `sha` — see below.

## Red, green, and neither

**Some non-zero `verify_exit` values are not evidence about the code.** `127`
means the command was never found; `130`, `137` and `143` are deaths by signal.
All four say the suite did not run, not did not pass. Stop and report; do not
enter the fix-and-regate loop below.

**Evidence red** — `verify_exit` non-zero for a reason that is about the code,
or `placeholder_hits` above zero — means the wave does not close. Go fix it,
then gate again.

**Evidence green** is a necessary condition and not a sufficient one. Walk the
wave's `exit_criteria` from the constitution, one at a time, against the
repository — not against your impression of the work. **An unmet criterion is
a failed attempt**: fix it, gate again, and count it against the ceiling.

## A dirty tree at gate time

`tree_clean=false` means the evidence describes a tree no `sha` names.

Name the paths first — from the document, not from memory:

```bash
git -c core.quotePath=false status --porcelain -uall --ignore-submodules=none
```

Those flags are `baton-observe`'s own.

Discount `.baton/` before anything else — it is the gate's own working
directory. If it shows up at all, `.gitignore` lost a line: report that and
carry on with the wave.

Check every remaining path against the **union** of the wave's plan, its spec,
and the diff since this wave's `--since`. Inside any of them: ordinary work.
Commit it and gate again — this does not count against the three-attempt
ceiling, since no verdict was rendered. If it comes back dirty on that next
run, something is writing files nothing accounts for: take the stop below.
Outside all three — something you cannot account for as this wave's work:
`needs_human: true`, name the paths, stop. Do not stash it; that hides it from
the next session too.

## The verdict file

`verify_log` is unbounded, so tail it rather than reading it whole:

```bash
tail -50 "$(git rev-parse --show-toplevel)/.baton/gate-verify.log"
```

It is also **truncated on every run**, and `.baton/` is gitignored, so the
failing tail goes *into* the verdict file below rather than a reference to it.

Write it through `baton-write`, to
`docs/baton/gates/wave-<N>-attempt-<K>-<short_sha>.md`, where `<short_sha>` is
the short form of `sha` — the tree this verdict judged, not `work_sha`:

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
placeholder_patterns: <the placeholder_patterns= from the evidence>
placeholder_hits: 0
tree_clean: true
---

# Gate: wave 2 — attempt 1

## Evidence

<the eleven key=value lines, verbatim>

## Verify output

<the tail of the verify log: the failing block, or the last fifty lines>

## Criteria

- **When a token is renewed, the system shall preserve its subject** — met.
  `src/session.js:12` carries it through; `test/session.test.js:8` covers it.

## Decision

Closed under the autopilot. No human confirmed this.
```

A red attempt gets a file too, with `verdict: fail`.

Then close the wave exactly the way `baton-checkpoint` describes — four edits,
`gate` taking `auto`. Write the verdict before the checkpoint; it lands under
`docs/baton/`, which `work_sha` excludes, so the closure is unaffected either
way.

## When fixing stops being fixing

A red gate is work, not a stop. Fix it and gate again.

Stop when the evidence stops moving: unchanged evidence is the same
`verify_exit` and the same set of failing tests as the previous attempt.
**Evidence-red attempts only.** A criteria walk leaves the evidence identical
every time, so this would stop every criteria failure at attempt 2.

There is also a ceiling: **three attempts** at closing one wave.

Keep the count in `state.md`'s **In flight** line — `wave 2: attempt 2 of 3` —
not in your head. It belongs to the wave, not to this session:
`/baton:continue` does not reset it. The only thing that does is a human
clearing the `blocked` status.

## The pat

When a wave cannot close:

1. wave `status` → `blocked`;
2. a journal entry, `type: blocked` — what stopped, the evidence, what you
   tried, and why each attempt did not move it;
3. checkpoint;
4. look for another wave.

**Do not raise `needs_human` here.** It is the run-level stop flag:
`baton-resume` and `/baton:continue` both halt on finding it set, before the
lease is taken.

**A wave is available only if all four hold:**

1. its status is `todo` and it is inside the granted scope;
2. every wave in the **transitive** closure of its `depends_on` is `done`;
3. nothing in its `consumes` appears in the `produces` of any wave that is
   `blocked`;
4. its `spec` in the constitution **names a document**. `—` and an absent
   `spec:` key are one refusal, not two — absent is not permission. That
   document is the human's to write, and `baton-write` refuses the path you
   would write it at.

If no wave is available, the run is over and this is where the flag belongs:
checkpoint, `needs_human: true` **if anything is `blocked`, or was
skipped for want of a spec**, write `autopilot: off`, and stop with a report.

Say in that report that the run is over and
`superpowers:finishing-a-development-branch` is what closes it — merge, PR or
clean up. Name every blocked wave in that report, and say what each was
waiting on. If you raised `needs_human`, name `/baton:clear` too: nothing else
lowers it, and this report is the only thing the morning reads.

Name every wave you skipped for want of a spec too — `—`, or no `spec:` key
at all — and say that is why. A skipped wave is still `todo`, so nothing on
disk records that you passed it — this report is the only place it exists. It
wants the human more plainly than a blocked wave does: what it needs is a
`brainstorming` session, which is the one thing this run could not have
supplied for itself.

If nothing is blocked, nothing was skipped, and the scope simply finished,
leave `needs_human` alone — that run wants no one.

## What the autopilot never covers

Autonomy removes the need to confirm each step. It adds no authority. These
stop the run regardless of how many waves are left, and every stop that raises
`needs_human` — here or above — names `/baton:clear` in what it reports:

- **New input that contradicts the constitution.** Journal it as `incoming`,
  wave → `blocked`, `needs_human: true`. The amendment is the human's.
- **A claimed field that diverged.** `suspect: true` and stop. The autopilot
  is not permission to repair a claim.
- **`baton-lock` exit 3.** Another session holds a live lease. Stop, report,
  write nothing.
- **Anything that would weaken the gate.** `verify_cmd`, `placeholder_patterns`
  and the exit criteria live in the constitution, and `baton-write` refuses
  that path. Editing tests so they pass instead of the code is the same act.
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

- **baton** — what is authoritative, the two logs, the divergence policy.
- **baton-checkpoint** — the write. Closing a wave under the autopilot is the
  second path of its "Closing a wave" section.
- **baton-resume** — runs before this on every fresh or compacted session, and
  decides whether the autopilot continues silently or waits for a word.
