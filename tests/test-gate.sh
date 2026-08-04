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

# Build a copy of baton-gate beside a baton-observe shim whose body is $1,
# under observe-shim/. baton-gate resolves its siblings from its own
# directory, so this is the only way to make baton-observe misbehave
# without touching the real one -- and both of the gate's calls to it are
# guarded paths that nothing else here can reach. The shim gets $REAL so it
# can delegate for the calls it does not want to break.
make_observe_shim() {
    rm -rf observe-shim
    mkdir -p observe-shim
    cp "$GATE" observe-shim/baton-gate
    {
        printf '#!/usr/bin/env bash\n'
        printf 'REAL="%s"\n' "$REPO_ROOT/plugins/baton/scripts/baton-observe"
        printf '%s\n' "$1"
    } > observe-shim/baton-observe
    chmod +x observe-shim/baton-gate observe-shim/baton-observe
}

make_fixture_repo

# .baton/ gitignored before anything else happens, as /baton:init writes it
# into a real repository and as the cold-start fixtures build it. The gate
# writes .baton/gate-verify.log on every run, so without this the tree is
# dirty from the first invocation onwards and the tree_clean assertions at
# the bottom of this file would be reporting on the gate's own scratch
# output rather than on the wave's work. make_fixture_repo is shared with
# every other test file and is deliberately not changed for this.
printf '.baton/\n' > .gitignore
git add .gitignore
git commit -q -m "baton: gitignore .baton/"
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
out="$("$GATE" --since "$base" || true)"
assert_contains "$out" "verify_exit=0" "a green verify_cmd reports verify_exit=0"
assert_contains "$out" "verify_cmd=true" "the evidence names the command that was run"
assert_exit_code 0 "a green verify_cmd exits 0" "$GATE" --since "$base"

write_constitution "false"
out="$("$GATE" --since "$base" || true)"
assert_equals "$(gate_field "$out" verify_exit)" "1" "a red verify_cmd reports its exit code, exactly (not merely a string that contains it)"
assert_exit_code 0 "a RED verify_cmd still exits 0 -- the script reports, it does not judge" \
    "$GATE" --since "$base"

# The guard consults bash's own command -v, so the run has to be bash too --
# under /bin/sh-as-dash (Debian, Ubuntu) this bashism would otherwise report
# verify_exit=127, a command that was never found, arriving dressed as a
# suite that failed.
write_constitution "[[ 1 == 1 ]]"
out="$("$GATE" --since "$base" || true)"
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
out="$("$GATE" --since "$base" || true)"
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
empty_verify_stderr="$("$GATE" --since "$base" 2>&1 >/dev/null || true || true)"
assert_contains "$empty_verify_stderr" "verify_cmd is empty" \
    "the empty refusal names itself, distinct from the not-runnable refusal below"

write_constitution "definitely-not-a-real-command-9d3f"
assert_exit_code 4 "refuses a verify_cmd whose command does not exist" "$GATE" --since "$base"

# "CI=1 npm test" names npm, not CI=1 -- an env-var prefix is the ordinary
# shape of a test command, and exit 4 means stop the run, so refusing this
# would halt overnight work over nothing.
write_constitution "CI=1 true"
out="$("$GATE" --since "$base" || true)"
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
# The message, not just the code: the log-write guard a few lines below the
# mkdir guard in the script also returns 4, so deleting the mkdir guard
# entirely leaves this exit-code assertion passing. Same trap as the empty
# verify_cmd and the not-runnable one, and the same escape -- the two
# messages differ, so one of them can be asserted.
baton_file_stderr="$("$GATE" --since "$base" 2>&1 >/dev/null || true || true)"
assert_contains "$baton_file_stderr" "cannot create .baton/" \
    "the refusal names the directory it could not create, distinct from the log-write refusal that shares its exit code"
rm -f .baton

# fm_field takes the first matching line and no more. A constitution with
# the same key twice is malformed, but it is malformed in a way nothing
# here refuses, so the question is only which value wins -- and without
# head -1 sed emits both, the two glue into one string across a newline,
# and what reaches `command -v` is a word that was never written in the
# file. The first value winning is also what makes the `|| true` on that
# pipeline necessary: sed keeps writing after head has taken its line and
# exited, and the SIGPIPE status would otherwise abort the script.
write_constitution "true"
cat > docs/baton/constitution.md <<'EOF'
---
schema: baton/constitution/v1
run_id: gate-fixture
status: ratified
verify_cmd: "true"
verify_cmd: "false"
placeholder_patterns: "TODO|FIXME"
---
# Gate fixture
EOF
dup_out="$("$GATE" --since "$base" 2>/dev/null || true || true)"
assert_equals "$(gate_field "$dup_out" verify_cmd)" "true" \
    "a key repeated in the frontmatter takes its first value, not both glued across a newline"
assert_equals "$(gate_field "$dup_out" verify_exit)" "0" \
    "...and the command that actually ran is that first one"

