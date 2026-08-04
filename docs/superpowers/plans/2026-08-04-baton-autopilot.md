# baton autopilot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a human hand a baton run over to the agent with `/baton:auto`, walk away, and find in the morning either closed waves with a verdict file behind each one, or a single named point where the run stopped.

**Architecture:** One new script gathers the mechanical half of a wave gate (`verify_cmd` plus a placeholder scan) and decides nothing; the agent walks the EARS exit criteria and files a verdict under `docs/baton/gates/`. The grant to work unattended lives in `state.md` frontmatter, not in a chat turn, so it survives compaction — and it is asymmetric: only a human-typed command sets it, any party may clear it.

**Tech Stack:** POSIX-ish bash (macOS `/bin/bash` 3.2 and GNU bash both), git, the existing `tests/run-tests` harness with `tests/helpers.sh`. No new dependencies. Python3 is used by the harness only.

**Spec:** `docs/superpowers/specs/2026-08-04-baton-autopilot-design.md`

**Branch:** `baton-autopilot` (already created, holds the spec commit `c015daa`).

---

## File Structure

| Path | Responsibility |
|---|---|
| `plugins/baton/scripts/baton-gate` | **New.** Gathers evidence: reads `verify_cmd` / `placeholder_patterns` from the constitution, runs the command, scans changed files. Prints `key=value`. Knows nothing about waves and closes nothing. |
| `plugins/baton/commands/auto.md` | **New.** `/baton:auto [wave]` — the readiness review, the human's "go", the grant. Human-invocable only. |
| `plugins/baton/commands/continue.md` | **New.** `/baton:continue` — pick the run back up on a fresh session. Human-invocable only. |
| `plugins/baton/skills/baton-autopilot/SKILL.md` | **New.** The model of unattended work: the wave loop, the verdict, the pat, the five things autonomy never covers. |
| `plugins/baton/templates/state.md` | Two frontmatter fields plus the `gate` column legend. |
| `plugins/baton/skills/baton-checkpoint/SKILL.md` | "Closing a wave" grows a second path; the first one is unchanged. |
| `plugins/baton/skills/baton-resume/SKILL.md` | Pick the grant up; decide silent-continue vs ask by session source. |
| `plugins/baton/skills/baton/SKILL.md` | Granted fields as a third kind; the three `gate` values; two Red Flags. |
| `plugins/baton/commands/status.md` | Show the mode and its scope. |
| `plugins/baton/hooks/session-start` | One injected line when the autopilot is on. |
| `tests/test-gate.sh` | **New.** Everything mechanical about `baton-gate`. |
| `tests/fixtures/cold-start/build-autopilot.sh` | **New.** Fourth fixture: a run on autopilot with one blocked wave. |
| `tests/test-cold-start-autopilot.sh` | **New.** Pins that fixture's premise. |
| `tests/test-skills.sh`, `tests/test-commands.sh`, `tests/test-templates.sh`, `tests/test-hooks.sh`, `tests/test-skill-commands.sh` | Assertions for each decision that would otherwise weather out of the prose. |
| `tests/fixtures/cold-start/RUNBOOK.md` | Scenario 4, run by a human. |
| `README.md` | New commands; the "what's not built yet" section shrinks by half. |

**Task order rationale:** the script first (Tasks 1–4), because every document downstream describes calling it; then the state shape (Task 5), because the skills reference the fields; then the prose (Tasks 6–12); then hook, fixture, runbook, README (Tasks 13–16).

---

## Task 1: `baton-gate` — guards and usage

**Files:**
- Create: `plugins/baton/scripts/baton-gate`
- Create: `tests/test-gate.sh`

- [ ] **Step 1: Write the failing test**

Create `tests/test-gate.sh`:

```bash
#!/usr/bin/env bash
# baton-gate gathers the mechanical half of a wave gate and decides nothing.
# The distinction this file exists to pin is the exit code: a red verify_cmd
# is exit 0 with verify_exit non-zero, because "the tests failed" and "the
# gate is broken" need opposite responses from the only caller there is.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
GATE="$REPO_ROOT/plugins/baton/scripts/baton-gate"
. "$SCRIPT_DIR/helpers.sh"

# Write a ratified constitution carrying the given verify_cmd.
write_constitution() {
    mkdir -p docs/baton
    cat > docs/baton/constitution.md <<EOF
---
schema: baton/constitution/v1
run_id: gate-fixture
status: ratified
verify_cmd: "$1"
placeholder_patterns: "${2:-TODO|FIXME}"
---

# Gate fixture

## Waves

\`\`\`yaml
- wave: 1
  name: one
  depends_on: []
  exit_criteria:
    - The system shall work
\`\`\`
EOF
}

make_fixture_repo
base="$(git rev-parse HEAD)"

# --- usage ---
assert_exit_code 64 "refuses to run without --since" "$GATE"
assert_exit_code 64 "refuses an empty --since" "$GATE" --since ""
assert_exit_code 64 "refuses an unknown flag" "$GATE" --wave 2

# --- the constitution guards ---
assert_exit_code 3 "refuses when there is no constitution" "$GATE" --since "$base"

write_constitution "true"
sed -i.bak 's/^status: ratified$/status: draft/' docs/baton/constitution.md
rm -f docs/baton/constitution.md.bak
assert_exit_code 3 "refuses an unratified constitution" "$GATE" --since "$base"

write_constitution "true"
printf 'REPLACE-WITH-SOMETHING\n' >> docs/baton/constitution.md
assert_exit_code 3 "refuses a constitution with an unfilled placeholder marker" "$GATE" --since "$base"

# --- a SHA that is not a commit is a usage error, not a git crash ---
write_constitution "true"
assert_exit_code 64 "refuses a --since that is not a commit" "$GATE" --since "not-a-sha"

finish
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bash tests/test-gate.sh`
Expected: FAIL on every assertion — the first ones report exit `127` (file not found) against an expected `64`.

- [ ] **Step 3: Write minimal implementation**

Create `plugins/baton/scripts/baton-gate`:

```bash
#!/usr/bin/env bash
# Gather the mechanical half of a wave gate: run the constitution's
# verify_cmd, and scan the files a wave touched for placeholder markers.
#
# This script decides nothing. It does not know what a wave is, does not
# read state.md, and never sets a status. Exit criteria are EARS prose and
# only the agent can check them; what a machine can establish is what this
# collects, so that the agent's verdict has something under it besides
# recollection.
#
# Exit codes:
#   0   evidence gathered -- read verify_exit and placeholder_hits. A red
#       gate is exit 0 with verify_exit non-zero, NOT a non-zero exit of
#       this script. A script that exited non-zero both when the tests
#       failed and when it could not run them would make those two
#       indistinguishable to its only caller, and they call for opposite
#       responses: fix the code, versus stop and report the tooling.
#   1   not a git repository
#   3   docs/baton/constitution.md is missing, is not ratified, or still
#       carries an unfilled placeholder marker
#   4   verify_cmd is empty, or names a command that cannot be run
#   64  usage error, including a --since that is not a commit
set -euo pipefail

usage() { echo "usage: baton-gate --since <SHA>" >&2; exit 64; }

since=""
while [ $# -gt 0 ]; do
    case "$1" in
        --since)
            [ $# -ge 2 ] || usage
            since="$2"
            shift 2
            ;;
        -h|--help) usage ;;
        *) usage ;;
    esac
done
[ -n "$since" ] || usage

if ! git rev-parse --git-dir >/dev/null 2>&1; then
    echo "baton-gate: not a git repository" >&2
    exit 1
fi

# baton-write, baton-lock, baton-journal and baton-observe were each fixed
# for this once already: invoked from a subdirectory, every relative path
# below names something that is not there.
cd "$(git rev-parse --show-toplevel)"

constitution="docs/baton/constitution.md"
if [ ! -f "$constitution" ]; then
    echo "baton-gate: $constitution not found: there is no run here to gate" >&2
    exit 3
fi

# Lines between the opening and closing --- only. A "status:" further down
# in the prose is not the frontmatter's.
frontmatter="$(awk 'NR==1 && $0=="---" { infm=1; next } infm && $0=="---" { exit } infm { print }' "$constitution")"

fm_field() {
    printf '%s\n' "$frontmatter" | sed -n "s/^$1: *//p" | head -1
}

# One layer of surrounding quotes, since verify_cmd is conventionally
# written quoted and placeholder_patterns always is.
unquote() {
    local s="$1"
    case "$s" in
        \"*\") s="${s#\"}"; s="${s%\"}" ;;
        \'*\') s="${s#\'}"; s="${s%\'}" ;;
    esac
    printf '%s' "$s"
}

status="$(fm_field status)"
if [ "$status" != "ratified" ]; then
    echo "baton-gate: constitution status is '${status:-unset}', not ratified: gating a run that was never handed over judges work against rules nobody signed" >&2
    exit 3
fi

if grep -q 'REPLACE-WITH' "$constitution"; then
    echo "baton-gate: the constitution still carries an unfilled placeholder marker; it has not been ratified whatever its status field says" >&2
    exit 3
fi

if ! git rev-parse --verify -q "${since}^{commit}" >/dev/null 2>&1; then
    echo "baton-gate: --since '$since' is not a commit in this repository" >&2
    exit 64
fi

exit 0
```

