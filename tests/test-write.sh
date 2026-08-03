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

# --- refuses a gitignored target before writing anything ---
echo "docs/baton/ignored.md" > .gitignore
git add .gitignore
git commit -q -m "ignore docs/baton/ignored.md"

set +e
printf 'updated_at: X\nshould never be written\n' \
    | "$WRITE" -m "checkpoint to an ignored path" docs/baton/ignored.md
ignored_rc=$?
set -e

assert_equals "$ignored_rc" "3" "refuses a gitignored target"
if [ -e docs/baton/ignored.md ]; then
    fail "a refused gitignored write leaves nothing on disk"
else
    pass "a refused gitignored write leaves nothing on disk"
fi
assert_equals "$(git status --porcelain --ignored -- docs/baton/ignored.md)" "" \
    "git status --porcelain --ignored shows no trace of the refused write either"

# --- a git add failure (not just a commit failure) enters the same
# rollback path: a contended .git/index.lock makes `git add` itself fail ---
addfail_head_before="$(git rev-parse HEAD)"
touch .git/index.lock
set +e
printf 'updated_at: X\nshould be rolled back\n' \
    | "$WRITE" -m "checkpoint blocked by a failed add" docs/baton/index-locked.md
addfail_rc=$?
set -e
rm -f .git/index.lock

echo "  -- git status --porcelain after the failed-add rollback --"
git status --porcelain docs/baton | sed 's/^/     /'
assert_equals "$addfail_rc" "5" "a git add failure (not just a commit failure) triggers the rollback path"
assert_equals "$(git rev-parse HEAD)" "$addfail_head_before" \
    "the rollback after a failed add leaves HEAD unmoved"
assert_equals "$(git status --porcelain docs/baton | wc -l | tr -d ' ')" "0" \
    "the rollback after a failed add leaves docs/baton clean"
if [ -e docs/baton/index-locked.md ]; then
    fail "the rollback after a failed add removes the brand-new file"
else
    pass "the rollback after a failed add removes the brand-new file"
fi

# --- a rollback that itself cannot restore reports exit 7 loudly, instead
# of crashing (the old behaviour) or silently claiming a clean tree ---
unrecoverable_head_before="$(git rev-parse HEAD)"
touch .git/index.lock
set +e
unrecoverable_stderr="$(printf 'updated_at: X\nunrecoverable attempt\n' \
    | "$WRITE" -m "checkpoint that cannot roll back" docs/baton/state.md 2>&1 >/dev/null)"
unrecoverable_rc=$?
set -e
rm -f .git/index.lock

echo "  -- git status --porcelain right after the exit-7 case (this is the assertion that matters) --"
git status --porcelain docs/baton | sed 's/^/     /'
assert_equals "$unrecoverable_rc" "7" "a rollback that cannot restore the tree exits 7"
assert_contains "$unrecoverable_stderr" "docs/baton/state.md" \
    "the exit-7 message names the path that needs manual resolution"
assert_equals "$(git rev-parse HEAD)" "$unrecoverable_head_before" \
    "no commit lands when the rollback itself fails"
assert_contains "$(git status --porcelain docs/baton)" "M docs/baton/state.md" \
    "the exit-7 case genuinely leaves the tree dirty rather than silently claiming success"

# Clean up by hand (the lock is gone now, so this succeeds) so later
# assertions are not built on a tree this case deliberately left dirty.
git checkout -q HEAD -- docs/baton/state.md
assert_equals "$(git status --porcelain docs/baton | wc -l | tr -d ' ')" "0" \
    "sanity: manual cleanup after the exit-7 case restores a clean tree"

# --- an absolute path to a file with real committed content, given empty
# stdin: refused, not silently truncated. $FIXTURE is used unresolved
# (not canonicalised first) because that is the realistic case: mktemp -d
# routes through a symlink on macOS (/tmp -> /private/tmp), so a caller
# building an absolute path this way is the normal case, not an edge one. ---
before_state_content_abs="$(cat docs/baton/state.md)"
set +e
: | "$WRITE" -m "oops empty via absolute path" "$FIXTURE/docs/baton/state.md"
abs_empty_rc=$?
set -e

assert_equals "$abs_empty_rc" "3" "an absolute path does not bypass the empty-stdin guard"
assert_equals "$(cat docs/baton/state.md)" "$before_state_content_abs" \
    "the committed content survives the absolute-path empty-stdin attempt"
assert_equals "$(git status --porcelain docs/baton | wc -l | tr -d ' ')" "0" \
    "docs/baton stays clean after the refused absolute-path write"

# --- invoked from a subdirectory with the conventional repo-root-relative
# path: the real docs/baton/state.md is what gets updated, not a duplicate
# nested under the subdirectory ---
mkdir -p somewhere/deep
subdir_commits_before="$(git rev-list --count HEAD)"
(cd somewhere/deep && printf 'updated_at: 2026-08-03T16:00:00Z\nCurrent wave: 4\n' \
    | "$WRITE" -m "checkpoint from a subdirectory" docs/baton/state.md)

assert_equals "$(git rev-list --count HEAD)" "$((subdir_commits_before + 1))" \
    "a subdirectory invocation with a root-relative path creates exactly one commit"
assert_contains "$(cat docs/baton/state.md)" "Current wave: 4" \
    "the real, repo-root state.md is what gets updated"
if [ -e somewhere/deep/docs/baton/state.md ]; then
    fail "no duplicate file appears under the subdirectory"
else
    pass "no duplicate file appears under the subdirectory"
fi
assert_equals "$(git status --porcelain | wc -l | tr -d ' ')" "0" \
    "the tree is fully clean after the subdirectory invocation"

