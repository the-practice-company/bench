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

# SessionStart fires on five distinct events, and this hook has to run on
# every one of them. A matcher naming only "compact" left four of the five
# unhooked -- including `startup` and `resume`, which are how day two of a
# multi-day run begins, with the least surviving context and the most need
# for deterministic state injection. The hook has no compact-specific logic
# and already exits 0 silently outside a baton run, so there is no event it
# should decline.
session_start_matcher="$(python3 -c \
    "import json,sys; print(json.load(open(sys.argv[1]))['hooks']['SessionStart'][0]['matcher'])" \
    "$HOOKS/hooks.json")"
for event in startup resume clear compact fork; do
    assert_contains "$session_start_matcher" "$event" "SessionStart matches the $event event"
done

make_fixture_repo
export CLAUDE_PLUGIN_ROOT="$REPO_ROOT/plugins/baton"
export CLAUDE_PROJECT_DIR="$FIXTURE"

# Without docs/baton the hooks must be silent no-ops: the plugin is installed
# globally, most repositories are not baton runs.
out="$("$HOOKS/session-start" < /dev/null)"
assert_equals "$out" "" "session-start says nothing in a repository without docs/baton"
# < /dev/null here, not just on the direct invocations below: this hook now
# reads its own stdin (for the session source), and assert_exit_code's
# "$@" would otherwise inherit this file's own stdin -- fine under this
# test runner, but not guaranteed empty in every context that might run
# this file, and the one thing this line and the source-reading change
# both must never do is hang on it.
assert_exit_code 0 "session-start exits 0 without docs/baton" "$HOOKS/session-start" < /dev/null

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

# Captures the exit code rather than letting it fall through this file's own
# set -e, because the exit code is one of the things under test: for
# PreCompact, a non-zero exit is not a louder warning, it is a BLOCKED
# compaction. Left to set -e, a regression to exit 2 would abort this file at
# the first invocation with no failed assertion naming what went wrong.
run_pre_compact() {
    set +e
    pre_compact_stdout="$("$HOOKS/pre-compact" < /dev/null 2>/dev/null)"
    pre_compact_rc=$?
    set -e
}

run_pre_compact
assert_equals "$pre_compact_rc" "0" \
    "pre-compact exits 0 - anything else blocks the compaction instead of reporting on it"
assert_file_exists ".baton/precompact-facts" "pre-compact records facts when the run is under baton"
assert_contains "$(cat .baton/precompact-facts)" "sha=" "recorded facts include the SHA"

state_before="$(cat docs/baton/state.md)"
run_pre_compact
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

# A warning is a `systemMessage` JSON object on stdout, with exit 0 -- these
# assertions used to certify a line on stderr, which is a channel nothing
# reads: Claude Code discards a hook's stderr on exit 0, and for PreCompact
# it does not surface stdout in the transcript either, so every warning this
# hook produced reached neither the human nor the model. The exit code is
# asserted alongside the message on purpose. Exit 2 is the other channel a
# hook can be seen through, and for PreCompact it BLOCKS the compaction --
# a stalled run in place of a warning -- so a future change that reaches for
# it has to fail here, loudly, rather than pass as "the warning is visible
# now".
run_pre_compact
assert_equals "$pre_compact_stdout" "" \
    "pre-compact says nothing when observed_sha matches HEAD and the tree is clean"
assert_equals "$pre_compact_rc" "0" \
    "pre-compact exits 0 when the checkpoint is current"
assert_file_exists ".baton/precompact-facts" \
    "pre-compact still writes facts even when the checkpoint is current"
assert_not_contains "$(cat .baton/precompact-facts)" "observe_failed" \
    "a successful baton-observe run never records observe_failed"

echo "more work landed" > later-work.txt
git add later-work.txt
git commit -q -m "more work landed after the checkpoint"

run_pre_compact
assert_equals "$pre_compact_rc" "0" \
    "pre-compact exits 0 when it warns - exit 2 would block the compaction, not report on it"
printf '%s\n' "$pre_compact_stdout" > behind-warning.json
assert_valid_json "behind-warning.json" \
    "pre-compact warns with a JSON object Claude Code can parse, not a bare line"
# `|| true` so that a regression producing unparseable output fails the
# assertions below with the field it could not read, instead of aborting
# this file under set -e and taking every later assertion with it.
behind_message="$(json_get behind-warning.json systemMessage 2>/dev/null || true)"
assert_contains "$behind_message" "checkpoint is behind" \
    "the warning goes out through systemMessage, the field that is actually shown to the user"
