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

outside="$(mktemp -d)"
cd "$outside"
assert_exit_code 1 "exits 1 outside a git repository" "$OBSERVE"
cd /
rm -rf "$outside"

finish
