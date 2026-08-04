#!/usr/bin/env bash
# Pins the premise of the takeover fixture (tests/fixtures/cold-start/
# build-takeover.sh): what this suite can check mechanically about a
# repository where the writer lease is stale. The behaviour this fixture
# exists to exercise -- that a resuming agent notices the pre-existing
# lease, takes it over deliberately rather than by accident, and journals
# who it displaced -- is not something a script can observe; that half is
# RUNBOOK.md's third scenario, run by a human. What is checked here is
# narrower and purely mechanical, the same way test-cold-start-diverged.sh
# is narrower than the scenario it backs: that the fixture's premise is
# real. Two facts are what the manual scenario rests on, and both are
# exactly what would rot silently, with the fixture still looking plausible
# on read, if the staleness constant or the lease's field names ever
# changed underneath it:
#
#   1. baton-lock genuinely reports the lease as expired to a session that
#      is not the one that wrote it.
#   2. The lease names a session other than the one that will resume, so a
#      real takeover -- not an ordinary uncontested acquire -- is what the
#      resuming session actually faces.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PLUGIN="$REPO_ROOT/plugins/baton"
. "$SCRIPT_DIR/helpers.sh"

FIXTURE="$(mktemp -d)"
bash "$SCRIPT_DIR/fixtures/cold-start/build-takeover.sh" "$FIXTURE" >/dev/null
cd "$FIXTURE"

# The fixture must still pass baton-resume's ratification guard -- a
# fixture that trips that guard tests the guard, not the takeover path.
constitution="$(cat docs/baton/constitution.md)"
assert_contains "$constitution" "status: ratified" "the takeover fixture's constitution is ratified"
assert_not_contains "$constitution" "REPLACE-WITH" "the takeover fixture's constitution has no unfilled placeholders"

assert_not_contains "$(cat docs/baton/state.md)" "| pass |" \
    "no takeover-fixture wave claims a verdict no gate produced"

# This fixture is the one that most needs .baton/ ignored: it ships a lease
# there, so without the ignore rule the very file the scenario is about
# reads as untracked noise the agent may try to tidy away.
assert_contains "$(cat .gitignore 2>/dev/null || true)" ".baton/" \
    "the takeover fixture gitignores .baton/ the way /baton:init leaves it"

assert_file_exists ".baton/lock" "the fixture ships a pre-existing lease"

# Fact 2 first: read the lease's own session= field directly, not inferred
# from baton-lock's exit code. lock_state() fails OPEN to "expired" for a
# missing or garbled acquired_epoch (see baton-lock's own comment on that),
# so a fixture whose field names had rotted could still make `check` below
# report exit 4 for the wrong reason -- reading the field straight from the
# file is what actually pins that "session=" is present and holds the
# session this fixture claims, not some accident of the fail-open path.
resuming_session="resuming-session"
lock_session="$(sed -n 's/^session=//p' .baton/lock | head -1)"
assert_equals "$lock_session" "ghost-session-from-a-crashed-run" \
    "the lease names the crashed session the fixture claims to have left behind"
if [ "$lock_session" != "$resuming_session" ]; then
    pass "the lease names a session other than the one that will resume"
else
    fail "the lease names a session other than the one that will resume"
fi

# acquired_epoch, read the same direct way, must be old -- not just present.
# An hour is used here, not baton-lock's own six-hour STALE_SECONDS: this
# assertion exists to catch the field going missing or non-numeric (which
# would also fail-open to "expired" via fact 1 below, masking the rot), not
# to duplicate baton-lock's own staleness threshold in a second place.
lock_epoch="$(sed -n 's/^acquired_epoch=//p' .baton/lock | head -1)"
case "$lock_epoch" in
    ''|*[!0-9]*)
        fail "acquired_epoch is a plain positive integer"
        ;;
    *)
        pass "acquired_epoch is a plain positive integer"
        one_hour_ago="$(( $(date -u +%s) - 3600 ))"
        if [ "$lock_epoch" -lt "$one_hour_ago" ]; then
            pass "acquired_epoch is genuinely old, not merely absent"
        else
            fail "acquired_epoch is genuinely old, not merely absent"
        fi
        ;;
esac

# Fact 1: baton-lock's own read of this lease, from a session that is not
# the one that wrote it -- the real behavioural premise the manual scenario
# rests on, not a reimplementation of its staleness logic in this test.
# Exit 4 specifically (see baton-lock's check verb), not just non-zero.
assert_exit_code 4 "baton-lock reports this fixture's lease as expired to the resuming session" \
    "$PLUGIN/scripts/baton-lock" check "$resuming_session"

# And acquire against it succeeds as a takeover, naming the displaced
# session -- the exact printed line RUNBOOK.md's scenario 3 tells the human
# to look for.
set +e
acquire_out="$("$PLUGIN/scripts/baton-lock" acquire "$resuming_session" 2>&1)"
acquire_rc=$?
set -e
assert_equals "$acquire_rc" "0" "acquiring this fixture's expired lease succeeds"
assert_contains "$acquire_out" "takeover=ghost-session-from-a-crashed-run" \
    "acquiring this fixture's expired lease names the session it displaced"

cd /
rm -rf "$FIXTURE"
FIXTURE=""
finish