assert_contains "$behind_message" "$head_now" \
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
run_pre_compact
chmod 644 .git/index

assert_equals "$pre_compact_rc" "0" \
    "pre-compact still exits 0 when baton-observe fails - a hook must not break the session"
printf '%s\n' "$pre_compact_stdout" > observe-failed-warning.json
# git's own `fatal:` text is quoted into this message verbatim, so this
# assertion is also the one that catches an escaper that lets a stray quote
# or newline through and turns the whole warning back into silence.
assert_valid_json "observe-failed-warning.json" \
    "the observe-failure warning is still a parseable JSON object once git's fatal: text is quoted into it"
observe_fail_message="$(json_get observe-failed-warning.json systemMessage 2>/dev/null || true)"
assert_contains "$observe_fail_message" "could not establish repository facts" \
    "pre-compact says plainly that facts could not be established, rather than guessing"
assert_not_contains "$observe_fail_message" "work_sha ()" \
    "pre-compact never fabricates a comparison against an empty work_sha when observe failed"
assert_file_exists ".baton/precompact-facts" \
    "pre-compact still writes a facts file when baton-observe fails"
assert_contains "$(cat .baton/precompact-facts)" "observe_failed=true" \
    "the facts file records that observation failed, instead of silently omitting the fields it could not get"
assert_not_contains "$(cat .baton/precompact-facts)" "work_sha=" \
    "the facts file carries no fabricated empty work_sha when observe genuinely failed"

# --- the autopilot line in the injected block ---
# That block is what a compacted session sees before it decides anything. A
# grant it has to go and open the file to discover is a grant it may act
# after rather than on.
mkdir -p docs/baton
cat > docs/baton/state.md <<'EOF'
---
schema: baton/state/v1
suspect: false
needs_human: false
autopilot: all
autopilot_grant: DEC-0007
---

# State

**Goal:** ship the widget pipeline
**Operating mode:** orchestrator
**Non-negotiables:** never modify the billing schema

## Now

- **Next action:** write the failing test in widget.spec.ts
EOF

out="$("$HOOKS/session-start" < /dev/null)"
assert_contains "$out" "Autopilot: all" "session-start injects the autopilot scope when it is on"
assert_contains "$out" "DEC-0007" "session-start names the entry that granted it"
"$HOOKS/session-start" < /dev/null > autopilot-output.json
assert_valid_json "autopilot-output.json" "the autopilot line still leaves valid JSON"
rm -f autopilot-output.json

# Off is the common case and must add nothing: the injected block is the
# one thing that has to stay short enough to be read whole.
sed -i.bak 's/^autopilot: all$/autopilot: off/' docs/baton/state.md
rm -f docs/baton/state.md.bak
out="$("$HOOKS/session-start" < /dev/null)"
assert_not_contains "$out" "Autopilot:" "session-start stays quiet about the autopilot when it is off"

# state.md is written by an agent, not validated input, so the byte-level
# shape of "off" can drift: a trailing space, a quoted scalar, a case
# variant, a CRLF line ending. The dangerous direction is a false positive
# -- announcing a grant that was never made tells a session it may act
# unattended when the human set it to off. Each variant below must stay
# silent, the same as the exact "off" case above.
mkdir -p docs/baton
# A heredoc's trailing whitespace is invisible on the page and too easy for
# a future edit to trim away without anyone noticing the test went dark, so
# this one line is built with printf instead, where the trailing space is a
# literal, visible character in the source.
printf -- '---\nschema: baton/state/v1\nautopilot: off \nautopilot_grant: \xe2\x80\x94\n---\n\n# State\n\n**Goal:** g\n**Operating mode:** m\n**Non-negotiables:** n\n\n## Now\n- **Next action:** a\n' > docs/baton/state.md
out="$("$HOOKS/session-start" < /dev/null)"
assert_not_contains "$out" "Autopilot:" "session-start treats a trailing space after off as still off"

cat > docs/baton/state.md <<'EOF'
---
schema: baton/state/v1
autopilot: "off"
autopilot_grant: —
---

# State

**Goal:** g
**Operating mode:** m
**Non-negotiables:** n

## Now
- **Next action:** a
EOF
out="$("$HOOKS/session-start" < /dev/null)"
assert_not_contains "$out" "Autopilot:" "session-start treats a quoted off as still off"

cat > docs/baton/state.md <<'EOF'
---
schema: baton/state/v1
autopilot: OFF
autopilot_grant: —
---

# State

**Goal:** g
**Operating mode:** m
**Non-negotiables:** n

