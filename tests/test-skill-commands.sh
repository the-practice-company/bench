#!/usr/bin/env bash
# The scripts are tested exhaustively elsewhere. This file tests the CALL:
# the exact text the skills and commands tell the agent to run.
#
# That distinction is not academic. Every other test file drives baton-lock
# with a literal session id -- session-a, session-b, racer-3-4 -- so the
# suite could grow to 368 assertions while every documented lock invocation
# in the plugin exited 64 in the field, because they named an environment
# variable that does not exist. A script can be perfect and still be
# unreachable through the only door the agent is told to use. These tests
# open that door.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PLUGIN="$REPO_ROOT/plugins/baton"
LOCK="$PLUGIN/scripts/baton-lock"
. "$SCRIPT_DIR/helpers.sh"

# The one place the session-id expression is written down in this suite.
# The docs must match it (below), and the acquire test further down runs the
# docs' own copy of it -- so the name in the plugin and the name the tests
# exercise cannot drift apart without something here failing.
EXPECTED_SESSION_EXPR='"${CLAUDE_CODE_SESSION_ID:-$CLAUDE_SESSION_ID}"'

# Files that tell the agent to run something.
DOC_FILES="
commands/init.md
commands/checkpoint.md
commands/status.md
commands/auto.md
commands/continue.md
skills/baton/SKILL.md
skills/baton-resume/SKILL.md
skills/baton-checkpoint/SKILL.md
skills/baton-autopilot/SKILL.md
"

# The subset that invokes baton-lock, and so has a session id to get right.
# baton-autopilot is deliberately not here: it names baton-lock only in prose
# (exit 3 stops the run), and the guard below fails a listed file that never
# invokes it -- which is the guard working, not a file to paper over.
LOCK_DOC_FILES="
commands/init.md
commands/auto.md
commands/continue.md
skills/baton-resume/SKILL.md
skills/baton-checkpoint/SKILL.md
"

# --- the lists cover everything they are supposed to ---
# Every check in this file iterates one of the two lists above, so a file
# missing from a list is not checked at all -- and nothing says so. That is
# how both lists silently stopped covering the plugin: they were written
# when it had three commands and three skills, and the autopilot's two
# commands and one skill were added to neither, so every rule below skipped
# them for the whole feature's development. Derive membership from the
# directory rather than trusting the lists to be maintained.
for f in "$PLUGIN"/commands/*.md "$PLUGIN"/skills/*/SKILL.md; do
    rel="${f#$PLUGIN/}"
    if printf '%s\n' $DOC_FILES | grep -qxF "$rel"; then
        pass "$rel is in DOC_FILES"
    else
        fail "$rel is in DOC_FILES"
    fi
done

# And the lock list, derived from the files themselves: a doc that invokes
# baton-lock has a session id to get right, whichever list someone remembered
# to add it to. The converse -- a listed file that never invokes it -- is
# caught by the guard in the loop below.
for rel in $DOC_FILES; do
    grep -q 'baton-lock" \(acquire\|release\|takeover\|check\)' "$PLUGIN/$rel" || continue
    if printf '%s\n' $LOCK_DOC_FILES | grep -qxF "$rel"; then
        pass "$rel invokes baton-lock, so it is in LOCK_DOC_FILES"
    else
        fail "$rel invokes baton-lock, so it is in LOCK_DOC_FILES"
    fi
done

# --- every documented baton-lock call passes the session id the same way ---
for rel in $LOCK_DOC_FILES; do
    calls="$(grep -n 'baton-lock" \(acquire\|release\|takeover\|check\)' "$PLUGIN/$rel" || true)"
    if [ -z "$calls" ]; then
        # Not a pedantic check: without it every assertion below passes
        # vacuously the day someone renames the script or reflows the call
        # onto two lines, which is exactly when they stop being checked.
        fail "$rel invokes baton-lock with a verb at least once"
        continue
    fi
    pass "$rel invokes baton-lock with a verb at least once"

    wrong="$(printf '%s\n' "$calls" | grep -vF "$EXPECTED_SESSION_EXPR" || true)"
    if [ -n "$wrong" ]; then
        fail "every baton-lock call in $rel passes $EXPECTED_SESSION_EXPR"
        printf '%s\n' "$wrong" | sed 's/^/    /'
    else
        pass "every baton-lock call in $rel passes $EXPECTED_SESSION_EXPR"
    fi
done

# --- every ${CLAUDE_PLUGIN_ROOT}/... path names something that is there ---
# A path prefix left off (`baton-lock check <session-id>` in prose, when
# baton-lock is not on PATH) and a path prefix pointing at a file that does
# not exist fail identically for the agent: command not found, at the moment
# it is trying to take the writer lease.
referenced="$(mktemp)"
for rel in $DOC_FILES; do
    grep -oE '\$\{CLAUDE_PLUGIN_ROOT\}/(scripts|templates)/[A-Za-z0-9._-]+' "$PLUGIN/$rel" 2>/dev/null \
        | sed "s#^\\\${CLAUDE_PLUGIN_ROOT}/#$rel	#" >> "$referenced" || true
done

# Column 2 is the referenced path; column 1 is the doc that referenced it,
# kept so a failure can name the file to go and fix.
paths="$(cut -f2 "$referenced" | sort -u)"
if [ -z "$paths" ]; then
    fail "the docs reference at least one \${CLAUDE_PLUGIN_ROOT} path"
else
    pass "the docs reference at least one \${CLAUDE_PLUGIN_ROOT} path"