# Two defects, and the constitution-syntax one is reported first. Exit 3 is
# "this file is not fit to gate against" and exit 4 is "the gate could not
# gather evidence from it"; reported the other way round the human fixes
# verify_cmd, reruns, and only then learns placeholder_patterns is missing,
# paying two round trips for one reading of one file.
cat > docs/baton/constitution.md <<'EOF'
---
schema: baton/constitution/v1
run_id: gate-fixture
status: ratified
verify_cmd: "definitely-not-a-real-command-9d3f"
---
# Gate fixture
EOF
both_stderr="$("$GATE" --since "$base" 2>&1 >/dev/null || true || true)"
assert_exit_code 3 "a constitution both missing placeholder_patterns and naming an unrunnable verify_cmd is exit 3, the constitution defect, not exit 4" \
    "$GATE" --since "$base"
assert_contains "$both_stderr" "placeholder_patterns is not set" \
    "and it is the missing field that gets named, so one run reports the defect that has to be fixed first"

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

out="$("$GATE" --since "$scan_base" || true)"
assert_contains "$out" "placeholder_hits=0" "a marker outside the wave's diff is not counted"

printf 'export function renew() { /* TODO: finish */ }\n' > new.js
git add new.js
git commit -q -m "wave work with a marker"
out="$("$GATE" --since "$scan_base" || true)"
assert_contains "$out" "placeholder_hits=1" "a marker in a file the wave touched is counted"
assert_contains "$out" "placeholder_files=new.js" "the evidence names the file the marker is in"
assert_contains "$out" "changed_files=1" "the evidence counts the files considered"

# An uncommitted file is the most common shape of in-flight work and must
# be seen -- baton-observe already reports it, this must not filter it out.
printf 'const x = 1; // FIXME\n' > uncommitted.js
out="$("$GATE" --since "$scan_base" || true)"
assert_contains "$out" "placeholder_hits=2" "an uncommitted file is scanned too"
# The exact joined list, not just the count: baton-observe's
# --changed-since pipes the committed diff and the untracked-file list
# through `sort -u`, so the order is alphabetical across both sources
# together, not "committed first" -- confirmed by running baton-observe
# directly rather than assumed, since a guess here would just as easily
# have passed against either order.
assert_contains "$out" "placeholder_files=new.js,uncommitted.js" \
    "placeholder_files is the comma-joined list in baton-observe's own (sorted) order, not just a count"

# The verdict file quotes this block verbatim, so the key order is part of
# what a human reads, not an implementation detail -- checked as a
# sequence, not merely that each key is present somewhere in the output.
key_order="$(printf '%s\n' "$out" | sed -n 's/^\([a-z_]*\)=.*/\1/p' | paste -sd, -)"
assert_equals "$key_order" \
    "verify_cmd,verify_exit,verify_log,placeholder_patterns,placeholder_hits,placeholder_files,changed_files,since,sha,work_sha,tree_clean" \
    "the verdict's keys appear in exactly this order"
rm -f uncommitted.js

# baton's own files are excluded: a journal entry describing a TODO, or a
# gate verdict quoting one, is prose about the work, not a stub in it.
mkdir -p docs/baton/journal
printf 'A decision about the TODO markers we allow.\n' > docs/baton/journal/0001-note.md
out="$("$GATE" --since "$scan_base" || true)"
assert_contains "$out" "placeholder_hits=1" "docs/baton/ is excluded from the scan"
rm -f docs/baton/journal/0001-note.md

# An empty pattern list means no scan, not a pattern that matches
# everything: grep -E '' matches every line.
write_constitution "true" ""
out="$("$GATE" --since "$scan_base" || true)"
assert_contains "$out" "placeholder_hits=0" "an empty placeholder_patterns scans nothing rather than matching everything"

# ...and the block has to SAY the scan was switched off, because that zero
# and a real zero are the same three characters. A human who writes
# placeholder_patterns: "" gets placeholder_hits=0; so does a wave whose
# every changed file was read and found clean. The agent under /baton:auto
# reads the second as the placeholder half of a green gate and closes the
# wave -- unattended, with nobody to ask -- and reading the first the same
# way closes a wave over a scan that never ran.
#
# changed_files does not separate them: the loop counts a file before it
# consults the pattern, so a disabled scan still reports files considered.
# Verified against a constitution with an empty pattern list over a tree
# holding a real marker: changed_files=1, placeholder_hits=0, and nothing
# else in the block moved.
#
# Emitting the pattern list is what separates them, and it belongs in the
# verdict rather than in a second call the morning would have to know to
# make: the value that was scanned FOR is evidence about the scan in the
# same way the command that was run is evidence about the tests.
disabled_out="$("$GATE" --since "$scan_base" || true)"
write_constitution "true" "NOTHING-IN-THIS-FIXTURE-MATCHES-THIS"
clean_out="$("$GATE" --since "$scan_base" || true)"
assert_equals "$(gate_field "$clean_out" placeholder_hits)" "0" \
    "the control arm is a real scan that found nothing, so both arms report the same placeholder_hits"
# Presence is asserted separately from emptiness, because gate_field cannot
# tell them apart: an absent key and a key with an empty value both come
# back as the empty string, so the emptiness assertion below would pass
# against a script that never printed the key at all.
disabled_keys="$(printf '%s\n' "$disabled_out" | sed -n 's/^\([a-z_]*\)=.*/\1/p' | paste -sd, -)"
assert_contains "$disabled_keys" "placeholder_patterns" \
    "a disabled scan still emits the key rather than omitting it, which is what makes the empty value readable as an answer"