- [ ] **Step 4: Make it executable and run the test**

```bash
chmod +x plugins/baton/scripts/baton-gate
bash tests/test-gate.sh
```

Expected: every assertion PASSes; the file ends with no `assertion(s) failed` line.

- [ ] **Step 5: Commit**

```bash
git add plugins/baton/scripts/baton-gate tests/test-gate.sh
git commit -m "baton-gate: the guards, before anything is gathered"
```

---

## Task 2: `baton-gate` — running `verify_cmd`

**Files:**
- Modify: `plugins/baton/scripts/baton-gate` (append after the `--since` validation)
- Modify: `tests/test-gate.sh` (append before `finish`)

- [ ] **Step 1: Write the failing test**

Insert into `tests/test-gate.sh`, immediately before the closing `finish`:

```bash
# --- verify_cmd: the evidence, and the exit code that is NOT the evidence ---
write_constitution "true"
out="$("$GATE" --since "$base")"
assert_contains "$out" "verify_exit=0" "a green verify_cmd reports verify_exit=0"
assert_contains "$out" "verify_cmd=true" "the evidence names the command that was run"
assert_exit_code 0 "a green verify_cmd exits 0" "$GATE" --since "$base"

write_constitution "false"
out="$("$GATE" --since "$base")"
assert_contains "$out" "verify_exit=1" "a red verify_cmd reports its exit code"
assert_exit_code 0 "a RED verify_cmd still exits 0 -- the script reports, it does not judge" \
    "$GATE" --since "$base"

# The log is where the agent reads what actually broke, so it has to exist
# and hold the command's own output.
write_constitution "echo boom-from-the-verify-command; exit 3"
out="$("$GATE" --since "$base")"
assert_contains "$out" "verify_exit=3" "the exact non-zero exit code is passed through, not flattened to 1"
assert_file_exists ".baton/gate-verify.log" "the command's output is captured to a log"
assert_contains "$(cat .baton/gate-verify.log)" "boom-from-the-verify-command" \
    "the log holds the command's own output"

# .baton/ is gitignored in a real run, which is why the log goes there: a
# gate that dirtied the tree would trip the next checkpoint's tree_clean.
assert_contains "$out" "verify_log=.baton/gate-verify.log" "the evidence names where the log went"

# A command that cannot be run at all is the script failing, not the gate.
write_constitution ""
assert_exit_code 4 "refuses an empty verify_cmd" "$GATE" --since "$base"
write_constitution "definitely-not-a-real-command-9d3f"
assert_exit_code 4 "refuses a verify_cmd whose command does not exist" "$GATE" --since "$base"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bash tests/test-gate.sh`
Expected: the new assertions FAIL — `verify_exit=0` is not found because the script currently prints nothing, and the exit-4 assertions report `0`.

- [ ] **Step 3: Write minimal implementation**

In `plugins/baton/scripts/baton-gate`, replace the final `exit 0` with:

```bash
verify_cmd="$(unquote "$(fm_field verify_cmd)")"
if [ -z "$verify_cmd" ]; then
    echo "baton-gate: verify_cmd is empty in the constitution: there is nothing to run, so there is no evidence to gather" >&2
    exit 4
fi

# The first word only. verify_cmd is a shell line, so this misses the case
# where the missing binary is the second command in a pipeline -- that one
# surfaces as a non-zero verify_exit instead, which is the correct reading
# anyway: the suite ran and did not pass.
verify_bin="${verify_cmd%% *}"
if ! command -v "$verify_bin" >/dev/null 2>&1; then
    echo "baton-gate: verify_cmd names '$verify_bin', which is not runnable here" >&2
    exit 4
fi

# .baton/ is gitignored by every /baton:init'd repository, which is the
# point: a gate run that left an untracked log behind would show up as a
# dirty tree at the next checkpoint and read as work in flight.
mkdir -p .baton
verify_log=".baton/gate-verify.log"
verify_exit=0
sh -c "$verify_cmd" > "$verify_log" 2>&1 || verify_exit=$?

printf 'verify_cmd=%s\n' "$verify_cmd"
printf 'verify_exit=%s\n' "$verify_exit"
printf 'verify_log=%s\n' "$verify_log"
exit 0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `bash tests/test-gate.sh`
Expected: all assertions PASS.

- [ ] **Step 5: Commit**

```bash
git add plugins/baton/scripts/baton-gate tests/test-gate.sh
git commit -m "baton-gate: run the verification, report it as a fact"
```

---

## Task 3: `baton-gate` — the placeholder scan

**Files:**
- Modify: `plugins/baton/scripts/baton-gate`
- Modify: `tests/test-gate.sh`

- [ ] **Step 1: Write the failing test**

Insert into `tests/test-gate.sh`, immediately before `finish`:

```bash
# --- the placeholder scan runs over what the wave touched ---
write_constitution "true"
git add docs/baton/constitution.md
git commit -q -m "baton: constitution"

# A marker that predates --since, in a file nothing has touched since,
# is not this wave's business.
printf 'const old = 1; // TODO: from before the wave\n' > old.js
git add old.js
git commit -q -m "old work with a marker"
scan_base="$(git rev-parse HEAD)"

out="$("$GATE" --since "$scan_base")"
assert_contains "$out" "placeholder_hits=0" "a marker outside the wave's diff is not counted"

printf 'export function renew() { /* TODO: finish */ }\n' > new.js
git add new.js
git commit -q -m "wave work with a marker"
out="$("$GATE" --since "$scan_base")"
assert_contains "$out" "placeholder_hits=1" "a marker in a file the wave touched is counted"
assert_contains "$out" "placeholder_files=new.js" "the evidence names the file the marker is in"
assert_contains "$out" "changed_files=1" "the evidence counts the files considered"

# An uncommitted file is the most common shape of in-flight work and must
# be seen -- baton-observe already reports it, this must not filter it out.
printf 'const x = 1; // FIXME\n' > uncommitted.js
out="$("$GATE" --since "$scan_base")"
assert_contains "$out" "placeholder_hits=2" "an uncommitted file is scanned too"
rm -f uncommitted.js

# baton's own files are excluded: a journal entry describing a TODO, or a
# gate verdict quoting one, is prose about the work, not a stub in it.
mkdir -p docs/baton/journal
printf 'A decision about the TODO markers we allow.\n' > docs/baton/journal/0001-note.md
out="$("$GATE" --since "$scan_base")"
assert_contains "$out" "placeholder_hits=1" "docs/baton/ is excluded from the scan"
rm -f docs/baton/journal/0001-note.md

# An empty pattern list means no scan, not a pattern that matches
# everything: grep -E '' matches every line.
write_constitution "true" ""
out="$("$GATE" --since "$scan_base")"
assert_contains "$out" "placeholder_hits=0" "an empty placeholder_patterns scans nothing rather than matching everything"

# --- invoked from a subdirectory, same answer ---
write_constitution "true"
mkdir -p deep/nested
out_root="$("$GATE" --since "$scan_base")"
out_deep="$(cd deep/nested && "$GATE" --since "$scan_base")"
assert_equals "$out_deep" "$out_root" "invoked from a subdirectory it reports the same evidence"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bash tests/test-gate.sh`
Expected: the new assertions FAIL — `placeholder_hits=` appears nowhere in the output yet.

- [ ] **Step 3: Write minimal implementation**

In `plugins/baton/scripts/baton-gate`, replace the final `printf`/`exit 0` block with:

```bash
patterns="$(unquote "$(fm_field placeholder_patterns)")"

script_dir="$(cd "$(dirname "$0")" && pwd)"
changed="$("$script_dir/baton-observe" --changed-since "$since")"