fi

for path in $paths; do
    referrers="$(awk -F'\t' -v p="$path" '$2 == p { print $1 }' "$referenced" | sort -u | tr '\n' ' ')"
    if [ -f "$PLUGIN/$path" ]; then
        pass "$path exists (referenced by: $referrers)"
    else
        fail "$path exists (referenced by: $referrers)"
    fi
    case "$path" in
        scripts/*)
            if [ -x "$PLUGIN/$path" ]; then
                pass "$path is executable (referenced by: $referrers)"
            else
                fail "$path is executable (referenced by: $referrers)"
            fi
            ;;
    esac
done
rm -f "$referenced"

# --- no bash block runs a baton script by bare name ---
# The plugin scripts are not on PATH. Prose may name them freely -- "see
# baton-resume", "baton-write exits non-zero" -- but a line inside a ```bash
# block is a line the agent will run, and a bare `baton-lock check ...`
# there is a command not found, not an instruction.
#
# Every script under plugins/baton/scripts/ belongs in the alternation. A
# script missing from it is not checked at all, which is how baton-gate went
# uncovered from the day it was written until the day the doc lists were
# extended to the files that call it.
bare="$(
    for rel in $DOC_FILES; do
        awk -v rel="$rel" '
            /^```bash$/ { inblock = 1; next }
            /^```/      { inblock = 0; next }
            inblock     { print rel ":" FNR ": " $0 }
        ' "$PLUGIN/$rel"
    done | sed 's#scripts/baton-[a-z]*##g' | grep -E 'baton-(lock|observe|write|journal|gate)' || true
)"
if [ -n "$bare" ]; then
    fail "no bash block invokes a baton script by bare name (it is not on PATH)"
    printf '%s\n' "$bare" | sed 's/^/    /'
else
    pass "no bash block invokes a baton script by bare name (it is not on PATH)"
fi

# --- the documented acquire, run for real ---
make_fixture_repo

# Lifted out of the skill rather than retyped: retyping it here would
# recreate the very gap this file exists to close -- a test that agrees
# with itself while the document the agent actually reads says something
# else.
doc_expr="$(sed -n 's#.*baton-lock" acquire ##p' "$PLUGIN/skills/baton-resume/SKILL.md" | head -1)"
assert_equals "$doc_expr" "$EXPECTED_SESSION_EXPR" \
    "baton-resume's acquire passes the session-id expression this suite exercises"

# `set +u` because the agent's shell has none: an unset name has to expand
# to an empty string here exactly as it would there, or the "neither name
# set" case below would abort this script instead of testing anything.
set +u

export CLAUDE_CODE_SESSION_ID="session-from-claude-code"
unset CLAUDE_SESSION_ID
eval "session_id=$doc_expr"
assert_equals "$session_id" "session-from-claude-code" \
    "the documented expression reads the session id Claude Code actually exports"
assert_exit_code 0 "acquire succeeds with the session id the skills tell the agent to pass" \
    "$LOCK" acquire "$session_id"
assert_file_exists ".baton/lock" "the documented acquire writes a lock file"
assert_equals "$(sed -n 's/^session=//p' .baton/lock | head -1)" "session-from-claude-code" \
    "the lease records the id that came from the environment"

# Neither name is documented by Claude Code, so the fallback is load-bearing
# rather than decorative: it is what keeps the lease working the day the
# exported name changes again.
rm -rf .baton
unset CLAUDE_CODE_SESSION_ID
export CLAUDE_SESSION_ID="session-from-the-fallback"
eval "session_id=$doc_expr"
assert_equals "$session_id" "session-from-the-fallback" \
    "the documented expression falls back to the second name when the first is unset"
assert_exit_code 0 "acquire succeeds through the fallback name" "$LOCK" acquire "$session_id"
assert_equals "$(sed -n 's/^session=//p' .baton/lock | head -1)" "session-from-the-fallback" \
    "the lease records the id that came from the fallback name"

# With neither name set the expression is an empty string, and baton-lock's
# entry check is all that stands between that and two sessions quietly
# sharing a lease. Refusal is the correct outcome, not a broken test.
rm -rf .baton
unset CLAUDE_CODE_SESSION_ID CLAUDE_SESSION_ID
eval "session_id=$doc_expr"
assert_equals "$session_id" "" \
    "with neither name set the documented expression yields an empty session id"
assert_exit_code 64 "acquire refuses the empty session id an unset environment produces" \
    "$LOCK" acquire "$session_id"
if [ -e .baton/lock ]; then
    fail "no lease is written when neither session-id name is set"
else
    pass "no lease is written when neither session-id name is set"
fi

set -u

# --- the runbook covers the autopilot ---
# The scripted autopilot test pins the fixture's premise and says so itself:
# what an agent does with that fixture is the runbook's job, run by a human.
# Without a scenario there, the fixture is built and checked by nobody.
runbook="$(cat "$REPO_ROOT/tests/fixtures/cold-start/RUNBOOK.md")"
# The heading, not the bare words: "Scenario 4" alone appears in the bullet
# list and in "Recording the result" too, so deleting the entire section
# would leave that assertion green off a mention elsewhere in the file.
assert_contains "$runbook" "## Scenario 4: autopilot" "the runbook has a scenario for the autopilot"
assert_contains "$runbook" "build-autopilot.sh" "scenario 4 names the fixture it runs against"
assert_contains "$runbook" "/baton:continue" "scenario 4 exercises the fresh-session pickup"

finish
