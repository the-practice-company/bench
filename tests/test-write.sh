#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
WRITE="$REPO_ROOT/plugins/baton/scripts/baton-write"
. "$SCRIPT_DIR/helpers.sh"

make_fixture_repo

# Every write to docs/baton/state.md below goes through this. baton-write
# refuses a state.md whose frontmatter it cannot read -- flags it cannot see
# are a stop it cannot enforce -- so a two-line fixture that was never a state
# document would now be turned away for that, rather than for whatever the
# case using it is actually testing. A seven-line header -- the block, then the
# blank line under it -- and then whatever body the case wants; called with no
# body at all it emits just the header, which is what the line-cap cases pad.
state_doc() {
    # state_doc <updated_at> [<body line>...]
    local updated_at="$1"
    shift
    printf '%s\n' \
        '---' \
        'schema: baton/state/v1' \
        "updated_at: $updated_at" \
        'suspect: false' \
        'needs_human: false' \
        '---' \
        ''
    [ $# -eq 0 ] || printf '%s\n' "$@"
    return 0
}

# CRLF on every line, the opening --- included, which is what a file written
# by a Windows editor actually looks like. Used by the idle-checkpoint case
# below and by the reader case at the end of this file.
crlf() { awk '{ printf "%s\r\n", $0 }'; }

state_doc 2026-08-03T10:00:00Z 'Current wave: 1' \
    | "$WRITE" -m "baton: first checkpoint" docs/baton/state.md

assert_file_exists "docs/baton/state.md" "creates the file and its parents"
assert_equals "$(git status --porcelain docs/baton | wc -l | tr -d ' ')" "0" \
    "leaves docs/baton clean, so no state exists outside the log"
assert_contains "$(git log -1 --pretty=%s)" "baton: first checkpoint" "uses the given commit message"

commits_before="$(git rev-list --count HEAD)"

# Same content, later timestamp: nothing of substance changed.
state_doc 2026-08-03T11:00:00Z 'Current wave: 1' \
    | "$WRITE" -m "baton: idle checkpoint" docs/baton/state.md

assert_equals "$(git rev-list --count HEAD)" "$commits_before" "an idle checkpoint creates no commit"
assert_equals "$(git status --porcelain docs/baton | wc -l | tr -d ' ')" "0" \
    "an idle checkpoint leaves no dirty file behind"
assert_contains "$(cat docs/baton/state.md)" "2026-08-03T10:00:00Z" \
    "an idle checkpoint does not even rewrite the timestamp"

# Real change: commits.
state_doc 2026-08-03T12:00:00Z 'Current wave: 2' \
    | "$WRITE" -m "baton: wave 2" docs/baton/state.md

assert_equals "$(git rev-list --count HEAD)" "$((commits_before + 1))" "a real change creates one commit"
assert_contains "$(cat docs/baton/state.md)" "Current wave: 2" "a real change lands on disk"
assert_equals "$(git status --porcelain docs/baton | wc -l | tr -d ' ')" "0" \
    "docs/baton is clean after a real change too"

# --- the fallback commit message (-m omitted) has never once run under
# test: every call above passes -m explicitly. baton-write falls back to
# `message="baton: update $(basename "$target")"` -- exercise it directly,
# including through a target whose basename holds characters that would
# matter if this were built by anything less careful than plain variable
# expansion: a space, and a double quote. ---
default_msg_commits_before="$(git rev-list --count HEAD)"
printf 'updated_at: 2026-08-03T18:00:00Z\nno -m given\n' \
    | "$WRITE" docs/baton/default-message-target.md

assert_equals "$(git rev-list --count HEAD)" "$((default_msg_commits_before + 1))" \
    "a write without -m still creates a commit"
assert_equals "$(git log -1 --pretty=%s)" "baton: update default-message-target.md" \
    "the fallback commit message is baton: update <basename>, exercised for the first time here"

# A basename with a space: the fallback message must carry it through
# whole, not split it into separate words somewhere along the way.
printf 'updated_at: 2026-08-03T18:05:00Z\nspace in basename\n' \
    | "$WRITE" "docs/baton/has space.md"
assert_equals "$(git log -1 --pretty=%s)" "baton: update has space.md" \
    "the fallback message preserves a basename containing a space"

# A basename with a double quote: $(basename "$target") lands inside
# message="baton: update $(...)" through plain variable expansion, never
# eval or re-parsed as shell -- a literal quote in the byte stream must
# stay a literal quote in the commit subject, not get shell-interpreted or
# silently dropped.
printf 'updated_at: 2026-08-03T18:10:00Z\nquote in basename\n' \
    | "$WRITE" "docs/baton/weird\"name.md"
assert_equals "$(git log -1 --pretty=%s)" 'baton: update weird"name.md' \
    "the fallback message preserves a basename containing a double quote"

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
state_doc 2026-08-03T13:00:00Z 'Current wave: 2' \
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
state_doc 2026-08-03T14:00:00Z 'Current wave: 3' \
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
state_doc 2026-08-03T15:00:00Z 'Current wave: 2' \
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

# --- whitespace-only stdin is refused exactly like empty stdin, over
# existing committed content: `[ ! -s "$tmp" ]` (the old guard) only ever
# caught a strictly zero-byte file, so a single newline -- the shape a
# failed command substitution piped through `printf '%s\n'` actually
# produces -- sailed straight past it. Reproduced: a full state.md replaced
# by one blank line, exit 0, committed as an ordinary checkpoint. ---
whitespace_commits_before="$(git rev-list --count HEAD)"
before_state_content_ws="$(cat docs/baton/state.md)"

set +e
newline_stderr="$(printf '\n' | "$WRITE" -m "oops one blank line" docs/baton/state.md 2>&1 >/dev/null)"
newline_rc=$?
set -e

assert_equals "$newline_rc" "3" "a single newline over existing committed content is refused like empty stdin"
assert_contains "$newline_stderr" "docs/baton/state.md" "the whitespace-only refusal names the path"
# A single newline has no frontmatter either, so this pins which guard answers
# it: the caller bug it is, not the document shape it also happens to lack.
assert_contains "$newline_stderr" "empty-or-whitespace-only content" \
    "the single-newline refusal comes from the whitespace guard, which is the one that knows what went wrong"
assert_equals "$(git rev-list --count HEAD)" "$whitespace_commits_before" \
    "the refused single-newline write creates no commit"
assert_equals "$(cat docs/baton/state.md)" "$before_state_content_ws" \
    "the refused single-newline write leaves the committed content untouched"

set +e
printf '   \t  \t\n   \n\t\n' | "$WRITE" -m "oops spaces and tabs" docs/baton/state.md
spaces_tabs_rc=$?
set -e

assert_equals "$spaces_tabs_rc" "3" "spaces and tabs alone over existing committed content are refused like empty stdin"
assert_equals "$(git rev-list --count HEAD)" "$whitespace_commits_before" \
    "the refused spaces-and-tabs write creates no commit"
assert_equals "$(cat docs/baton/state.md)" "$before_state_content_ws" \
    "the refused spaces-and-tabs write leaves the committed content untouched"

# --- whitespace-only stdin is still fine for a path with no committed
# version, same as strictly-empty stdin already is above ---
set +e
printf '\n' | "$WRITE" -m "whitespace but new" docs/baton/never-existed-ws.md
whitespace_new_rc=$?
set -e

assert_equals "$whitespace_new_rc" "0" "whitespace-only stdin succeeds for a path absent from HEAD"
assert_file_exists "docs/baton/never-existed-ws.md" "the whitespace-only file is created"
assert_equals "$(cat docs/baton/never-existed-ws.md)" "" \
    "the created file holds only the whitespace it was given"

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
unrecoverable_stderr="$(state_doc 2026-08-03T14:30:00Z 'unrecoverable attempt' \
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

# --- a rollback whose own verification command fails must also exit 7, not
# exit 5. This is a different failure shape than the case just above: there,
# `git status` ran fine and correctly reported a dirty tree. Here, `git
# status` itself cannot run at all (reproduced with an unreadable
# .git/index, which also makes `git add`/`git commit` fail the same way).
# Before the fix, `[ -n "$(git status ... 2>/dev/null)" ]` read that failure
# as empty stdout, which is indistinguishable from "clean" -- so the script
# reported exit 5 ("the tree was restored") and exited having verified
# nothing, while the new, uncommitted content was still sitting in the
# working tree. ---
verify_fail_head_before="$(git rev-parse HEAD)"
verify_fail_content_before="$(cat docs/baton/state.md)"
chmod 000 .git/index
set +e
verify_fail_stderr="$(state_doc 2026-08-03T14:45:00Z 'unverifiable rollback attempt' \
    | "$WRITE" -m "checkpoint whose rollback cannot even be checked" docs/baton/state.md 2>&1 >/dev/null)"
verify_fail_rc=$?
set -e
chmod 644 .git/index

assert_equals "$verify_fail_rc" "7" \
    "a rollback whose own verification fails exits 7, not the 5 that would claim a clean tree"
assert_contains "$verify_fail_stderr" "docs/baton/state.md" \
    "the exit-7-from-unverifiable message names the path that needs manual resolution"
assert_not_contains "$verify_fail_stderr" "the tree was restored" \
    "an unverifiable rollback never claims the tree was restored"
assert_equals "$(git rev-parse HEAD)" "$verify_fail_head_before" \
    "no commit lands when the rollback's own verification fails"
assert_contains "$(cat docs/baton/state.md)" "unverifiable rollback attempt" \
    "the unrolled-back write is genuinely still on disk, proving exit 5 would have lied"

# Clean up by hand so later assertions are not built on a tree this case
# deliberately left dirty.
git checkout -q HEAD -- docs/baton/state.md
assert_equals "$(cat docs/baton/state.md)" "$verify_fail_content_before" \
    "sanity: manual cleanup after the unverifiable-rollback case restores the prior content"
assert_equals "$(git status --porcelain docs/baton | wc -l | tr -d ' ')" "0" \
    "sanity: manual cleanup after the unverifiable-rollback case restores a clean tree"

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
(cd somewhere/deep && state_doc 2026-08-03T16:00:00Z 'Current wave: 4' \
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
# normalisation (git hash-object), not raw bytes.
#
# Captured rather than run bare, because a state.md written in CRLF now has to
# get past the frontmatter reader before the idle comparison is even reached.
# A reader that stopped stripping \r would refuse it, and a bare call refused
# under set -e takes the whole file down mid-run -- reporting nothing, with
# every case after this one silently unrun. Named assertions instead. ---
git config core.autocrlf input
crlf_commits_before="$(git rev-list --count HEAD)"
set +e
crlf_idle_stderr="$(state_doc 2026-08-03T17:00:00Z 'Current wave: 4' | crlf \
    | "$WRITE" -m "checkpoint, CRLF, should be idle" docs/baton/state.md 2>&1 >/dev/null)"
crlf_idle_rc=$?
set -e

assert_equals "$crlf_idle_rc" "0" \
    "a CRLF state.md is read like any other, not turned away for its line endings"
assert_equals "$crlf_idle_stderr" "" "the CRLF idle checkpoint prints no refusal"
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

# --- same refusal again, this time via alternate spellings of the identical
# path: a leading "./", an internal "..", and a doubled "/". Before
# canonicalize_target existed, each of these walked straight past the plain
# `[ "$target" = "docs/baton/constitution.md" ]` string comparison and
# committed the tampered content -- git add/commit resolve all of them to
# the same blob path, so the resulting commit was indistinguishable from a
# legitimate checkpoint. This is the reproduced bypass the fix closes. ---
for spelling in \
    "./docs/baton/constitution.md" \
    "docs/baton/../baton/constitution.md" \
    "docs//baton/constitution.md"
do
    set +e
    printf 'schema: baton/constitution/v1\nstatus: ratified\nverify_cmd: "echo always-pass"\n' \
        | "$WRITE" -m "agent: weaken the gate via $spelling" "$spelling"
    spelling_rc=$?
    set -e

    assert_equals "$spelling_rc" "3" "refuses docs/baton/constitution.md spelled as $spelling"
    assert_equals "$(git rev-list --count HEAD)" "$constitution_commits_before" \
        "the refused $spelling write creates no commit"
    if [ -e docs/baton/constitution.md ]; then
        fail "the refused $spelling write leaves nothing on disk"
    else
        pass "the refused $spelling write leaves nothing on disk"
    fi
done

# --- canonicalisation is not just a refusal-widener: a doubled slash to an
# ordinary, unguarded target used to die with an unguarded `fatal: path ...
# exists on disk, but not in 'HEAD'` and exit 128 (git's own path lookups
# never treated "docs//baton/plain.md" and "docs/baton/plain.md" as the same
# path the way `git add`/`git commit` do). Canonicalising up front means
# git only ever sees the clean spelling, so this now succeeds normally. ---
set +e
canon_stderr="$(printf 'updated_at: X\nplain content\n' \
    | "$WRITE" -m "checkpoint via a doubled slash" docs//baton/plain.md 2>&1 >/dev/null)"
canon_rc=$?
set -e

assert_equals "$canon_rc" "0" "a doubled slash to an ordinary target no longer dies with exit 128"
assert_equals "$canon_stderr" "" "a doubled slash to an ordinary target produces no fatal: noise"
assert_contains "$(cat docs/baton/plain.md 2>/dev/null)" "plain content" \
    "the doubled-slash write lands at the canonical, single-slash path"

# --- docs/baton/state.md's 60-line cap is enforced here, not only checked
# against the shipped template: a state file grown past the cap by real
# checkpoints must be refused too, not just the day-one copy.
#
# Both documents are real state files, header and all, padded to length with
# body lines -- sixty lines of bare filler is a shape state.md cannot take, and
# a cap tested against a document that could never exist tests nothing. It also
# turns the 61-line case into the wrong refusal: baton-write would turn it away
# for its unreadable frontmatter, which is exit 3 with the right number on it
# for the wrong reason, so the assertions below name the cap's own message. ---
cap_commits_before="$(git rev-list --count HEAD)"

# state_doc's header is 7 lines, so $1 filler lines make a document of $1 + 7.
cap_filler() {
    local i
    for i in $(seq 1 "$1"); do echo "line $i"; done
}

sixty_lines="$(state_doc 2026-08-03T19:00:00Z; cap_filler 53)"
printf '%s\n' "$sixty_lines" | "$WRITE" -m "checkpoint at exactly 60 lines" docs/baton/state.md
assert_equals "$(git rev-list --count HEAD)" "$((cap_commits_before + 1))" \
    "exactly 60 lines is accepted, not refused by an off-by-one"
assert_equals "$(wc -l < docs/baton/state.md | tr -d ' ')" "60" \
    "the 60-line file lands with exactly 60 lines"

over_cap_commits_before="$(git rev-list --count HEAD)"
sixty_one_lines="$(state_doc 2026-08-03T19:05:00Z; cap_filler 54)"
assert_equals "$(printf '%s\n' "$sixty_one_lines" | wc -l | tr -d ' ')" "61" \
    "sanity: the over-cap fixture is one line over the cap, not merely long"
set +e
cap_stderr="$(printf '%s\n' "$sixty_one_lines" | "$WRITE" -m "checkpoint at 61 lines" docs/baton/state.md 2>&1 >/dev/null)"
cap_rc=$?
set -e

assert_equals "$cap_rc" "3" "refuses docs/baton/state.md at 61 lines, over the 60-line cap"
assert_contains "$cap_stderr" "at 61 lines: the cap is 60" "the refusal message names the 60-line cap"
assert_not_contains "$cap_stderr" "no frontmatter block this tool can read" \
    "the over-cap write is refused for being over the cap, not for a frontmatter block it has"
assert_equals "$(git rev-list --count HEAD)" "$over_cap_commits_before" \
    "the refused over-cap write creates no commit"
assert_equals "$(wc -l < docs/baton/state.md | tr -d ' ')" "60" \
    "state.md still holds the last accepted (60-line) content, not the refused 61-line one"
assert_equals "$(git status --porcelain docs/baton | wc -l | tr -d ' ')" "0" \
    "docs/baton is clean after the refused over-cap write"

# --- the same 61-line refusal via the same alternate spellings as the
# constitution bypass above: the cap is baton's own schema knowledge, gated
# on `[ "$target" = "docs/baton/state.md" ]` exactly like the constitution
# refusal is, so it was defeated by the identical trick. ---
for spelling in \
    "./docs/baton/state.md" \
    "docs/baton/../baton/state.md" \
    "docs//baton/state.md"
do
    spelling_cap_commits_before="$(git rev-list --count HEAD)"
    set +e
    spelling_cap_stderr="$(printf '%s\n' "$sixty_one_lines" \
        | "$WRITE" -m "checkpoint at 61 lines via $spelling" "$spelling" 2>&1 >/dev/null)"
    spelling_cap_rc=$?
    set -e

    assert_equals "$spelling_cap_rc" "3" "refuses docs/baton/state.md at 61 lines spelled as $spelling"
    assert_contains "$spelling_cap_stderr" "at 61 lines: the cap is 60" \
        "the $spelling refusal message names the 60-line cap"
    assert_equals "$(git rev-list --count HEAD)" "$spelling_cap_commits_before" \
        "the refused $spelling over-cap write creates no commit"
    assert_equals "$(wc -l < docs/baton/state.md | tr -d ' ')" "60" \
        "state.md still holds 60 lines after the refused $spelling over-cap write"
done

# --- granted fields move one way only. The skill states it as a rule --
# "raising suspect or needs_human is always yours; clearing either is the
# human's" -- and baton-write is where it stops being only prose. The refusal
# is on the transition, not on the value, so it takes four cases to pin and
# not two: refusing every state.md write outright would be just as green on
# the two refusals below as the real rule is. ---

# 19 lines, under the cap, and shaped like the real template: the `Now`
# section carries a `**Suspect:**` line, which is exactly the body text a
# flag lookup that was not scoped to the frontmatter would read as the flag.
state_with_flags() {
    printf '%s\n' \
        '---' \
        'schema: baton/state/v1' \
        'writer: test-session' \
        'updated_at: 2026-08-04T09:00:00Z' \
        'observed_sha: 0000000' \
        'observed_branch: main' \
        'tree_clean: true' \
        "suspect: $1" \
        "needs_human: $2" \
        'autopilot: off' \
        'autopilot_grant: —' \
        '---' \
        '' \
        '# State' \
        '' \
        '## Now' \
        '' \
        "- **Next action:** $3" \
        '- **Suspect:** none'
}

# The baseline goes into HEAD with plain git, never through baton-write: the
# `suspect: true` baseline could not be arrived at through the refusal it is
# about to test, and a fixture built out of the thing under test proves less.
#
# --allow-empty because a baseline is allowed to repeat one: with nothing
# staged, `git commit` exits 1 and set -e kills this file mid-run, reporting
# git's "nothing to commit" instead of any named assertion. Only the third
# argument -- which reads as a label, and is one -- keeps that from happening
# today, and a label is not a thing to make load-bearing.
commit_state_flags() {
    state_with_flags "$1" "$2" "$3" > docs/baton/state.md
    git add docs/baton/state.md
    git commit -q --allow-empty -m "fixture: state.md suspect=$1 needs_human=$2 ($3)"
}

commit_state_flags true false "suspect baseline"
clear_suspect_commits_before="$(git rev-list --count HEAD)"

set +e
clear_suspect_stderr="$(state_with_flags false false "clear my own suspect" \
    | "$WRITE" -m "agent: clear suspect" docs/baton/state.md 2>&1 >/dev/null)"
clear_suspect_rc=$?
set -e

assert_equals "$clear_suspect_rc" "3" "refuses to clear suspect: true in HEAD"
assert_contains "$clear_suspect_stderr" "refusing to clear suspect" \
    "the refusal names the field it will not let the agent clear"
assert_contains "$(git show HEAD:docs/baton/state.md)" "suspect: true" \
    "the flag the refused write tried to clear is still set in HEAD"
assert_equals "$(git rev-list --count HEAD)" "$clear_suspect_commits_before" \
    "the refused suspect-clearing write creates no commit"

# needs_human is the expensive one: it is what halts the run, and a run that
# can clear its own stop does not have one.
commit_state_flags false true "needs_human baseline"
clear_needs_human_commits_before="$(git rev-list --count HEAD)"

set +e
clear_needs_human_stderr="$(state_with_flags false false "clear my own stop" \
    | "$WRITE" -m "agent: clear needs_human" docs/baton/state.md 2>&1 >/dev/null)"
clear_needs_human_rc=$?
set -e

assert_equals "$clear_needs_human_rc" "3" "refuses to clear needs_human: true in HEAD"
assert_contains "$clear_needs_human_stderr" "refusing to clear needs_human" \
    "the refusal names needs_human, the flag that halts the run"
assert_contains "$(git show HEAD:docs/baton/state.md)" "needs_human: true" \
    "the stop the refused write tried to lift is still set in HEAD"
assert_equals "$(git rev-list --count HEAD)" "$clear_needs_human_commits_before" \
    "the refused needs_human-clearing write creates no commit"

# The other direction, and not a formality: without it, a green run is
# equally consistent with a script that refuses every write to state.md.
# Raising is always the agent's.
commit_state_flags false false "raise baseline"
raise_commits_before="$(git rev-list --count HEAD)"

set +e
state_with_flags true false "raise suspect on a real divergence" \
    | "$WRITE" -m "agent: raise suspect" docs/baton/state.md
raise_rc=$?
set -e

assert_equals "$raise_rc" "0" "raising suspect from false to true is allowed"
assert_equals "$(git rev-list --count HEAD)" "$((raise_commits_before + 1))" \
    "the raised flag lands as an ordinary commit"
assert_contains "$(git show HEAD:docs/baton/state.md)" "suspect: true" \
    "the raise genuinely reached the log, rather than exiting 0 having written nothing"

# False over false is not a clearing: it is every checkpoint of a run that
# was never stopped in the first place.
commit_state_flags false false "unchanged baseline"
unchanged_commits_before="$(git rev-list --count HEAD)"

set +e
state_with_flags false false "an ordinary checkpoint, nothing stopped" \
    | "$WRITE" -m "agent: ordinary checkpoint" docs/baton/state.md
unchanged_rc=$?
set -e

assert_equals "$unchanged_rc" "0" "writing false over false is an ordinary checkpoint, not a clearing"
assert_equals "$(git rev-list --count HEAD)" "$((unchanged_commits_before + 1))" \
    "the unchanged-flags checkpoint commits like any other"
assert_contains "$(cat docs/baton/state.md)" "an ordinary checkpoint, nothing stopped" \
    "the unchanged-flags checkpoint lands its content on disk"

# --- the same rule from the other side. `false` is only the honest spelling
# of a clearing, and the agent writes every byte of what is piped in, so a
# refusal that fires on true -> false alone leaves it two quieter ways to
# put the flag down: write a document this reader finds no frontmatter in,
# or leave the line out. Both were accepted, exit 0, flag gone from HEAD.
# What the rule actually cares about is that a set flag is still set in what
# was written -- so anything that is not a positive `true` is refused. ---

# The reader anchors its frontmatter on line 1, so a document that opens
# with a single blank line has, as far as it can tell, no frontmatter at all
# and therefore no flags in it. Every other line is the ordinary template.
state_after_blank_line() {
    printf '\n'
    state_with_flags "$@"
}

# The other spelling: the line is simply not there. Built by dropping it
# from the template, so the document stays the template in every other
# respect -- this is a plausible write, not a corrupt file.
state_without_flag() {
    local field="$1"
    shift
    state_with_flags "$@" | grep -v "^$field: "
}

commit_state_flags true false "unreadable-frontmatter baseline"
blank_line_commits_before="$(git rev-list --count HEAD)"

set +e
blank_line_stderr="$(state_after_blank_line false false "clear suspect past the reader" \
    | "$WRITE" -m "agent: clear suspect past the reader" docs/baton/state.md 2>&1 >/dev/null)"
blank_line_rc=$?
set -e

assert_equals "$blank_line_rc" "3" \
    "refuses a clearing write whose frontmatter starts one line late, where the reader cannot see it"
assert_contains "$blank_line_stderr" "suspect" \
    "the refusal names the field the write failed to carry forward"
assert_contains "$blank_line_stderr" "/baton:clear" \
    "the refusal points at the command that does clear it"
assert_contains "$(git show HEAD:docs/baton/state.md)" "suspect: true" \
    "the flag is still set in HEAD after the refused unreadable-frontmatter write"
assert_equals "$(git rev-list --count HEAD)" "$blank_line_commits_before" \
    "the refused unreadable-frontmatter write creates no commit"
assert_equals "$(git status --porcelain docs/baton | wc -l | tr -d ' ')" "0" \
    "docs/baton is clean after the refused unreadable-frontmatter write"

# needs_human with the line dropped: the stop is gone from the file just as
# completely as if it had been written false, and empty is not false, so the
# transition test never saw this one at all.
commit_state_flags false true "dropped-field baseline"
dropped_commits_before="$(git rev-list --count HEAD)"

set +e
dropped_stderr="$(state_without_flag needs_human false true "drop the stop rather than lower it" \
    | "$WRITE" -m "agent: drop needs_human" docs/baton/state.md 2>&1 >/dev/null)"
dropped_rc=$?
set -e

assert_equals "$dropped_rc" "3" "refuses a write that omits needs_human while HEAD has it set"
assert_contains "$dropped_stderr" "needs_human" \
    "the refusal names the stop the write left out"
assert_contains "$dropped_stderr" "/baton:clear" \
    "the omission refusal points at the command that does clear the stop"
assert_contains "$(git show HEAD:docs/baton/state.md)" "needs_human: true" \
    "the stop is still set in HEAD after the refused omitting write"
assert_equals "$(git rev-list --count HEAD)" "$dropped_commits_before" \
    "the refused omitting write creates no commit"

# The case the tightening puts most at risk, and the reason it is a "still
# set" test and not a "never write it" one: a stopped run still checkpoints.
# Refusing this would make the flag un-writable rather than un-clearable,
# and a green suite without it is equally consistent with that.
commit_state_flags true false "true-over-true baseline"
carry_commits_before="$(git rev-list --count HEAD)"

set +e
state_with_flags true false "checkpoint while suspect stands" \
    | "$WRITE" -m "agent: checkpoint under a raised suspect" docs/baton/state.md
carry_rc=$?
set -e

assert_equals "$carry_rc" "0" "writing true over true is an ordinary checkpoint of a stopped run"
assert_equals "$(git rev-list --count HEAD)" "$((carry_commits_before + 1))" \
    "the checkpoint under a raised flag commits like any other"
assert_contains "$(git show HEAD:docs/baton/state.md)" "checkpoint while suspect stands" \
    "the checkpoint's content genuinely reached the log, not just its exit code"
assert_contains "$(git show HEAD:docs/baton/state.md)" "suspect: true" \
    "the flag carried forward through the checkpoint is still set in HEAD"

# --- and the spellings, as for the constitution and the cap above. This
# refusal is spelling-safe only because it sits after canonicalize_target;
# nothing else in this file pins that it stays there, and gated on the
# literal string instead, `./docs/baton/state.md` walks past it. Every write
# in the loop is refused, so the one baseline holds for all of them. ---
commit_state_flags true false "spelling baseline"
spelling_flag_commits_before="$(git rev-list --count HEAD)"

for spelling in \
    "./docs/baton/state.md" \
    "docs/baton/../baton/state.md" \
    "docs//baton/state.md"
do
    set +e
    spelling_clear_stderr="$(state_with_flags false false "clear suspect via $spelling" \
        | "$WRITE" -m "agent: clear suspect via $spelling" "$spelling" 2>&1 >/dev/null)"
    spelling_clear_rc=$?
    spelling_drop_stderr="$(state_without_flag suspect false false "drop suspect via $spelling" \
        | "$WRITE" -m "agent: drop suspect via $spelling" "$spelling" 2>&1 >/dev/null)"
    spelling_drop_rc=$?
    set -e

    assert_equals "$spelling_clear_rc" "3" "refuses to clear suspect spelled as $spelling"
    assert_contains "$spelling_clear_stderr" "/baton:clear" \
        "the $spelling clearing refusal still points at /baton:clear"
    assert_equals "$spelling_drop_rc" "3" "refuses to drop suspect entirely spelled as $spelling"
    assert_contains "$spelling_drop_stderr" "suspect" \
        "the $spelling omission refusal names the field"
done

assert_contains "$(git show HEAD:docs/baton/state.md)" "suspect: true" \
    "the flag is still set in HEAD after every alternate-spelling attempt on it"
assert_equals "$(git rev-list --count HEAD)" "$spelling_flag_commits_before" \
    "no alternate spelling of the path produced a commit"

# --- carriage returns, on both sides of the same reader. baton-gate and
# baton-digest strip \r from every line before comparing any of it, and both
# carry a comment saying why: a file a Windows editor writes has CRLF on
# EVERY line, the opening --- included, and the line-1 test is an exact string
# comparison -- "---\r" is not "---", so the block is never entered and every
# field reads empty. baton-write's reader did not strip it, and an empty read
# is exactly what this guard treats as "the flag is not here".
#
# Which made the flag clearable in two steps, both of them exit 0: raise
# needs_human from a CRLF editor (baton-write reads no flag, allows it;
# baton-digest reads the same commit and prints needs_human: true, because it
# strips), then clear it from an LF one (`was` is empty, so nothing fires).
#
# The suite could not see any of it. The fixture has run under
# core.autocrlf=input since the idle-CRLF case above, and this machine's
# global config says the same, so git normalises CRLF away on commit and the
# committed blob is always LF -- a regression test added anywhere else in this
# file would have passed against the unfixed reader. This block turns that off
# for its own scope only, and the first assertion is that the baseline blob
# genuinely kept its carriage returns: without it, green here proves nothing.
crlf_autocrlf_before="$(git config --local --get core.autocrlf || true)"
git config core.autocrlf false

commit_state_flags_crlf() {
    state_with_flags "$1" "$2" "$3" | crlf > docs/baton/state.md
    git add docs/baton/state.md
    git commit -q --allow-empty -m "fixture: CRLF state.md suspect=$1 needs_human=$2 ($3)"
}

commit_state_flags_crlf false true "a stop raised from a CRLF editor"
assert_contains "$(git show HEAD:docs/baton/state.md | tr '\r' '@')" "needs_human: true@" \
    "sanity: what baton-write reads back from HEAD still carries its carriage returns, so this case is genuinely reproduced and not normalised away by autocrlf"

crlf_bypass_commits_before="$(git rev-list --count HEAD)"

set +e
crlf_clear_stderr="$(state_with_flags false false "clear a stop the reader could not see" \
    | "$WRITE" -m "agent: clear a CRLF stop" docs/baton/state.md 2>&1 >/dev/null)"
crlf_clear_rc=$?
set -e

assert_equals "$crlf_clear_rc" "3" \
    "refuses to clear a needs_human that HEAD spells with CRLF line endings"
assert_contains "$crlf_clear_stderr" "needs_human" \
    "the CRLF-HEAD refusal names the stop it will not let the agent clear"
assert_contains "$(git show HEAD:docs/baton/state.md)" "needs_human: true" \
    "the CRLF stop is still set in HEAD after the refused clearing write"
assert_equals "$(git rev-list --count HEAD)" "$crlf_bypass_commits_before" \
    "the refused CRLF-HEAD clearing write creates no commit"

# The same defect from the other side, and the reason this is a reader fix
# rather than another refusal: HEAD spells the flag in LF, the agent writes
# the same document from an editor that ends lines with CRLF, and every byte
# of `suspect: true` is there in a block opening on line 1. That was refused,
# with a message telling the writer to keep a line it had kept.
commit_state_flags true false "an LF baseline a CRLF writer checkpoints over"
crlf_carry_commits_before="$(git rev-list --count HEAD)"

set +e
crlf_carry_stderr="$(state_with_flags true false "checkpoint from a CRLF editor" | crlf \
    | "$WRITE" -m "agent: CRLF checkpoint under a raised suspect" docs/baton/state.md 2>&1 >/dev/null)"
crlf_carry_rc=$?
set -e

assert_equals "$crlf_carry_rc" "0" \
    "a CRLF write that plainly carries suspect: true forward is accepted, not turned away for its line endings"
assert_equals "$crlf_carry_stderr" "" "the accepted CRLF checkpoint prints no refusal"
assert_equals "$(git rev-list --count HEAD)" "$((crlf_carry_commits_before + 1))" \
    "the CRLF checkpoint commits like any other"
assert_contains "$(git show HEAD:docs/baton/state.md)" "checkpoint from a CRLF editor" \
    "the CRLF checkpoint's content reached the log, not just its exit code"

# Put the fixture's line-ending policy back exactly as it was, and its
# state.md back to LF with it: everything after this block is written and read
# in LF, and a stray autocrlf=false -- or a CRLF blob in HEAD -- would quietly
# change what those cases mean rather than failing them.
if [ -n "$crlf_autocrlf_before" ]; then
    git config core.autocrlf "$crlf_autocrlf_before"
else
    git config --unset core.autocrlf || true
fi
assert_equals "$(git config --local --get core.autocrlf || true)" "$crlf_autocrlf_before" \
    "the fixture's core.autocrlf is back to what the rest of this file runs under"

commit_state_flags false false "back to LF after the CRLF block"
assert_equals "$(git status --porcelain docs/baton | wc -l | tr -d ' ')" "0" \
    "sanity: the fixture is back to an LF state.md and a clean tree"

# --- the same reader out of step with its siblings again, over two
# characters this time. baton-digest's field reader strips one matched pair
# of surrounding quotes before it decides anything, and so does baton-gate's;
# baton-write's did not. So `suspect: "true"` said `true` to two readers and
# `"true"` to the third, and the disagreement ran the one direction that
# loses a stop -- the guard is the reader that saw no flag.
#
# Raise the flag quoted (allowed: raising always is), and every reader agrees
# the run is stopped -- /baton:status and baton-digest both print `Raised:
# suspect`. Clear it plainly at the next checkpoint and the guard finds
# nothing set in HEAD to carry forward, so it says nothing: exit 0, flag down
# in the log, the run unstopped by the run. Reproduced in three steps, all of
# them exit 0. Nothing else changed its report along the way, which is what
# made it worth a test rather than a curiosity: the human had no signal at all.
#
# Quoted frontmatter is this repository's own idiom, not a corrupt file --
# the constitution's verify_cmd is conventionally written that way, and
# test-digest.sh writes it so. An agent regenerating state.md wholesale
# quotes a value without meaning anything by it.
#
# Both quote characters, both flags, and both sides of the write: HEAD's
# spelling and the incoming document's are read by the same function, so a
# fix that unquoted only what it read out of HEAD would leave the incoming
# `"false"` landing in the wrong branch and telling the writer to keep a line
# they deleted on purpose. The refusals below are paired with the writes that
# must still be accepted -- including a quoted RAISE, which a guard that
# refused the shape outright would have turned away, and refusing a raise is
# refusing a stop. ---

commit_state_flags '"true"' false "a suspect raised in the quoted spelling"
assert_contains "$(git show HEAD:docs/baton/state.md)" 'suspect: "true"' \
    "sanity: HEAD really does spell the flag with quotes, so this case is reproduced and not normalised away"

quoted_clear_commits_before="$(git rev-list --count HEAD)"

set +e
quoted_clear_stderr="$(state_with_flags false false "clear a quoted suspect plainly" \
    | "$WRITE" -m "agent: clear a quoted suspect" docs/baton/state.md 2>&1 >/dev/null)"
quoted_clear_rc=$?
set -e

assert_equals "$quoted_clear_rc" "3" \
    "refuses to clear a suspect that HEAD spells suspect: \"true\""
assert_contains "$quoted_clear_stderr" "refusing to clear suspect" \
    "the quoted-HEAD refusal names the field, and names it as a clearing rather than an unreadable write"
assert_contains "$quoted_clear_stderr" "/baton:clear" \
    "the quoted-HEAD refusal still points at the command that does clear it"
assert_contains "$(git show HEAD:docs/baton/state.md)" 'suspect: "true"' \
    "the quoted flag is still set in HEAD after the refused clearing write"
assert_equals "$(git rev-list --count HEAD)" "$quoted_clear_commits_before" \
    "the refused quoted-HEAD clearing write creates no commit"

# The incoming side of the same reader. `suspect: "false"` is a clearing
# spelled exactly as the raise was, and it has to arrive at the branch that
# says whose the clearing is -- not at the generic one, which would tell a
# writer who deleted the flag deliberately to go and put a line back.
set +e
quoted_false_stderr="$(state_with_flags '"false"' false "clear a quoted suspect, quoted" \
    | "$WRITE" -m "agent: clear a quoted suspect with a quoted false" docs/baton/state.md 2>&1 >/dev/null)"
quoted_false_rc=$?
set -e

assert_equals "$quoted_false_rc" "3" \
    "refuses a quoted false written over a quoted true"
assert_contains "$quoted_false_stderr" "refusing to clear suspect" \
    "the incoming quoted false reaches the clearing branch, so the reader unquotes what is written as well as what is in HEAD"
assert_equals "$(git rev-list --count HEAD)" "$quoted_clear_commits_before" \
    "the refused quoted-false write creates no commit"

# The other quote character, on the flag that halts the run. Single quotes
# are the second half of the matched pair both siblings strip, and a fix that
# handled only the double kind would leave this one exactly as it was.
commit_state_flags false "'true'" "a stop raised in the single-quoted spelling"
squoted_clear_commits_before="$(git rev-list --count HEAD)"

set +e
squoted_clear_stderr="$(state_with_flags false false "clear a single-quoted stop" \
    | "$WRITE" -m "agent: clear a single-quoted stop" docs/baton/state.md 2>&1 >/dev/null)"
squoted_clear_rc=$?
set -e

assert_equals "$squoted_clear_rc" "3" \
    "refuses to clear a needs_human that HEAD spells needs_human: 'true'"
assert_contains "$squoted_clear_stderr" "refusing to clear needs_human" \
    "the single-quoted refusal names the stop it will not let the agent clear"
assert_contains "$(git show HEAD:docs/baton/state.md)" "needs_human: 'true'" \
    "the single-quoted stop is still set in HEAD after the refused clearing write"
assert_equals "$(git rev-list --count HEAD)" "$squoted_clear_commits_before" \
    "the refused single-quoted clearing write creates no commit"

# --- and the other direction, which is most of the point. A guard that
# refused the quoted shape outright would be just as green on all three
# refusals above, and would have refused every write below. ---

# A stopped run still checkpoints, in the spelling its own frontmatter uses.
commit_state_flags '"true"' false "quoted baseline a quoted checkpoint carries forward"
quoted_carry_commits_before="$(git rev-list --count HEAD)"

set +e
state_with_flags '"true"' false "checkpoint while a quoted suspect stands" \
    | "$WRITE" -m "agent: quoted checkpoint under a raised suspect" docs/baton/state.md
quoted_carry_rc=$?
set -e

assert_equals "$quoted_carry_rc" "0" \
    "writing a quoted true over a quoted true is an ordinary checkpoint of a stopped run"
assert_equals "$(git rev-list --count HEAD)" "$((quoted_carry_commits_before + 1))" \
    "the checkpoint under a quoted flag commits like any other"
assert_contains "$(git show HEAD:docs/baton/state.md)" "checkpoint while a quoted suspect stands" \
    "the quoted checkpoint's content genuinely reached the log, not just its exit code"

# The spelling may change between HEAD and the write without that being a
# clearing: what the rule asks is whether this document still says the flag
# is up, and a bare true over a quoted true says so.
mixed_carry_commits_before="$(git rev-list --count HEAD)"

set +e
mixed_carry_stderr="$(state_with_flags true false "carry a quoted flag forward, bare" \
    | "$WRITE" -m "agent: bare checkpoint over a quoted flag" docs/baton/state.md 2>&1 >/dev/null)"
mixed_carry_rc=$?
set -e

assert_equals "$mixed_carry_rc" "0" \
    "a bare true written over a quoted true still says the flag is set, and is accepted"
assert_equals "$mixed_carry_stderr" "" "the accepted cross-spelling checkpoint prints no refusal"
assert_equals "$(git rev-list --count HEAD)" "$((mixed_carry_commits_before + 1))" \
    "the cross-spelling checkpoint commits like any other"
assert_contains "$(git show HEAD:docs/baton/state.md)" "suspect: true" \
    "the flag carried forward in the other spelling is still set in HEAD"

# And the raise itself, in both quote characters. This is the write a rule
# reading "a flag must be spelled bare" would have turned away, and a refused
# raise is a stop that did not land -- the one direction this guard must
# never make harder.
for quoted_raise in '"true"' "'true'"; do
    commit_state_flags false false "raise baseline for $quoted_raise"
    quoted_raise_commits_before="$(git rev-list --count HEAD)"

    set +e
    quoted_raise_stderr="$(state_with_flags "$quoted_raise" false "raise suspect as $quoted_raise" \
        | "$WRITE" -m "agent: raise suspect as $quoted_raise" docs/baton/state.md 2>&1 >/dev/null)"
    quoted_raise_rc=$?
    set -e

    assert_equals "$quoted_raise_rc" "0" "raising suspect spelled $quoted_raise is allowed"
    assert_equals "$quoted_raise_stderr" "" "the accepted $quoted_raise raise prints no refusal"
    assert_equals "$(git rev-list --count HEAD)" "$((quoted_raise_commits_before + 1))" \
        "the $quoted_raise raise lands as an ordinary commit"
    assert_contains "$(git show HEAD:docs/baton/state.md)" "suspect: $quoted_raise" \
        "the $quoted_raise raise genuinely reached the log, rather than exiting 0 having written nothing"
done

# One matched pair, and only a matched pair -- which is unquote's rule in
# both siblings, not an incidental detail of how they are written. A value
# that opens a quote and never closes it is not a quoted flag: baton-digest
# refuses the whole file rather than reading it as true, and here it reads as
# neither true nor false, so a write spelling the carried-forward flag that
# way has not carried it forward. Pinned as a refusal so that "strip one
# matched pair" cannot drift into "strip any quote you find" -- which would
# read this as a flag still set here while baton-digest went on refusing the
# file, the same disagreement rebuilt from the other side.
commit_state_flags true false "bare baseline an unbalanced write tries to carry"
unbalanced_commits_before="$(git rev-list --count HEAD)"

set +e
unbalanced_stderr="$(state_with_flags '"true' false "carry the flag with a quote that never closes" \
    | "$WRITE" -m "agent: unbalanced quote on a carried flag" docs/baton/state.md 2>&1 >/dev/null)"
unbalanced_rc=$?
set -e

assert_equals "$unbalanced_rc" "3" \
    "refuses a write whose carried-forward flag opens a quote it never closes: that is not a readable true"
assert_contains "$unbalanced_stderr" "suspect" \
    "the unbalanced-quote refusal names the flag the write failed to carry forward"
assert_contains "$(git show HEAD:docs/baton/state.md)" "suspect: true" \
    "the flag is still set in HEAD after the refused unbalanced-quote write"
assert_equals "$(git rev-list --count HEAD)" "$unbalanced_commits_before" \
    "the refused unbalanced-quote write creates no commit"

commit_state_flags false false "back to bare flags after the quoted block"
assert_equals "$(git status --porcelain docs/baton | wc -l | tr -d ' ')" "0" \
    "sanity: the fixture is back to bare flags and a clean tree"

# --- and the entry into an unreadable HEAD, which was the hole the guard
# above could not close from where it stands: it only engages once a flag is
# up, so the way past it was to go first. Land a document this tool cannot
# read while both flags are still false -- no flag is set, nothing fires --
# and every step after it is unguarded, because `was` reads empty from a HEAD
# that cannot be read. Reproduced end to end at exit 0 three times over.
#
# So the rule is about the document, not the transition: a state.md whose
# frontmatter this tool cannot read is refused whatever HEAD says, which is
# what makes "HEAD is readable" an invariant instead of an assumption.
state_unterminated() {
    state_with_flags "$@" | awk 'NR == 1 || $0 != "---"'
}

commit_state_flags false false "readable HEAD, nothing raised"
unreadable_entry_commits_before="$(git rev-list --count HEAD)"
unreadable_entry_head_before="$(git show HEAD:docs/baton/state.md)"

set +e
unreadable_entry_stderr="$(state_after_blank_line false false "land an unreadable state.md first" \
    | "$WRITE" -m "agent: step one, nothing raised yet" docs/baton/state.md 2>&1 >/dev/null)"
unreadable_entry_rc=$?
set -e

assert_equals "$unreadable_entry_rc" "3" \
    "refuses an unreadable state.md even with both flags false -- the step that used to be free"
assert_contains "$unreadable_entry_stderr" "no frontmatter block this tool can read" \
    "the refusal says what it could not read, rather than naming a flag that is not set"
assert_contains "$unreadable_entry_stderr" "line 1 is not a bare ---" \
    "and says which shape this document has, so the reader repairs the opening rather than checking all three"
assert_equals "$(git show HEAD:docs/baton/state.md)" "$unreadable_entry_head_before" \
    "HEAD still holds the readable document after the refused unreadable write"
assert_equals "$(git rev-list --count HEAD)" "$unreadable_entry_commits_before" \
    "the refused unreadable write creates no commit"
assert_equals "$(git status --porcelain docs/baton | wc -l | tr -d ' ')" "0" \
    "docs/baton is clean after the refused unreadable write"

# The other malformed shape, and the one the reader's siblings both name: a
# block that opens on line 1 and never closes. Left unrefused, "frontmatter"
# quietly means "everything after line 1", so any body line spelled like a
# field reads as one.
set +e
unterminated_stderr="$(state_unterminated false false "a block that never closes" \
    | "$WRITE" -m "agent: unterminated frontmatter" docs/baton/state.md 2>&1 >/dev/null)"
unterminated_rc=$?
set -e

assert_equals "$unterminated_rc" "3" \
    "refuses a state.md whose frontmatter block opens on line 1 and is never closed"
assert_contains "$unterminated_stderr" "no frontmatter block this tool can read" \
    "the unterminated-block refusal is the same one, for the same reason"
assert_contains "$unterminated_stderr" "nothing closes it" \
    "the unterminated-block refusal names the close, not the opening this document already has"
assert_equals "$(git rev-list --count HEAD)" "$unreadable_entry_commits_before" \
    "the refused unterminated write creates no commit either"

# The third shape, and the one the single message was untrue about. A block
# that opens on line 1 and closes on line 2 has nothing in it to read, so the
# refusal is right -- but "one opening with --- on line 1, closed by a later
# ---" described a document this one already is. The reader checked both,
# found both, and was sent hunting for a defect the file does not have, which
# is the failure baton-gate names for its own diagnostics at unquote. So the
# assertions below pin which message arrives, not just that one does: without
# that, the wording drifts back and nothing goes red.
state_empty_block() {
    printf '%s\n' '---' '---' '' '# State' '' '## Now' '' "- **Next action:** $1"
}

# Same block, spelled with blank lines inside it rather than none. Nothing
# separates the two as far as any reader here is concerned -- the block is
# just as empty of fields -- so it must arrive at the same diagnostic and not
# at the unterminated one.
state_blank_block() {
    printf '%s\n' '---' '' '' '---' '' '# State' '' "- **Next action:** $1"
}

empty_block_commits_before="$(git rev-list --count HEAD)"
empty_block_head_before="$(git show HEAD:docs/baton/state.md)"

set +e
empty_block_stderr="$(state_empty_block "a block with nothing in it" \
    | "$WRITE" -m "agent: empty frontmatter block" docs/baton/state.md 2>&1 >/dev/null)"
empty_block_rc=$?
set -e

assert_equals "$empty_block_rc" "3" \
    "refuses a state.md whose frontmatter block opens on line 1, closes, and holds nothing"
assert_contains "$empty_block_stderr" "its frontmatter block is empty" \
    "the empty-block refusal says the block is empty, which is the shape this document actually has"
assert_not_contains "$empty_block_stderr" "no frontmatter block this tool can read" \
    "it no longer claims the document has no block, when the block is right there and closed"
assert_not_contains "$empty_block_stderr" "closed by a later ---" \
    "and no longer sends the reader to check a close this document already has"
assert_equals "$(git show HEAD:docs/baton/state.md)" "$empty_block_head_before" \
    "HEAD still holds the readable document after the refused empty-block write"
assert_equals "$(git rev-list --count HEAD)" "$empty_block_commits_before" \
    "the refused empty-block write creates no commit"

set +e
blank_block_stderr="$(state_blank_block "a block holding only blank lines" \
    | "$WRITE" -m "agent: blank frontmatter block" docs/baton/state.md 2>&1 >/dev/null)"
blank_block_rc=$?
set -e

assert_equals "$blank_block_rc" "3" \
    "refuses a state.md whose frontmatter block holds only blank lines"
assert_contains "$blank_block_stderr" "its frontmatter block is empty" \
    "a block of blank lines gets the empty-block diagnostic, not the unterminated one -- it is closed"
assert_equals "$(git rev-list --count HEAD)" "$empty_block_commits_before" \
    "the refused blank-block write creates no commit either"

# The neighbour every refusal needs. Nothing is raised, nothing is being
# carried, and the document is an ordinary one: this is the path the new rule
# must leave completely alone, and a suite without it is just as green against
# a script that refuses every state.md write.
ordinary_commits_before="$(git rev-list --count HEAD)"

set +e
ordinary_stderr="$(state_with_flags false false "an ordinary checkpoint of a readable state.md" \
    | "$WRITE" -m "agent: ordinary readable checkpoint" docs/baton/state.md 2>&1 >/dev/null)"
ordinary_rc=$?
set -e

assert_equals "$ordinary_rc" "0" "a well-formed state.md write is still an ordinary checkpoint"
assert_equals "$ordinary_stderr" "" "the well-formed write prints no refusal"
assert_equals "$(git rev-list --count HEAD)" "$((ordinary_commits_before + 1))" \
    "the well-formed write commits like any other"
assert_contains "$(git show HEAD:docs/baton/state.md)" "an ordinary checkpoint of a readable state.md" \
    "the well-formed write's content reached the log"

# And on a path HEAD has nothing at. The rule cannot be conditioned on the
# previous version, because the first state.md a run ever writes is the one
# every later `was` gets read from -- an unreadable one there poisons the
# whole run from its first commit.
git rm -q docs/baton/state.md
git commit -q -m "fixture: a run with no state.md yet"
absent_commits_before="$(git rev-list --count HEAD)"

set +e
absent_stderr="$(state_after_blank_line false false "create it unreadable from the start" \
    | "$WRITE" -m "agent: create an unreadable state.md" docs/baton/state.md 2>&1 >/dev/null)"
absent_rc=$?
set -e

assert_equals "$absent_rc" "3" \
    "refuses to create an unreadable state.md at a path HEAD has nothing at"
assert_contains "$absent_stderr" "no frontmatter block this tool can read" \
    "the creation refusal names the same unreadable frontmatter"
if [ -e docs/baton/state.md ]; then
    fail "the refused unreadable creation leaves nothing on disk"
else
    pass "the refused unreadable creation leaves nothing on disk"
fi
assert_equals "$(git rev-list --count HEAD)" "$absent_commits_before" \
    "the refused unreadable creation creates no commit"

# The caller bug the empty-stdin guard above exists to name, arriving here
# instead. That guard only speaks when HEAD already holds content, so on a
# run's FIRST checkpoint -- exactly here, nothing committed at this path yet --
# a failed command substitution or an empty heredoc falls through to the
# frontmatter refusal. Told "line 1 is not a bare ---", the caller goes and
# inspects line 1 of a document they believe they wrote and finds nothing
# there, because there is nothing there: they wrote no document at all. It is
# the same wrong trip the empty-block case sends its reader on, one branch
# over, so it is refused in its own words. Whitespace-only is the same bug --
# `printf '%s\n' "$unset"` produces a lone newline, not zero bytes -- and gets
# the same words.
for empty_shape in "nothing at all" "a lone newline" "spaces and tabs"; do
    case "$empty_shape" in
        "nothing at all") empty_doc="" ;;
        "a lone newline") empty_doc=$'\n' ;;
        *)                empty_doc=$'   \n\t\n' ;;
    esac

    set +e
    unwritten_stderr="$(printf '%s' "$empty_doc" \
        | "$WRITE" -m "agent: create state.md from an empty heredoc" docs/baton/state.md 2>&1 >/dev/null)"
    unwritten_rc=$?
    set -e

    assert_equals "$unwritten_rc" "3" \
        "refuses to create state.md from $empty_shape, at a path HEAD has nothing at"
    assert_contains "$unwritten_stderr" "empty, or nothing but whitespace" \
        "the refusal for $empty_shape says the document is empty, which is what the caller actually has"
    assert_contains "$unwritten_stderr" "a command substitution that failed" \
        "and names the caller bug, the way the empty-stdin refusal does"
    assert_not_contains "$unwritten_stderr" "line 1 is not a bare ---" \
        "rather than sending the reader to inspect line 1 of a document that was never written ($empty_shape)"
    assert_equals "$(git rev-list --count HEAD)" "$absent_commits_before" \
        "the refused $empty_shape creation creates no commit"