placeholder_hits=0
placeholder_files=""
changed_files=0
while IFS= read -r f; do
    [ -n "$f" ] || continue
    # Deleted paths still appear in the diff; there is nothing to scan.
    [ -f "$f" ] || continue
    # baton's own files describe the work rather than being it. A journal
    # entry that says "we agreed to allow TODO here" is not a stub, and a
    # gate verdict that quotes one is evidence about a scan, not a subject
    # of it. This is the same exclusion baton-observe applies for work_sha.
    case "$f" in
        docs/baton/*) continue ;;
    esac
    changed_files=$((changed_files + 1))
    # An empty pattern list is a legitimate choice by the human who owns
    # the constitution. It must mean "scan nothing" -- grep -E '' matches
    # every line, so treating it as a pattern would fail every gate.
    [ -n "$patterns" ] || continue
    if grep -Eq -- "$patterns" "$f" 2>/dev/null; then
        placeholder_hits=$((placeholder_hits + 1))
        placeholder_files="${placeholder_files:+$placeholder_files,}$f"
    fi
done <<EOF
$changed
EOF

printf 'verify_cmd=%s\n' "$verify_cmd"
printf 'verify_exit=%s\n' "$verify_exit"
printf 'verify_log=%s\n' "$verify_log"
printf 'placeholder_hits=%s\n' "$placeholder_hits"
printf 'placeholder_files=%s\n' "$placeholder_files"
printf 'changed_files=%s\n' "$changed_files"
printf 'since=%s\n' "$since"
printf 'sha=%s\n' "$(git rev-parse HEAD)"
exit 0
```

Add to the script's header comment, after the exit-code table:

```bash
# Known limitation, deliberate: the scan reads whole files that changed
# since --since, not only the changed hunks. A marker that predates the
# wave, sitting in a file the wave touched for an unrelated reason, is
# counted. That is the reading that fails safe -- a file the wave edited is
# a file the wave is answerable for -- and hunk-level attribution would
# make the gate depend on diff context size, which is not a property of
# the work.
```

- [ ] **Step 4: Run test to verify it passes**

Run: `bash tests/test-gate.sh`
Expected: all assertions PASS.

- [ ] **Step 5: Commit**

```bash
git add plugins/baton/scripts/baton-gate tests/test-gate.sh
git commit -m "baton-gate: scan what the wave touched, and only that"
```

---

## Task 4: `baton-gate` — the tree fact, and wiring into the suite

**Files:**
- Modify: `plugins/baton/scripts/baton-gate`
- Modify: `tests/test-gate.sh`
- Modify: `tests/test-manifests.sh`

- [ ] **Step 1: Write the failing test**

Insert into `tests/test-gate.sh` before `finish`:

```bash
# --- tree_clean travels with the evidence ---
# A verdict filed against a dirty tree is a verdict about something that
# was never committed, so the agent needs this fact in the same breath as
# the rest, not from a second call.
git add -A
git commit -q -m "settle the tree"
out="$("$GATE" --since "$scan_base")"
assert_contains "$out" "tree_clean=true" "reports a clean tree"
printf 'scratch\n' > scratch.txt
out="$("$GATE" --since "$scan_base")"
assert_contains "$out" "tree_clean=false" "reports a dirty tree"
rm -f scratch.txt

# --- not a git repository ---
outside="$(mktemp -d)"
assert_exit_code 1 "refuses to run outside a git repository" \
    env -C "$outside" "$GATE" --since "$scan_base"
rm -rf "$outside"
```

Append to `tests/test-manifests.sh`, before its `finish`:

```bash
assert_file_exists "$REPO_ROOT/plugins/baton/scripts/baton-gate" "baton-gate ships with the plugin"
if [ -x "$REPO_ROOT/plugins/baton/scripts/baton-gate" ]; then
    pass "baton-gate is executable"
else
    fail "baton-gate is executable"
fi
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bash tests/test-gate.sh && bash tests/test-manifests.sh`
Expected: `tree_clean=true` is not found (the script does not print it); the manifest executable check may already pass from Task 1 — that is fine, the `tree_clean` assertions are the RED here.

- [ ] **Step 3: Write minimal implementation**

In `plugins/baton/scripts/baton-gate`, add before `exit 0`:

```bash
# Read from baton-observe rather than recomputed: it already handles
# status.showUntrackedFiles=no and quotePath, both of which have hidden a
# dirty tree from this suite before.
tree_clean="$("$script_dir/baton-observe" | sed -n 's/^tree_clean=//p' | head -1)"
printf 'tree_clean=%s\n' "$tree_clean"
```

Note `env -C` in the test requires coreutils `env` supporting `-C` (GNU) or macOS 13+. If it is unavailable, replace that assertion with a subshell:

```bash
rc=0
( cd "$outside" && "$GATE" --since "$scan_base" ) >/dev/null 2>&1 || rc=$?
assert_equals "$rc" "1" "refuses to run outside a git repository"
```

Use the subshell form; it has no portability question at all.

- [ ] **Step 4: Run test to verify it passes**

Run: `bash tests/run-tests`
Expected: `All test files passed.`

- [ ] **Step 5: Commit**

```bash
git add plugins/baton/scripts/baton-gate tests/test-gate.sh tests/test-manifests.sh
git commit -m "baton-gate: the tree fact belongs with the rest of the evidence"
```

---

## Task 5: The state shape — two fields and the gate legend

**Files:**
- Modify: `plugins/baton/templates/state.md`
- Modify: `tests/test-templates.sh`

- [ ] **Step 1: Write the failing test**

Append to `tests/test-templates.sh` before `finish`:

```bash
# The grant has to live on disk or it does not survive the compaction it
# exists to survive. Frontmatter, not prose, because baton-resume and the
# session-start hook both read it without parsing the body.
assert_contains "$state" "autopilot: off" "state carries the autopilot flag, defaulting to off"
assert_contains "$state" "autopilot_grant:" "state points at the journal entry that granted autonomy"

# Three values, and the fact that two of them mean different things, is
# the whole point -- see the v0.1.0 runbook run, where an agent wrote pass
# into a column nothing claimed ownership of.
assert_contains "$state" "auto\` closed under the autopilot" "state's gate legend distinguishes auto from pass"

lines3="$(wc -l < "$TPL/state.md" | tr -d ' ')"
if [ "$lines3" -le 60 ]; then
    pass "state template is still within the 60-line cap after the autopilot fields ($lines3 lines)"
else
    fail "state template is still within the 60-line cap after the autopilot fields ($lines3 lines)"
fi
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bash tests/test-templates.sh`
Expected: FAIL — `autopilot: off`, `autopilot_grant:` and the legend line are all absent.

- [ ] **Step 3: Write minimal implementation**

In `plugins/baton/templates/state.md`, add to the frontmatter after `needs_human: false`:

```yaml
# Granted, not observed and not claimed: only a human turns this on, with
# /baton:auto, and any party may turn it off. off | all | <wave number>.
autopilot: off
autopilot_grant: —
```

And after the `**Status:**` legend lines, add:

```markdown
**Gate:** `—` nothing produced a verdict; `auto` closed under the autopilot,
verdict in `docs/baton/gates/`; `pass` a human confirmed it.
```

- [ ] **Step 4: Run test to verify it passes**

Run: `bash tests/test-templates.sh`
Expected: PASS, including the 60-line cap check.

- [ ] **Step 5: Commit**

```bash
git add plugins/baton/templates/state.md tests/test-templates.sh
git commit -m "state: the grant, and a gate column that says who filled it"
```

---

## Task 6: The autopilot skill

**Files:**
- Create: `plugins/baton/skills/baton-autopilot/SKILL.md`
- Modify: `tests/test-skills.sh`

- [ ] **Step 1: Write the failing test**

In `tests/test-skills.sh`, extend the loop on line 8 to include the new skill:

```bash
for name in baton baton-checkpoint baton-resume baton-autopilot; do
```

Then append before `finish`:

```bash
autopilot="$(cat "$SKILLS/baton-autopilot/SKILL.md")"

# The asymmetry is the whole safety story. Stated once in prose, it is the
# first thing to go when the file is next edited for length.
assert_contains "$autopilot" "may always turn it off, and never on" \
    "autopilot skill states the asymmetry: the agent clears the grant, never sets it"

# Eligibility has three conditions and the third is the one that would be
# dropped as pedantic -- two waves can be independent in the graph and
# still share a contract the blocked wave was to define.
assert_contains "$autopilot" "transitive" \
    "autopilot skill requires the whole transitive dependency closure to be done"
assert_contains "$autopilot" "consumes" \
    "autopilot skill excludes a wave that consumes what a blocked wave produces"

# The pat is bounded by evidence first and a counter second.
assert_contains "$autopilot" "unchanged evidence" \
    "autopilot skill names unchanged evidence as the signal that fixing has stopped being fixing"
assert_contains "$autopilot" "three attempts" "autopilot skill states the absolute ceiling"
assert_contains "$autopilot" "In flight" \
    "autopilot skill keeps the attempt counter in state.md, not in the session"

# What autonomy never covers.
assert_contains "$autopilot" "contradicts the constitution" "autopilot skill stops on a constitution contradiction"
assert_contains "$autopilot" "suspect" "autopilot skill stops on a diverged claim"
assert_contains "$autopilot" "exit 3" "autopilot skill stops when another session holds the lease"
assert_contains "$autopilot" "weaken the gate" "autopilot skill forbids weakening the gate"

assert_contains "$autopilot" "baton-gate" "autopilot skill calls the evidence script"
assert_contains "$autopilot" "docs/baton/gates/" "autopilot skill files the verdict"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bash tests/test-skills.sh`
Expected: FAIL — `skill baton-autopilot exists` reports a missing file, and every content assertion fails on empty input.

- [ ] **Step 3: Write the skill**

Create `plugins/baton/skills/baton-autopilot/SKILL.md`:

````markdown
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
writer lease. If `autopilot` reads `off`, this skill does not apply: closing
a wave then needs a human, and `baton-checkpoint` says how.

## The grant is asymmetric

A human turns the autopilot on, by typing `/baton:auto` — a command the model
cannot invoke. You may always turn it off, and never on.

This is the same direction as `suspect` and `needs_human`, where you raise the
flag and a human clears it. In both cases you are free to move toward more
human involvement and not free to move toward less. An agent that could grant
itself autonomy is bounded by nothing, and the grant would stop meaning
anything the first time one did.

So: writing `autopilot: off` is always available to you. Writing anything else
into that field is not, whatever the reason seems to be.

## The loop

For each wave in scope, in the order `/baton:auto` established:

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

For the first wave in a run, `--since` is the repository's first commit
(`git rev-list --max-parents=0 HEAD | tail -1`), unless the human named a
base at `/baton:auto`.

Read the exit code before the output:

| Exit | Meaning | What to do |
|---|---|---|
| 0 | Evidence gathered. | Read `verify_exit` and `placeholder_hits`. |
| 1 | Not a git repository. | Stop and report; nothing here works without git. |
| 3 | The constitution is missing, unratified, or still has a placeholder. | Stop. This is a `needs_human` situation, not something to route around. |
| 4 | `verify_cmd` is empty or unrunnable. | Stop and report. Do not substitute a command you think is equivalent — `verify_cmd` is in the constitution precisely so you cannot choose it. |
| 64 | Usage, including a `--since` that is not a commit. | Fix the argument and rerun. |

Exit 0 is not a pass. It means the evidence exists. A red gate is exit 0 with
`verify_exit` non-zero, and that distinction is the reason to read the code
first: exit 4 and a red `verify_exit` look similar in a summary and call for
opposite responses.

**Evidence red** — `verify_exit` non-zero or `placeholder_hits` above zero —
means the wave does not close. Go fix it, then gate again.

**Evidence green** is a necessary condition and not a sufficient one. Walk the
wave's `exit_criteria` from the constitution, one at a time, against the
repository — not against your impression of the work. No script will ever do
this part: "the system shall preserve the subject when a token is renewed" is
a claim about behaviour, and only reading the behaviour settles it.

## The verdict file

Write it through `baton-write`, to
`docs/baton/gates/wave-<N>-attempt-<K>-<short_sha>.md`:

```markdown
---
schema: baton/gate/v1
wave: 2
verdict: auto
decided_by: <your session id>
decided_at: <ISO8601>
since: <the --since SHA>
sha: <HEAD>
verify_exit: 0
placeholder_hits: 0
---

# Gate: wave 2 — session

## Evidence

<the key=value block from baton-gate, verbatim>

## Criteria

- **When a token is renewed, the system shall preserve its subject** — met.
  `src/session.js:12` carries the subject through; covered by
  `test/session.test.js:8`, green in the run above.

## Decision

Closed under the autopilot. No human confirmed this.
```

A red attempt gets a file too, with `verdict: fail`. What broke at 03:40 is
exactly what the morning needs, and it is gone by then if only successes are
written down. The attempt number is in the filename because two red attempts
without a commit between them share a `short_sha`, and the second would
otherwise overwrite the first.

Then close the wave the way `baton-checkpoint` describes, with one difference:
the `gate` column takes `auto`, not `pass`. `pass` says a human confirmed it,
and none did. The morning's job is turning `auto` into `pass` or into an
objection, and it cannot be done if the two were already conflated overnight.

## When fixing stops being fixing

A red gate is work, not a stop. Fix it and gate again.

Stop when the evidence stops moving: the same `verify_exit` and the same set
of failing tests as the previous attempt. **Unchanged evidence** after a fix
means the fix did not address what is actually broken, and running it again is
what a loop looks like from the inside.

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
| "Nobody will read a fail verdict, I'll just fix it" | The morning reads it. It is the only account of what happened at 03:40. |
| "This wave doesn't depend on the blocked one, I'll take it" | Check `consumes` against the blocked wave's `produces` too. The graph is not the whole dependency. |
| "It's faster if I write this bit myself" | It is faster, and speed is not the constraint. Nobody is here to notice the context going. |

## Related skills

- **baton** — the model this rides on: what is authoritative, the two logs,
  the divergence policy.
- **baton-checkpoint** — the write. Closing a wave under the autopilot is its
  "Closing a wave" section, second path.
- **baton-resume** — runs before this on every fresh or compacted session, and
  decides whether the autopilot continues silently or waits for a word.
````

- [ ] **Step 4: Run test to verify it passes**

Run: `bash tests/test-skills.sh`
Expected: all assertions PASS, including the 500-line convention check for the new skill.

- [ ] **Step 5: Commit**

```bash
git add plugins/baton/skills/baton-autopilot/SKILL.md tests/test-skills.sh
git commit -m "baton-autopilot: what working unattended permits, and what it does not"
```

---

## Task 7: `/baton:auto`

**Files:**
- Create: `plugins/baton/commands/auto.md`
- Modify: `tests/test-commands.sh`

- [ ] **Step 1: Write the failing test**

In `tests/test-commands.sh`, change line 8's loop to:

```bash
for name in init checkpoint status auto continue; do
```

Then append before `finish`:

```bash
auto="$(cat "$CMD/auto.md")"

# The one invariant that cannot be enforced by anything else: a command the
# model can invoke is a grant the model can give itself.
assert_contains "$auto" "disable-model-invocation: true" \
    "auto is human-invocable only, so the agent cannot grant itself autonomy"
assert_contains "$auto" "readiness review" "auto runs a readiness review rather than asking for questions"
assert_contains "$auto" "exit_criteria" "the review quotes the exit criteria it will close against"
assert_contains "$auto" "not sure" "the review has to say where the agent is unsure"
assert_contains "$auto" "autopilot_grant" "auto records which journal entry granted the run"
assert_contains "$auto" "pbcopy" "auto puts the session goal on the clipboard"
assert_contains "$auto" "does not exist" "auto covers the not-a-baton-run case"
assert_contains "$auto" "ratified" "auto covers the not-yet-ratified case"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bash tests/test-commands.sh`
Expected: FAIL — `command auto exists` reports a missing file, every content assertion fails.

- [ ] **Step 3: Write the command**

Create `plugins/baton/commands/auto.md`:

````markdown
---
description: Hand the run to the agent - readiness review, then work without a human present
disable-model-invocation: true
---

Put this run on the autopilot.

This command carries `disable-model-invocation: true` for the same reason
`/baton:init` does. A grant the agent can give itself bounds nothing, and
"turn the autopilot on" is exactly the grant that must stay with the human.
`/baton:checkpoint` and `/baton:status` remain open to the model; they write
nothing the agent is judged by.

`$ARGUMENTS`, if present, is a single wave number: put only that wave on the
autopilot. Empty means every wave still `todo`.

## 1. Refuse the cases that are not a run

If `docs/baton/state.md` does not exist, this repository is not a baton run:
say so, suggest `/baton:init`, and stop. If `docs/baton/constitution.md`'s
`status` is not `ratified`, or a `REPLACE-WITH` token remains in it, say so and
stop — nobody has signed the rules this run would be held to.

Take the writer lease before anything else:

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/baton-lock" acquire "${CLAUDE_CODE_SESSION_ID:-$CLAUDE_SESSION_ID}"
```

Exit 3 means another session holds a live lease: stop and report it. Exit 64
means the environment gave neither session-id name: report it and stop rather
than inventing an id.

Then check the tree is clean, with `baton-observe`. Uncommitted work at the
moment the human leaves is work that no later session can tell apart from work
in flight.

## 2. Establish the scope

No argument: every wave with status `todo`, ordered topologically by
`depends_on` from the constitution.

An argument: that wave alone. If any wave in its transitive `depends_on` is not
`done`, say which and stop — that is not a scope, it is a wish.

## 3. Run the readiness review

Not "do you have any questions". A question only covers a gap you already
know is there, and the gaps that cost a night are the ones you do not.

Lay out, wave by wave in execution order:

- **which waves, in what order**, and why that order — cite `depends_on`;
- **where each spec comes from**: the file named in the wave's `spec` cell, or
  "I will derive it from the constitution";
- **what closing it means**: the `exit_criteria` quoted from the constitution,
  word for word, not paraphrased;
- **what will check it**: `verify_cmd`;
- **where you are not sure** — a plain list, and the most useful part of this
  whole exercise.

Then hand it to the human. They correct it or say go. A correction is theirs
to state and yours to fold in and show again — do not argue it down.

## 4. On "go", record the grant

Three writes, in this order:

**The journal entry.** `baton-journal autopilot-grant` for the id and path,
then write it through `baton-write`. `type: autopilot`, and the body carries
the scope, the review as it stood when approved, and the human's corrections.
This entry is the grant; everything else points at it.

**The state.** Through `baton-write`, in the same checkpoint:
`autopilot: <all|N>`, `autopilot_grant: DEC-NNNN`, and a **Next action** that
names the first concrete step of the first wave.

**The session goal.** One English line, short, the thing this session is for.
Print it, and put it on the clipboard:

```bash
printf '%s' "<the goal line>" | { pbcopy || wl-copy || xclip -selection clipboard; } 2>/dev/null \
    || echo "(copy it by hand — no clipboard tool here)"
```

The copy failing stops nothing. It is a convenience, not part of the protocol.

## 5. Start

Use the `baton-autopilot` skill and begin. Do not wait for a further word — the
human has left; that was the point.
````

- [ ] **Step 4: Run test to verify it passes**

Run: `bash tests/test-commands.sh`
Expected: the `auto` assertions PASS. `command continue exists` still FAILS — that is Task 8.

- [ ] **Step 5: Commit**

```bash
git add plugins/baton/commands/auto.md tests/test-commands.sh
git commit -m "/baton:auto: the review that buys the right to work alone"
```

---

## Task 8: `/baton:continue`

**Files:**
- Create: `plugins/baton/commands/continue.md`
- Modify: `tests/test-commands.sh`

- [ ] **Step 1: Write the failing test**

Append to `tests/test-commands.sh` before `finish`:

```bash
continue_cmd="$(cat "$CMD/continue.md")"
assert_contains "$continue_cmd" "disable-model-invocation: true" \
    "continue is human-invocable only: resuming unattended work is the human's call"
assert_contains "$continue_cmd" "baton-resume" "continue verifies state before resuming anything"
assert_contains "$continue_cmd" "does not grant" \
    "continue uses an existing grant and never creates one"
assert_contains "$continue_cmd" "needs_human" \
    "continue refuses to resume over an unresolved stop"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bash tests/test-commands.sh`
Expected: FAIL — the file does not exist.

- [ ] **Step 3: Write the command**

Create `plugins/baton/commands/continue.md`:

````markdown
---
description: Pick the run back up on a fresh session and carry on
disable-model-invocation: true
---

Resume this run.

After a compaction the `baton-resume` skill picks the run up on its own and,
if the autopilot is on, carries straight on — the grant is still live and it is
the same session. This command is for the other case: a fresh session, or one
after `/clear`, where continuing silently would mean that opening the
repository to check one thing started an hour of unattended work.

`disable-model-invocation: true`, because step 5 below resumes autonomous work
and that decision is the human's.

Run these in order and stop at the first that says stop.

## 1. Verify the state

Use the `baton-resume` skill in full: read the constitution and `state.md`,
check them against the repository with `baton-observe`, ancestry-check every
wave marked `done`. Nothing here is skipped because the run "was fine an hour
ago" — that is precisely the belief `baton-resume` exists to check.

## 2. Take the lease

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/baton-lock" acquire "${CLAUDE_CODE_SESSION_ID:-$CLAUDE_SESSION_ID}"
```

Exit 3: another session is live. Stop, report, write nothing. If `acquire`
prints `takeover=<session>`, journal it as a `takeover` entry.

## 3. Stop if the run is stopped

If `suspect: true` or `needs_human: true`, show what raised it and stop. A pat
nobody has resolved does not stop being a pat because a human typed
`continue` — and clearing either flag is theirs, not yours.

## 4. Check there is a grant

Read `autopilot`. If it is `off`, say so and stop: report where the run stands
and wait. **This command does not grant autonomy** — it uses a grant that
already exists. Turning the autopilot on is `/baton:auto` and nothing else.

## 5. Carry on

Report in two or three lines where the run stopped and what comes next, then
use the `baton-autopilot` skill and continue.
````

- [ ] **Step 4: Run test to verify it passes**

Run: `bash tests/test-commands.sh`
Expected: all assertions PASS.

- [ ] **Step 5: Commit**

```bash
git add plugins/baton/commands/continue.md tests/test-commands.sh
git commit -m "/baton:continue: the one word that restarts an unattended run"
```

---

## Task 9: `baton-resume` picks the grant up

**Files:**
- Modify: `plugins/baton/skills/baton-resume/SKILL.md`
- Modify: `tests/test-skills.sh`

- [ ] **Step 1: Write the failing test**

Append to `tests/test-skills.sh` before `finish`:

```bash
# The grant is useless if the session that wakes up after a compaction does
# not know it exists. And it is dangerous if a session started to check one
# thing acts on it.
assert_contains "$resume" "autopilot" "resume reads the autopilot grant"
assert_contains "$resume" "compact" "resume names the compact source, where it continues silently"
assert_contains "$resume" "startup" "resume names the startup source, where it waits"
assert_contains "$resume" "/baton:continue" "resume tells the human the word that restarts it"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bash tests/test-skills.sh`
Expected: FAIL on all four — `baton-resume/SKILL.md` says nothing about the autopilot.

- [ ] **Step 3: Write the implementation**

Add a new section to `plugins/baton/skills/baton-resume/SKILL.md`, after the
divergence handling and before whatever it says about continuing:

````markdown
## The autopilot grant

Read `autopilot` from `state.md`'s frontmatter. If it is `off`, nothing here
applies: this is an ordinary resume and a human is expected.

If it is anything else, this run was handed over — the entry named by
`autopilot_grant` in `docs/baton/journal/` is the handover. What you do next
depends on how this session started, which the `SessionStart` hook's matcher
tells you:

| Session source | What to do |
|---|---|
| `compact`, `resume` | Continue. Same session, same grant, and the human is still away. Say one line about where the run stands and carry on with the `baton-autopilot` skill. |
| `startup`, `clear`, `fork` | Do not start work. Report that the autopilot is on, name the scope and the granting entry, and wait. |

The second row is not caution for its own sake. A session started to check one
thing is not a session that agreed to an hour of unattended work, and the
grant cannot tell the two apart — only the human can, by typing
`/baton:continue`.

Both rows come after everything above: the divergence checks are not skipped
because the run is on the autopilot. A grant to work without a human is not a
grant to work from an unverified state.
````

- [ ] **Step 4: Run test to verify it passes**

Run: `bash tests/test-skills.sh`
Expected: all assertions PASS.

- [ ] **Step 5: Commit**

```bash
git add plugins/baton/skills/baton-resume/SKILL.md tests/test-skills.sh
git commit -m "baton-resume: a grant that survives the compaction it was written for"
```

---

## Task 10: `baton-checkpoint` grows a second closing path

**Files:**
- Modify: `plugins/baton/skills/baton-checkpoint/SKILL.md` (the "Closing a wave" section)
- Modify: `tests/test-skills.sh`

- [ ] **Step 1: Write the failing test**

Append to `tests/test-skills.sh` before `finish`:

```bash
# Two paths, not a relaxation of one. The wording matters: "if no human is
# around, close it yourself" is a rule an agent will apply to every moment
# the human is slow to reply.
assert_contains "$checkpoint" "autopilot" "checkpoint's closing rule knows about the second path"
assert_contains "$checkpoint" "While \`autopilot\` reads \`off\`" \
    "checkpoint gates the second path on the flag, not on whether a human happens to be replying"
assert_contains "$checkpoint" "\`auto\`, not \`pass\`" \
    "checkpoint says which value the autopilot path writes into the gate column"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bash tests/test-skills.sh`
Expected: FAIL — the closing section does not mention the autopilot at all.

- [ ] **Step 3: Write the implementation**

In `plugins/baton/skills/baton-checkpoint/SKILL.md`, replace the paragraph
beginning "`baton-verify` and `baton-gate` — the scripted gate that would set
`done` for you — are not built yet" with:

````markdown
There are two ways a wave closes, and which one applies is decided by the
`autopilot` field in `state.md`, not by whether a human happens to be
answering right now.

**While `autopilot` reads `off`** — the default, and the case this section is
mostly about — you are the only mechanism. A wave moves to `done` only when
every exit criterion the constitution lists for it has been checked, one by
one, against the repository, not against your impression of the work, with the
check recorded, **and** the human has confirmed it. Either half missing means
it stays where it is. Green tests are not a confirmation; they are the
condition under which asking for one is worth the human's time.

**While `autopilot` names a scope**, a human handed the run over and is not
here to confirm anything. The confirmation is replaced — not waived — by
`baton-gate`'s evidence plus a verdict file under `docs/baton/gates/` that
records your walk through the criteria. The `baton-autopilot` skill has the
procedure.

Do not read the second path as "close it yourself when nobody answers". It
applies while the flag is set and at no other time, and the flag is set by a
human typing `/baton:auto`.
````

Then replace the paragraph beginning "The `gate` column stays `—`" with:

````markdown
The `gate` column takes one of three values, and which one is not a matter of
taste:

| Value | What it says |
|---|---|
| `—` | Nothing produced a verdict. |
| `auto` | Closed under the autopilot: `baton-gate`'s evidence was green and you walked the criteria. The verdict is filed in `docs/baton/gates/`. |
| `pass` | A human confirmed it, or a future `baton-verify` did. |

Closing under the autopilot writes `auto`, not `pass`. `pass` claims a human
saw this, and if none did, that is a claim with no record behind it — one a
later resume, or a human deciding whether to trust this row, has nothing to
check against. Turning `auto` into `pass` is the morning's work, and it cannot
be done if the two were conflated overnight.

The row above the one you are filling in may already carry a value; that is
the previous run's table, not an instruction.
````

- [ ] **Step 4: Run test to verify it passes**

Run: `bash tests/test-skills.sh`
Expected: all assertions PASS, including the pre-existing `'The `gate` column stays'` assertion — **which will now fail**, since that string is gone. Replace that older assertion with:

```bash
assert_contains "$checkpoint" 'The `gate` column takes one of three values' \
    "checkpoint skill says what the gate column holds and who fills it"
```

- [ ] **Step 5: Commit**

```bash
git add plugins/baton/skills/baton-checkpoint/SKILL.md tests/test-skills.sh
git commit -m "baton-checkpoint: a second way to close, not a weaker first one"
```

---

## Task 11: The core skill — granted fields and the gate values

**Files:**
- Modify: `plugins/baton/skills/baton/SKILL.md`
- Modify: `tests/test-skills.sh`

- [ ] **Step 1: Write the failing test**

Append to `tests/test-skills.sh` before `finish`:

```bash
# The divergence policy has two kinds of field and now needs a third, or
# the autopilot flag falls into "a field on neither list is claimed" and
# gets treated as evidence to preserve rather than a grant to honour.
assert_contains "$core" "Granted fields" "core skill classifies the autopilot flag as a third kind of field"
assert_contains "$core" "toward more human involvement" \
    "core skill states which direction the agent may move a granted field"
assert_contains "$core" "auto" "core skill knows the gate column can read auto"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bash tests/test-skills.sh`
Expected: FAIL on the first two; the third may pass incidentally on the word "auto" appearing elsewhere — check the output, and if it passes vacuously, tighten it to `assert_contains "$core" '\`auto\` (closed under the autopilot)'`.

- [ ] **Step 3: Write the implementation**

In `plugins/baton/skills/baton/SKILL.md`, in the "Divergence policy" section,
replace the closing paragraph "`suspect` and `needs_human` are neither
kind..." with:

````markdown
- **Granted fields** — `suspect`, `needs_human`, `autopilot`,
  `autopilot_grant`. Neither observed nor claimed: they say how much of a
  human this run currently needs. You may only move them **toward more human
  involvement**. Raising `suspect` or `needs_human` is always yours; clearing
  either is the human's. `autopilot` runs the same rule in the other
  direction — writing `off` is always yours, writing anything else is the
  human's, through `/baton:auto`, a command you cannot invoke.

Clearing your own `suspect` is the same act as silently fixing the claim that
raised it. Granting yourself the autopilot is that act one level up: it
removes the human from every decision at once.
````

And in the wave-table description, wherever the `gate` column is mentioned,
add:

````markdown
The `gate` column reads `—` when nothing produced a verdict, `auto` (closed
under the autopilot, with a verdict filed in `docs/baton/gates/`), or `pass`
(a human confirmed it). They are not interchangeable: `auto` is a record that
the tests were green and the criteria were walked, by the same agent that did
the work. `pass` is a second party saying so.
````

Add two rows to the Red Flags table:

````markdown
| "The human is away, so the autopilot is implied" | It is set by a command or it is not set. An implied grant is one you gave yourself. |
| "I'll write `pass`, the tests were green" | Green tests are `auto`. `pass` says someone else looked. |
````

- [ ] **Step 4: Run test to verify it passes**

Run: `bash tests/test-skills.sh`
Expected: all assertions PASS.

- [ ] **Step 5: Commit**

```bash
git add plugins/baton/skills/baton/SKILL.md tests/test-skills.sh
git commit -m "baton: a third kind of field, for how much human a run needs"
```

---

## Task 12: `/baton:status` shows the mode

**Files:**
- Modify: `plugins/baton/commands/status.md`
- Modify: `tests/test-commands.sh`

- [ ] **Step 1: Write the failing test**

Append to `tests/test-commands.sh` before `finish`:

```bash
assert_contains "$status" "autopilot" "status says whether the run is unattended"
assert_contains "$status" "docs/baton/gates/" "status points at the verdicts behind auto-closed waves"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bash tests/test-commands.sh`
Expected: FAIL on both.

- [ ] **Step 3: Write the implementation**

In `plugins/baton/commands/status.md`, add to the reporting order — after the
`needs_human` item, since a stopped run still matters more:

````markdown
- **Whether this run is unattended.** If `autopilot` is not `off`, say so on
  its own line, with the scope and the granting journal entry:
  `Autopilot: all (DEC-0007)`. A human reading this after a night away needs
  to know the difference between "nothing happened" and "a great deal
  happened and nobody watched".
- **Waves closed without a human.** Any row whose `gate` reads `auto` is
  waiting on review; name the verdict file under `docs/baton/gates/` for each,
  so the review has somewhere to start. Waves reading `pass` are settled.
````

- [ ] **Step 4: Run test to verify it passes**

Run: `bash tests/test-commands.sh`
Expected: all assertions PASS.

- [ ] **Step 5: Commit**

```bash
git add plugins/baton/commands/status.md tests/test-commands.sh
git commit -m "/baton:status: say when nobody was watching"
```

---

## Task 13: The session-start hook injects the mode

**Files:**
- Modify: `plugins/baton/hooks/session-start`
- Modify: `tests/test-hooks.sh`

- [ ] **Step 1: Write the failing test**

`tests/test-hooks.sh` writes each `state.md` it needs inline with a heredoc
and drives the hook as `"$HOOKS/session-start"` with `CLAUDE_PLUGIN_ROOT`
already exported (line 28). Follow that pattern. Append before `finish`:

```bash
# --- the autopilot line in the injected block ---
# That block is what a compacted session sees before it decides anything. A
# grant it has to go and open the file to discover is a grant it may act
# after rather than on.
mkdir -p docs/baton
cat > docs/baton/state.md <<'EOF'
---
schema: baton/state/v1
suspect: false
needs_human: false
autopilot: all
autopilot_grant: DEC-0007
---

# State

**Goal:** ship the widget pipeline
**Operating mode:** orchestrator
**Non-negotiables:** never modify the billing schema

## Now

- **Next action:** write the failing test in widget.spec.ts
EOF

out="$("$HOOKS/session-start" < /dev/null)"
assert_contains "$out" "Autopilot: all" "session-start injects the autopilot scope when it is on"
assert_contains "$out" "DEC-0007" "session-start names the entry that granted it"
"$HOOKS/session-start" < /dev/null > autopilot-output.json
assert_valid_json "autopilot-output.json" "the autopilot line still leaves valid JSON"
rm -f autopilot-output.json

# Off is the common case and must add nothing: the injected block is the
# one thing that has to stay short enough to be read whole.
sed -i.bak 's/^autopilot: all$/autopilot: off/' docs/baton/state.md
rm -f docs/baton/state.md.bak
out="$("$HOOKS/session-start" < /dev/null)"
assert_not_contains "$out" "Autopilot:" "session-start stays quiet about the autopilot when it is off"
```

Place this block **before** the control-character test at line 223, which
overwrites `docs/baton/state.md` with a deliberately broken one.

- [ ] **Step 2: Run test to verify it fails**

Run: `bash tests/test-hooks.sh`
Expected: FAIL — `Autopilot: all` is absent from the injected context.

- [ ] **Step 3: Write the implementation**

In `plugins/baton/hooks/session-start`, after the `next="$(...)"` line, add:

```bash
autopilot="$(sed -n 's/^autopilot: *//p' "$state" | head -1)"
autopilot_grant="$(sed -n 's/^autopilot_grant: *//p' "$state" | head -1)"

