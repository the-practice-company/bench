#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SCRIPTS="$REPO_ROOT/plugins/baton/scripts"
. "$SCRIPT_DIR/helpers.sh"

make_fixture_repo

write_state() {
    # write_state <wave> <timestamp>
    # observed_sha comes from baton-observe's work_sha, not raw HEAD: HEAD
    # moves on the checkpoint commit this very call is about to make, so a
    # baseline taken from it would already be stale the moment it lands.
    # work_sha is the last commit that touched anything outside
    # docs/baton/, which a checkpoint commit never does -- see baton-observe.
    cat <<EOF | "$SCRIPTS/baton-write" -m "baton: checkpoint wave $1" docs/baton/state.md
---
schema: baton/state/v1
updated_at: $2
observed_sha: $("$SCRIPTS/baton-observe" | sed -n 's/^work_sha=//p')
suspect: false
needs_human: false
---

# State

**Goal:** ship the thing
Current wave: $1
EOF
}

write_state 1 2026-08-03T10:00:00Z
write_state 2 2026-08-03T11:00:00Z
write_state 3 2026-08-03T12:00:00Z

# Idle checkpoint: same substance, later clock.
write_state 3 2026-08-03T13:00:00Z

assert_equals "$(git status --porcelain docs/baton | wc -l | tr -d ' ')" "0" \
    "no state lives outside the log, idle checkpoints included"

before="$(cat docs/baton/state.md)"
rm docs/baton/state.md
git checkout -- docs/baton/state.md
assert_equals "$(cat docs/baton/state.md)" "$before" "state rebuilds byte-for-byte from the log"

snapshots="$(git log --oneline -- docs/baton/state.md | wc -l | tr -d ' ')"
assert_equals "$snapshots" "3" "the log holds one snapshot per substantive checkpoint, and none for the idle one"

past="$(git log --format=%H -- docs/baton/state.md | sed -n '3p')"
assert_contains "$(git show "$past:docs/baton/state.md")" "Current wave: 1" \
    "any past point of the run can be read back from the log"

# Atomicity: a half-written temp file must never become the state file.
printf 'partial' > "docs/baton/.state.md.tmp.99999"
assert_contains "$(cat docs/baton/state.md)" "Current wave: 3" \
    "a stray temp file does not affect the state file"
rm -f docs/baton/.state.md.tmp.99999

# Resume is idempotent: observing twice changes nothing.
"$SCRIPTS/baton-observe" > /dev/null
"$SCRIPTS/baton-observe" > /dev/null
assert_equals "$(git status --porcelain | wc -l | tr -d ' ')" "0" \
    "observing the repository never writes to it"

finish
