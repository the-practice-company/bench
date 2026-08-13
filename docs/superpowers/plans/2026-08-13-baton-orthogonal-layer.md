# baton Orthogonal Layer — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop `baton` substituting for steps of the superpowers flow — name the flow's procedures instead — and cut the skills back to their rules so the layer stops costing more context than the workflow it wraps.

**Architecture:** Documentation-and-schema change only. No script under `plugins/baton/scripts/` is touched, and no exit code changes. Four skill files, two commands, two templates, the README, the test suite and the cold-start runbook. The test suite is the executable part: every rule this plan adds or moves is pinned by an `assert_contains` in `tests/`, and the cleanup is bounded by line-count caps so the weight cannot creep back.

**Tech Stack:** Markdown, bash, the repository's own assert helpers (`tests/helpers.sh`). Tests run with `bash tests/run-tests`.

**Spec:** `docs/superpowers/specs/2026-08-13-baton-orthogonal-layer-design.md`

---

## Decisions this plan settles

The spec left three questions to planning (§12). Two are answered here; the third is answered by doing.

**1. How the worktree preference is declared** → a frontmatter field in the constitution, `workspace: in-place`, taking `in-place` or `worktree`.

Frontmatter rather than prose in `## Operating mode` for two reasons. It is assertable by a one-line test, which prose is not. And the agent has to *restate* this preference to `using-git-worktrees` — a field it reads verbatim survives that hop, a sentence it has to interpret does not. The cost the spec worried about (one more field on the constitution's schema) is one enum with two values.

**2. What `/baton:continue` does when `observed_branch` diverged** → name the expected branch and the actual one, and stop. Do not offer to switch.

Switching branches is a write to the working tree from a procedure that has not taken the lease yet. And the divergence may be the human's own doing — they moved deliberately, and the state file is the stale thing. Naming both sides costs one line and leaves the call where it belongs.

**3. How much the cleanup actually yields** → measured per task, capped in Task 11.

Recording the arithmetic honestly up front: the spec estimated 900–1000 lines total. A third off each file gives `157 + 333 + 291 + 305 = 1086`, and the `baton` skill grows slightly from Tasks 3 and 7. So **1100 is the realistic ceiling**, and the spec's estimate was optimistic by about 10%. Task 11 sets the cap at 1100. If the cleanup lands lower without breaking the invariant, tighten it in that same commit.

**The cleanup invariant, restated because every cleanup task depends on it:**

> Ни одно правило не исчезает. Уезжает только проза, которая за него аргументирует.

A line telling the agent *what to do* stays. A line explaining *why the rule is that way* moves to the README or is dropped — the design specs already hold the reasoning. All four Red Flags tables are exempt and are not touched.

---

## File Structure

| File | Responsibility after this change |
|---|---|
| `plugins/baton/templates/state.md` | Wave table without the `branch/worktree` column |
| `plugins/baton/templates/constitution.md` | Adds `workspace:`; Operating mode names the flow's procedures |
| `plugins/baton/skills/baton/SKILL.md` | Model. `observed_branch` becomes a stop; related-skills wording. Exempt from cleanup |
| `plugins/baton/skills/baton-resume/SKILL.md` | Resume procedure. Step 2 compares `observed_branch` instead of repairing it. Cleaned |
| `plugins/baton/skills/baton-autopilot/SKILL.md` | Autopilot loop. Steps 1 and 3 rewritten, gate reframed as a record. Cleaned |
| `plugins/baton/skills/baton-checkpoint/SKILL.md` | Checkpoint procedure. Cleaned only |
| `plugins/baton/commands/auto.md` | Refuses a scope containing a spec-less wave |
| `plugins/baton/commands/init.md` | Asks two more questions; ratification note |
| `plugins/baton/README.md` | Gains the §4 before/after picture; receives prose evicted by the cleanup |
| `tests/test-templates.sh` | Schema assertions for both templates |
| `tests/test-skills.sh` | Rule assertions and per-file line caps |
| `tests/test-skill-commands.sh` | Command-text assertions |
| `tests/test-budget.sh` | **New.** Total skill-line ceiling |
| `tests/fixtures/cold-start/*.sh` | Wave tables lose the column; diverged fixture gains a branch divergence |
| `tests/fixtures/cold-start/RUNBOOK.md` | **New scenario 5** — the half of the `observed_branch` stop no script can observe |

---

### Task 1: Drop the `branch/worktree` column

The column encoded per-wave worktrees, which fork `state.md` itself (spec §6). It goes from the template, the four fixture builders, and its assertion.

**Files:**
- Modify: `plugins/baton/templates/state.md:26`
- Modify: `tests/test-templates.sh:26`
- Modify: `tests/fixtures/cold-start/build.sh:103`, `build-autopilot.sh:287`, `build-diverged.sh:160`, `build-takeover.sh:105`

- [ ] **Step 1: Change the failing assertion**

In `tests/test-templates.sh`, replace line 26:

```bash
assert_contains "$state" "branch/worktree" "state records where each wave lives"
```

with:

```bash
assert_not_contains "$state" "branch/worktree" "state's wave table carries no per-wave worktree column"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `bash tests/test-templates.sh`
Expected: FAIL — `did not expect to find: branch/worktree`

- [ ] **Step 3: Remove the column from the template**

In `plugins/baton/templates/state.md`, replace these two lines:

```markdown
| # | name | status | branch/worktree | spec | plan | closed_at_sha | gate |
|---|------|--------|-----------------|------|------|---------------|------|
```

with:

```markdown
| # | name | status | spec | plan | closed_at_sha | gate |
|---|------|--------|------|------|---------------|------|
```

And the data row below them:

```markdown
| 1 | REPLACE-WITH-WAVE-NAME | todo | — | — | — | — |
```

becomes:

```markdown
| 1 | REPLACE-WITH-WAVE-NAME | todo | — | — | — |
```

- [ ] **Step 4: Remove it from all four fixture builders**

Each of `tests/fixtures/cold-start/build.sh`, `build-autopilot.sh`, `build-diverged.sh`, `build-takeover.sh` contains a wave table inside a heredoc. In each, drop the `branch/worktree` header cell, its `-----------------` separator cell, and the corresponding cell from every data row. Verify none remain:

```bash
grep -rn "branch/worktree" tests/ plugins/ ; echo "exit=$?"
```

Expected: no output, `exit=1`.

- [ ] **Step 5: Run the full suite**

Run: `bash tests/run-tests`
Expected: `All test files passed.`

- [ ] **Step 6: Commit**

```bash
git add plugins/baton/templates/state.md tests/test-templates.sh tests/fixtures/cold-start/
git commit -m "state: a wave does not live in a tree of its own"
```

---

### Task 2: Declare the workspace preference in the constitution

`using-git-worktrees` honours a declared preference without asking (its Step 0). Declaring it once, per run, is what keeps it from asking under the autopilot where nobody can answer.

**Files:**
- Modify: `plugins/baton/templates/constitution.md:16` (after `placeholder_patterns`), `:25-29` (Operating mode)
- Modify: `tests/test-templates.sh`

- [ ] **Step 1: Write the failing assertions**

Append to `tests/test-templates.sh`, immediately before the `finish` call:

```bash
# Declared once, per run, so using-git-worktrees never has to ask under the
# autopilot -- its Step 0 honours a declared preference without a prompt.
assert_contains "$constitution" "workspace: in-place" "constitution declares the workspace preference, defaulting to in-place"
assert_contains "$constitution" "in-place | worktree" "constitution names both workspace values"
assert_contains "$constitution" "subagent-driven-development" "constitution's operating mode names the procedure work is delegated to"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `bash tests/test-templates.sh`
Expected: three FAILs, `expected to find: workspace: in-place` among them.

- [ ] **Step 3: Add the field**

In `plugins/baton/templates/constitution.md`, after the `placeholder_patterns:` line, add:

```yaml
# in-place | worktree. Where the run works. Declared here so
# superpowers:using-git-worktrees honours it without asking -- under the
# autopilot there is nobody to answer a consent prompt. baton needs no tree
# of its own; this protects your other work in this repository, not the run.
workspace: in-place
```

- [ ] **Step 4: Rewrite the Operating mode section**

Replace the body of `## Operating mode`:

```markdown
Who the agent is in this run. Default: orchestrator. It delegates
implementation to subagents and workflows, does not write code in the primary
session, and is answerable for carrying the work to completion.
```

with:

```markdown
Who the agent is in this run. Default: orchestrator. It does not write code in
the primary session, and it is answerable for carrying the work to completion.

Delegation goes through the named procedures, not through whatever tool is at
hand: `superpowers:writing-plans` for the wave's plan, then
`superpowers:subagent-driven-development` to execute it. A wave executed by
some other means loses that skill's two-stage review, and the first stage is
the one that catches work drifting from the spec.
```

- [ ] **Step 5: Run the template tests**

Run: `bash tests/test-templates.sh`
Expected: all PASS, including the 60-line cap checks on `state.md` (untouched here).

- [ ] **Step 6: Commit**

```bash
git add plugins/baton/templates/constitution.md tests/test-templates.sh
git commit -m "constitution: where the run works, and which procedure does the work"
```

---

### Task 3: `observed_branch` becomes a stop, not a silent repair

Spec §6. A session on the wrong branch reads a `state.md` that is not the run's, silently rewrites `observed_branch` to the branch it is actually on, and works against someone else's state.

**Files:**
- Modify: `plugins/baton/skills/baton/SKILL.md:74-84` (Divergence policy), `:155-157` (Related skills)
- Modify: `tests/test-skills.sh`

- [ ] **Step 1: Write the failing assertions**

Append to `tests/test-skills.sh`, before `finish`:

```bash
# Observed fields are repaired silently; this one is not, because it does not
# describe the tree -- it answers whether this is the tree at all.
assert_contains "$core" "observed_branch" "core skill names the branch field"
assert_contains "$core" "a stop, not a repair" "core skill makes a diverged observed_branch a stop"
assert_contains "$core" "superpowers:subagent-driven-development" "core skill names the procedure that executes a wave"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `bash tests/test-skills.sh`
Expected: FAIL — `expected to find: a stop, not a repair`

- [ ] **Step 3: Move the field out of the observed list**

In `plugins/baton/skills/baton/SKILL.md`, the Observed-fields bullet currently reads:

```markdown
- **Observed fields** — `observed_sha`, `observed_branch`, `tree_clean`,
  `writer`, `updated_at`. Fix them silently. Each describes something you can
  check at this moment — the repository, the lease file, the clock — so the
  file's copy of it is never the authority.
```

Replace with:

```markdown
- **Observed fields** — `observed_sha`, `tree_clean`, `writer`, `updated_at`.
  Fix them silently. Each describes something you can check at this moment —
  the repository, the lease file, the clock — so the file's copy of it is
  never the authority.
- **`observed_branch`** — looks observed and is not. The others describe the
  tree; this one answers whether this is the tree at all. A disagreement is
  **a stop, not a repair**: `needs_human: true`, name the branch `state.md`
  expects and the branch you are on, and stop. Repairing it silently is how a
  session on the wrong branch adopts a `state.md` that belongs to no run it is
  in.
```

- [ ] **Step 4: Fix the related-skills entries**

Replace these three lines:

```markdown
- **superpowers:brainstorming** — writes the per-wave spec
- **superpowers:writing-plans** — writes the per-wave plan
- **superpowers:subagent-driven-development** — executes the wave
```

with:

```markdown
- **superpowers:brainstorming** — writes a wave's own spec, when the umbrella
  spec does not cover that wave closely enough. Never run unattended.
- **superpowers:writing-plans** — writes the per-wave plan
- **superpowers:subagent-driven-development** — executes the wave, including
  its own two-stage review. Named at step 3 of the autopilot loop, not left
  to the agent's choice of tool.
- **superpowers:using-git-worktrees** and
  **superpowers:finishing-a-development-branch** — both bracket one unit of
  work, and baton's unit is the run. The first is settled once by the
  constitution's `workspace`; the second runs when the run ends, not when a
  wave does.
```

- [ ] **Step 5: Run the skill tests**

Run: `bash tests/test-skills.sh`
Expected: all PASS, including `skill baton is within the 500-line convention`.

- [ ] **Step 6: Commit**

```bash
git add plugins/baton/skills/baton/SKILL.md tests/test-skills.sh
git commit -m "baton: the branch is not an observed field"
```

---

### Task 4: `baton-resume` compares the branch instead of fixing it

The rule from Task 3, applied in the procedure that executes it.

**Files:**
- Modify: `plugins/baton/skills/baton-resume/SKILL.md:96-108` (step 2)
- Modify: `tests/test-skills.sh`

- [ ] **Step 1: Write the failing assertion**

Append to `tests/test-skills.sh`, before `finish`:

```bash
resume="$(cat "$SKILLS/baton-resume/SKILL.md")"
assert_contains "$resume" "Repair all three silently" "resume still repairs the three genuinely observed fields"
assert_contains "$resume" "observed_branch" "resume checks the branch"
assert_contains "$resume" "do not repair it" "resume does not silently repair a diverged branch"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `bash tests/test-skills.sh`
Expected: FAIL — `expected to find: do not repair it`

- [ ] **Step 3: Narrow the silent repair to three fields**

In step 2 of `plugins/baton/skills/baton-resume/SKILL.md`, this paragraph:

```markdown
Three frontmatter fields in `state.md` describe the repository rather than
claiming anything about the work: `observed_sha`, `observed_branch`,
`tree_clean`. Repair all three silently where they disagree with what came
back — stale reading, and the repository is right. Note the repairs; you do
not hold the lease yet, so nothing is written until step 6.
```

becomes:

```markdown
Three frontmatter fields in `state.md` describe the repository rather than
claiming anything about the work: `observed_sha`, `tree_clean`, `writer`.
Repair all three silently where they disagree with what came back — stale
reading, and the repository is right. Note the repairs; you do not hold the
lease yet, so nothing is written until step 6.
```

- [ ] **Step 4: Replace the branch comparison with the stop**

The sentence at the end of that step currently reads:

```markdown
Then compare `observed_branch`.
```

Replace with:

```markdown
Then compare `observed_branch` — and **do not repair it**. It is the one
field here that does not describe the tree but asks whether this is the tree
at all, so a disagreement means this session may be reading a `state.md` that
is not this run's. Set `needs_human: true`, say which branch `state.md`
expects and which one you are on, and stop. Do not switch branches to
resolve it: you hold no lease yet, and the human may have moved on purpose.
```

- [ ] **Step 5: Run the skill tests**

Run: `bash tests/test-skills.sh`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add plugins/baton/skills/baton-resume/SKILL.md tests/test-skills.sh
git commit -m "baton-resume: a branch that disagrees is not a stale reading"
```

---

### Task 5: The autopilot loop names its procedures

The core of the change. Step 1 loses the derivation branch; step 3 names `subagent-driven-development`; the gate is reframed as a record rather than a review.

**Files:**
- Modify: `plugins/baton/skills/baton-autopilot/SKILL.md:69-80` (steps 1–4), `:92-95` (gate preamble)
- Modify: `tests/test-skills.sh`

- [ ] **Step 1: Write the failing assertions**

Append to `tests/test-skills.sh`, before `finish`:

```bash
auto_skill="$(cat "$SKILLS/baton-autopilot/SKILL.md")"
assert_not_contains "$auto_skill" "derive one from" "the autopilot no longer writes a wave's spec for itself"
assert_contains "$auto_skill" "superpowers:subagent-driven-development" "the work step names the procedure that executes it"
assert_contains "$auto_skill" "not a second review of the code" "the gate is framed as a record of closure"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `bash tests/test-skills.sh`
Expected: FAILs including `did not expect to find: derive one from`.

The needle is `derive one from` and not the whole phrase on purpose. In the
file today, `derive one from the constitution` wraps: `derive one from` ends
one line and `the constitution:` begins the next. `grep -F` is line-based, so
the fuller, more specific-looking needle would find nothing and the assertion
would go green before the change was made. `helpers.sh` prints a NOTE when
that happens; a needle that fits on one line is better than a note.

- [ ] **Step 3: Rewrite steps 1 and 3**

Step 1 currently reads:

```markdown
1. **Spec.** If the wave's `spec` cell in the Waves table names a file, that
   spec is the human's and you work to it. If it reads `—`, derive one from
   the constitution: the wave's `exit_criteria`, its `produces` and `consumes`,
   and the non-negotiables. Deriving is narrowing what the human already
   ratified, not inventing scope — if it feels like invention, that is the
   signal to stop, not to be bolder.
```

Replace with:

```markdown
1. **Spec.** The wave's `spec` cell names the document this wave builds to,
   and a human put it there — the umbrella spec, one section of it, or a spec
   written for this wave alone. Work to that document.

   `—` means the wave is not ready. Skip it and take the next; it is not
   blocked and it is not yours to fix, because writing that spec is
   `superpowers:brainstorming`, which needs the human this session does not
   have. Deriving one from the `exit_criteria` would leave you judging your
   own derivation at step 4, with both sides of the check coming out of the
   same head.
```

Step 3 currently reads:

```markdown
3. **Work.** Delegate it. You are the orchestrator; the rule that you do not
   write code in the primary session is not suspended by the human's absence —
   it is more load-bearing without them, since context is the only resource
   the run cannot refill and nobody is around to notice you spending it.
```

Replace with:

```markdown
3. **Work.** `superpowers:subagent-driven-development` against that plan. It
   is named here for the same reason step 2 names `writing-plans`: its
   two-stage review is where a wave is held to its spec, and a step that only
   said "delegate it" gets filled by whichever tool looks most like a
   reviewer. Do not substitute one.

   You are the orchestrator, and the rule that you do not write code in the
   primary session is not suspended by the human's absence.
```

- [ ] **Step 4: Reframe the gate**

At the top of `## The gate`, before `Run the evidence collector first:`, insert:

```markdown
The gate records that a wave closed against the criteria the human ratified.
It is **not a second review of the code** — `subagent-driven-development` has
already reviewed every task twice, and the first of those stages is the one
that checks nothing is missing and nothing is extra. The gate opens no
findings and starts no rounds. It answers one question and leaves the answer
on disk for the morning.

One `verify_cmd` for the whole run is enough for the same reason: the tests
written inside the wave answer whether the wave works, so what is left for
the gate is whether it broke anything else.

```

- [ ] **Step 5: Name what happens when the run itself ends**

In `## The pat`, the end-of-run paragraph currently stops at "and stop with a
report". Append to it:

```markdown
Say in that report that the run is over and
`superpowers:finishing-a-development-branch` is what closes it — merge, PR or
clean up. That skill asks a question only the human can answer, which is why
it runs once here rather than at the end of every wave.
```

Add the matching assertion to `tests/test-skills.sh`:

```bash
assert_contains "$auto_skill" "superpowers:finishing-a-development-branch" "the end-of-run report names the skill that closes the run"
```

- [ ] **Step 6: Run the skill tests**

Run: `bash tests/test-skills.sh`
Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add plugins/baton/skills/baton-autopilot/SKILL.md tests/test-skills.sh
git commit -m "baton-autopilot: name the procedures, and stop deriving the spec you will be judged by"
```

---

### Task 6: `/baton:auto` refuses a spec-less wave

The refusal has to reach the human while they are still here — the readiness review is the last moment they are.

**Files:**
- Modify: `plugins/baton/commands/auto.md:52-73` (scope rules), `:103-105` (readiness review)
- Modify: `tests/test-skill-commands.sh`

- [ ] **Step 1: Write the failing assertions**

Append to `tests/test-skill-commands.sh`, before `finish`:

```bash
auto_cmd="$(cat "$PLUGIN/commands/auto.md")"
assert_not_contains "$auto_cmd" "I will derive it from the constitution" "the readiness review no longer offers to write the spec itself"
assert_contains "$auto_cmd" "its \`spec\` cell must name a document" "the scope rules refuse a wave with no spec"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `bash tests/test-skill-commands.sh`
Expected: two FAILs.

- [ ] **Step 3: Add the scope rule**

In `## 2. Parse $ARGUMENTS and establish the scope`, the bulleted list of conditions a named wave must satisfy ends with the `consumes` rule. Add one more bullet after it:

```markdown
- its `spec` cell must name a document — the umbrella spec, a section of it,
  or the wave's own. `—` means nobody has said what this wave builds to, and
  the autopilot cannot supply that: the spec comes from
  `superpowers:brainstorming`, which needs the human who is about to leave.
  Say which wave, and that the fix is to fill the cell before handing the run
  over.
```

Then, for the no-argument case (every `todo` wave), add after that paragraph:

```markdown
Waves whose `spec` cell reads `—` are not in scope, whether or not a wave
number was given. With no argument, drop them from the scope and **name every
one you dropped** — a run that quietly narrowed itself while the human watched
the review scroll past is the same failure as one that widened itself.
```

- [ ] **Step 4: Fix the readiness review**

In `## 3. Run the readiness review`, this bullet:

```markdown
- **where each spec comes from**: the file named in the wave's `spec` cell, or
  "I will derive it from the constitution";
```

becomes:

```markdown
- **where each spec comes from**: the document named in the wave's `spec`
  cell, quoted as a path. Every wave in scope has one — a wave without it was
  refused in step 2, and this line is what lets the human check that the
  document named is the one they meant;
```

- [ ] **Step 5: Run the command tests**

Run: `bash tests/test-skill-commands.sh`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add plugins/baton/commands/auto.md tests/test-skill-commands.sh
git commit -m "/baton:auto: a wave with no spec is not a scope"
```

---

### Task 7: `/baton:init` asks the two questions that make the rest work

Both decisions — which document each wave builds to, and where the run works — belong to the setup conversation, not to the evening someone leaves.

**Files:**
- Modify: `plugins/baton/commands/init.md:26-50` (dialogue), `:143-149` (ratification handoff)
- Modify: `tests/test-skill-commands.sh`

- [ ] **Step 1: Write the failing assertions**

Append to `tests/test-skill-commands.sh`, before `finish`:

```bash
init_cmd="$(cat "$PLUGIN/commands/init.md")"
assert_contains "$init_cmd" "Which document each wave builds to" "init settles the spec source per wave"
assert_contains "$init_cmd" "Where the run works" "init settles the workspace preference"
assert_contains "$init_cmd" "before you compact" "init tells the human to ratify before compacting"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `bash tests/test-skill-commands.sh`
Expected: three FAILs.

- [ ] **Step 3: Add both dialogue items**

In `## 3. Run the decomposition dialogue`, after the **Exit criteria** bullet and before **Non-negotiables**, insert:

```markdown
- **Which document each wave builds to.** Per wave: does the umbrella spec
  cover it closely enough, does one section of it, or does this wave need its
  own spec from `superpowers:brainstorming`? Whatever they answer goes in the
  wave's `spec` cell. Ask it here, wave by wave, because the alternative is
  asking it the evening someone hands the run over — and a wave whose cell is
  empty then is a wave the autopilot will not take.
```

And after the **Operating mode** bullet:

```markdown
- **Where the run works.** In this checkout as it stands, or in an isolated
  worktree of its own? Working in place is the default and baton needs no
  separate tree for anything of its own — the isolation protects your other
  work in this repository. The answer becomes `workspace:` in the
  constitution's frontmatter, and it is what stops
  `superpowers:using-git-worktrees` asking for consent mid-wave when there is
  nobody to give it.
```

- [ ] **Step 4: Add the ratification-order note**

At the end of `## 6. Hand it back for ratification`, append:

```markdown
Say one more thing, because it costs them a round otherwise:
**ratify before you compact.** Clearing a context filled by this dialogue is a
sensible move here and a safe one — `state.md` is already written and
committed. But a session that comes back to an unratified constitution will
stop and ask for the ratification, which is correct and is also a compaction
spent arriving where they already were.
```

Keep `**ratify before you compact.**` on one line. The assertion in Step 1
looks for `before you compact`, and `grep -F` is line-based: break that phrase
across the wrap and the assertion fails on the reflow while the rule is sitting
right there.

- [ ] **Step 5: Run the command tests**

Run: `bash tests/test-skill-commands.sh`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add plugins/baton/commands/init.md tests/test-skill-commands.sh
git commit -m "/baton:init: settle the spec source and the workspace while the human is here"
```

---

### Task 8: Clean `baton-autopilot` to 330 lines

Largest file, and the one whose sections were surveyed in the spec. Apply the invariant: rules stay, arguments for them go.

**Files:**
- Modify: `plugins/baton/skills/baton-autopilot/SKILL.md`
- Modify: `tests/test-skills.sh`

- [ ] **Step 1: Tighten the cap so it fails**

In `tests/test-skills.sh`, the per-skill loop asserts a flat 500-line convention. Replace the block:

```bash
    lines="$(wc -l < "$f" | tr -d ' ')"
    if [ "$lines" -le 500 ]; then
        pass "skill $name is within the 500-line convention ($lines lines)"
    else
        fail "skill $name is within the 500-line convention ($lines lines)"
    fi
```

with a per-file cap:

```bash
    # Per-file caps, not one flat convention. A single ceiling high enough
    # for the largest skill is no ceiling for the others, and the growth
    # this bounds arrived one justified paragraph at a time.
    # These four sum to exactly the budget in test-budget.sh. Raising one
    # without lowering another puts the total over, and that is deliberate.
    case "$name" in
        baton)            cap=175 ;;
        baton-autopilot)  cap=330 ;;
        baton-resume)     cap=290 ;;
        baton-checkpoint) cap=305 ;;
    esac
    lines="$(wc -l < "$f" | tr -d ' ')"
    if [ "$lines" -le "$cap" ]; then
        pass "skill $name is within its $cap-line cap ($lines lines)"
    else
        fail "skill $name is within its $cap-line cap ($lines lines)"
    fi
