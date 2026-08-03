#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
HOOKS="$REPO_ROOT/plugins/baton/hooks"
. "$SCRIPT_DIR/helpers.sh"

assert_valid_json "$HOOKS/hooks.json" "hooks.json is valid JSON"
cfg="$(cat "$HOOKS/hooks.json")"
assert_contains "$cfg" '"PreCompact"' "registers PreCompact"
assert_contains "$cfg" '"SessionStart"' "registers SessionStart"
assert_contains "$cfg" '"compact"' "SessionStart matches the compact event"

make_fixture_repo
export CLAUDE_PLUGIN_ROOT="$REPO_ROOT/plugins/baton"
export CLAUDE_PROJECT_DIR="$FIXTURE"

# Without docs/baton the hooks must be silent no-ops: the plugin is installed
# globally, most repositories are not baton runs.
out="$("$HOOKS/session-start" < /dev/null)"
assert_equals "$out" "" "session-start says nothing in a repository without docs/baton"
assert_exit_code 0 "session-start exits 0 without docs/baton" "$HOOKS/session-start"

out="$("$HOOKS/pre-compact" < /dev/null 2>/dev/null)"
assert_equals "$out" "" "pre-compact says nothing in a repository without docs/baton"
if [ -f .baton/precompact-facts ]; then
    fail "pre-compact writes no facts without docs/baton"
else
    pass "pre-compact writes no facts without docs/baton"
fi

mkdir -p docs/baton
cat > docs/baton/state.md <<'EOF'
---
schema: baton/state/v1
observed_sha: deadbee
suspect: false
needs_human: false
---

# State

**Goal:** ship the widget pipeline
**Operating mode:** orchestrator; delegates implementation to subagents
**Non-negotiables:** never modify the billing schema

## Now
- **Next action:** run npm test -- widget.spec.ts and fix the failing assertion
EOF

out="$("$HOOKS/session-start" < /dev/null)"
assert_contains "$out" "additionalContext" "session-start emits context for Claude Code"
assert_contains "$out" "ship the widget pipeline" "session-start carries the goal"
assert_contains "$out" "orchestrator" "session-start carries the operating mode"
assert_contains "$out" "never modify the billing schema" "session-start carries the non-negotiables"
assert_contains "$out" "widget.spec.ts" "session-start carries the next action"
assert_contains "$out" "baton-resume" "session-start tells the agent to resume"

"$HOOKS/pre-compact" < /dev/null 2>/dev/null
assert_file_exists ".baton/precompact-facts" "pre-compact records facts when the run is under baton"
assert_contains "$(cat .baton/precompact-facts)" "sha=" "recorded facts include the SHA"

state_before="$(cat docs/baton/state.md)"
"$HOOKS/pre-compact" < /dev/null 2>/dev/null
assert_equals "$(cat docs/baton/state.md)" "$state_before" \
    "pre-compact never writes state.md - the lock holder is the only writer"

# --- pre-compact resolves paths against the git top level, not the caller's
# cwd. CLAUDE_PROJECT_DIR unset with cwd inside a subdirectory used to make
# pre-compact find no docs/baton and silently record nothing - the same
# class of bug baton-lock, baton-write and baton-journal were fixed for. ---
rm -f .baton/precompact-facts
mkdir -p src
(
    cd src
    unset CLAUDE_PROJECT_DIR
    "$HOOKS/pre-compact" < /dev/null >/dev/null 2>/dev/null
)
assert_file_exists ".baton/precompact-facts" \
    "pre-compact invoked from a subdirectory still resolves to the repository root"
if [ -e "src/.baton" ]; then
    fail "pre-compact invoked from a subdirectory must not write facts under that subdirectory"
else
    pass "pre-compact invoked from a subdirectory must not write facts under that subdirectory"
fi
rm -rf src

# --- the warning must not cry wolf ---
# .baton/ is machine state, entirely gitignored by design (see the spec) -
# do that here too so the lock/facts files this test already produced don't
# themselves make the tree look dirty below.
echo ".baton/" >> .gitignore