assert_equals "$(gate_field "$disabled_out" placeholder_patterns)" "" \
    "and its value is empty, so placeholder_hits=0 can be read as 'nothing was asked'"
assert_equals "$(gate_field "$clean_out" placeholder_patterns)" "NOTHING-IN-THIS-FIXTURE-MATCHES-THIS" \
    "a real scan reports the pattern it looked for, so the same zero can be read as 'asked, and found nothing'"

# The two halves of the evidence are gathered independently, and nothing
# here observed that: every placeholder assertion above runs under
# verify_cmd: "true". A scan loop beginning `[ "$verify_exit" = 0 ] ||
# continue` -- the plausible "why scan a wave that is already red"
# optimisation -- passes the entire suite while reporting
# placeholder_hits=0 over a tree holding a marker.
#
# A red gate still has to say everything else that is wrong with it. The
# morning reads one verdict; a second defect discovered only after the
# first is fixed costs another night, which is the whole cost this feature
# exists to avoid. A pattern of its own is used rather than the fixture's
# default, so this counts exactly the file below and not the markers
# earlier assertions left in the diff.
printf 'export function stub() { /* RED-SCAN-MARKER: not finished */ }\n' > red-stub.js
write_constitution "false" "RED-SCAN-MARKER"
red_out="$("$GATE" --since "$scan_base" 2>/dev/null || true || true)"
assert_equals "$(gate_field "$red_out" verify_exit)" "1" \
    "a red verify_cmd reports its exit code"
assert_equals "$(gate_field "$red_out" placeholder_hits)" "1" \
    "the placeholder scan runs even when verify_cmd is red -- the two halves of the evidence do not depend on each other"
assert_equals "$(gate_field "$red_out" placeholder_files)" "red-stub.js" \
    "and names the file, so one verdict carries both defects instead of hiding the second behind the first"
rm -f red-stub.js

# --- invoked from a subdirectory, same answer ---
write_constitution "true"
mkdir -p deep/nested
out_root="$("$GATE" --since "$scan_base" || true)"
out_deep="$(cd deep/nested && "$GATE" --since "$scan_base")"
assert_equals "$out_deep" "$out_root" "invoked from a subdirectory it reports the same evidence"

# The test above invokes $GATE by its absolute path ($GATE is set from
# $REPO_ROOT), so dirname "$0" is already absolute and the later
# `cd "$repo_root"` inside baton-gate cannot change what it means -- it
# proves the caller's cwd does not affect the answer, not that a relative
# $0 survives the cd. A relative invocation is the ordinary shape for a
# project's own vendored copy of the scripts, and is exactly the shape the
# script_dir fix (capturing $0's directory before the cd, not after) was
# for -- a fixture with the scripts vendored under it, invoked by a
# relative path from a subdirectory, is what actually exercises that fix.
mkdir -p vendor/baton/scripts
cp "$GATE" vendor/baton/scripts/baton-gate
cp "$REPO_ROOT/plugins/baton/scripts/baton-observe" vendor/baton/scripts/baton-observe
chmod +x vendor/baton/scripts/baton-gate vendor/baton/scripts/baton-observe
relative_base="$(git rev-parse HEAD)"
out_absolute="$("$GATE" --since "$relative_base" || true)"
# `|| true`, because the way this breaks is not a wrong answer but no
# answer: with dirname "$0" computed after the cd, the relative path is
# resolved against repo_root, baton-gate dies on its own `cd` with
# "No such file or directory", and under set -e the non-zero status of the
# command substitution takes this whole file down at this line -- the
# mutant is killed, but by a bare shell error, with the fifteen assertions
# below it never reaching the report. Swallowing the status turns that into
# one [FAIL] naming the property that was lost, against an empty actual.
out_relative="$(cd deep/nested && ../../vendor/baton/scripts/baton-gate --since "$relative_base" 2>/dev/null || true)"
assert_equals "$out_relative" "$out_absolute" \
    "invoked by a relative path from a subdirectory (a vendored copy of the scripts) it reports the same evidence too"
# Removed immediately: left in place, these untracked files (baton-gate's
# own source carries the literal word "TODO" in a comment) would be picked
# up by every later scan in this file and inflate placeholder_hits for
# tests that expect an exact count.
rm -rf vendor

# --- an invalid pattern is the gate unable to look, not a clean scan ---
# grep -Eq exits 2 on a pattern that does not compile; discarding that
# behind 2>/dev/null used to read as "no match", reporting a scan that
# never happened as placeholder_hits=0.
write_constitution "true" "TODO("
git add docs/baton/constitution.md
git commit -q -m "a placeholder_patterns that does not compile"
bad_ere_base="$(git rev-parse HEAD)"
printf 'TODO(alice)\n' > has-marker.js
git add has-marker.js
git commit -q -m "a file with a real marker, under a pattern that cannot compile"
bad_ere_stderr="$("$GATE" --since "$bad_ere_base" 2>&1 >/dev/null || true || true)"
assert_exit_code 4 "an invalid ERE is the gate unable to look, not a clean scan" "$GATE" --since "$bad_ere_base"
assert_contains "$bad_ere_stderr" "not a valid extended regular expression" \
    "the refusal names the pattern, distinct from the not-runnable and empty verify_cmd refusals"
rm -f has-marker.js

