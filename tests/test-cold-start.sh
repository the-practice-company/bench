#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PLUGIN="$REPO_ROOT/plugins/baton"
. "$SCRIPT_DIR/helpers.sh"

FIXTURE="$(mktemp -d)"
bash "$SCRIPT_DIR/fixtures/cold-start/build.sh" "$FIXTURE" >/dev/null
cd "$FIXTURE"

state="$(cat docs/baton/state.md)"

# Everything a resuming agent needs must already be on disk.
assert_contains "$state" "**Goal:**" "the fixture state carries the goal"
assert_contains "$state" "**Operating mode:**" "the fixture state carries the operating mode"
assert_contains "$state" "**Non-negotiables:**" "the fixture state carries the live constraints"

next="$(sed -n 's/^- \*\*Next action:\*\* *//p' docs/baton/state.md | head -1)"
if [ "${#next}" -ge 40 ]; then
    pass "next action is specific enough to act on without context (${#next} chars)"
else
    fail "next action is specific enough to act on without context (${#next} chars)"
fi
assert_contains "$next" "src/session.js" "next action names the exact file to touch"

# A wave claimed done must be verifiable against the repository, not believed.
closed="$(sed -n 's/^| 1 |.*| \([0-9a-f]\{7,\}\) | pass |$/\1/p' docs/baton/state.md)"
if git merge-base --is-ancestor "$closed" HEAD; then
    pass "the closed wave's SHA is an ancestor of HEAD, so the claim checks out"
else
    fail "the closed wave's SHA is an ancestor of HEAD, so the claim checks out"
fi

# The constitution must pass baton-resume's ratification guard: status must
# read ratified, and no REPLACE-WITH token may remain. A fixture that trips
# this guard tests the guard, not cold-start recovery.
constitution="$(cat docs/baton/constitution.md)"
assert_contains "$constitution" "status: ratified" "the fixture constitution is ratified"
assert_not_contains "$constitution" "REPLACE-WITH" "the fixture constitution has no unfilled placeholders"

# observed_sha must equal work_sha (the last commit touching anything
# outside docs/baton/), not raw HEAD, which moves on the checkpoint commit
# itself and would make this comparison meaningless on a real run.
observed_sha="$(sed -n 's/^observed_sha: *//p' docs/baton/state.md | head -1)"
work_sha="$("$PLUGIN/scripts/baton-observe" | sed -n 's/^work_sha=//p')"
head_sha="$(git rev-parse HEAD)"
assert_equals "$observed_sha" "$work_sha" "fixture observed_sha matches baton-observe's work_sha"
if [ "$observed_sha" != "$head_sha" ]; then
    pass "fixture observed_sha is not raw HEAD (the checkpoint commit moved past it)"
else
    fail "fixture observed_sha is not raw HEAD (the checkpoint commit moved past it)"
fi

# The hook hands the agent the same four lines without reading the file.
export CLAUDE_PLUGIN_ROOT="$PLUGIN"
export CLAUDE_PROJECT_DIR="$FIXTURE"
injected="$("$PLUGIN/hooks/session-start" < /dev/null)"
assert_contains "$injected" "Ship authentication" "the hook injects the goal"
assert_contains "$injected" "Never change the token format" "the hook injects the constraints"
assert_contains "$injected" "src/session.js" "the hook injects the next action"

cd /
rm -rf "$FIXTURE"
FIXTURE=""
finish