# Only when it is on, and on its own line. An "Autopilot: off" line in
# every injection is noise in the one block that has to stay short enough
# to be read in full.
autopilot_line=""
if [ -n "$autopilot" ] && [ "$autopilot" != "off" ]; then
    autopilot_line="
Autopilot: ${autopilot} (granted ${autopilot_grant}) — this run continues without a human present. Check the session source before acting on it: see baton-resume."
fi
```

Then change the `context=` assignment to include it, immediately after the
`Next action:` line:

```bash
context="This repository runs under baton. Before anything else, use the baton-resume skill: read docs/baton/constitution.md and docs/baton/state.md, verify them against the repository with baton-observe, and only then continue.

Goal: ${goal}
Operating mode: ${mode}
Non-negotiables: ${rules}
Next action: ${next}${autopilot_line}

These four lines are a summary for orientation, not a substitute for reading the files."
```

- [ ] **Step 4: Run test to verify it passes**

Run: `bash tests/test-hooks.sh`
Expected: all assertions PASS, including the existing JSON-validity checks —
the new line goes through the same escaper.

- [ ] **Step 5: Commit**

```bash
git add plugins/baton/hooks/session-start tests/test-hooks.sh
git commit -m "session-start: say the run is unattended before anything acts on it"
```

---

## Task 14: The fourth fixture

**Files:**
- Create: `tests/fixtures/cold-start/build-autopilot.sh`
- Create: `tests/test-cold-start-autopilot.sh`

- [ ] **Step 1: Write the failing test**

Create `tests/test-cold-start-autopilot.sh`:

```bash
#!/usr/bin/env bash
# Pins the premise of the autopilot fixture (tests/fixtures/cold-start/
# build-autopilot.sh): a run handed over, with one wave blocked and two
# waves left, exactly one of which is available. What a resuming agent
# does with that -- take the available wave, leave the other alone,
# continue without asking -- is RUNBOOK.md's fourth scenario, run by a
# human. What is checked here is the premise: that the fixture really does
# contain one available wave and one that only the consumes/produces rule
# excludes, so it cannot rot into a fixture where the easy rule suffices.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PLUGIN="$REPO_ROOT/plugins/baton"
. "$SCRIPT_DIR/helpers.sh"