# A file the scan cannot read is the same class of failure, discovered per
# file instead of once for the whole pattern. Skipped as root for the same
# reason the .baton/ write-permission test above is: root ignores the mode
# bits, so the assertion would fail for the wrong reason.
if [ "$(id -u)" != "0" ]; then
    write_constitution "true"
    git add docs/baton/constitution.md
    git commit -q -m "a valid constitution again, for the unreadable-file check"
    unreadable_scan_base="$(git rev-parse HEAD)"
    printf 'TODO\n' > cannot-read.js
    chmod 000 cannot-read.js
    unreadable_scan_stderr="$("$GATE" --since "$unreadable_scan_base" 2>&1 >/dev/null || true)"
    assert_exit_code 4 "a file the scan cannot read is the gate unable to look, not a clean scan" "$GATE" --since "$unreadable_scan_base"
    assert_contains "$unreadable_scan_stderr" "could not scan cannot-read.js" \
        "the refusal names the unreadable file, distinct from the invalid-pattern refusal above"
    chmod 644 cannot-read.js
    rm -f cannot-read.js
else
    pass "(skipped as root) a file the scan cannot read is the gate failing, not a clean scan"
fi

# --- three inputs that used to scan nothing and say so with a green face ---

# A trailing comment after the closing quote is not part of the pattern --
# unquote only strips a leading quote when the matching trailing one is
# right there, so "TODO|FIXME" # markers we forbid used to become the
# pattern in full, quotes and comment included, which matched nothing.
mkdir -p docs/baton
cat > docs/baton/constitution.md <<'EOF'
---
schema: baton/constitution/v1
run_id: gate-fixture
status: ratified
verify_cmd: "true"
placeholder_patterns: "TODO|FIXME" # markers we forbid
---
# Gate fixture
EOF
git add docs/baton/constitution.md
git commit -q -m "a trailing comment after placeholder_patterns' closing quote"
comment_base="$(git rev-parse HEAD)"
assert_exit_code 3 "a trailing comment after placeholder_patterns' closing quote is refused, not read as the whole literal string" \
    "$GATE" --since "$comment_base"

# /baton:init's template always writes placeholder_patterns, so an absent
# field means someone removed it -- a different statement from writing it
# empty, which is the deliberate "scan nothing" case tested above.
cat > docs/baton/constitution.md <<'EOF'
---
schema: baton/constitution/v1
run_id: gate-fixture
status: ratified
verify_cmd: "true"
---
# Gate fixture
EOF
git add docs/baton/constitution.md
git commit -q -m "placeholder_patterns removed entirely"
absent_base="$(git rev-parse HEAD)"
absent_stderr="$("$GATE" --since "$absent_base" 2>&1 >/dev/null || true || true)"
assert_exit_code 3 "an absent placeholder_patterns is refused, distinct from a deliberately empty one" "$GATE" --since "$absent_base"
assert_contains "$absent_stderr" "placeholder_patterns is not set" \
    "the refusal says what to write if scanning nothing is what is meant"

# An absent verify_cmd is exit 4, not the 3 its neighbour above gets, and
# the header's exit table has to say which. fm_field hands back an empty
# string whether the field was written empty or never written at all, so
# this script genuinely cannot tell those two apart and does not pretend
# to -- it reports the one thing that is true of both, that there is
# nothing to run. The asymmetry with placeholder_patterns is deliberate:
# scanning nothing is a real choice a human might mean by writing that
# field empty, so absence is worth distinguishing there. There is no
# reading of an absent verify_cmd under which the gate has something to run.
cat > docs/baton/constitution.md <<'EOF'
---
schema: baton/constitution/v1
run_id: gate-fixture
status: ratified
placeholder_patterns: "TODO|FIXME"
---
# Gate fixture
EOF
git add docs/baton/constitution.md
git commit -q -m "verify_cmd removed entirely"
absent_verify_base="$(git rev-parse HEAD)"
assert_exit_code 4 "an absent verify_cmd is exit 4, the gate unable to gather -- not the exit 3 the constitution-syntax refusals use" \
    "$GATE" --since "$absent_verify_base"

# A CRLF line ending left a carriage return attached to the end of the
# extracted value, which defeated unquote's exact match on the trailing
# quote and made a well-formed pattern read as unusable.
printf -- '---\nschema: baton/constitution/v1\nrun_id: gate-fixture\nstatus: ratified\nverify_cmd: "true"\nplaceholder_patterns: "TODO|FIXME"\r\n---\n# Gate fixture\n' > docs/baton/constitution.md
git add docs/baton/constitution.md
git commit -q -m "a CRLF line ending on placeholder_patterns"
crlf_base="$(git rev-parse HEAD)"
printf 'TODO here\n' > crlf-marker.js
git add crlf-marker.js
git commit -q -m "wave work under the CRLF constitution"
crlf_out="$("$GATE" --since "$crlf_base" || true)"
assert_contains "$crlf_out" "placeholder_hits=1" "a CRLF line ending on placeholder_patterns does not defeat the scan"
rm -f crlf-marker.js

