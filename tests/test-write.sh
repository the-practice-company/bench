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

# --- refuses before touching anything: mid-merge ---
git checkout -qb merge-feature
echo "feature" > conflict.txt
git add conflict.txt
git commit -q -m "feature change"
git checkout -q main
echo "main" > conflict.txt
git add conflict.txt
git commit -q -m "main change"
git merge -q merge-feature -m "merge attempt" >/dev/null 2>&1 || true

if [ -f .git/MERGE_HEAD ]; then
    pass "sanity: the fixture merge is genuinely conflicted before testing refusal"
else
    fail "sanity: the fixture merge is genuinely conflicted before testing refusal"
fi

dotfiles_before="$(find docs/baton -maxdepth 1 -name '.*' -type f | sort)"

set +e
printf 'updated_at: 2026-08-03T13:00:00Z\nCurrent wave: 2\n' \
    | "$WRITE" -m "checkpoint during merge" docs/baton/state.md
merge_rc=$?
set -e

assert_equals "$merge_rc" "3" "refuses to write during an unresolved merge"
assert_equals "$(git status --porcelain docs/baton | wc -l | tr -d ' ')" "0" \
    "docs/baton is untouched by the refused merge-time write"
assert_equals "$(find docs/baton -maxdepth 1 -name '.*' -type f | sort)" "$dotfiles_before" \
    "no temp files are left behind by the refused merge-time write"

git merge --abort

# --- rolls back if the commit fails after the file is already written ---
mkdir -p .git/hooks
cat > .git/hooks/pre-commit <<'EOF'
#!/bin/sh
exit 1
EOF
chmod +x .git/hooks/pre-commit

head_sha_before="$(git rev-parse HEAD)"
head_content_before="$(cat docs/baton/state.md)"

set +e
printf 'updated_at: 2026-08-03T14:00:00Z\nCurrent wave: 3\n' \
    | "$WRITE" -m "checkpoint blocked by hook" docs/baton/state.md
hook_rc=$?
set -e

assert_equals "$hook_rc" "5" "a rejecting pre-commit hook makes baton-write exit 5"
assert_equals "$(git rev-parse HEAD)" "$head_sha_before" "a rejected commit does not move HEAD"
assert_equals "$(git status --porcelain docs/baton | wc -l | tr -d ' ')" "0" \
    "the rollback leaves docs/baton clean, not staged-but-uncommitted"
assert_equals "$(cat docs/baton/state.md)" "$head_content_before" \
    "the rollback restores the file to exactly what HEAD had"

# --- the same rollback applies when the target never existed in HEAD ---
set +e
printf 'updated_at: X\nbrand new target\n' \
    | "$WRITE" -m "new file blocked by hook" docs/baton/other.md
new_target_rc=$?
set -e

assert_equals "$new_target_rc" "5" "a rejecting hook on a brand-new target also exits 5"
assert_equals "$(git status --porcelain docs/baton | wc -l | tr -d ' ')" "0" \
    "the rollback leaves docs/baton clean when the target never existed"
if [ -e docs/baton/other.md ]; then
    fail "the rollback removes the brand-new file rather than leaving it behind"
else
    pass "the rollback removes the brand-new file rather than leaving it behind"
fi

rm -f .git/hooks/pre-commit

# --- a dirty working tree forces a real commit even when stdin only differs
# from HEAD by the timestamp ---
printf '%s\nHAND EDITED, NEVER COMMITTED\n' "$(cat docs/baton/state.md)" > docs/baton/state.md
assert_contains "$(git status --porcelain docs/baton)" "M docs/baton/state.md" \
    "sanity: the hand edit leaves docs/baton dirty before the call"

dirty_commits_before="$(git rev-list --count HEAD)"
printf 'updated_at: 2026-08-03T15:00:00Z\nCurrent wave: 2\n' \
    | "$WRITE" -m "checkpoint over a dirty tree" docs/baton/state.md

assert_equals "$(git rev-list --count HEAD)" "$((dirty_commits_before + 1))" \
    "a dirty tree plus a timestamp-only diff still produces a commit"
assert_equals "$(git status --porcelain docs/baton | wc -l | tr -d ' ')" "0" \
    "the tree ends clean once the hand edit has been committed"

# --- empty stdin refuses to overwrite existing committed content ---
empty_commits_before="$(git rev-list --count HEAD)"
before_state_content="$(cat docs/baton/state.md)"

set +e
: | "$WRITE" -m "oops empty" docs/baton/state.md
empty_rc=$?
set -e

assert_equals "$empty_rc" "3" "empty stdin over existing committed content is refused"
assert_equals "$(git rev-list --count HEAD)" "$empty_commits_before" \
    "the refused empty write creates no commit"
assert_equals "$(cat docs/baton/state.md)" "$before_state_content" \
    "the refused empty write leaves the committed content untouched"

# --- empty stdin is still fine for a path with no committed version ---
set +e
: | "$WRITE" -m "empty but new" docs/baton/never-existed.md
empty_new_rc=$?
set -e

assert_equals "$empty_new_rc" "0" "empty stdin succeeds for a path absent from HEAD"
assert_file_exists "docs/baton/never-existed.md" "the empty file is created"
assert_equals "$(wc -c < docs/baton/never-existed.md | tr -d ' ')" "0" \
    "the created file is genuinely empty"
assert_equals "$(git status --porcelain docs/baton | wc -l | tr -d ' ')" "0" \
    "docs/baton is clean after the empty-but-new write"

assert_exit_code 64 "rejects being called without a path" "$WRITE"

finish