FIXTURE="$(mktemp -d)"
bash "$SCRIPT_DIR/fixtures/cold-start/build-autopilot.sh" "$FIXTURE" >/dev/null
cd "$FIXTURE"

state="$(cat docs/baton/state.md)"
constitution="$(cat docs/baton/constitution.md)"

assert_contains "$constitution" "status: ratified" "the autopilot fixture's constitution is ratified"
assert_not_contains "$constitution" "REPLACE-WITH" "the autopilot fixture's constitution has no unfilled placeholders"

# The grant, and the entry it points at. A flag with a dangling grant is
# a fixture that tests nothing about how the grant is recorded.
assert_contains "$state" "autopilot: all" "the fixture is on the autopilot"
grant="$(sed -n 's/^autopilot_grant: *//p' docs/baton/state.md | head -1)"
assert_equals "$grant" "DEC-0001" "the fixture names the entry that granted autonomy"
assert_file_exists "docs/baton/journal/0001-autopilot-grant.md" "the granting entry exists"
assert_contains "$(cat docs/baton/journal/0001-autopilot-grant.md)" "type: autopilot" \
    "the granting entry is typed as the grant"

# One blocked wave, and a needs_human raised with it.
assert_contains "$state" "| 2 | session | blocked |" "wave 2 is blocked"
assert_contains "$state" "needs_human: true" "the fixture raised needs_human with the block"