# The same defect one step earlier, and the shape an editor actually
# produces. A file written by a Windows editor has CRLF on EVERY line,
# including the opening ---, and the frontmatter extractor compares $0
# against "---" exactly -- "---\r" is not that, so infm is never set, no
# frontmatter is ever emitted, and the strip in fm_field is handed an empty
# buffer to strip a carriage return from. The constitution then reads as
# status 'unset' and the whole run is refused as unratified.
#
# Both shapes are pinned, but not because each kills a mutant the other
# misses -- that was checked, and it is not true. Narrow the extractor's
# strip to line 1, or remove it outright, and only THIS assertion goes red:
# a lone \r on a single value is caught downstream by fm_field's
# trailing-whitespace strip as well, so the partial shape above now has two
# fixes standing behind it and cannot discriminate between them. It is kept
# as a value-level regression pin, and because it is the shape a hand-edit
# or a bad merge leaves behind.
#
# This one is the shape an editor produces, and it is the only one that
# fails structurally rather than at the value: no frontmatter is found at
# all, so the constitution reads as unratified rather than as carrying a
# damaged pattern. Nothing above would have caught it.
#
# Written to disk and deliberately not committed, unlike every other
# constitution in this file. The gate reads the working file, so a commit
# would add nothing -- and it cannot be relied on to add nothing either:
# under core.autocrlf=input (a machine-local git setting, on by default
# nowhere and set globally on plenty of developer machines) `git add`
# normalises CRLF to LF, so this file and the partial-CRLF one above stage
# to byte-identical blobs and the commit fails with "no changes added".
# Whether that happens is a property of whoever is running the suite, which
# is not something this assertion should depend on.
printf -- '---\r\nschema: baton/constitution/v1\r\nrun_id: gate-fixture\r\nstatus: ratified\r\nverify_cmd: "true"\r\nplaceholder_patterns: "TODO|FIXME"\r\n---\r\n# Gate fixture\r\n' > docs/baton/constitution.md
all_crlf_base="$(git rev-parse HEAD)"
printf 'TODO here\n' > all-crlf-marker.js
git add all-crlf-marker.js
git commit -q -m "wave work under the all-CRLF constitution"
# `|| true` so a regression here reports as one [FAIL] naming the behaviour
# that broke. Without it the refusal this pins is a non-zero exit inside a
# command substitution, which under `set -e` takes the whole file down at
# this line -- every assertion below would stop running, and the diagnostic
# would be baton-gate's own stderr rather than anything saying which
# property was lost.
all_crlf_out="$("$GATE" --since "$all_crlf_base" 2>/dev/null || true || true)"
assert_contains "$all_crlf_out" "placeholder_hits=1" \
    "CRLF on every line, the --- delimiters included, is read rather than refused as an unratified constitution"
rm -f all-crlf-marker.js

# Trailing whitespace after a closing quote is not an unclosed quote. One
# trailing space -- invisible in every editor, surviving every copy-paste --
# used to be refused with "opens a quote it never closes", sending the
# reader hunting for a defect the file does not have. The quote is closed;
# what `s/^field: *//` does not strip is whitespace at the END of the value,
# which then defeated unquote's exact match on the trailing quote.
#
# Whitespace INSIDE the quotes is part of the value and has to survive,
# which is what the pattern here is chosen to prove rather than assert by
# assumption: "TODO $" matches a line ending in "TODO " and not one ending
# in "TODO", so a strip that reached past the closing quote would move the
# hit from one of the two files below to the other.
printf -- '---\nschema: baton/constitution/v1\nrun_id: gate-fixture\nstatus: ratified\nverify_cmd: "true" \nplaceholder_patterns: "TODO $" \n---\n# Gate fixture\n' > docs/baton/constitution.md
git add docs/baton/constitution.md
git commit -q -m "trailing whitespace after both closing quotes"
ws_base="$(git rev-parse HEAD)"
printf 'const a = 1; // TODO\n' > ws-no-space.js
printf 'const b = 2; // TODO \n' > ws-space.js
git add ws-no-space.js ws-space.js
git commit -q -m "wave work under the trailing-whitespace constitution"
ws_out="$("$GATE" --since "$ws_base" 2>/dev/null || true || true)"
assert_equals "$(gate_field "$ws_out" verify_exit)" "0" \
    "a trailing space after verify_cmd's closing quote is stripped, not read as a quote that was never closed"
assert_equals "$(gate_field "$ws_out" placeholder_files)" "ws-space.js" \
    "the space INSIDE placeholder_patterns' quotes survives the strip: the pattern matches only the line that ends in one"
rm -f ws-no-space.js ws-space.js

# --- baton-observe failing must not throw away a completed verify_cmd run ---

# --since is resolved to a SHA before baton-observe ever sees it, so a
# --since that also names a tracked path (ambiguous to a bare
# `git diff --name-only`) no longer reaches baton-observe as the ambiguous
# string at all.
write_constitution "true"
git add docs/baton/constitution.md
git commit -q -m "a valid constitution, for the ambiguous --since check"
git branch ambiguous-ref
mkdir -p ambiguous-ref
echo x > ambiguous-ref/f.txt
git add ambiguous-ref
git commit -q -m "a tracked path that shares its name with a ref"
resolved_ambiguous="$(git rev-parse ambiguous-ref^{commit})"
assert_exit_code 0 "a --since that is also a tracked path does not crash baton-observe" "$GATE" --since ambiguous-ref
ambiguous_out="$("$GATE" --since ambiguous-ref || true)"
assert_contains "$ambiguous_out" "since=$resolved_ambiguous" \
    "the verdict's since= holds the resolved SHA, not the ambiguous ref name baton-observe would choke on"