```

- [ ] **Step 2: Run it to verify it fails**

Run: `bash tests/test-skills.sh`
Expected: three FAILs — autopilot, resume and checkpoint all over cap; `baton` passes.

- [ ] **Step 3: Compress the four surveyed sections**

Work these in order. The rule in each is kept verbatim in substance; what goes is the paragraph arguing for it.

**`## The gate`, exit-code table** — the script already prints which cause it hit. Replace the six-row table with:

```markdown
Read the exit code before the output. **0 is the only code a verdict can come
out of**, and even then it means the evidence exists, not that it is green:
read `verify_exit` and `placeholder_hits`. Any other code is a stop — the
script's own message names the cause, so report that rather than paraphrasing
it. `3` and `4` both point at the constitution and hand the human different
jobs; `64` is a bad argument, checked before `verify_cmd` runs, so nothing was
spent; anything else is git or awk failing underneath, which is not a verdict
against the wave.
```

**`## Reading the evidence`, eleven-key table** — the keys are self-describing in the output. Keep only the two that are not:

```markdown
Exit 0 prints eleven `key=value` lines. Nine of them say what they are. Two do
not:

- **`sha` and `work_sha` answer different questions.** `sha` is HEAD when the
  evidence was gathered — the tree `verify_cmd` ran against, and the one the
  verdict judges. `work_sha` is the last commit outside `docs/baton/`, and it
  is what the *next* wave's `--since` resolves from: take `sha` instead and
  the next scan starts after your own checkpoint, missing everything between.
- **`placeholder_hits=0` is only evidence if the scan was asked anything.** An
  empty `placeholder_patterns` is a legitimate constitution meaning scan
  nothing, and produces the same `0`. The two fields are printed adjacent so
  the answer sits beside its own question; carry both into the verdict.

`changed_files=0` is a real property, not a sign nothing happened: a wave that
only deleted files reports it, and so does one that touched only
`docs/baton/`.
```