# Wave 3 is excluded ONLY by the consumes/produces rule: its depends_on
# does not include the blocked wave, so a resuming agent applying just the
# graph rule would wrongly take it. That is the whole point of this fixture.
assert_contains "$constitution" "produces: [session-contract]" "the blocked wave publishes a contract"
assert_contains "$constitution" "consumes: [session-contract]" "a later wave takes that contract"
deps3="$(sed -n '/^- wave: 3$/,/^$/p' docs/baton/constitution.md | sed -n 's/^  depends_on: *//p')"
assert_equals "$deps3" "[1]" "wave 3 does not depend on the blocked wave in the graph -- only through the contract"

# Wave 4 is the one genuinely available wave: nothing blocked upstream and
# no shared contract. Without it the fixture would only ever test refusal.
assert_contains "$state" "| 4 | docs | todo |" "wave 4 is still todo"
deps4="$(sed -n '/^- wave: 4$/,/^$/p' docs/baton/constitution.md | sed -n 's/^  depends_on: *//p')"
assert_equals "$deps4" "[1]" "wave 4 depends only on the closed wave"

# No wave claims a verdict nothing produced.
assert_not_contains "$state" "| pass |" "no autopilot-fixture wave claims a human confirmation"

assert_contains "$(cat .gitignore 2>/dev/null || true)" ".baton/" \
    "the autopilot fixture gitignores .baton/ the way /baton:init leaves it"