## Now
- **Next action:** a
EOF
out="$("$HOOKS/session-start" < /dev/null)"
assert_not_contains "$out" "Autopilot:" "session-start treats OFF case-insensitively as still off"

printf -- '---\r\nschema: baton/state/v1\r\nautopilot: off\r\nautopilot_grant: \xe2\x80\x94\r\n---\r\n\r\n# State\r\n\r\n**Goal:** g\r\n**Operating mode:** m\r\n**Non-negotiables:** n\r\n\r\n## Now\r\n- **Next action:** a\r\n' > docs/baton/state.md
out="$("$HOOKS/session-start" < /dev/null)"
assert_not_contains "$out" "Autopilot:" "session-start treats a CRLF-terminated off as still off"
"$HOOKS/session-start" < /dev/null > crlf-off-output.json
assert_valid_json "crlf-off-output.json" "a CRLF-terminated state.md still leaves valid JSON"
rm -f crlf-off-output.json

# The CRLF "off" case above staying silent is not, on its own, proof that
# CRLF parses correctly -- a block match broken by "---\r" not matching
# "^---$" would ALSO stay silent, for the wrong reason. Prove the block
# match survives CRLF by checking the "on" case: a real grant in a fully
# CRLF-terminated file must still show up.
printf -- '---\r\nschema: baton/state/v1\r\nautopilot: all\r\nautopilot_grant: DEC-0007\r\n---\r\n\r\n# State\r\n\r\n**Goal:** g\r\n**Operating mode:** m\r\n**Non-negotiables:** n\r\n\r\n## Now\r\n- **Next action:** a\r\n' > docs/baton/state.md
out="$("$HOOKS/session-start" < /dev/null)"
assert_contains "$out" "Autopilot: all" \
    "a CRLF-terminated file with a real grant still shows the autopilot line -- proves the frontmatter block match survives CRLF rather than happening to stay silent"
assert_contains "$out" "granted DEC-0007)" \
    "a CRLF-terminated file's grant id is displayed without a trailing CR"
"$HOOKS/session-start" < /dev/null > crlf-on-output.json
assert_valid_json "crlf-on-output.json" "a CRLF-terminated file with a real grant still leaves valid JSON"
rm -f crlf-on-output.json

# autopilot_grant needs the same normalization as autopilot: it is what a
# compacted session reads to know which entry authorised the run, and a
# trailing space or a quoted scalar would make the id printed not the id a
# human wrote.
printf -- '---\nschema: baton/state/v1\nautopilot: all\nautopilot_grant: DEC-0007 \n---\n\n# State\n\n**Goal:** g\n**Operating mode:** m\n**Non-negotiables:** n\n\n## Now\n- **Next action:** a\n' > docs/baton/state.md
out="$("$HOOKS/session-start" < /dev/null)"
assert_contains "$out" "granted DEC-0007)" "session-start trims a trailing space from the displayed grant id"

cat > docs/baton/state.md <<'EOF'
---
schema: baton/state/v1
autopilot: all
autopilot_grant: "DEC-0007"
---

# State

**Goal:** g
**Operating mode:** m
**Non-negotiables:** n

## Now
- **Next action:** a
EOF
out="$("$HOOKS/session-start" < /dev/null)"
assert_contains "$out" "granted DEC-0007)" "session-start unquotes the displayed grant id"

# A stray line starting with "autopilot: " in the body, after a real
# frontmatter grant of "all", must not overwrite it: the frontmatter block
# is always read first, and both fields are read with head -1.
cat > docs/baton/state.md <<'EOF'
---
schema: baton/state/v1
autopilot: all
autopilot_grant: DEC-0007
---

# State

**Goal:** g
**Operating mode:** m
**Non-negotiables:** n

## Schema notes
autopilot: off
autopilot_grant: DEC-9999

## Now
- **Next action:** a
EOF
out="$("$HOOKS/session-start" < /dev/null)"
assert_contains "$out" "Autopilot: all" "a body line starting with autopilot: cannot override the frontmatter grant"
assert_contains "$out" "DEC-0007" "a body line starting with autopilot_grant: cannot override the frontmatter grant id"

# --- control characters in state.md must not break the emitted JSON ---
printf -- '---\nschema: baton/state/v1\n---\n**Goal:** bell\x07here esc\x1bhere\n**Operating mode:** orchestrator\n**Non-negotiables:** none\n## Now\n- **Next action:** go\n' > docs/baton/state.md
"$HOOKS/session-start" < /dev/null > ctrl-char-output.json
assert_valid_json "ctrl-char-output.json" \
    "session-start's output still parses as JSON when state.md contains a raw control character"