# --- a path git C-quotes is refused, not silently dropped from the count ---

# core.quotePath=false (set in baton-observe) only unquotes non-ASCII
# bytes; a backslash, a literal quote or a control character in a path
# still comes back C-quoted, and `[ -f "$f" ]` on that literal quoted
# string used to fail silently, undercounting both placeholder_hits and
# changed_files in the direction of a greener gate. HEAD is already a
# valid ratified constitution from the ambiguous-ref check above, so it is
# reused as the base rather than recommitted -- write_constitution "true"
# would stage nothing, since the content would be byte-identical to what
# is already committed, and `git commit` with nothing staged fails.
quoted_base="$(git rev-parse HEAD)"
printf 'TODO backslash\n' > 'back\slash.js'
quoted_stderr="$("$GATE" --since "$quoted_base" 2>&1 >/dev/null || true || true)"
assert_exit_code 4 "a git-C-quoted path (one containing a backslash) is refused, not silently dropped from the scan" \
    "$GATE" --since "$quoted_base"
# git's C-quoting escapes the backslash itself, so the path this refusal
# names is "back\\slash.js" (two backslashes) -- the file on disk is
# named with one, git's quoted rendering of it doubles the escape.
assert_contains "$quoted_stderr" 'cannot scan "back\\slash.js"' \
    "the refusal names the quoted path, not a garbled or silently-skipped one"
rm -f 'back\slash.js'

# --- sha and work_sha, read from baton-observe rather than recomputed ---

# A checkpoint commit that touches only docs/baton/ moves HEAD without
# moving the work -- sha and work_sha must diverge across exactly that
# commit, or the next wave's --since would resolve from the wrong point.
# HEAD is already a valid ratified constitution (reused for the same
# reason as the quoted-path check above), so it is used directly as the
# base rather than recommitted.
sha_check_base="$(git rev-parse HEAD)"
printf 'export const y = 1;\n' > sha-work.js
git add sha-work.js
git commit -q -m "real work"
real_work_sha="$(git rev-parse HEAD)"
mkdir -p docs/baton/journal
printf 'checkpoint note\n' > docs/baton/journal/sha-check.md
git add docs/baton/journal/sha-check.md
git commit -q -m "baton: a checkpoint-only commit"
head_after_checkpoint="$(git rev-parse HEAD)"
sha_out="$("$GATE" --since "$sha_check_base" || true)"
assert_contains "$sha_out" "sha=$head_after_checkpoint" "sha is HEAD, the tree verify_cmd actually ran against"
assert_contains "$sha_out" "work_sha=$real_work_sha" "work_sha is the last commit outside docs/baton/, not HEAD -- they differ across a checkpoint commit"
rm -f docs/baton/journal/sha-check.md sha-work.js

# --- tree_clean travels with the evidence ---

# A verdict filed against a dirty tree is a verdict about something that was
# never committed, so the agent needs this fact in the same breath as the
# rest, not from a second call.
#
# The tree is settled by naming the four paths this file left deleted, not
# with `git add -A`. -A would also commit .baton/gate-verify.log -- the
# gate's own output, written by every run above this line. Committed once,
# it makes tree_clean=true below depend on the next run's verify_cmd
# happening to write the same bytes: today's `true` writes an empty log and
# the assertion passes by luck, and the first verify_cmd here that prints
# anything would turn this into a failure about the fixture rather than
# about the gate. .baton/ is gitignored at the top of this file instead,
# which is what /baton:init writes into a real repository.
git commit -q -m "settle the tree" -- \
    all-crlf-marker.js crlf-marker.js docs/baton/journal/sha-check.md \
    has-marker.js sha-work.js ws-no-space.js ws-space.js
out="$("$GATE" --since "$scan_base" || true)"
assert_contains "$out" "tree_clean=true" "reports a clean tree"
printf 'scratch\n' > scratch.txt
out="$("$GATE" --since "$scan_base" || true)"
assert_contains "$out" "tree_clean=false" "reports a dirty tree"
rm -f scratch.txt

# Where tree_clean comes from, not merely what it says. Swapping the read
# off baton-observe for a plain `git status --porcelain` here passes both
# assertions above, and the comment in the script defends three properties
# none of which they touch. This is the one that bites: with
# status.showUntrackedFiles=no set in the repository, a bare
# `git status --porcelain` reports a clean tree over a directory of
# uncommitted work. baton-observe passes -uall, which overrides it -- the
# exact failure the script's comment says has hidden a dirty tree from this
# suite before.
git config status.showUntrackedFiles no
printf 'export const invisible = 1;\n' > hidden-work.js
hidden_out="$("$GATE" --since "$scan_base" || true)"
assert_contains "$hidden_out" "tree_clean=false" \
    "a repository configured to hide untracked files still reports a dirty tree -- tree_clean comes from baton-observe's -uall, not from a bare git status"
rm -f hidden-work.js
git config --unset status.showUntrackedFiles