cd /
rm -rf "$FIXTURE"
FIXTURE=""
finish
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bash tests/test-cold-start-autopilot.sh`
Expected: FAIL immediately — `build-autopilot.sh` does not exist, so the
script aborts at the `bash ... build-autopilot.sh` line.

- [ ] **Step 3: Write the fixture builder**

Create `tests/fixtures/cold-start/build-autopilot.sh`:

```bash
#!/usr/bin/env bash
# Build a run that was handed over and then hit a pat: wave 1 closed, wave
# 2 blocked, waves 3 and 4 still todo -- and only wave 4 available.
#
# The shape is the point. Wave 3's depends_on is [1], so the dependency
# graph alone says it may be taken; it is excluded only because it consumes
# the contract wave 2 was to produce. A fixture where the blocked wave was
# also a graph dependency would pass with an agent that never learned the
# third rule, which is the rule most likely to be dropped as pedantic.
set -euo pipefail

dest="${1:?usage: build-autopilot.sh <destination-dir>}"
mkdir -p "$dest"
cd "$dest"

git init -q -b main
git config user.name "baton fixture"
git config user.email "baton@example.invalid"
git config commit.gpgsign false

mkdir -p src docs/baton/journal

printf '.baton/\n' > .gitignore
git add .gitignore
git commit -q -m "baton: gitignore .baton/"

cat > src/auth.js <<'EOF'
export function login(user) {
  return { user, token: "signed" };
}
EOF
git add src/auth.js
git commit -q -m "wave 1: login"
wave1_sha="$(git rev-parse --short HEAD)"

cat > src/session.js <<'EOF'
export function renew(token) {
  return token;
}
EOF
git add src/session.js
git commit -q -m "wave 2: session renewal, incomplete"
work_sha="$(git rev-parse HEAD)"

cat > docs/baton/constitution.md <<'EOF'
---
schema: baton/constitution/v1
run_id: fixture-auth-autopilot
status: ratified
verify_cmd: "true"
placeholder_patterns: "TODO|FIXME|NotImplemented"
---

# Fixture run (autopilot)

## Goal
Ship authentication.

## Operating mode
Orchestrator; delegates implementation to subagents.

## Non-negotiables
Never change the token format.

## Waves

- wave: 1
  name: login
  depends_on: []
  parallel_with: []
  exit_criteria:
    - The system shall return a token for a valid user

- wave: 2
  name: session
  depends_on: [1]
  parallel_with: [3]
  produces: [session-contract]
  exit_criteria:
    - When a token is renewed, the system shall preserve its subject

- wave: 3
  name: refresh
  depends_on: [1]
  parallel_with: [2]
  consumes: [session-contract]
  exit_criteria:
    - When a session expires, the system shall issue a refreshed token

- wave: 4
  name: docs
  depends_on: [1]
  parallel_with: []
  exit_criteria:
    - The system shall document the login endpoint
EOF

cat > docs/baton/journal/0001-autopilot-grant.md <<'EOF'
---
id: DEC-0001
type: autopilot
date: 2026-08-04
scope: all
---

# Autopilot granted for all remaining waves

The readiness review covered waves 2, 3 and 4, their exit criteria as
written in the constitution, and the two places the agent said it was
unsure. The human corrected the order and said go.
EOF

cat > docs/baton/state.md <<EOF
---
schema: baton/state/v1
writer: fixture-session
updated_at: 2026-08-04T02:14:00Z
observed_sha: $work_sha
observed_branch: $(git symbolic-ref --short HEAD)
tree_clean: true
suspect: false
needs_human: true
autopilot: all
autopilot_grant: DEC-0001
---

# State

**Goal:** Ship authentication.
**Operating mode:** Orchestrator; delegates implementation to subagents.
**Non-negotiables:** Never change the token format.

## Waves

| # | name | status | branch/worktree | spec | plan | closed_at_sha | gate |
|---|------|--------|-----------------|------|------|---------------|------|
| 1 | login | done | main | — | — | $wave1_sha | auto |
| 2 | session | blocked | main | — | — | — | — |
| 3 | refresh | todo | main | — | — | — | — |
| 4 | docs | todo | main | — | — | — | — |

**Current wave:** 2 — session

## Now

- **Next action:** take wave 4 (docs); wave 3 consumes the contract wave 2 was to publish
- **In flight:** wave 2: attempt 3 of 3, evidence unchanged since attempt 2
- **Suspect:** none
- **Open questions:** wave 2 needs a decision on where the subject is stored

## Pointers

- Constitution: docs/baton/constitution.md
- Recent decisions: docs/baton/journal/
EOF

