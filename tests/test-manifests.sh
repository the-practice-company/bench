#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
. "$SCRIPT_DIR/helpers.sh"

MARKETPLACE="$REPO_ROOT/.claude-plugin/marketplace.json"
PLUGIN="$REPO_ROOT/plugins/baton/.claude-plugin/plugin.json"

assert_file_exists "$MARKETPLACE" "marketplace.json exists"
assert_file_exists "$PLUGIN" "plugin.json exists"

assert_valid_json "$MARKETPLACE" "marketplace.json is valid JSON"
assert_valid_json "$PLUGIN" "plugin.json is valid JSON"

assert_equals "$(json_get "$PLUGIN" name)" "baton" "plugin is named baton"
assert_contains "$(cat "$MARKETPLACE")" '"./plugins/baton"' "marketplace points at the local plugin"
assert_contains "$(cat "$MARKETPLACE")" 'obra/superpowers' "marketplace lists superpowers as the companion"

finish
