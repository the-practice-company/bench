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

# session-start never reads CLAUDE_PLUGIN_ROOT at all (grepped above), so an
# unset value can't exercise a fallback it doesn't have. What this actually
# checks is narrower: the hook still runs to completion, unaided by any
# hook-provided environment, when invoked directly.
assert_exit_code 0 "session-start runs to completion with no CLAUDE_PLUGIN_ROOT in the environment (it never reads the variable)" "$PLUGIN/hooks/session-start"

# pre-compact is the hook that DOES have a real fallback for a missing
# CLAUDE_PLUGIN_ROOT: it resolves its own plugin root from $0 instead
# (`${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}`), so it can still
# find baton-observe next to itself. Unlike test-hooks.sh, which exports
# CLAUDE_PLUGIN_ROOT once at the top and leaves it set for every call, this
# unsets it immediately before the call below so the fallback path is
# actually exercised, not merely present in the source and never taken.
rm -f .baton/precompact-facts
unset CLAUDE_PLUGIN_ROOT || true
assert_exit_code 0 "pre-compact runs to completion with no CLAUDE_PLUGIN_ROOT in the environment" "$PLUGIN/hooks/pre-compact"
assert_file_exists ".baton/precompact-facts" \
    "pre-compact with no CLAUDE_PLUGIN_ROOT still locates baton-observe via \$0 and writes the facts file"
assert_contains "$(cat .baton/precompact-facts)" "sha=" \
    "the facts file written under the fallback holds real observed facts, not an empty stub"

finish
