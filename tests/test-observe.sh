#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
OBSERVE="$REPO_ROOT/plugins/baton/scripts/baton-observe"
. "$SCRIPT_DIR/helpers.sh"

make_fixture_repo

out="$("$OBSERVE")"
expected_sha="$(git rev-parse HEAD)"

assert_contains "$out" "sha=$expected_sha" "reports the current SHA"
assert_contains "$out" "tree_clean=true" "reports a clean tree as clean"
assert_contains "$out" "dirty_count=0" "counts zero dirty paths on a clean tree"

branch="$(git symbolic-ref --short HEAD)"
assert_contains "$out" "branch=$branch" "reports the current branch"

echo "scratch" > untracked.txt
out="$("$OBSERVE")"
assert_contains "$out" "tree_clean=false" "reports a dirty tree as dirty"
assert_contains "$out" "dirty_count=1" "counts one dirty path"

base="$(git rev-parse HEAD)"
git add untracked.txt
git commit -q -m "add untracked"
echo "more" > second.txt
git add second.txt
git commit -q -m "add second"

changed="$("$OBSERVE" --changed-since "$base")"
assert_contains "$changed" "untracked.txt" "lists a file changed since the given SHA"
assert_contains "$changed" "second.txt" "lists every file changed since the given SHA"
assert_not_contains "$changed" "seed.txt" "omits files untouched since the given SHA"

# Regression: status.showUntrackedFiles=no must not hide a dirty tree from
# baton-observe. Reporting what local config prefers to show, instead of
# what is actually true, is exactly the failure this script exists to
# prevent.
git config status.showUntrackedFiles no
echo "hidden by config" > hidden_untracked.txt
out="$("$OBSERVE")"
git config --unset status.showUntrackedFiles
rm -f hidden_untracked.txt
assert_contains "$out" "tree_clean=false" "reports dirty even when status.showUntrackedFiles=no would hide it"
assert_contains "$out" "dirty_count=1" "counts the untracked file even when status.showUntrackedFiles=no"

# Regression: a file created but never `git add`ed is the most common shape
# of in-flight work and must still show up in --changed-since.
unstaged_base="$(git rev-parse HEAD)"
echo "never staged" > never_staged.txt
changed_unstaged="$("$OBSERVE" --changed-since "$unstaged_base")"
rm -f never_staged.txt
assert_contains "$changed_unstaged" "never_staged.txt" "includes an unstaged, never-added file in --changed-since"

# Regression: an empty --changed-since value must be a usage error, not a
# silent fall-through to the fact block. This is exactly the shape of the
# very first checkpoint's observed_sha.
assert_exit_code 64 "rejects an empty --changed-since value" "$OBSERVE" --changed-since ""

# Regression: an unborn HEAD (freshly initialized repo, no commits yet) must
# not crash and must report an empty sha rather than a guess. Cleaned up
# without leaving the test cd'd into the directory being removed.
unborn="$(mktemp -d)"
git init -q -b main "$unborn" >/dev/null
unborn_out="$(cd "$unborn" && "$OBSERVE")"
unborn_exit=0
( cd "$unborn" && "$OBSERVE" >/dev/null 2>&1 ) || unborn_exit=$?
rm -rf "$unborn"
assert_equals "$unborn_exit" "0" "exits 0 on an unborn HEAD"
first_line="$(printf '%s\n' "$unborn_out" | head -n1)"
assert_equals "$first_line" "sha=" "reports an empty sha on an unborn HEAD"

outside="$(mktemp -d)"
cd "$outside"
assert_exit_code 1 "exits 1 outside a git repository" "$OBSERVE"
cd /
rm -rf "$outside"

finish
