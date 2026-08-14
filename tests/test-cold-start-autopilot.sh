#!/usr/bin/env bash
# Pins the premise of the autopilot fixture (tests/fixtures/cold-start/
# build-autopilot.sh): a run handed over, with one wave blocked and two
# waves left, exactly one of which is available. What a resuming agent
# does with that -- take the available wave, leave the other alone,
# continue without asking -- is RUNBOOK.md's fourth scenario, run by a
# human. What is checked here is the premise: that the fixture really does
# contain one available wave and one that is excluded only by the
# consumes/produces rule, not also by an empty spec cell -- availability has
# a fourth rule now (a `spec` cell that is not `—`), and this fixture's whole
# point collapses if it silently leaves that rule unmet, the way a spec-less
# fixture briefly did on this branch. So it cannot rot into a fixture where
# the easy rule suffices, or one where no wave is available at all.
#
# The assertions below extract fields per wave and per table row, not
# substrings anywhere in the file. A file-wide `assert_contains
# "produces: [session-contract]"` still passes if that line moved to a
# different wave -- the fixture would rot into one where the graph rule
# alone suffices, silently, with every assertion still green. Extracting
# wave 2's own produces: and wave 3's own consumes: is what makes the
# fixture's shape, not just its vocabulary, load-bearing. The same applies to
# each wave's own spec cell, read from its own table row below.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PLUGIN="$REPO_ROOT/plugins/baton"
. "$SCRIPT_DIR/helpers.sh"

FIXTURE="$(mktemp -d)"
bash "$SCRIPT_DIR/fixtures/cold-start/build-autopilot.sh" "$FIXTURE" >/dev/null
cd "$FIXTURE"

state="$(cat docs/baton/state.md)"
constitution="$(cat docs/baton/constitution.md)"

# Field <name>: from wave <n>'s own block in the constitution, not the file
# as a whole. Relies on a blank line following every wave block -- unlike
# the other three cold-start fixtures, whose constitutions have no blank
# lines between waves, this one's does, on purpose: without it, this range
# either stops at the wrong place or (for the last wave) never stops until
# EOF. Confirmed by hand against the built fixture, not just by reading.
wave_field() {
    sed -n "/^- wave: $1\$/,/^\$/p" docs/baton/constitution.md | sed -n "s/^  $2: *//p"
}

# Column <n> (1-based, matching the Waves table header) of table row
# "| <wave> | ... |". awk -F'|' on a row starting with "| " produces an
# empty $1 for the text before the first pipe, so column n is $(n+1).
row_field() {
    printf '%s\n' "$1" | awk -F'|' -v n="$(($2 + 1))" '{gsub(/^[ \t]+|[ \t]+$/,"",$n); print $n}'
}
wave_row() {
    printf '%s\n' "$state" | grep -E "^\| $1 \|"
}

assert_contains "$constitution" "status: ratified" "the autopilot fixture's constitution is ratified"
assert_not_contains "$constitution" "REPLACE-WITH" "the autopilot fixture's constitution has no unfilled placeholders"

# The grant, and the entry it points at. A flag with a dangling grant is
# a fixture that tests nothing about how the grant is recorded.
assert_contains "$state" "autopilot: all" "the fixture is on the autopilot"
grant="$(sed -n 's/^autopilot_grant: *//p' docs/baton/state.md | head -1)"
assert_equals "$grant" "DEC-0001" "the fixture names the entry that granted autonomy"
assert_file_exists "docs/baton/journal/0001-autopilot-grant.md" "the granting entry exists"
grant_entry="$(cat docs/baton/journal/0001-autopilot-grant.md)"
assert_contains "$grant_entry" "type: autopilot" "the granting entry is typed as the grant"
assert_contains "$grant_entry" "base: —" \
    "the grant records base: in its own frontmatter, which is the only place baton-autopilot reads it from"

# Wave 1: closed, and closed under the autopilot -- its row's status and
# gate columns, read by column position, not by hoping the right words
# appear somewhere in the file. A row that regressed to todo, or to a gate
# nothing produced, is exactly what these two catch.
row1="$(wave_row 1)"
assert_equals "$(row_field "$row1" 3)" "done" "wave 1's status is done"
assert_equals "$(row_field "$row1" 7)" "auto" "wave 1's gate reads auto, matching the verdict file below"

# Rule 4 does not gate a done or blocked wave's availability -- only a todo
# wave's -- but a done wave that already closed, or a blocked wave that
# reached three attempts, could not have been started under this rule with
# an empty spec cell either. A fixture that left either — would model a
# state the autopilot could never actually have reached, not just a state
# this test fails to check.
spec1="$(row_field "$row1" 4)"
if [ -n "$spec1" ] && [ "$spec1" != "—" ]; then
    pass "wave 1 has a real spec cell -- consistent with a wave that was actually started"
else
    fail "wave 1 has a real spec cell -- consistent with a wave that was actually started"
    echo "    spec cell: $spec1"
fi

# gate: auto is a claim; the verdict file is the evidence for it. A row
# that says auto with no file behind it is a claim /baton:status and a
# resuming agent both have nothing to check it against.
wave1_sha="$(row_field "$row1" 6)"
gate_file="docs/baton/gates/wave-1-attempt-1-${wave1_sha}.md"
assert_file_exists "$gate_file" "wave 1's auto-gate verdict file exists, named after its own closed_at_sha"
gate_content="$(cat "$gate_file" 2>/dev/null || true)"
assert_contains "$gate_content" "verdict: auto" "the verdict file records an autopilot verdict, not a human one"
assert_contains "$gate_content" "wave: 1" "the verdict file is filed against wave 1"

