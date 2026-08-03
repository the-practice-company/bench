#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOCK="$REPO_ROOT/plugins/baton/scripts/baton-lock"
. "$SCRIPT_DIR/helpers.sh"

make_fixture_repo

assert_exit_code 0 "acquires a free lock" "$LOCK" acquire session-a
assert_file_exists ".baton/lock" "writes the lock file"
assert_exit_code 0 "acquiring our own lock again is a no-op" "$LOCK" acquire session-a
assert_exit_code 0 "check reports our own lock as held by us" "$LOCK" check session-a

# A different session, whose pid is this live test process, must be refused.
assert_exit_code 3 "refuses a lock held by another live session" "$LOCK" acquire session-b
assert_exit_code 3 "check reports another live session" "$LOCK" check session-b

assert_exit_code 3 "refuses to release a lock we do not hold" "$LOCK" release session-b
assert_exit_code 0 "releases our own lock" "$LOCK" release session-a
assert_exit_code 5 "check reports no lock once released" "$LOCK" check session-a

# A lock owned by a dead pid is stale and may be taken over.
mkdir -p .baton
cat > .baton/lock <<'EOF'
session=ghost
pid=99999999
acquired=2026-08-03T00:00:00Z
acquired_epoch=1785715200
EOF
assert_exit_code 4 "check reports a dead-pid lock as stale" "$LOCK" check session-c
takeover="$("$LOCK" acquire session-c)"
assert_contains "$takeover" "takeover=ghost" "reports whose stale lock was taken over"
assert_exit_code 0 "check reports our lock after takeover" "$LOCK" check session-c

# A lock older than six hours is stale even if its pid is alive.
cat > .baton/lock <<EOF
session=elder
pid=$$
acquired=2026-08-03T00:00:00Z
acquired_epoch=$(( $(date -u +%s) - 21601 ))
EOF
assert_exit_code 4 "check reports a six-hour-old lock as stale" "$LOCK" check session-d

finish