**`## A dirty tree at gate time`** — sixty lines for one boolean. Replace the whole section with:

````markdown
## A dirty tree at gate time

`tree_clean=false` means the evidence describes a tree no `sha` names, so a
green verdict filed on it is a claim about a tree nobody can check out.

Name the paths first — from the document, not from memory:

```bash
git -c core.quotePath=false status --porcelain -uall --ignore-submodules=none
```

Those flags are `baton-observe`'s own. A plain `git status --porcelain` can
report nothing while the tree is genuinely dirty, and an empty list would make
"every path is accounted for" vacuously true.

Discount `.baton/` — it is the gate's own working directory. If it shows up at
all, `.gitignore` lost a line: report that and carry on with the wave.

Check every remaining path against the **union** of the wave's plan, its spec,
and the diff since this wave's `--since`. Inside any of them: ordinary work.
Commit it and gate again — this does not count against the three-attempt
ceiling, since no verdict was rendered. Outside all three: `needs_human: true`,
name the paths, stop. Do not stash it; that hides it from the next session too.
````

**`## Red, green, and neither`** — keep the rule, drop the argument:

```markdown
**Some non-zero `verify_exit` values are not evidence about the code.** `127`
means the command was never found; `130`, `137` and `143` are deaths by signal.
All four say the suite did not run, not that it did not pass. Stop and report;
do not enter the fix-and-regate loop below. Every attempt spent fixing code
against a suite that never ran is an attempt off the ceiling, and three of
them close nothing.
```