# Wave 2: blocked, and the pat journaled -- but needs_human stays false.
# baton-autopilot's "The pat" is explicit that needs_human is the run-level
# stop flag, raised only when no wave is left to move to; wave 4 is still
# available here (see below), so a correctly-behaving run carries on
# without it. A fixture that raised it here would be pinning the wrong
# scenario: a run that had to stop, not one that didn't.
row2="$(wave_row 2)"
assert_equals "$(row_field "$row2" 3)" "blocked" "wave 2's status is blocked"
assert_contains "$state" "needs_human: false" \
    "needs_human stays false -- wave 4 remains available, so the run is not the run-level stop this flag is for"
spec2="$(row_field "$row2" 4)"
if [ -n "$spec2" ] && [ "$spec2" != "—" ]; then
    pass "wave 2 has a real spec cell -- it reached three attempts, which rule 4 could not have allowed with an empty one"
else
    fail "wave 2 has a real spec cell -- it reached three attempts, which rule 4 could not have allowed with an empty one"
    echo "    spec cell: $spec2"
fi
assert_file_exists "docs/baton/journal/0002-wave2-blocked.md" "the pat on wave 2 is journaled"
blocked_entry="$(cat docs/baton/journal/0002-wave2-blocked.md)"
assert_contains "$blocked_entry" "type: blocked" "the pat entry is typed as a block"
assert_not_contains "$blocked_entry" "needs_human" \
    "the pat entry carries no needs_human of its own -- that field belongs to state.md's grant, not any entry's envelope"
assert_contains "$state" "attempt 3 of 3" \
    "the In flight line keeps the attempt count -- the ceiling that caused the pat, not just that a pat happened"
assert_contains "$state" "evidence unchanged" \
    "the In flight line keeps why the ceiling was reached, not only that it was"

# Wave 3: excluded ONLY by the consumes/produces rule. Its own depends_on
# does not include the blocked wave, so a resuming agent applying just the
# graph rule would wrongly take it; what actually excludes it is that it
# consumes the contract wave 2 -- and only wave 2 -- was to produce. Each
# field is read from its own wave's block, so moving produces:/consumes:
# to the wrong wave (which a file-wide substring check cannot catch) fails
# here instead.
row3="$(wave_row 3)"
assert_equals "$(row_field "$row3" 3)" "todo" \
    "wave 3's status is todo, not blocked or done -- rule 1 alone would not exclude it either"
produces2="$(wave_field 2 produces)"
assert_equals "$produces2" "[session-contract]" "wave 2 -- the blocked wave -- is the one that publishes the contract"
consumes3="$(wave_field 3 consumes)"
assert_equals "$consumes3" "[session-contract]" \
    "wave 3 consumes the contract wave 2 was to publish -- this, not depends_on, is what excludes it"
deps3="$(wave_field 3 depends_on)"
assert_equals "$deps3" "[1]" "wave 3 does not depend on the blocked wave in the graph -- only through the contract"

# Rule 4: wave 3 has a real spec cell too, so it is excluded for the
# contract alone, not for a missing spec as well. A wave failing two rules
# at once no longer tells a reader which one this fixture is pinning.
spec3="$(row_field "$row3" 4)"
if [ -n "$spec3" ] && [ "$spec3" != "—" ]; then
    pass "wave 3 has a real spec cell -- it is unavailable for the contract alone, not for a missing spec too"
else
    fail "wave 3 has a real spec cell -- it is unavailable for the contract alone, not for a missing spec too"
    echo "    spec cell: $spec3"
fi

# Wave 4: the one genuinely available wave -- nothing blocked upstream in
# its depends_on, no contract of its own tying it to the blocked wave, and a
# real spec cell of its own. Without a real check of each, a mutation that
# gives it consumes: [session-contract], or resets its spec cell to —,
# would leave no wave available at all and this test would not notice.
row4="$(wave_row 4)"
assert_equals "$(row_field "$row4" 3)" "todo" "wave 4's status is todo"
deps4="$(wave_field 4 depends_on)"
assert_equals "$deps4" "[1]" "wave 4 depends only on the closed wave"
consumes4="$(wave_field 4 consumes)"
assert_equals "$consumes4" "" "wave 4 consumes nothing -- no contract ties it to the blocked wave either"

# Rule 4: wave 4's spec cell is real, so it is genuinely available under
# all four rules, not just the first three.
spec4="$(row_field "$row4" 4)"
if [ -n "$spec4" ] && [ "$spec4" != "—" ]; then
    pass "wave 4 has a real spec cell -- available under all four rules, not just the first three"
else
    fail "wave 4 has a real spec cell -- available under all four rules, not just the first three"
    echo "    spec cell: $spec4"
fi

# Next action states that a decision is needed without making it: no wave
# number, no mention of the contract that is the actual reason. A next
# action that named wave 4, or session-contract, would hand a resuming
# agent the answer this fixture exists to make it work out.
next="$(sed -n 's/^- \*\*Next action:\*\* *//p' docs/baton/state.md | head -1)"
assert_not_contains "$next" "wave 4" "Next action does not name which wave to take"
assert_not_contains "$next" "wave 3" "Next action does not single out wave 3 either"
assert_not_contains "$next" "session-contract" "Next action does not name the contract that excludes wave 3"

# No wave claims a verdict nothing produced. `pass` is no longer a value the
# gate column takes at all, which makes this a guard against a fixture
# reviving one the plugin no longer defines.
assert_not_contains "$state" "| pass |" "no autopilot-fixture wave claims a verdict no gate produced"

assert_contains "$(cat .gitignore 2>/dev/null || true)" ".baton/" \
    "the autopilot fixture gitignores .baton/ the way /baton:init leaves it"

cd /
rm -rf "$FIXTURE"
FIXTURE=""
finish
