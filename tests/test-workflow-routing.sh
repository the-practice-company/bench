#!/usr/bin/env bash
# workflow-routing ships two skills and one reference script. The script is
# the plugin's own rule applied to itself: a workflow whose every agent() call
# names a model below the session tier. Nothing else in the suite reads it,
# so an unpinned call added in a refresh would ship silently without this.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
. "$SCRIPT_DIR/helpers.sh"

PLUGIN="$REPO_ROOT/plugins/workflow-routing"
MANIFEST="$PLUGIN/.claude-plugin/plugin.json"
POLICY="$PLUGIN/skills/launching-workflows/SKILL.md"
PROCEDURE="$PLUGIN/skills/materialize-stock-workflow/SKILL.md"
REFERENCE="$PLUGIN/skills/materialize-stock-workflow/references/deep-research-routed.js"

assert_file_exists "$MANIFEST" "plugin.json exists"
assert_valid_json "$MANIFEST" "plugin.json is valid JSON"
assert_equals "$(json_get "$MANIFEST" name)" "workflow-routing" "plugin is named workflow-routing"
assert_contains "$(cat "$REPO_ROOT/.claude-plugin/marketplace.json")" '"./plugins/workflow-routing"' \
    "marketplace points at the local plugin"

assert_file_exists "$POLICY" "launching-workflows skill ships"
assert_file_exists "$PROCEDURE" "materialize-stock-workflow skill ships"
assert_file_exists "$REFERENCE" "deep-research-routed.js reference ships"
assert_contains "$(sed -n '1,5p' "$POLICY")" 'name: launching-workflows' "policy skill keeps its name"
assert_contains "$(sed -n '1,5p' "$PROCEDURE")" 'name: materialize-stock-workflow' "procedure skill keeps its name"

# The skills used to carry `version: "1.0"` in frontmatter, and two different
# texts both did. The plugin manifest is the version now; a second one in the
# skill is the drift this plugin exists to end.
assert_not_contains "$(cat "$POLICY" "$PROCEDURE")" 'version: "' "skills carry no version of their own"

# Cross-references name the plugin-qualified skill, and the reference script
# is reached through the plugin root. A bare /launching-workflows or a
# .claude/skills/ path is a leftover from a per-repository copy and resolves
# to nothing once installed as a plugin.
for f in "$POLICY" "$PROCEDURE"; do
    assert_not_contains "$(cat "$f")" '/launching-workflows`' "$(basename "$(dirname "$f")") names no bare /launching-workflows"
    assert_not_contains "$(cat "$f")" '/materialize-stock-workflow`' "$(basename "$(dirname "$f")") names no bare /materialize-stock-workflow"
    assert_not_contains "$(cat "$f")" '.claude/skills/' "$(basename "$(dirname "$f")") has no .claude/skills/ path"
    assert_not_contains "$(cat "$f")" 'docs/workflows/' "$(basename "$(dirname "$f")") has no docs/workflows/ path"
    assert_not_contains "$(cat "$f")" 'docs/harness-program/' "$(basename "$(dirname "$f")") has no docs/harness-program/ path"
done
assert_contains "$(cat "$POLICY")" 'workflow-routing:materialize-stock-workflow' "policy points at the plugin-qualified procedure"
assert_contains "$(cat "$PROCEDURE")" 'workflow-routing:launching-workflows' "procedure points at the plugin-qualified policy"
assert_contains "$(cat "$PROCEDURE")" '${CLAUDE_PLUGIN_ROOT}/skills/materialize-stock-workflow/references/deep-research-routed.js' \
    "procedure reaches the reference through the plugin root"

# Every agent() call site in the reference carries a model:, and none of them
# is the session tier. Comment lines are dropped first; the header mentions
# agent() in prose.
call_sites="$(grep -v '^[[:space:]]*//' "$REFERENCE" | grep -c 'agent(' || true)"
pins="$(grep -c 'model: "' "$REFERENCE" || true)"
if [ "$call_sites" -gt 0 ]; then
    pass "reference has agent() call sites ($call_sites)"
else
    fail "reference has agent() call sites"
fi
assert_equals "$pins" "$call_sites" "every agent() call in the reference names a model"
assert_not_contains "$(cat "$REFERENCE")" 'model: "fable"' "no reference agent runs on the session tier"
unknown="$(grep -o 'model: "[a-z0-9-]*"' "$REFERENCE" | grep -v -E 'model: "(haiku|sonnet|opus)"' || true)"
assert_equals "$unknown" "" "reference pins only to haiku, sonnet or opus"

finish