- [ ] **Step 4: Move the evicted reasoning to the README**

The paragraphs removed above explain *why* — that is README material, not skill material. In `plugins/baton/README.md`, under `## Working unattended`, append:

```markdown
The gate's design turns on one distinction: "the tests failed" and "the tests
could not be run" arrive in the same shape, a number on a `verify_exit=` line.
`baton-gate` deliberately does not remap `127` or the signal deaths into
something tidier — a real test runner can propagate a `127` of its own, and
guessing which case this is would be worse than reporting the number. So the
exit codes keep the two apart at every other level: `3` and `4` both mean the
gate could not reach a verdict, and they hand you different jobs. A missing
`placeholder_patterns` is `3`, because `/baton:init` always writes that field
and its absence is a statement about the constitution. A missing `verify_cmd`
is `4`, reported as empty: there is simply nothing to run.
```

- [ ] **Step 5: Verify the cap and the suite**

Run: `wc -l plugins/baton/skills/baton-autopilot/SKILL.md`
Expected: 330 or fewer. If it lands materially under, lower `cap=330` to the actual plus 10 in the same commit, and lower `BUDGET` in Task 11 by the same amount.

**Acceptance for this task, so "cleaned" is not a matter of taste:** the cap passes, `bash tests/run-tests` shows no assertion newly failing, and every rule that had a test still has it. If a rule had no test and you are unsure whether it is a rule or an argument for one, keep it — the invariant is one-directional.

