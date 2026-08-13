#!/usr/bin/env bash
# Pins the premise of the diverged fixture (tests/fixtures/cold-start/
# build-diverged.sh): what this suite can check mechanically about a
# repository where a claim disagrees with the repository. The behaviour
# this fixture exists to exercise -- that a resuming agent notices a
# divergence, says what diverged, and stops rather than continuing to
# Next action -- is not something a script can observe; that half is
# RUNBOOK.md's, run by a human: scenario 2 for the two divergences that set
# suspect: true, scenario 5 for the third, which is a different kind of stop
# that writes nothing at all. What is checked here is narrower and purely
# mechanical: that the fixture's three divergences are real, so it cannot rot
# into a clean fixture without this suite noticing.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PLUGIN="$REPO_ROOT/plugins/baton"
. "$SCRIPT_DIR/helpers.sh"

FIXTURE="$(mktemp -d)"
bash "$SCRIPT_DIR/fixtures/cold-start/build-diverged.sh" "$FIXTURE" >/dev/null
cd "$FIXTURE"

state="$(cat docs/baton/state.md)"

# The fixture must still pass baton-resume's ratification guard -- a
# fixture that trips that guard tests the guard, not the divergence path.
constitution="$(cat docs/baton/constitution.md)"
assert_contains "$constitution" "status: ratified" "the diverged fixture's constitution is ratified"
assert_not_contains "$constitution" "REPLACE-WITH" "the diverged fixture's constitution has no unfilled placeholders"

# Divergence 1: wave 1 is claimed done at a closed_at_sha that is NOT an
# ancestor of HEAD. Read the exit code, not just whether it was zero -- see
# baton-resume step 2's table. 1 means "not an ancestor", the real
# divergence this fixture is for; a fixture that instead produced 128
# ("not a valid commit") would be exercising a different failure than the
# one it claims to.
assert_not_contains "$(cat docs/baton/state.md)" "| pass |" \
    "no diverged-fixture wave claims a verdict no gate produced"
closed="$(sed -n 's/^| 1 |.*| \([0-9a-f]\{7,\}\) | — |$/\1/p' docs/baton/state.md)"
if [ -n "$closed" ]; then
    pass "state.md names a closed_at_sha for wave 1"
else
    fail "state.md names a closed_at_sha for wave 1"
fi

set +e
git merge-base --is-ancestor "$closed" HEAD
merge_base_rc=$?
set -e
assert_equals "$merge_base_rc" "1" \
    "wave 1's closed_at_sha is genuinely not an ancestor of HEAD (git merge-base --is-ancestor exits 1, not 0 or 128)"

# Divergence 2: observed_sha is behind the repository's current work_sha --
# not merely different from it, but a real ancestor of it, so this is
# genuinely "work landed since", not some unrelated sha.
observed_sha="$(sed -n 's/^observed_sha: *//p' docs/baton/state.md | head -1)"
work_sha="$("$PLUGIN/scripts/baton-observe" | sed -n 's/^work_sha=//p')"

if [ "$observed_sha" != "$work_sha" ]; then
    pass "fixture observed_sha differs from the repository's current work_sha"
else
    fail "fixture observed_sha differs from the repository's current work_sha"
fi

assert_exit_code 0 "observed_sha is an ancestor of the current work_sha, i.e. genuinely behind it, not just different" \
    git merge-base --is-ancestor "$observed_sha" "$work_sha"

# .baton/precompact-facts must exist and carry the later work_sha -- this is
# what gives baton-resume's step 3 something to find without a live
# PreCompact hook run.
assert_file_exists ".baton/precompact-facts" "the fixture ships .baton/precompact-facts"
precompact_work_sha="$(sed -n 's/^work_sha=//p' .baton/precompact-facts | head -1)"
assert_equals "$precompact_work_sha" "$work_sha" \
    "precompact-facts' work_sha matches the repository's actual current work_sha"
assert_equals "$([ "$precompact_work_sha" = "$observed_sha" ] && echo same || echo different)" "different" \
    "precompact-facts' work_sha disagrees with state.md's observed_sha -- that disagreement is what step 3 exists to catch"

# Neither divergence is flagged on disk: suspect and needs_human both read
# false. Noticing is the resuming agent's job, not the fixture's -- a
# fixture that pre-flagged this would test the flag-handling path (already
# covered), not the actual detection this fixture is for.
assert_contains "$state" "suspect: false" "the fixture does not pre-flag the divergence: suspect reads false"
assert_contains "$state" "needs_human: false" "the fixture does not pre-flag the divergence: needs_human reads false"

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

cd /
rm -rf "$FIXTURE"
FIXTURE=""
finish
