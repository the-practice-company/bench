#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
WRITE="$REPO_ROOT/plugins/baton/scripts/baton-write"
. "$SCRIPT_DIR/helpers.sh"

make_fixture_repo

printf 'updated_at: 2026-08-03T10:00:00Z\nCurrent wave: 1\n' \
    | "$WRITE" -m "baton: first checkpoint" docs/baton/state.md

assert_file_exists "docs/baton/state.md" "creates the file and its parents"
assert_equals "$(git status --porcelain docs/baton | wc -l | tr -d ' ')" "0" \
    "leaves docs/baton clean, so no state exists outside the log"
assert_contains "$(git log -1 --pretty=%s)" "baton: first checkpoint" "uses the given commit message"

commits_before="$(git rev-list --count HEAD)"

# Same content, later timestamp: nothing of substance changed.
printf 'updated_at: 2026-08-03T11:00:00Z\nCurrent wave: 1\n' \
    | "$WRITE" -m "baton: idle checkpoint" docs/baton/state.md

assert_equals "$(git rev-list --count HEAD)" "$commits_before" "an idle checkpoint creates no commit"
assert_equals "$(git status --porcelain docs/baton | wc -l | tr -d ' ')" "0" \
    "an idle checkpoint leaves no dirty file behind"
assert_contains "$(cat docs/baton/state.md)" "2026-08-03T10:00:00Z" \
    "an idle checkpoint does not even rewrite the timestamp"

# Real change: commits.
printf 'updated_at: 2026-08-03T12:00:00Z\nCurrent wave: 2\n' \
    | "$WRITE" -m "baton: wave 2" docs/baton/state.md

assert_equals "$(git rev-list --count HEAD)" "$((commits_before + 1))" "a real change creates one commit"
assert_contains "$(cat docs/baton/state.md)" "Current wave: 2" "a real change lands on disk"
assert_equals "$(git status --porcelain docs/baton | wc -l | tr -d ' ')" "0" \
    "docs/baton is clean after a real change too"

assert_exit_code 64 "rejects being called without a path" "$WRITE"

finish