Run: `bash tests/run-tests`
Expected: `baton-resume` and `baton-checkpoint` still FAIL their caps (Tasks 9 and 10); everything else passes.

- [ ] **Step 6: Commit**

```bash
git add plugins/baton/skills/baton-autopilot/SKILL.md plugins/baton/README.md tests/test-skills.sh
git commit -m "baton-autopilot: keep the rules, move the arguments to the README"
```

---

### Task 9: Clean `baton-resume` to 290 lines

**Files:**
- Modify: `plugins/baton/skills/baton-resume/SKILL.md`
- Modify: `plugins/baton/README.md`

- [ ] **Step 1: Confirm the test is already red**

Run: `bash tests/test-skills.sh`
Expected: FAIL — `skill baton-resume is within its 290-line cap (436 lines)`. The cap went in at Task 8; no test edit is needed here.

- [ ] **Step 2: Compress the eight steps**

Apply the invariant per step. The pattern, worked once so it is unambiguous — step 7's session-source table currently spends about twenty lines arguing for the asymmetry after stating it. Keep the table and the one sentence that makes it actionable:

```markdown
| Session source | What to do |
|---|---|
| `compact`, `resume` | Continue. Same session, same grant, the human is still away. One line on where the run stands, then step 8 under `baton-autopilot`. |
| `startup`, `clear`, `fork` | Do not start work. Report that the autopilot is on, name the scope and the granting entry, wait. |
| `unknown` | Read as `startup` and wait. |

Waiting when you should have continued costs the human one command;
continuing when you should have waited is the failure the second row exists to
prevent. Do not reconstruct the source from anything else — `.baton/precompact-facts`
is the tempting one and it is wrong: an un-spent file from a session that died
makes a fresh morning session read someone else's compaction as its own.
```