# A committed file cannot state the hash of the commit that carries it - a
# commit's hash is computed from its own content, so it cannot also declare
# it. To build a fixture where observed_sha genuinely equals the current
# HEAD with a clean tree, state.md has to sit outside the commit that would
# otherwise have to predict its own hash. It was never committed in this
# fixture (only written to the working tree above), so ignoring it here
# does that without faking anything: the file lives in the working tree,
# doesn't move HEAD, and doesn't count as dirty.
echo "docs/baton/state.md" >> .gitignore
git add .gitignore
git commit -q -m "test fixture: gitignore machine state and state.md"
head_now="$(git rev-parse HEAD)"
cat > docs/baton/state.md <<EOF
---
schema: baton/state/v1
observed_sha: ${head_now}
suspect: false
needs_human: false
---

# State

**Goal:** ship the widget pipeline
**Operating mode:** orchestrator; delegates implementation to subagents
**Non-negotiables:** never modify the billing schema

## Now
- **Next action:** run npm test -- widget.spec.ts and fix the failing assertion
EOF

stderr_current="$( { "$HOOKS/pre-compact" < /dev/null >/dev/null; } 2>&1 )"
assert_equals "$stderr_current" "" \
    "pre-compact stays silent when observed_sha matches HEAD and the tree is clean"
assert_file_exists ".baton/precompact-facts" \
    "pre-compact still writes facts even when the checkpoint is current"
assert_not_contains "$(cat .baton/precompact-facts)" "observe_failed" \
    "a successful baton-observe run never records observe_failed"

echo "more work landed" > later-work.txt
git add later-work.txt
git commit -q -m "more work landed after the checkpoint"

stderr_behind="$( { "$HOOKS/pre-compact" < /dev/null >/dev/null; } 2>&1 )"
if [ -n "$stderr_behind" ]; then
    pass "pre-compact warns when observed_sha is behind HEAD"
else
    fail "pre-compact warns when observed_sha is behind HEAD"
fi
assert_contains "$stderr_behind" "$head_now" \
    "the warning names the stale observed_sha, not just that something diverged"

# --- a genuine baton-observe failure must be recorded, not silently
# reinterpreted as "no work landed". Reproduced with an unreadable
# .git/index (which makes baton-observe itself die with a git fatal:
# error): before the fix, pre-compact discarded both baton-observe's
# stderr and its exit status, so every field baton-observe would have
# printed came out empty instead of absent, and the hook warned with a
# fabricated "work_sha ()" - the real fatal: error thrown away and never
# surfaced anywhere. ---
rm -f .baton/precompact-facts
chmod 000 .git/index
set +e
observe_fail_stderr="$( { "$HOOKS/pre-compact" < /dev/null >/dev/null; } 2>&1 )"
observe_fail_rc=$?
set -e
chmod 644 .git/index

assert_equals "$observe_fail_rc" "0" \
    "pre-compact still exits 0 when baton-observe fails - a hook must not break the session"
assert_contains "$observe_fail_stderr" "could not establish repository facts" \
    "pre-compact says plainly that facts could not be established, rather than guessing"
assert_not_contains "$observe_fail_stderr" "work_sha ()" \
    "pre-compact never fabricates a comparison against an empty work_sha when observe failed"
assert_file_exists ".baton/precompact-facts" \
    "pre-compact still writes a facts file when baton-observe fails"
assert_contains "$(cat .baton/precompact-facts)" "observe_failed=true" \
    "the facts file records that observation failed, instead of silently omitting the fields it could not get"
assert_not_contains "$(cat .baton/precompact-facts)" "work_sha=" \
    "the facts file carries no fabricated empty work_sha when observe genuinely failed"

# --- control characters in state.md must not break the emitted JSON ---
printf -- '---\nschema: baton/state/v1\n---\n**Goal:** bell\x07here esc\x1bhere\n**Operating mode:** orchestrator\n**Non-negotiables:** none\n## Now\n- **Next action:** go\n' > docs/baton/state.md
"$HOOKS/session-start" < /dev/null > ctrl-char-output.json
assert_valid_json "ctrl-char-output.json" \
    "session-start's output still parses as JSON when state.md contains a raw control character"

finish
