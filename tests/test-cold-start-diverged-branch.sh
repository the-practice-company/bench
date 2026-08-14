#!/usr/bin/env bash
# Pins the premise of the diverged-branch fixture (tests/fixtures/cold-start/
# build-diverged-branch.sh): what this suite can check mechanically about a
# repository whose state.md names a branch the checkout is not on. The
# behaviour this fixture exists to exercise -- that a resuming agent notices
# the mismatch, names both branches, stops, and writes nothing at all, not
# even needs_human -- is not something a script can observe; that half is
# RUNBOOK.md's fifth scenario, run by a human. What is checked here is
# narrower and purely mechanical, the same way test-cold-start-diverged.sh is
# narrower than the scenario it backs: that the fixture's one divergence is
# real, and that nothing else about it diverges. The second half matters as
# much as the first: build-diverged.sh's two divergences deliberately do not
# live here, because baton-resume's branch check runs and stops before the
# checks that would catch them ever fire (see build-diverged-branch.sh's own
# comment) -- so this fixture has to prove, not just assert, that the branch
# mismatch is the only thing an agent running RUNBOOK.md scenario 5 can find.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PLUGIN="$REPO_ROOT/plugins/baton"
. "$SCRIPT_DIR/helpers.sh"

FIXTURE="$(mktemp -d)"
bash "$SCRIPT_DIR/fixtures/cold-start/build-diverged-branch.sh" "$FIXTURE" >/dev/null
cd "$FIXTURE"

state="$(cat docs/baton/state.md)"

# The fixture must still pass baton-resume's ratification guard -- a
# fixture that trips that guard tests the guard, not the branch-check path.
constitution="$(cat docs/baton/constitution.md)"
assert_contains "$constitution" "status: ratified" "the diverged-branch fixture's constitution is ratified"
assert_not_contains "$constitution" "REPLACE-WITH" "the diverged-branch fixture's constitution has no unfilled placeholders"

assert_not_contains "$state" "| pass |" \
    "no diverged-branch-fixture wave claims a verdict no gate produced"

# The divergence itself: state.md names a branch this checkout is not on and
# never was.
claimed_branch="$(printf '%s' "$state" | sed -n 's/^observed_branch: *//p' | head -1)"
actual_branch="$(git symbolic-ref --short -q HEAD || echo '(detached)')"
if [ -n "$claimed_branch" ] && [ "$claimed_branch" != "$actual_branch" ]; then
    pass "the diverged-branch fixture claims a branch it is not on ($claimed_branch vs $actual_branch)"
else
    fail "the diverged-branch fixture claims a branch it is not on"
    echo "    claimed: $claimed_branch"
    echo "    actual:  $actual_branch"
fi

set +e
git rev-parse -q --verify "refs/heads/$claimed_branch" >/dev/null
claimed_branch_exists_rc=$?
set -e
assert_equals "$claimed_branch_exists_rc" "1" \
    "the branch state.md claims was never created in this checkout (git rev-parse finds no such ref)"

# Everything else must be exactly as consistent as the plain cold-start
# fixture -- if any of these ever went the other way, this fixture would
# quietly grow a second divergence and RUNBOOK.md scenario 5 would no longer
# be testing what it says it tests.
closed="$(sed -n 's/^| 1 |.*| \([0-9a-f]\{7,\}\) | — |$/\1/p' docs/baton/state.md)"
if [ -n "$closed" ]; then
    pass "state.md names a closed_at_sha for wave 1"
else
    fail "state.md names a closed_at_sha for wave 1"
fi
assert_exit_code 0 "wave 1's closed_at_sha is genuinely an ancestor of HEAD -- no divergence smuggled in alongside the branch mismatch" \
    git merge-base --is-ancestor "$closed" HEAD

observed_sha="$(sed -n 's/^observed_sha: *//p' docs/baton/state.md | head -1)"
work_sha="$("$PLUGIN/scripts/baton-observe" | sed -n 's/^work_sha=//p')"
assert_equals "$observed_sha" "$work_sha" \
    "observed_sha genuinely equals the repository's current work_sha -- the checkpoint is not stale"

assert_contains "$state" "tree_clean: true" "the fixture claims a clean tree"
assert_equals "$(git status --porcelain)" "" "the tree is genuinely clean, matching the tree_clean: true claim"

assert_not_contains "$(ls -a .baton 2>/dev/null || true)" "precompact-facts" \
    "the fixture ships no .baton/precompact-facts -- no live-hook staleness question for step 3 to raise"

assert_contains "$state" "suspect: false" "the fixture does not pre-flag the divergence: suspect reads false"
assert_contains "$state" "needs_human: false" "the fixture does not pre-flag the divergence: needs_human reads false"

cd /
rm -rf "$FIXTURE"
FIXTURE=""
finish