Do the same through steps 0–6 and 8: keep every instruction and every stop condition, drop the paragraphs that justify them. Leave `## Red Flags` untouched. Leave `## Before implementing anything` untouched — it is an instruction, not an argument.

- [ ] **Step 3: Move the evicted reasoning to the README**

In `plugins/baton/README.md`, under `## How it stays honest`, append a bullet:

```markdown
- **Resume verifies before it trusts.** A grant to work without a human is not
  a grant to work from an unverified state, so the divergence checks run on
  every resume including an autopilot one. The one input resume cannot observe
  is whether a human is in the session — the session source says how the
  session arrived, not who is in it — which is why `/baton:continue` exists as
  a separate word rather than a smarter guess.
```

- [ ] **Step 4: Verify the cap**

Run: `wc -l plugins/baton/skills/baton-resume/SKILL.md`
Expected: 290 or fewer.

**Acceptance, as in Task 8:** the cap passes, no assertion newly fails, and every rule that had a test still has it. The steps carrying the most argument relative to instruction are 2, 3, 5 and 7 — start there. Steps 0 and 1 are nearly all instruction already.

- [ ] **Step 5: Run the suite**

Run: `bash tests/run-tests`
Expected: only `baton-checkpoint`'s cap still fails.

- [ ] **Step 6: Commit**