# --- an absolute path outside the repository is refused, not guessed at ---
outside_dir="$(mktemp -d)"
set +e
printf 'updated_at: X\nshould be refused\n' \
    | "$WRITE" -m "should be refused" "$outside_dir/docs/baton/state.md"
outside_rc=$?
set -e
rm -rf "$outside_dir"

assert_equals "$outside_rc" "3" "an absolute path outside the repository is refused"

# --- CRLF content that differs from HEAD only by the timestamp is still
# idle under core.autocrlf=input: the comparison goes through git's own
# normalisation (git hash-object), not raw bytes ---
git config core.autocrlf input
crlf_commits_before="$(git rev-list --count HEAD)"
printf 'updated_at: 2026-08-03T17:00:00Z\r\nCurrent wave: 4\r\n' \
    | "$WRITE" -m "checkpoint, CRLF, should be idle" docs/baton/state.md

assert_equals "$(git rev-list --count HEAD)" "$crlf_commits_before" \
    "a CRLF-only, timestamp-only diff under autocrlf=input still creates no commit"
assert_equals "$(git status --porcelain docs/baton | wc -l | tr -d ' ')" "0" \
    "the tree stays clean after the CRLF idle attempt"

assert_exit_code 64 "rejects being called without a path" "$WRITE"

# --- the constitution is the human's file: baton-write refuses it outright,
# before anything is written, no matter how the path is spelled. This is the
# fix for a real, reproduced bypass: an agent stuck on a failing verify_cmd
# could otherwise pipe a new one straight into the file it is judged
# against, through the exact same tool used for every ordinary checkpoint. ---
constitution_commits_before="$(git rev-list --count HEAD)"

set +e
printf 'schema: baton/constitution/v1\nstatus: ratified\nverify_cmd: "echo always-pass"\n' \
    | "$WRITE" -m "agent: weaken the gate" docs/baton/constitution.md
constitution_rc=$?
set -e

assert_equals "$constitution_rc" "3" "refuses to write docs/baton/constitution.md by its plain relative path"
assert_equals "$(git rev-list --count HEAD)" "$constitution_commits_before" \
    "the refused constitution write creates no commit"
if [ -e docs/baton/constitution.md ]; then
    fail "the refused constitution write leaves nothing on disk"
else
    pass "the refused constitution write leaves nothing on disk"
fi

# Same refusal via an absolute path -- the normalisation that turns an
# absolute path back into a repo-root-relative one must not create a way
# around this, or the "before touching anything" guarantee is a fiction.
set +e
printf 'status: ratified\nverify_cmd: "echo always-pass"\n' \
    | "$WRITE" -m "agent: weaken the gate via absolute path" "$FIXTURE/docs/baton/constitution.md"
constitution_abs_rc=$?
set -e

assert_equals "$constitution_abs_rc" "3" "refuses to write docs/baton/constitution.md via an absolute path"
assert_equals "$(git rev-list --count HEAD)" "$constitution_commits_before" \
    "the refused absolute-path constitution write creates no commit"

# Same refusal called from a subdirectory with the conventional repo-root-
# relative path -- the same shape that once made baton-write and baton-lock
# silently operate on the wrong file entirely (see the subdirectory tests
# above); here the risk is the opposite one, silently succeeding where it
# must not.
set +e
( cd somewhere/deep && printf 'status: ratified\nverify_cmd: "echo always-pass"\n' \
    | "$WRITE" -m "agent: weaken the gate from a subdirectory" docs/baton/constitution.md )
constitution_subdir_rc=$?
set -e

assert_equals "$constitution_subdir_rc" "3" "refuses to write docs/baton/constitution.md invoked from a subdirectory"
assert_equals "$(git rev-list --count HEAD)" "$constitution_commits_before" \
    "the refused subdirectory constitution write creates no commit"
if [ -e docs/baton/constitution.md ] || [ -e somewhere/deep/docs/baton/constitution.md ]; then
    fail "no constitution.md appears anywhere after the refused subdirectory write"
else
    pass "no constitution.md appears anywhere after the refused subdirectory write"
fi

# --- docs/baton/state.md's 60-line cap is enforced here, not only checked
# against the shipped template: a state file grown past the cap by real
# checkpoints must be refused too, not just the day-one copy. ---
cap_commits_before="$(git rev-list --count HEAD)"

sixty_lines="$(for i in $(seq 1 60); do echo "line $i"; done)"
printf '%s\n' "$sixty_lines" | "$WRITE" -m "checkpoint at exactly 60 lines" docs/baton/state.md
assert_equals "$(git rev-list --count HEAD)" "$((cap_commits_before + 1))" \
    "exactly 60 lines is accepted, not refused by an off-by-one"
assert_equals "$(wc -l < docs/baton/state.md | tr -d ' ')" "60" \
    "the 60-line file lands with exactly 60 lines"

over_cap_commits_before="$(git rev-list --count HEAD)"
sixty_one_lines="$(for i in $(seq 1 61); do echo "line $i"; done)"
set +e
cap_stderr="$(printf '%s\n' "$sixty_one_lines" | "$WRITE" -m "checkpoint at 61 lines" docs/baton/state.md 2>&1 >/dev/null)"
cap_rc=$?
set -e

assert_equals "$cap_rc" "3" "refuses docs/baton/state.md at 61 lines, over the 60-line cap"
assert_contains "$cap_stderr" "60" "the refusal message names the 60-line cap"
assert_equals "$(git rev-list --count HEAD)" "$over_cap_commits_before" \
    "the refused over-cap write creates no commit"
assert_equals "$(wc -l < docs/baton/state.md | tr -d ' ')" "60" \
    "state.md still holds the last accepted (60-line) content, not the refused 61-line one"
assert_equals "$(git status --porcelain docs/baton | wc -l | tr -d ' ')" "0" \
    "docs/baton is clean after the refused over-cap write"

finish
