#!/usr/bin/env bash
# Pins the premise of the autopilot fixture (tests/fixtures/cold-start/
# build-autopilot.sh): a run handed over, with one wave blocked and two
# waves left, exactly one of which is available. What a resuming agent
# does with that -- take the available wave, leave the other alone,
# continue without asking -- is RUNBOOK.md's fourth scenario, run by a
# human. What is checked here is the premise: that the fixture really does
# contain one available wave and one that only the consumes/produces rule
# excludes, so it cannot rot into a fixture where the easy rule suffices.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PLUGIN="$REPO_ROOT/plugins/baton"
. "$SCRIPT_DIR/helpers.sh"

FIXTURE="$(mktemp -d)"
bash "$SCRIPT_DIR/fixtures/cold-start/build-autopilot.sh" "$FIXTURE" >/dev/null
cd "$FIXTURE"

state="$(cat docs/baton/state.md)"
constitution="$(cat docs/baton/constitution.md)"

assert_contains "$constitution" "status: ratified" "the autopilot fixture's constitution is ratified"
assert_not_contains "$constitution" "REPLACE-WITH" "the autopilot fixture's constitution has no unfilled placeholders"

# The grant, and the entry it points at. A flag with a dangling grant is
# a fixture that tests nothing about how the grant is recorded.
assert_contains "$state" "autopilot: all" "the fixture is on the autopilot"
grant="$(sed -n 's/^autopilot_grant: *//p' docs/baton/state.md | head -1)"
assert_equals "$grant" "DEC-0001" "the fixture names the entry that granted autonomy"
assert_file_exists "docs/baton/journal/0001-autopilot-grant.md" "the granting entry exists"
assert_contains "$(cat docs/baton/journal/0001-autopilot-grant.md)" "type: autopilot" \
    "the granting entry is typed as the grant"

# One blocked wave, and a needs_human raised with it.
assert_contains "$state" "| 2 | session | blocked |" "wave 2 is blocked"
assert_contains "$state" "needs_human: true" "the fixture raised needs_human with the block"

# Wave 3 is excluded ONLY by the consumes/produces rule: its depends_on
# does not include the blocked wave, so a resuming agent applying just the
# graph rule would wrongly take it. That is the whole point of this fixture.
assert_contains "$constitution" "produces: [session-contract]" "the blocked wave publishes a contract"
assert_contains "$constitution" "consumes: [session-contract]" "a later wave takes that contract"
deps3="$(sed -n '/^- wave: 3$/,/^$/p' docs/baton/constitution.md | sed -n 's/^  depends_on: *//p')"
assert_equals "$deps3" "[1]" "wave 3 does not depend on the blocked wave in the graph -- only through the contract"

# Wave 4 is the one genuinely available wave: nothing blocked upstream and
# no shared contract. Without it the fixture would only ever test refusal.
assert_contains "$state" "| 4 | docs | todo |" "wave 4 is still todo"
deps4="$(sed -n '/^- wave: 4$/,/^$/p' docs/baton/constitution.md | sed -n 's/^  depends_on: *//p')"
assert_equals "$deps4" "[1]" "wave 4 depends only on the closed wave"

# No wave claims a verdict nothing produced.
assert_not_contains "$state" "| pass |" "no autopilot-fixture wave claims a human confirmation"

assert_contains "$(cat .gitignore 2>/dev/null || true)" ".baton/" \
    "the autopilot fixture gitignores .baton/ the way /baton:init leaves it"

cd /
rm -rf "$FIXTURE"
FIXTURE=""
finish