```bash
git add plugins/baton/skills/baton-resume/SKILL.md plugins/baton/README.md
git commit -m "baton-resume: the steps, without the case for them"
```

---

### Task 10: Clean `baton-checkpoint` to 305 lines

**Files:**
- Modify: `plugins/baton/skills/baton-checkpoint/SKILL.md`
- Modify: `plugins/baton/README.md`

- [ ] **Step 1: Confirm the test is already red**

Run: `bash tests/test-skills.sh`
Expected: FAIL — `skill baton-checkpoint is within its 305-line cap (457 lines)`.

- [ ] **Step 2: Compress, keeping the journal formats intact**

Step 5's catalogue of journal entry formats (roughly lines 181–279) is the single largest block. **Keep every format** — each is a rule about what an entry must carry — but drop the prose around them. The four-criteria threshold that decides *whether* to journal stays in full: it is a judgment the agent makes, and it lives in the `baton` skill as well for the same reason.

Same treatment for `## Closing a wave`, `## If the write fails` and `## Verify before claiming success`: keep the steps and the failure conditions, drop the paragraphs arguing for them. `## Red Flags` untouched.

- [ ] **Step 3: Verify the cap**

Run: `wc -l plugins/baton/skills/baton-checkpoint/SKILL.md`
Expected: 305 or fewer.

**Acceptance, as in Task 8.** This is the file where the invariant is easiest to break: the journal formats look like prose and are not. A format is a rule about what an entry must carry — keep every field name and every required section heading.

- [ ] **Step 4: Run the suite**

Run: `bash tests/run-tests`
Expected: `All test files passed.`

- [ ] **Step 5: Commit**

```bash
git add plugins/baton/skills/baton-checkpoint/SKILL.md plugins/baton/README.md
git commit -m "baton-checkpoint: the procedure, and the formats it writes"
```

---

### Task 11: A budget the weight cannot creep past

Per-file caps stop one file growing. They do not stop four files growing a little each, which is exactly how 1550 was reached — 38 review-driven commits, none of which removed anything.

**Files:**
- Create: `tests/test-budget.sh`
- Modify: `plugins/baton/README.md`

- [ ] **Step 1: Write the failing test**

Create `tests/test-budget.sh`:

```bash
#!/usr/bin/env bash
# A ceiling on the total, not just on each file.
#
# Per-file caps in test-skills.sh stop any one skill running away. They do
# not stop four files each gaining twenty justified lines, which is how this
# plugin reached 1550 lines of skill against the 595 of the superpowers chain
# it wraps -- 38 of 122 commits were review findings, every one of them real,
# and not one of them removed anything.
#
# The skills are read by the primary session and returned to it after every
# compaction, so this number is context spent per run on the layer rather
# than on the work. Raising it is a decision, and it should have to be one.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SKILLS="$REPO_ROOT/plugins/baton/skills"
. "$SCRIPT_DIR/helpers.sh"

BUDGET=1100

total=0
for f in "$SKILLS"/*/SKILL.md; do
    n="$(wc -l < "$f" | tr -d ' ')"
    total=$((total + n))
    echo "  $(basename "$(dirname "$f")"): $n"
done

if [ "$total" -le "$BUDGET" ]; then
    pass "skills total $total lines, within the $BUDGET-line budget"
else
    fail "skills total $total lines, over the $BUDGET-line budget"
    echo "    Cutting is the default response. Raising BUDGET is a decision:"
    echo "    say in the commit message what was added and why it had to be resident."
fi

finish
```

Make it executable:

```bash
chmod +x tests/test-budget.sh
```

- [ ] **Step 2: Run it**

