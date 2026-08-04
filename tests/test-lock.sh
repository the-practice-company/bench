#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOCK="$REPO_ROOT/plugins/baton/scripts/baton-lock"
. "$SCRIPT_DIR/helpers.sh"

lock_field() {
    sed -n "s/^$1=//p" .baton/lock | head -1
}

make_fixture_repo

# --- free lock: acquire, re-acquire (the heartbeat), check ---
assert_exit_code 0 "acquires a free lock" "$LOCK" acquire session-a
assert_file_exists ".baton/lock" "writes the lock file"
assert_exit_code 0 "re-acquiring our own lock is the heartbeat, not an error" "$LOCK" acquire session-a
assert_exit_code 0 "check reports our own lock as held by us" "$LOCK" check session-a

# The lock file's contents, not just its existence: a write_lock that
# swapped or garbled fields would still pass an existence-only check.
assert_equals "$(lock_field session)" "session-a" "lock file records the session that holds it"
pid_field="$(lock_field pid)"
case "$pid_field" in
    ''|*[!0-9]*|0) fail "lock file records a plain positive integer pid" ;;
    *) pass "lock file records a plain positive integer pid" ;;
esac

# --- another session against an unexpired lease ---
assert_exit_code 3 "acquire refuses an unexpired lease held by someone else" "$LOCK" acquire session-b
assert_exit_code 3 "check reports an unexpired lease held by someone else" "$LOCK" check session-b

# --- release ---
assert_exit_code 3 "refuses to release a lock we do not hold" "$LOCK" release session-b
assert_file_exists ".baton/lock" "a refused release leaves the lock file in place"
assert_exit_code 0 "releases our own lock" "$LOCK" release session-a
assert_exit_code 5 "check reports no lock once released" "$LOCK" check session-a

# --- an expired lease (>= six hours old) ---
# Built from the current clock, not a hardcoded date: a fixed epoch is only
# "more than six hours old" depending on what time the suite happens to run.
mkdir -p .baton
cat > .baton/lock <<EOF
session=ghost
pid=99999999
acquired=2026-08-03T00:00:00Z
acquired_epoch=$(( $(date -u +%s) - 21601 ))
EOF
assert_exit_code 4 "check reports an expired lease as expired" "$LOCK" check session-c

set +e
acquire_out="$("$LOCK" acquire session-c)"
acquire_rc=$?
set -e
assert_equals "$acquire_rc" 0 "acquire on an expired lease succeeds"
assert_contains "$acquire_out" "takeover=ghost" "acquire on an expired lease names the displaced session"
assert_not_contains "$acquire_out" "takeover=session-c" "acquire on an expired lease does not name the new session"
assert_exit_code 0 "check reports our lock after taking over an expired lease" "$LOCK" check session-c

# --- concurrent acquire against an expired lease must have exactly one
# winner, not all of them. Before the mutex existed, every concurrent
# acquire against an expired lease returned 0 and printed takeover=<the
# same displaced session>, even though only one write actually persisted --
# reproduced ten trials out of ten. A single execution rarely catches a
# race, so this repeats the experiment ten times, each with several callers
# racing the same expired lease, and requires exactly one winner every time. ---
concurrent_trial=1
while [ "$concurrent_trial" -le 10 ]; do
    rm -rf .baton
    mkdir -p .baton
    cat > .baton/lock <<EOF
session=ghost-trial-$concurrent_trial
pid=99999999
acquired=2026-08-03T00:00:00Z
acquired_epoch=$(( $(date -u +%s) - 21601 ))
EOF

    race_results="$(mktemp -d)"
    racer=1
    while [ "$racer" -le 5 ]; do
        (
            # set +e around the call, not just `|| true`: this subshell
            # inherits set -e from the script, and a bare failing command
            # substitution assignment (`out="$(cmd)"` where cmd exits
            # non-zero -- the losing racers all do, with exit 3) would abort
            # the subshell right there, before rc=$? or the printf below
            # ever run. Four out of five racers are SUPPOSED to fail here;
            # losing the race is the normal case being tested, not an error
            # this subshell should die on.
            set +e
            out="$("$LOCK" acquire "racer-$concurrent_trial-$racer" 2>&1)"
            rc=$?
            set -e
            printf 'rc=%s out=%s\n' "$rc" "$out" > "$race_results/$racer"
        ) &
        racer=$((racer + 1))
    done
    wait

    # `|| true` on each: under pipefail (this script's own set -euo
    # pipefail), grep matching nothing exits non-zero even though wc/tr
    # after it succeed, which would abort this whole test file right here
    # if that pipeline's result is ever 0 -- exactly the outcome a broken
    # mutex would produce and this test exists to catch. The count still
    # ends up in $winners/$busy_losers either way; only the script's own
    # survival is being protected here, not the assertion below it.
    winners="$(grep -l '^rc=0' "$race_results"/* 2>/dev/null | wc -l | tr -d ' ')" || true
    assert_equals "$winners" "1" \
        "trial $concurrent_trial: exactly one concurrent acquire wins the takeover of an expired lease"

    busy_losers="$(grep -l '^rc=3' "$race_results"/* 2>/dev/null | wc -l | tr -d ' ')" || true
    assert_equals "$busy_losers" "4" \
        "trial $concurrent_trial: the other four concurrent acquires are correctly refused as busy, not silently dropped"

    rm -rf "$race_results"
    concurrent_trial=$((concurrent_trial + 1))
