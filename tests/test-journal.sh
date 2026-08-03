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

# Highest existing entry is still 0009 (after-gap above never created a file).
# Called from a subdirectory, the script must resolve docs/baton/journal
# against the repository root, not the caller's cwd -- otherwise it would see
# no entries there and hand out DEC-0001 again, colliding with the real one.
mkdir -p src/sub
out="$(cd src/sub && "$JOURNAL" from-subdir)"
assert_contains "$out" "id=DEC-0010" "allocates from a subdirectory using the repository root, not restarting at 1"
assert_contains "$out" "path=docs/baton/journal/0010-from-subdir.md" "path from a subdirectory is still relative to the repository root"

# A fixed 4-digit glob stops matching its own filenames once an id passes
# 9999, silently repeating the same id forever. Prove it now advances.
touch docs/baton/journal/9999-nines.md
out="$("$JOURNAL" first-past-nines)"
assert_contains "$out" "id=DEC-10000" "advances past 9999"
touch docs/baton/journal/10000-first-past-nines.md
out="$("$JOURNAL" second-past-nines)"
assert_contains "$out" "id=DEC-10001" "advances again instead of repeating DEC-10000"

finish
