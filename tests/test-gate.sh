#!/usr/bin/env bash
# baton-gate gathers the mechanical half of a wave gate and decides nothing.
# The distinction this file exists to pin is the exit code: a red verify_cmd
# is exit 0 with verify_exit non-zero, because "the tests failed" and "the
# gate is broken" need opposite responses from the only caller there is.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
GATE="$REPO_ROOT/plugins/baton/scripts/baton-gate"
. "$SCRIPT_DIR/helpers.sh"

# Write a ratified constitution carrying the given verify_cmd.
write_constitution() {
    mkdir -p docs/baton
    cat > docs/baton/constitution.md <<EOF
---
schema: baton/constitution/v1
run_id: gate-fixture
status: ratified
verify_cmd: "$1"
placeholder_patterns: "${2:-TODO|FIXME}"
---

# Gate fixture

## Waves

\`\`\`yaml
- wave: 1
  name: one
  depends_on: []
  exit_criteria:
    - The system shall work
\`\`\`
EOF
}

make_fixture_repo
base="$(git rev-parse HEAD)"

# --- usage ---
assert_exit_code 64 "refuses to run without --since" "$GATE"
assert_exit_code 64 "refuses an empty --since" "$GATE" --since ""
assert_exit_code 64 "refuses an unknown flag" "$GATE" --wave 2

# --- the constitution guards ---
assert_exit_code 3 "refuses when there is no constitution" "$GATE" --since "$base"

write_constitution "true"
sed -i.bak 's/^status: ratified$/status: draft/' docs/baton/constitution.md
rm -f docs/baton/constitution.md.bak
assert_exit_code 3 "refuses an unratified constitution" "$GATE" --since "$base"

write_constitution "true"
printf 'REPLACE-WITH-SOMETHING\n' >> docs/baton/constitution.md
assert_exit_code 3 "refuses a constitution with an unfilled placeholder marker" "$GATE" --since "$base"

# An unterminated frontmatter block must not promote the prose to
# frontmatter. Failing open here would let a "status: ratified" written in
# a paragraph gate a run nobody ratified.
write_constitution "true"
sed -i.bak '7s/^---$//' docs/baton/constitution.md
rm -f docs/baton/constitution.md.bak
assert_exit_code 3 "refuses a constitution whose frontmatter was never closed" "$GATE" --since "$base"

# --- a SHA that is not a commit is a usage error, not a git crash ---
write_constitution "true"
assert_exit_code 64 "refuses a --since that is not a commit" "$GATE" --since "not-a-sha"

# Every assertion above is a refusal. Without this one the guards could all
# be correct and the success path still never run -- and Tasks 2-4 append
# their work below it, where nothing would reach it.
write_constitution "true"
assert_exit_code 0 "a well-formed invocation passes every guard" "$GATE" --since "$base"

# --- verify_cmd: the evidence, and the exit code that is NOT the evidence ---
write_constitution "true"
out="$("$GATE" --since "$base")"
assert_contains "$out" "verify_exit=0" "a green verify_cmd reports verify_exit=0"
assert_contains "$out" "verify_cmd=true" "the evidence names the command that was run"
assert_exit_code 0 "a green verify_cmd exits 0" "$GATE" --since "$base"

write_constitution "false"
out="$("$GATE" --since "$base")"
assert_contains "$out" "verify_exit=1" "a red verify_cmd reports its exit code"
assert_exit_code 0 "a RED verify_cmd still exits 0 -- the script reports, it does not judge" \
    "$GATE" --since "$base"

# The log is where the agent reads what actually broke, so it has to exist
# and hold the command's own output.
write_constitution "echo boom-from-the-verify-command; exit 3"
out="$("$GATE" --since "$base")"
assert_contains "$out" "verify_exit=3" "the exact non-zero exit code is passed through, not flattened to 1"
assert_file_exists ".baton/gate-verify.log" "the command's output is captured to a log"
assert_contains "$(cat .baton/gate-verify.log)" "boom-from-the-verify-command" \
    "the log holds the command's own output"

# .baton/ is gitignored in a real run, which is why the log goes there: a
# gate that dirtied the tree would trip the next checkpoint's tree_clean.
assert_contains "$out" "verify_log=.baton/gate-verify.log" "the evidence names where the log went"

# A command that cannot be run at all is the script failing, not the gate.
write_constitution ""
assert_exit_code 4 "refuses an empty verify_cmd" "$GATE" --since "$base"
write_constitution "definitely-not-a-real-command-9d3f"
assert_exit_code 4 "refuses a verify_cmd whose command does not exist" "$GATE" --since "$base"

finish