git add docs/baton
git commit -q -m "baton: checkpoint at the pat on wave 2"
```

- [ ] **Step 4: Run test to verify it passes**

```bash
chmod +x tests/fixtures/cold-start/build-autopilot.sh
bash tests/test-cold-start-autopilot.sh
```

Expected: all assertions PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/fixtures/cold-start/build-autopilot.sh tests/test-cold-start-autopilot.sh
git commit -m "tests: a fixture where only the contract rule keeps a wave off the table"
```

---

## Task 15: Runbook scenario 4

**Files:**
- Modify: `tests/fixtures/cold-start/RUNBOOK.md`
- Modify: `tests/test-skill-commands.sh`

- [ ] **Step 1: Write the failing test**

In `tests/test-skill-commands.sh`, extend `DOC_FILES` to cover the new
documents — otherwise the `${CLAUDE_PLUGIN_ROOT}` path checks and the
bare-script-name check never look at them:

```bash
DOC_FILES="
commands/init.md
commands/checkpoint.md
commands/status.md
commands/auto.md
commands/continue.md
skills/baton/SKILL.md
skills/baton-resume/SKILL.md
skills/baton-checkpoint/SKILL.md
skills/baton-autopilot/SKILL.md
"
```

And extend `LOCK_DOC_FILES`:

```bash
LOCK_DOC_FILES="
commands/init.md
commands/auto.md
commands/continue.md
skills/baton-resume/SKILL.md
skills/baton-checkpoint/SKILL.md
"
```

Then add a check that the runbook covers the new scenario. Append to
`tests/test-skill-commands.sh` before `finish`:

```bash
runbook="$(cat "$REPO_ROOT/tests/fixtures/cold-start/RUNBOOK.md")"
assert_contains "$runbook" "Scenario 4" "the runbook has a scenario for the autopilot"
assert_contains "$runbook" "build-autopilot.sh" "scenario 4 names the fixture it runs against"
assert_contains "$runbook" "/baton:continue" "scenario 4 exercises the fresh-session pickup"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bash tests/test-skill-commands.sh`
Expected: FAIL — `Scenario 4` is absent, and the `${CLAUDE_PLUGIN_ROOT}` and
bare-name checks now also run over the two new commands and the new skill
(any path typo there surfaces here).

- [ ] **Step 3: Write the scenario**

Append to `tests/fixtures/cold-start/RUNBOOK.md`, before the "Runs on record"
section:

````markdown
## Scenario 4 — the autopilot carries the run

**Build:**

```bash
bash tests/fixtures/cold-start/build-autopilot.sh ~/Workspace/orchestra/baton-fixtures/4-autopilot
```

This fixture is already mid-pat: wave 1 closed under the autopilot, wave 2
blocked after three attempts, waves 3 and 4 still `todo`. Wave 3 does **not**
depend on wave 2 in the dependency graph — it is excluded only because it
consumes the contract wave 2 was to publish. That is the thing this scenario
tests.

**Run:** open a session in the fixture and let `baton-resume` run.

**Pass conditions:**

1. The agent reports that the run is on the autopilot, names the scope
   (`all`) and the granting entry (`DEC-0001`).
2. Because this is a fresh `startup` and not a compaction, it **waits**. It
   does not begin work.
3. Typing `/baton:continue` does not start work either: `needs_human: true`
   is set, and it reports the pat on wave 2 and stops.
4. Clear the flag by hand (`needs_human: false`, and wave 2 to `todo` if you
   want it retried) and run `/baton:continue` again. The agent now picks
   **wave 4**, not wave 3, and says why wave 3 is unavailable — naming the
   `session-contract` that wave 2 was to produce.
5. It closes wave 4 by running `baton-gate`, walking the exit criterion, and
   filing a verdict under `docs/baton/gates/`. The Waves row for wave 4 reads
   `auto` in the gate column, never `pass`.
6. Force a compaction mid-wave. The agent continues **without asking** — this
   is `compact`, not `startup`.
7. `/baton:status` afterwards names the autopilot, its scope, and every wave
   whose gate reads `auto` as awaiting review.

**What a failure looks like:** starting work on step 2; taking wave 3 at step
4; writing `pass` at step 5; asking for permission at step 6.
````

- [ ] **Step 4: Run test to verify it passes**

Run: `bash tests/test-skill-commands.sh`
Expected: all assertions PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/fixtures/cold-start/RUNBOOK.md tests/test-skill-commands.sh
git commit -m "runbook: the fourth scenario, and the doc lists that had stopped covering everything"
```

---

## Task 16: README, and the whole suite green

**Files:**
- Modify: `README.md`
- Verify: everything

- [ ] **Step 1: Run the full suite and record the count**

```bash
bash tests/run-tests 2>&1 | tail -5
bash tests/run-tests 2>&1 | grep -c '\[PASS\]'
```

Expected: `All test files passed.` and a count above 416 (the `v0.1.0`
baseline). Note the number; it goes in the commit message.

- [ ] **Step 2: Update the README**

In the commands table, add:

```markdown
| `/baton:auto [wave]` | Hand the run over: readiness review, then work with no human present. Human-typed only. |
| `/baton:continue` | Pick an unattended run back up on a fresh session. Human-typed only. |
```

In "What's not built yet", replace the gate entry with:

```markdown
- **`baton-verify`** — an independent gate. `baton-gate` now gathers the
  mechanical evidence (the constitution's `verify_cmd`, a placeholder scan
  over what the wave touched) and the agent walks the exit criteria and files
  a verdict under `docs/baton/gates/`. What is still missing is the second
  party: today the verdict is written by the same agent that did the work,
  which is why a wave closed unattended reads `auto` in the gate column and
  not `pass`. Turning `auto` into `pass` is a human's job.
```

Add to the requirements note: nothing new — `baton-gate` uses git and the
shell only.

- [ ] **Step 3: Verify the README claims are true**

```bash
ls plugins/baton/commands/
grep -n "auto\|continue" README.md | head -20
```

Expected: `auto.md` and `continue.md` are present and the README names both.

- [ ] **Step 4: Run the full suite once more**

```bash
bash tests/run-tests
```

Expected: `All test files passed.`

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "README: the autopilot, and the half of the gate that now exists"
```

---

## Self-Review

**Spec coverage:**

| Spec section | Task |
|---|---|
| §5 состав — `baton-gate` | 1–4 |
| §5 — `commands/auto.md` | 7 |
| §5 — `commands/continue.md` | 8 |
| §5 — `skills/baton-autopilot` | 6 |
| §5 — `templates/state.md` | 5 |
| §5 — `baton-resume` | 9 |
| §5 — `baton-checkpoint` | 10 |
| §5 — `baton/SKILL.md` | 11 |
| §5 — `status.md` | 12 |
| §5 — `session-start` | 13 |
| §5 — README | 16 |
| §6 асимметрия | 6 (skill), 7 (command frontmatter), 11 (granted fields) |
| §7.1 скрипт и коды выхода | 1–4 |
| §7.2 вердикт агента | 6 |
| §7.3 вердикт-файл, номер попытки | 6 |
| §7.4 три значения `gate` | 5, 10, 11 |
| §7.5 два пути закрытия | 10 |
| §8.1 неизменившаяся улика, потолок | 6 |
| §8.2 что происходит в пате | 6 |
| §8.3 условие доступности | 6 (prose), 14 (fixture) |
| §8.4 что не подлежит решению | 6 |
| §9.1 поля состояния | 5 |
| §9.2 инжект хука | 13 |
| §9.3 правило подхвата | 9 |
| §9.4 `/baton:continue` | 8 |
| §10 смотр готовности | 7 |
| §13 тестирование | 1–16, `test-gate.sh` in 1–4, fixture in 14, runbook in 15 |

No spec section is without a task.

**Placeholder scan:** every step carries the text or code it needs. No step
says "add error handling" or "write tests for the above" — the test code is
written out in each case, and every assertion carries the sentence explaining
what it is defending against.

**Consistency check:** the evidence keys are the same everywhere they appear —
`verify_cmd`, `verify_exit`, `verify_log`, `placeholder_hits`,
`placeholder_files`, `changed_files`, `since`, `sha`, `tree_clean` (Tasks 2–4,
quoted again in Task 6's verdict template). The state fields are `autopilot`
and `autopilot_grant` in Tasks 5, 9, 11, 13, 14. The gate values are `—`,
`auto`, `pass` in Tasks 5, 10, 11, 12, 14, 15. The verdict path is
`docs/baton/gates/wave-<N>-attempt-<K>-<short_sha>.md` in Task 6 and referred
to as `docs/baton/gates/` elsewhere.

**One known ordering hazard:** Task 10 removes the string
`` `The `gate` column stays` `` that a `v0.1.0` assertion in
`tests/test-skills.sh` checks for. Task 10 Step 4 replaces that assertion in
the same task, so the suite is never left red between commits — but a worker
splitting Task 10 across two commits will see it. Do not split it.
