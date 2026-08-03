#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TPL="$REPO_ROOT/plugins/baton/templates"
. "$SCRIPT_DIR/helpers.sh"

constitution="$(cat "$TPL/constitution.md")"
state="$(cat "$TPL/state.md")"

assert_contains "$constitution" "schema: baton/constitution/v1" "constitution declares its schema version"
assert_contains "$constitution" "verify_cmd:" "constitution carries verify_cmd, which the agent must not be able to edit"
assert_contains "$constitution" "placeholder_patterns:" "constitution carries the placeholder patterns"
assert_contains "$constitution" "## Operating mode" "constitution states who the agent is in this run"
assert_contains "$constitution" "## Non-negotiables" "constitution has the rules that survive into state"
assert_contains "$constitution" "exit_criteria" "constitution declares per-wave exit criteria"
assert_contains "$constitution" "The system shall" "constitution shows exit criteria in EARS form"
assert_contains "$constitution" "## Amendments" "constitution has an append-only amendments section"

assert_contains "$state" "schema: baton/state/v1" "state declares its schema version"
assert_contains "$state" "suspect: false" "state carries the suspect flag"
assert_contains "$state" "needs_human: false" "state carries the needs_human flag"
assert_contains "$state" "**Non-negotiables:**" "state restates the live constraints, not only the goal"
assert_contains "$state" "**Operating mode:**" "state restates who the agent is"
assert_contains "$state" "**Suspect:**" "state has a place to describe a divergence"
assert_contains "$state" "branch/worktree" "state records where each wave lives"

lines="$(wc -l < "$TPL/state.md" | tr -d ' ')"
if [ "$lines" -le 60 ]; then
    pass "state template is within the 60-line cap ($lines lines)"
else
    fail "state template is within the 60-line cap ($lines lines)"
fi

finish