# changed_files is its own number. Two mutants lived here: printing
# $placeholder_hits in its place, and moving the increment below the
# empty-pattern check. Both survived because the one assertion covering
# changed_files was taken where it happened to equal placeholder_hits.
# A fresh base is taken so the count is exactly the two files below --
# the constitution is modified too, and excluded, which is what makes the
# expected number 2 rather than 3.
cf_base="$(git rev-parse HEAD)"
printf 'export const counted_one = 1; // CF-MARKER\n' > cf-one.js
printf 'export const counted_two = 2;\n' > cf-two.js
write_constitution "true" "CF-MARKER"
cf_out="$("$GATE" --since "$cf_base" 2>/dev/null || true || true)"
assert_equals "$(gate_field "$cf_out" changed_files)" "2" \
    "changed_files counts every file considered, not the ones that matched"
assert_equals "$(gate_field "$cf_out" placeholder_hits)" "1" \
    "...and differs from placeholder_hits in the same run, so one cannot stand in for the other"

# The second mutant, and the claim this file states as verified fact in the
# comment on the disabled scan above: the loop counts a file before it
# consults the pattern, so switching the scan off does not switch off the
# count.
write_constitution "true" ""
cf_off_out="$("$GATE" --since "$cf_base" 2>/dev/null || true || true)"
assert_equals "$(gate_field "$cf_off_out" changed_files)" "2" \
    "a switched-off scan still counts the files it was handed -- the count happens before the pattern is consulted"
assert_equals "$(gate_field "$cf_off_out" placeholder_hits)" "0" \
    "...while reporting no hits, which is what leaves changed_files able to say whether the wave touched anything at all"
rm -f cf-one.js cf-two.js

# The .baton/ scan exclusion, in the shape it exists for. In this fixture it
# is unreachable -- .gitignore keeps the log out of the changed set
# entirely -- so deleting the exclusion passes the suite. Drop the ignore
# line and the log becomes an ordinary untracked file the scan is handed,
# and a verify_cmd that prints a marker into it makes the exclusion the
# only thing standing between the gate and counting its own output as the
# wave's work.
printf '# the .baton/ line is gone\n' > .gitignore
write_constitution "echo LOGMARKER-DO-NOT-COUNT" "LOGMARKER-DO-NOT-COUNT"
nolog_out="$("$GATE" --since "$cf_base" 2>/dev/null || true || true)"
assert_equals "$(gate_field "$nolog_out" placeholder_hits)" "0" \
    "the gate's own verify log is never scanned, even where .gitignore no longer hides it and it holds a matching marker"
assert_contains "$nolog_out" "tree_clean=false" \
    "...though the tree does go dirty, the log being a real untracked file -- which is what the .gitignore line exists to prevent, and what the header now says"
printf '.baton/\n' > .gitignore
git checkout -q -- .gitignore 2>/dev/null || printf '.baton/\n' > .gitignore

# --- the facts are read before the changed set, not after ---

# Both come from baton-observe, in two calls, and anything landing between
# them lands between the sha the verdict names and the tree the scan looked
# at. With the facts read second, a commit arriving in that window puts a
# sha in the verdict that the scan never saw -- a verdict about two
# different trees, presented as one. With the facts read first, the same
# commit only makes the scan cover MORE than sha claims, which is the
# direction that fails safe.
#
# Made deterministic rather than raced against a ~50ms window: baton-gate
# resolves baton-observe from its own directory, so a vendored copy of the
# gate sitting next to a shim that lands a commit immediately after
# answering --changed-since reproduces that window exactly, every run, with
# no sleep and nothing to flake.
mkdir -p shim/scripts
cp "$GATE" shim/scripts/baton-gate
cat > shim/scripts/baton-observe <<EOF
#!/usr/bin/env bash
# Answers --changed-since truthfully, then lands a commit before returning,
# so whatever baton-gate asks for next sees a HEAD the scan never looked at.
if [ "\$1" = "--changed-since" ]; then
    out="\$("$REPO_ROOT/plugins/baton/scripts/baton-observe" "\$@")"
    printf 'export const late = 1;\n' > late.js
    git add late.js
    git commit -q -m "landed between the two baton-observe calls"
    printf '%s\n' "\$out"
    exit 0
fi
exec "$REPO_ROOT/plugins/baton/scripts/baton-observe" "\$@"
EOF
chmod +x shim/scripts/baton-gate shim/scripts/baton-observe
order_base="$(git rev-parse HEAD)"
order_out="$(shim/scripts/baton-gate --since "$order_base")"
assert_equals "$(gate_field "$order_out" sha)" "$order_base" \
    "the facts are read before the changed set, so a commit landing between the two baton-observe calls cannot put a sha in the verdict that the scan never looked at"
# Removed for the same reason the vendored copy above was: baton-gate's own
# source carries the literal word TODO in a comment, and left in place these
# would inflate every later scan. late.js stays -- it is committed, holds no
# marker, and deleting it would only leave another deletion to settle.
rm -rf shim

# --- baton-observe failing is the gate unable to gather, not a green gate ---

# Both calls to baton-observe are guarded, and replacing either guard with
# `|| true` used to pass every assertion in this file. The
# exit-4-on-observe-failure row is written into this script's header table
# and into baton-autopilot's, so it was a contract with nothing standing
# behind it -- and what it fails into is the worst shape available: sha,
# work_sha and tree_clean all empty, beside verify_exit=0 and
# placeholder_hits=0, at exit 0. An agent running unattended reads that as
# the green gate it looks like and closes the wave.

