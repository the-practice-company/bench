#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PLUGIN="$REPO_ROOT/plugins/baton"
. "$SCRIPT_DIR/helpers.sh"

# Every mechanic must be reachable without any hook running. Hooks are
# convenience; the files are authoritative.
for s in baton-observe baton-write baton-lock baton-journal; do
    if [ -x "$PLUGIN/scripts/$s" ]; then
        pass "$s is executable and callable directly"
    else
        fail "$s is executable and callable directly"
    fi
done

# No script may depend on being launched by a hook.
for s in baton-observe baton-write baton-lock baton-journal; do
    body="$(cat "$PLUGIN/scripts/$s")"
    assert_not_contains "$body" "CLAUDE_PLUGIN_ROOT" "$s does not require the plugin-root variable"
    assert_not_contains "$body" "precompact-facts" "$s does not require hook output"
done

# The resume skill must name a path that does not involve hooks.
resume="$(cat "$PLUGIN/skills/baton-resume/SKILL.md")"
assert_contains "$resume" "docs/baton/state.md" "resume reads the file directly"
assert_contains "$resume" "if present" "resume treats hook output as optional"

# The human has a command for every point where a hook would have helped.
assert_file_exists "$PLUGIN/commands/checkpoint.md" "a manual checkpoint command exists"

make_fixture_repo
export CLAUDE_PROJECT_DIR="$FIXTURE"
unset CLAUDE_PLUGIN_ROOT || true

mkdir -p docs/baton
printf -- '---\nschema: baton/state/v1\n---\n\n**Goal:** g\n' > docs/baton/state.md
assert_exit_code 0 "session-start survives an unset plugin root" "$PLUGIN/hooks/session-start"

finish