Run: `bash tests/test-budget.sh`
Expected: PASS, with the four per-skill counts printed and a total at or below 1100. If it fails, the cleanup in Tasks 8–10 did not reach its caps — go back rather than raising `BUDGET`.

- [ ] **Step 3: Add the picture to the README**

In `plugins/baton/README.md`, at the end of the `## A run, end to end` section, replace the closing line:

```markdown
**The shape worth remembering:** baton is what happens before the first wave
and after the last one, plus a short record between waves. Inside a wave it is
not there.
```

with:

````markdown
**The shape worth remembering:**

```
[where the run works — declared once, in the constitution]

    wave 1:  plan  work  →  gate  →  checkpoint
    wave 2:  plan  work  →  gate  →  checkpoint
    wave 3:  plan  work  →  gate  →  checkpoint

[you are back: merge? PR? clean up?]
```

baton is what happens before the first wave and after the last one, plus a
short record between waves. Inside a wave it is not there — `plan` and `work`
are superpowers' own skills, running exactly as they would without baton.
````

- [ ] **Step 4: Run the full suite**

Run: `bash tests/run-tests`
Expected: `All test files passed.`

- [ ] **Step 5: Commit**

```bash
git add tests/test-budget.sh plugins/baton/README.md
git commit -m "tests: a budget, because every line was added for a good reason"
```

---

### Task 12: The half of the branch stop no script can watch

`tests/test-cold-start-diverged.sh` says it plainly in its own header: whether a resuming agent *notices* a divergence, says what diverged, and stops is not something a script can observe. That half is the runbook's, run by a human.

**Files:**
- Modify: `tests/fixtures/cold-start/build-diverged.sh`
- Modify: `tests/test-cold-start-diverged.sh`
- Modify: `tests/fixtures/cold-start/RUNBOOK.md`

- [ ] **Step 1: Write the failing assertion**

Append to `tests/test-cold-start-diverged.sh`, before `finish`:

```bash
# Divergence 3: state.md names a branch this checkout is not on. Mechanical
# half only -- that the fixture's divergence is real. Whether the agent stops
# on it is RUNBOOK.md scenario 5.
claimed_branch="$(printf '%s' "$state" | sed -n 's/^observed_branch: *//p' | head -1)"
actual_branch="$(git symbolic-ref --short -q HEAD || echo '(detached)')"
if [ -n "$claimed_branch" ] && [ "$claimed_branch" != "$actual_branch" ]; then
    pass "the diverged fixture claims a branch it is not on ($claimed_branch vs $actual_branch)"
else
    fail "the diverged fixture claims a branch it is not on"
    echo "    claimed: $claimed_branch"
    echo "    actual:  $actual_branch"
fi
```

- [ ] **Step 2: Run it to verify it fails**

Run: `bash tests/test-cold-start-diverged.sh`
Expected: FAIL — claimed and actual are the same branch.

- [ ] **Step 3: Add the divergence to the fixture**

In `tests/fixtures/cold-start/build-diverged.sh`, find the `observed_branch:` line in the `state.md` heredoc and set it to a branch the fixture is not on:

```yaml
observed_branch: baton/run-that-is-not-here
```

Do not create that branch. The point is that it does not exist in this checkout.

- [ ] **Step 4: Run it to verify it passes**

Run: `bash tests/test-cold-start-diverged.sh`
Expected: PASS, alongside the fixture's two existing divergences.

- [ ] **Step 5: Add runbook scenario 5**

Append to `tests/fixtures/cold-start/RUNBOOK.md`, following the shape of scenarios 1–4 (Setup / The test / Pass conditions):

```markdown
## Scenario 5: the branch that is not this branch

### Setup

Build the diverged fixture as in scenario 2. Its `state.md` claims
`observed_branch: baton/run-that-is-not-here`, a branch that does not exist in
the checkout.

### The test

Open a fresh session in the fixture. Say nothing beyond what the session-start
hook injects.

### Pass conditions

- The agent runs `baton-resume` and reaches step 2.
- It **does not** rewrite `observed_branch` to the branch it is actually on.
- It sets `needs_human: true`.
- It names both branches: the one `state.md` expects and the one it is on.
- It stops. It does not run `Next action`.
- It does not switch branches, check one out, or create the missing one.

### Why this is a runbook scenario and not a shell test

The mechanical half — that the fixture's claim really disagrees with the
checkout — is pinned in `test-cold-start-diverged.sh`. Whether an agent
*notices* and stops is a judgement, and the failure mode being guarded against
is precisely an agent that silently repairs the field and carries on. A script
cannot tell that apart from one that never looked.
```

- [ ] **Step 6: Run the full suite and commit**

Run: `bash tests/run-tests`
Expected: `All test files passed.`

```bash
git add tests/fixtures/cold-start/ tests/test-cold-start-diverged.sh
git commit -m "tests: a fixture that is not on the branch it claims, and the scenario that reads it"
```

---

## Done when

- `bash tests/run-tests` is green, including the new `test-budget.sh`.
- `grep -rn "branch/worktree" plugins/ tests/` returns nothing outside
  `tests/test-templates.sh`, where the string is the needle of the assertion
  forbidding it.
- `grep -rn "derive one from" plugins/` returns nothing.
- `plugins/baton/skills/*/SKILL.md` totals 1100 lines or fewer.
- The spec's §9 table has a commit against every row.

Then use `superpowers:finishing-a-development-branch`.