# The facts call is the first of the two, so a shim that always fails is
# caught there and the message has to say so.
make_observe_shim 'echo "observe: exploded" >&2; exit 9'
observe_fail_stderr="$(observe-shim/baton-gate --since "$scan_base" 2>&1 >/dev/null || true)"
assert_exit_code 4 "a baton-observe that fails on the facts call is exit 4, not a verdict" \
    observe-shim/baton-gate --since "$scan_base"
assert_contains "$observe_fail_stderr" "could not report the repository's current state" \
    "the refusal names which of the two calls failed"

# The changed-set call is reached only once the facts call has succeeded,
# so its guard needs a shim that fails selectively or it is never exercised
# at all -- an always-failing shim would exit at the first call and leave
# this second guard exactly as untested as it was.
make_observe_shim 'if [ "$1" = "--changed-since" ]; then echo "observe: exploded" >&2; exit 9; fi; exec "$REAL" "$@"'
changed_fail_stderr="$(observe-shim/baton-gate --since "$scan_base" 2>&1 >/dev/null || true)"
assert_exit_code 4 "a baton-observe that fails on the changed-set call is exit 4 too" \
    observe-shim/baton-gate --since "$scan_base"
assert_contains "$changed_fail_stderr" "could not report what changed since" \
    "and that refusal names the other call, so the two are told apart in the message"

# The nastier shape, which no `||` guard can catch: exit 0 with no output.
# The status is zero, so both guards are satisfied, and every fact parses
# to empty while the block still reads verify_exit=0, placeholder_hits=0
# and exit 0. sha cannot carry this check -- an empty sha is pinned as
# CORRECT for an unborn HEAD a few assertions below, so the one
# distinguishing signal is already spoken for. tree_clean can: baton-observe
# prints it as exactly true or false on every success, including on that
# unborn HEAD, where sha and work_sha are legitimately empty and it is not.
make_observe_shim 'exit 0'
silent_stderr="$(observe-shim/baton-gate --since "$scan_base" 2>&1 >/dev/null || true)"
assert_exit_code 4 "a baton-observe that exits 0 printing nothing is exit 4, not a green block assembled from empty facts" \
    observe-shim/baton-gate --since "$scan_base"
assert_contains "$silent_stderr" "returned no usable state" \
    "the refusal says the facts were unusable, rather than reporting them as facts"
rm -rf observe-shim

# --- not a git repository ---
# The exit code the header table spends on this has never been asserted; a
# subshell cd is used rather than `env -C`, which BSD env does not have.
outside="$(mktemp -d)"
rc=0
( cd "$outside" && "$GATE" --since "$scan_base" ) >/dev/null 2>&1 || rc=$?
assert_equals "$rc" "1" "refuses to run outside a git repository"
rm -rf "$outside"

# --- a bare repository ---
# Deliberately left as it is rather than given a baton-gate: prefix. It is
# the only exit path without one, and the header's catch-all row already
# covers it: `git rev-parse --show-toplevel` fails with its own message,
# and the assignment is kept separate from the cd precisely so that failure
# aborts with git's text intact. Giving it a prefix would mean either
# widening exit 1, which the table spends on "not a git repository" -- a
# bare repo IS one, it just has no work tree -- or minting a code for it,
# which is not a change to make in a review pass. What is worth pinning is
# that it stays a refusal: no key=value block, and a non-zero status, so it
# cannot drift into the green-looking exit 0 this whole round is about.
bare="$(mktemp -d)"
git init -q --bare "$bare/repo.git"
bare_rc=0
bare_out="$( ( cd "$bare/repo.git" && "$GATE" --since "$scan_base" ) 2>/dev/null )" || bare_rc=$?
assert_not_contains "$bare_out" "verify_exit=" \
    "a bare repository produces no evidence block -- whatever the code, it is not a verdict"
if [ "$bare_rc" -ne 0 ]; then
    pass "a bare repository is a refusal, not exit 0 (git's own code, $bare_rc, per the header's catch-all row)"
else
    fail "a bare repository is a refusal, not exit 0 (git's own code, $bare_rc, per the header's catch-all row)"
fi
rm -rf "$bare"

# --- an unborn HEAD reports empty, not the literal string "HEAD" ---

# `git rev-parse HEAD` prints its own argument straight back when it cannot
# resolve it, so before sha was taken from baton-observe (which guards with
# `rev-parse --verify -q`) an orphan branch wrote sha=HEAD into the verdict
# as though that were a commit. The fix landed with nothing pinning it,
# which is how it would come back. The orphan branch is checked out after
# real commits exist, since that is the only way a repository with history
# reaches an unborn HEAD -- and --since still resolves through it, the
# commit it names being an object in the repository whether or not anything
# currently points at it. This goes last: every assertion above it needs a
# HEAD.
git checkout -q --orphan unborn
orphan_out="$("$GATE" --since "$scan_base" || true)"
assert_equals "$(gate_field "$orphan_out" sha)" "" \
    "an unborn HEAD reports sha= empty, not the literal string HEAD dressed as a commit"
assert_equals "$(gate_field "$orphan_out" work_sha)" "" \
    "an unborn HEAD reports work_sha= empty too"

finish