done

if [ -e docs/baton/state.md ]; then
    fail "the refused empty creations leave nothing on disk either"
else
    pass "the refused empty creations leave nothing on disk either"
fi

set +e
state_with_flags false false "the first state.md of a run" \
    | "$WRITE" -m "baton: initial state" docs/baton/state.md
first_state_rc=$?
set -e

assert_equals "$first_state_rc" "0" \
    "a well-formed first state.md is still created normally -- /baton:init writes this one"
assert_contains "$(git show HEAD:docs/baton/state.md)" "the first state.md of a run" \
    "the created state.md reached the log"

# --- empty stdin over a state.md with a flag up. Both guards refuse it, so
# the only thing at stake is which one says why -- and the whitespace guard is
# the one that knows: a failed command substitution or an empty heredoc is a
# caller bug, and being told instead to "keep the line in the frontmatter
# block" sends the reader to look at a document that does not exist yet. ---
commit_state_flags true false "a raised flag for the empty-stdin diagnostic"
empty_under_flag_commits_before="$(git rev-list --count HEAD)"

set +e
empty_under_flag_stderr="$(: | "$WRITE" -m "oops empty under a raised flag" docs/baton/state.md 2>&1 >/dev/null)"
empty_under_flag_rc=$?
set -e

assert_equals "$empty_under_flag_rc" "3" "empty stdin over a state.md with suspect set is still refused"
assert_contains "$empty_under_flag_stderr" "empty-or-whitespace-only content" \
    "the refusal reports the caller bug it is, rather than a flag line the caller never had a chance to write"
assert_not_contains "$empty_under_flag_stderr" "Keep the line in the frontmatter block" \
    "the flag guard no longer shadows the empty-stdin diagnostic"
assert_contains "$(git show HEAD:docs/baton/state.md)" "suspect: true" \
    "the flag survives the refused empty write"
assert_equals "$(git rev-list --count HEAD)" "$empty_under_flag_commits_before" \
    "the refused empty write under a raised flag creates no commit"

finish
