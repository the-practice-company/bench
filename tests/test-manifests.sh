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
# This assertion used to require the opposite: that the marketplace re-export
# superpowers from obra/superpowers. It was inverted deliberately. That entry
# carried no ref, no sha and no version -- an unpinned copy of one that
# claude-plugins-official already ships WITH a pin. What reached a user at
# install, and again at every version bump, was whatever that repository's
# default branch happened to be at that moment, chosen by a third party. A
# marketplace that ships one plugin cannot become a distribution channel for
# code its owner does not control, which is the property worth pinning down
# in a test.
plugin_names="$(python3 -c \
    "import json,sys; print(' '.join(p['name'] for p in json.load(open(sys.argv[1]))['plugins']))" \
    "$MARKETPLACE")"
assert_equals "$plugin_names" "baton" "marketplace ships baton and nothing else"
assert_not_contains "$(cat "$MARKETPLACE")" 'obra/superpowers' \
    "marketplace does not re-export superpowers"

# The companion relationship itself is still asserted -- it just lives where it
# belongs now, as a pointer in the README rather than a second copy of someone
# else's manifest entry.
assert_contains "$(cat "$REPO_ROOT/README.md")" 'superpowers@claude-plugins-official' \
    "README points at the pinned official superpowers, not a re-export"

# baton-gate is reached by path from the autopilot skill, not through any
# manifest entry, so nothing else in this suite would notice if it stopped
# shipping or lost its executable bit -- test-gate.sh runs it from the
# working tree, where the bit is whatever the checkout happens to have.
assert_file_exists "$REPO_ROOT/plugins/baton/scripts/baton-gate" "baton-gate ships with the plugin"
if [ -x "$REPO_ROOT/plugins/baton/scripts/baton-gate" ]; then
    pass "baton-gate is executable"
else
    fail "baton-gate is executable"
fi

finish