done

# --- takeover verb against an unexpired (live) lease ---
cat > .baton/lock <<EOF
session=incumbent
pid=$$
acquired=$(date -u +%Y-%m-%dT%H:%M:%SZ)
acquired_epoch=$(date -u +%s)
EOF
assert_exit_code 3 "sanity: the incumbent's lease is live before takeover" "$LOCK" check session-d

set +e
takeover_out="$("$LOCK" takeover session-d)"
takeover_rc=$?
set -e
assert_equals "$takeover_rc" 0 "takeover verb succeeds against an unexpired live lease"
assert_contains "$takeover_out" "takeover=incumbent" "takeover verb names the displaced session"
assert_equals "$(lock_field session)" "session-d" "lock file records the new session after takeover"
assert_exit_code 0 "check reports our lock after the takeover verb" "$LOCK" check session-d

# --- a garbled acquired_epoch fails open instead of crashing ---
cat > .baton/lock <<'EOF'
session=confused
pid=12345
acquired=2026-08-03T00:00:00Z
acquired_epoch=abc
EOF
assert_exit_code 4 "an unparseable acquired_epoch fails open to expired, not a crash" "$LOCK" check session-e

# --- the lease resolves against the repository root, not the caller's cwd ---
# A session acquiring from a subdirectory and one acquiring from the root
# would otherwise each write their own separate .baton/lock and both believe
# they hold the sole writer role -- the single-writer guarantee gone. This
# is the case that would have caught it.
rm -rf .baton
mkdir -p src/sub
in_subdir() { (cd src/sub && "$LOCK" "$@"); }

assert_exit_code 0 "acquires from a subdirectory" in_subdir acquire session-g
assert_file_exists ".baton/lock" "a lease acquired from a subdirectory lands at the repository root"
if [ -e src/sub/.baton ]; then
    fail "no stray .baton is created inside the subdirectory"
else
    pass "no stray .baton is created inside the subdirectory"
fi
assert_exit_code 0 "check from the repository root sees the lease acquired from a subdirectory" "$LOCK" check session-g
assert_exit_code 3 "a second session acquiring from the root is correctly refused, not granted a separate lease" "$LOCK" acquire session-h

# --- usage errors ---
assert_exit_code 64 "usage error: no arguments" "$LOCK"
assert_exit_code 64 "usage error: unknown verb" "$LOCK" frobnicate session-f
assert_exit_code 64 "usage error: too many arguments" "$LOCK" acquire session-f extra-arg

# --- an empty session id is a usage error, not a silently shared lease ---
# baton-lock validated argument count but never that the session id itself
# was non-empty. Every real caller passes
# "${CLAUDE_CODE_SESSION_ID:-$CLAUDE_SESSION_ID}" verbatim, and neither name
# is a documented contract, so an environment providing neither -- the case
# that fallback exists for -- was enough for two independent callers to
# both read the lock as "ours" (an empty owner field equals an empty
# caller id) and both get exit 0 with no takeover= line and no error at
# all -- the single-writer guarantee gone with nothing to show for it.
rm -rf .baton
assert_exit_code 64 "usage error: empty session id" "$LOCK" acquire ""
if [ -e .baton/lock ]; then
    fail "a rejected empty session id writes no lock file"
else
    pass "a rejected empty session id writes no lock file"
fi

empty_id_stderr="$("$LOCK" acquire "" 2>&1 >/dev/null || true)"
assert_contains "$empty_id_stderr" "session id" "the usage-error message names what was wrong: the session id"

# The same two-caller collision the fix closes, made concrete: both callers
# passing an empty session id must not both succeed.
set +e
first_empty_rc=0; first_empty_out="$("$LOCK" acquire "" 2>&1)" || first_empty_rc=$?
second_empty_rc=0; second_empty_out="$("$LOCK" acquire "" 2>&1)" || second_empty_rc=$?
set -e
assert_equals "$first_empty_rc" "64" "the first of two callers with an empty session id is refused"
assert_equals "$second_empty_rc" "64" "the second of two callers with an empty session id is refused too, not silently granted a shared lease"

finish
