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

# Extracts field NAME's exact value from the gate's captured key=value
# output. Mirrors test-lock.sh's lock_field, adapted for output already
# captured in a variable rather than read from a file: an exact match, not
# assert_contains, since "verify_exit=1" is an unanchored substring of
# "verify_exit=127" and "verify_exit=130" -- exactly the codes that mean
# "did not run", not "did not pass". An assertion checking for exit code 1
# with assert_contains would pass against either by accident.
gate_field() {
    printf '%s\n' "$1" | sed -n "s/^$2=//p" | head -1
}

# Write a ratified constitution carrying the given verify_cmd and, optionally,
# placeholder_patterns. The dash form below (not colon-dash) is deliberate:
# $2 unset (the caller didn't pass a second argument at all) and $2="" (the
# caller explicitly passed an empty string, to test an empty pattern list)
# are different callers asking different things, and colon-dash cannot tell
# them apart -- it treats "set to empty" the same as "unset" and substitutes
# the default either way, which would make write_constitution "true" ""
# silently write "TODO|FIXME" instead of the empty patterns the caller
# asked for.
write_constitution() {
    mkdir -p docs/baton
    cat > docs/baton/constitution.md <<EOF
---
schema: baton/constitution/v1
run_id: gate-fixture
status: ratified
verify_cmd: "$1"
placeholder_patterns: "${2-TODO|FIXME}"
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
assert_equals "$(gate_field "$out" verify_exit)" "1" "a red verify_cmd reports its exit code, exactly (not merely a string that contains it)"
assert_exit_code 0 "a RED verify_cmd still exits 0 -- the script reports, it does not judge" \
    "$GATE" --since "$base"

# The guard consults bash's own command -v, so the run has to be bash too --
# under /bin/sh-as-dash (Debian, Ubuntu) this bashism would otherwise report
# verify_exit=127, a command that was never found, arriving dressed as a
# suite that failed.
write_constitution "[[ 1 == 1 ]]"
out="$("$GATE" --since "$base")"
assert_equals "$(gate_field "$out" verify_exit)" "0" "verify_cmd runs under bash, the shell whose command -v vouched for it"

# Stdin is redirected from /dev/null, so a verify_cmd that reads it gets EOF
# instead of whatever the caller happened to be holding. Feeding the gate a
# pipe here is what makes this discriminating, with no background process
# and no timing involved: without the redirect, cat swallows the line below
# and it lands in the log.
write_constitution "cat"
printf 'SHOULD-NOT-REACH-THE-VERIFY-COMMAND\n' | "$GATE" --since "$base" > /dev/null
assert_not_contains "$(cat .baton/gate-verify.log)" "SHOULD-NOT-REACH-THE-VERIFY-COMMAND" \
    "verify_cmd reads from /dev/null, not from whatever stdin the caller had open"

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
# The message is checked, not just the exit code: command -v "" also fails,
# so the empty-verify_cmd guard and the not-runnable guard both produce
# exit 4, and an exit-code-only assertion passes whether or not the empty
# guard exists at all -- it does not test the guard it is named for.
write_constitution ""
assert_exit_code 4 "refuses an empty verify_cmd" "$GATE" --since "$base"
empty_verify_stderr="$("$GATE" --since "$base" 2>&1 >/dev/null || true)"
assert_contains "$empty_verify_stderr" "verify_cmd is empty" \
    "the empty refusal names itself, distinct from the not-runnable refusal below"

write_constitution "definitely-not-a-real-command-9d3f"
assert_exit_code 4 "refuses a verify_cmd whose command does not exist" "$GATE" --since "$base"

# "CI=1 npm test" names npm, not CI=1 -- an env-var prefix is the ordinary
# shape of a test command, and exit 4 means stop the run, so refusing this
# would halt overnight work over nothing.
write_constitution "CI=1 true"
out="$("$GATE" --since "$base")"
assert_equals "$(gate_field "$out" verify_exit)" "0" "an env-var prefix names the command after it, not the assignment"

# --- a failed log write is the gate unable to gather evidence, not a red
# suite -- both must exit 4, with their own message, not present as
# verify_exit=<something small>. Skipped as root: root ignores the mode
# bits below, so the assertion would fail for the wrong reason.
if [ "$(id -u)" != "0" ]; then
    write_constitution "true"
    rm -rf .baton
    mkdir -p .baton
    chmod 555 .baton
    unwritable_stderr="$("$GATE" --since "$base" 2>&1 >/dev/null || true)"
    assert_exit_code 4 "refuses when .baton/'s log cannot be written" "$GATE" --since "$base"
    assert_contains "$unwritable_stderr" "cannot write" \
        "the refusal names what could not be written, not just a bare exit code"
    chmod 755 .baton
else
    pass "(skipped as root) an unwritable .baton/ is the gate failing, not the suite"
fi

# .baton existing as a plain file, not a directory, is the same class of
# bug: unguarded, mkdir -p fails there and set -e aborts with no
# baton-gate: prefix and exit 1 -- a code the header table already spends
# on "not a git repository".
write_constitution "true"
rm -rf .baton
touch .baton
assert_exit_code 4 "refuses when .baton exists as a file, not a directory" "$GATE" --since "$base"
rm -f .baton

# --- the placeholder scan runs over what the wave touched ---
write_constitution "true"
git add docs/baton/constitution.md
git commit -q -m "baton: constitution"

# A marker that predates --since, in a file nothing has touched since,
# is not this wave's business.
printf 'const old = 1; // TODO: from before the wave\n' > old.js
git add old.js
git commit -q -m "old work with a marker"
scan_base="$(git rev-parse HEAD)"

out="$("$GATE" --since "$scan_base")"
assert_contains "$out" "placeholder_hits=0" "a marker outside the wave's diff is not counted"

printf 'export function renew() { /* TODO: finish */ }\n' > new.js
git add new.js
git commit -q -m "wave work with a marker"
out="$("$GATE" --since "$scan_base")"
assert_contains "$out" "placeholder_hits=1" "a marker in a file the wave touched is counted"
assert_contains "$out" "placeholder_files=new.js" "the evidence names the file the marker is in"
assert_contains "$out" "changed_files=1" "the evidence counts the files considered"

# An uncommitted file is the most common shape of in-flight work and must
# be seen -- baton-observe already reports it, this must not filter it out.
printf 'const x = 1; // FIXME\n' > uncommitted.js
out="$("$GATE" --since "$scan_base")"
assert_contains "$out" "placeholder_hits=2" "an uncommitted file is scanned too"
rm -f uncommitted.js

# baton's own files are excluded: a journal entry describing a TODO, or a
# gate verdict quoting one, is prose about the work, not a stub in it.
mkdir -p docs/baton/journal
printf 'A decision about the TODO markers we allow.\n' > docs/baton/journal/0001-note.md
out="$("$GATE" --since "$scan_base")"
assert_contains "$out" "placeholder_hits=1" "docs/baton/ is excluded from the scan"
rm -f docs/baton/journal/0001-note.md

# An empty pattern list means no scan, not a pattern that matches
# everything: grep -E '' matches every line.
write_constitution "true" ""
out="$("$GATE" --since "$scan_base")"
assert_contains "$out" "placeholder_hits=0" "an empty placeholder_patterns scans nothing rather than matching everything"

# --- invoked from a subdirectory, same answer ---
write_constitution "true"
mkdir -p deep/nested
out_root="$("$GATE" --since "$scan_base")"
out_deep="$(cd deep/nested && "$GATE" --since "$scan_base")"
assert_equals "$out_deep" "$out_root" "invoked from a subdirectory it reports the same evidence"

finish
