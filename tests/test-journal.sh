#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
JOURNAL="$REPO_ROOT/plugins/baton/scripts/baton-journal"
. "$SCRIPT_DIR/helpers.sh"

make_fixture_repo

out="$("$JOURNAL" first-decision)"
assert_contains "$out" "id=DEC-0001" "numbers the first entry DEC-0001"
assert_contains "$out" "path=docs/baton/journal/0001-first-decision.md" "builds the first path"

mkdir -p docs/baton/journal
touch docs/baton/journal/0001-first-decision.md
touch docs/baton/journal/0007-later-decision.md

out="$("$JOURNAL" next-one)"
assert_contains "$out" "id=DEC-0008" "continues from the highest existing number, not the count"
assert_contains "$out" "path=docs/baton/journal/0008-next-one.md" "builds the next path"

touch docs/baton/journal/0009-not-a-gap.md
out="$("$JOURNAL" after-gap)"
assert_contains "$out" "id=DEC-0010" "ignores gaps below the maximum"

assert_exit_code 64 "rejects an empty slug" "$JOURNAL" ""
assert_exit_code 64 "rejects a slug with uppercase or spaces" "$JOURNAL" "Not A Slug"

finish