# --- the session source, passed through from Claude Code's hook stdin ---
# hooks.json's SessionStart matcher already tells the harness apart on
# startup|resume|clear|compact|fork; until this hook reads its own stdin,
# that distinction never reaches the agent, and baton-resume's entire
# safety property -- continue silently after a compact, wait on a fresh
# start -- has no way to be checked. This line has to be present on every
# run, not just when the autopilot is on: even with autopilot off, "clear"
# versus "compact" changes what the agent should assume about its own
# memory.
mkdir -p docs/baton
cat > docs/baton/state.md <<'EOF'
---
schema: baton/state/v1
autopilot: off
autopilot_grant: —
---

# State

**Goal:** g
**Operating mode:** m
**Non-negotiables:** n

## Now
- **Next action:** a
EOF

for src in startup resume clear compact fork; do
    out="$(printf '{"session_id":"abc","transcript_path":"/tmp/t","hook_event_name":"SessionStart","source":"%s"}' "$src" | "$HOOKS/session-start")"
    assert_contains "$out" "Session source: ${src}" "session-start passes through the $src source"
    printf '{"session_id":"abc","transcript_path":"/tmp/t","hook_event_name":"SessionStart","source":"%s"}' "$src" | "$HOOKS/session-start" > source-output.json
    assert_valid_json "source-output.json" "session-start's output is still valid JSON with source=$src on stdin"
    rm -f source-output.json
done

# Empty stdin, malformed JSON, and a source outside the enum must not be
# guessed into one of the five real values, and must not be silently
# omitted either -- an agent that sees no line at all concludes whatever it
# likes, which is the exact failure mode this line exists to close off.
out="$("$HOOKS/session-start" < /dev/null)"
assert_contains "$out" "Session source: unknown" "an empty stdin reads as an explicit unknown source, not a guess"

out="$(printf 'not json at all {{{' | "$HOOKS/session-start")"
assert_contains "$out" "Session source: unknown" "malformed JSON on stdin reads as unknown, not a crash and not a guess"

out="$(printf '{"source":"teleport"}' | "$HOOKS/session-start")"
assert_contains "$out" "Session source: unknown" "a source value outside the five-value enum reads as unknown"

# The fail-safe reading has to be stated in the injected text itself, not
# just decided in the hook's own logic -- the agent reading the block is
# the one that has to apply it. Waiting when the run should have continued
# costs a human one command; continuing when it should have waited is the
# failure this whole property exists to prevent.
out="$("$HOOKS/session-start" < /dev/null)"
assert_contains "$out" "unknown counts as startup, never as compact" \
    "session-start states the unknown-is-startup fail-safe reading in the injected text"

# A hostile source value (attempted JSON injection) is normalized against
# the five-value enum before it is ever interpolated, so it can only ever
# become one of six fixed literal strings -- but prove it, the same way
# autopilot_grant's hostile cases are proven rather than assumed.
out="$(printf '{"source": "evil\\"}, \\"pwned\\": \\"1"}' | "$HOOKS/session-start")"
assert_contains "$out" "Session source: unknown" "a source value crafted to break out of the JSON string still reads as unknown"
printf '{"source": "evil\\"}, \\"pwned\\": \\"1"}' | "$HOOKS/session-start" > hostile-source-output.json
assert_valid_json "hostile-source-output.json" "a hostile source value on stdin still leaves valid JSON"
python3 -c "import json,sys; d=json.load(open('hostile-source-output.json')); sys.exit(0 if list(d.keys())==['hookSpecificOutput'] else 1)" \
    && pass "the hostile source value injects no extra top-level JSON key" \
    || fail "the hostile source value injects no extra top-level JSON key"
rm -f hostile-source-output.json

# A repository without docs/baton must still say nothing at all, source or
# no source -- the no-op case this hook has always had.
rm -f docs/baton/state.md
out="$(printf '{"source":"compact"}' | "$HOOKS/session-start")"
assert_equals "$out" "" "session-start says nothing in a repository without docs/baton, even with a real source on stdin"

# --- line 66's "check the session source" is only a real instruction once
# something is there to check it against ---
mkdir -p docs/baton
cat > docs/baton/state.md <<'EOF'
---
schema: baton/state/v1
autopilot: all
autopilot_grant: DEC-0007
---

# State

**Goal:** g
**Operating mode:** m
**Non-negotiables:** n

## Now
- **Next action:** a
EOF
out="$(printf '{"source":"compact"}' | "$HOOKS/session-start")"
assert_contains "$out" "Session source line above" \
    "the autopilot line points at the Session source line now that one exists, not just at a skill"

finish
