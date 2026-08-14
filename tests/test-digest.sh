#!/usr/bin/env bash
# baton-digest prints what the file says, so that a human approving in chat
# approves the file rather than an agent's account of it. That is what these
# assertions have to pin, and it is not shape: every one of them names
# content this fixture and nothing else in this repository contains -- its
# own goal sentence, its own wave names, its own verify_cmd. A digest of
# some other constitution fails all of them, and a digest that paraphrased
# this one would fail them too.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DIGEST="$REPO_ROOT/plugins/baton/scripts/baton-digest"
. "$SCRIPT_DIR/helpers.sh"

# The verify_cmd is a parameter, and wave 1's spec is one for the same
# reason: the one scenario this script exists to serve is a substituted one,
# and the same fixture written twice, with only that value differing, is the
# only way to show the digest tracks the file instead of reciting something
# it was told once. Both values are the agent's to compose at /baton:init and
# nobody's to change afterwards, so both are values a swap has to be caught
# in.
#
# Two shapes below are deliberate and load-bearing, not decoration. The
# waves sit inside a ```yaml fence, as the real template writes them; and
# the EARS prose AFTER that fence carries a bulleted list whose items begin
# exactly like exit criteria do. A counter that stops at neither the fence
# nor the indent reports wave 2 with four criteria instead of one, and the
# assertion on that count below is what catches it.
#
# Wave 2's spec is the em dash the template gives a wave nobody has specified
# yet -- the value the autopilot refuses to take a wave on. It sits beside a
# wave that names a real document so that the two are digested in one run and
# can be told apart there.
write_constitution() {
    mkdir -p docs/baton
    cat > docs/baton/constitution.md <<EOF
---
schema: baton/constitution/v1
run_id: digest-fixture
status: ratified
verify_cmd: "${1-npm test -- --runInBand --reporters=summary}"
placeholder_patterns: "TODO|FIXME|NotImplementedYet"
workspace: worktree
---

# Digest fixture

## Goal

Ship the token exchange, with nothing left stubbed behind it.

## Non-negotiables

Never change the token format.
No network calls in the unit suite.

## Waves

\`\`\`yaml
- wave: 1
  name: exchange
  depends_on: []
  spec: ${2-docs/superpowers/specs/2026-08-14-token-exchange.md}
  exit_criteria:
    - The system shall exchange a code for a token
    - When the code has expired, the system shall refuse it

- wave: 2
  name: refresh
  depends_on: [1]
  spec: —
  exit_criteria:
    - When a token is refreshed, the system shall preserve its subject
\`\`\`

Exit criteria use EARS. Five patterns, "shall" is mandatory:

- The system shall \`<behaviour>\`
- When \`<trigger>\`, the system shall \`<behaviour>\`
- While \`<state>\`, the system shall \`<behaviour>\`
EOF
}

# write_state <suspect> <needs_human> <Suspect line> [wave 2 status]
write_state() {
    mkdir -p docs/baton
    cat > docs/baton/state.md <<EOF
---
schema: baton/state/v1
writer: digest-fixture
updated_at: 2026-08-14T09:00:00Z
observed_sha: $(git rev-parse HEAD)
observed_branch: main
tree_clean: true
suspect: $1
needs_human: $2
autopilot: off
---

# State

**Goal:** Ship the token exchange, with nothing left stubbed behind it.

## Waves

| # | name | status | plan | closed_at_sha | gate |
|---|------|--------|------|---------------|------|
| 1 | exchange | done | — | abc1234 | — |
| 2 | refresh | ${4-todo} | — | — | — |

## Now

- **Next action:** one deterministic sentence
- **In flight:** nothing
- **Suspect:** $3
- **Open questions:** none
EOF
}

# The line the digest prints directly under a wave's header line. Which wave
# a spec belongs to is half of what the digest has to get right, and no
# needle can pin it: assert_contains matches one line at a time, so a digest
# that printed wave 1's document under wave 2 would satisfy every needle in
# this file. awk rather than `grep -A1`, because a grep that finds nothing
# exits 1 and this script runs under `set -e`, where that is not a red
# assertion but a suite that stops mid-way looking green.
spec_line_under() {
    printf '%s\n' "$1" | awk -v want="$2" 'index($0, want) { getline; print; exit }'
}

make_fixture_repo

# --- usage ---
assert_exit_code 64 "refuses to run without an object" "$DIGEST"
assert_exit_code 64 "refuses an object it does not know" "$DIGEST" journal
assert_exit_code 64 "refuses two objects" "$DIGEST" constitution stop
assert_exit_code 64 "refuses a flag" "$DIGEST" --constitution

# --- the file has to be there, and the refusal has to name it ---
assert_exit_code 3 "refuses when there is no constitution" "$DIGEST" constitution
missing_stderr="$("$DIGEST" constitution 2>&1 >/dev/null || true)"
assert_contains "$missing_stderr" "docs/baton/constitution.md" \
    "the refusal names the path, so the reader knows which file to go and make"

assert_exit_code 3 "refuses when there is no state file" "$DIGEST" stop
missing_state_stderr="$("$DIGEST" stop 2>&1 >/dev/null || true)"
assert_contains "$missing_state_stderr" "docs/baton/state.md" \
    "the stop refusal names its path too"

# A file with no frontmatter at all is not a constitution to digest: printing
# a goal from its prose while silently reporting no verify_cmd would be a
# digest of half a file, wearing the face of a whole one.
mkdir -p docs/baton
printf '# A title and nothing else\n' > docs/baton/constitution.md
assert_exit_code 3 "refuses a constitution with no frontmatter" "$DIGEST" constitution

printf -- '---\nschema: baton/constitution/v1\nverify_cmd: "true"\n\n# never closed\n' \
    > docs/baton/constitution.md
assert_exit_code 3 "refuses a constitution whose frontmatter was never closed" "$DIGEST" constitution

# --- the constitution's own words ---
write_constitution
assert_exit_code 0 "digests a well-formed constitution" "$DIGEST" constitution
out="$("$DIGEST" constitution)"

assert_contains "$out" "Ship the token exchange, with nothing left stubbed behind it." \
    "the goal is the fixture's own sentence, not a summary of one"
assert_contains "$out" "Never change the token format." \
    "the non-negotiables are printed"
assert_contains "$out" "No network calls in the unit suite." \
    "every non-negotiable is printed, not just the first"

# The counts, not merely the names: a wave whose criteria are miscounted is
# a wave the reader believes they have read. Wave 2 is the discriminating
# one -- the EARS bullets in the prose below the fence are three more lines
# that begin like criteria and belong to no wave.
assert_contains "$out" "wave 1 — exchange (2 exit criteria)" \
    "wave 1 is named with the number of its exit criteria"
assert_contains "$out" "wave 2 — refresh (1 exit criterion)" \
    "wave 2 counts only its own criterion -- not the EARS bullets in the prose after the fence"

# The document each wave builds to, whole and under its own wave. Equality
# rather than containment: a spec cut short at the directory, folded into a
# sentence about the wave, or printed under the wrong one is exactly what
# ratifying off the digest has to catch, and every one of those still
# contains the path's first half.
assert_equals "$(spec_line_under "$out" "wave 1 — exchange")" \
    "    spec: docs/superpowers/specs/2026-08-14-token-exchange.md" \
    "wave 1 names the document it builds to, in full and under that wave"

# The em dash is a value, not a blank. The autopilot will not take a wave
# holding it, so a human ratifying the run is ratifying a wave that cannot
# start, and a digest that let that pass for a document -- or for nothing at
# all -- has hidden the one thing about that wave worth knowing.
assert_equals "$(spec_line_under "$out" "wave 2 — refresh")" \
    "    spec: — (nobody has named it yet, and the autopilot will not take a wave with none)" \
    "a wave whose spec is the em dash says so, and says what it costs"
assert_not_contains "$(spec_line_under "$out" "wave 2 — refresh")" "docs/superpowers/specs" \
    "and does not inherit the document the wave before it names"

assert_contains "$out" "verify_cmd: npm test -- --runInBand --reporters=summary" \
    "verify_cmd is printed whole, to its last flag"
assert_contains "$out" "placeholder_patterns: TODO|FIXME|NotImplementedYet" \
    "placeholder_patterns is printed as the file has it"
assert_contains "$out" "workspace: worktree" \
    "workspace is read from the file, not assumed to be the template's in-place"
assert_contains "$out" "Status: ratified" \
    "the status is printed, so nobody ratifies what is already ratified"

# A field the file does not carry -- the cold-start fixtures predate
# `workspace`, so this is not hypothetical. A bare `workspace:` with nothing
# after it reads as a value the eye skipped rather than one that is not
# there.
cat > docs/baton/constitution.md <<'EOF'
---
schema: baton/constitution/v1
status: draft
---

## Goal

Nothing declared but the schema.
EOF
sparse="$("$DIGEST" constitution)"
assert_contains "$sparse" "workspace: (not set)" \
    "a field the file does not carry says so, rather than trailing off after the colon"
assert_contains "$sparse" "verify_cmd: (not set)" \
    "and so does the one value the digest exists to make noticeable"
assert_contains "$sparse" "(the file declares no waves)" \
    "a constitution with no waves says that too"
assert_contains "$sparse" "(the file states none)" \
    "a missing section is reported as missing, not left out of the digest"

# A wave carrying no `spec:` key at all, which is what every constitution
# written before the field moved out of state.md looks like. Three states and
# not two: this one is a file that never knew about the field, the em dash
# above is a run saying nobody has decided yet, and neither may print as the
# other or as a wave that names a document.
#
# The wave above it names one, and that is the whole point of the fixture
# having two: a reader parsing per-wave values carries the last one it saw
# unless something clears it, so a wave with no key of its own is the wave
# that quietly borrows its neighbour's document. Nothing on the page would
# look wrong.
cat > docs/baton/constitution.md <<'EOF'
---
schema: baton/constitution/v1
status: draft
verify_cmd: "make check"
---

## Goal

Move every row across, and leave the old table where it stands.

## Waves

```yaml
- wave: 1
  name: migrate
  depends_on: []
  spec: docs/superpowers/specs/2026-08-14-row-migration.md
  exit_criteria:
    - The system shall copy every row to the new table

- wave: 2
  name: cutover
  depends_on: [1]
  exit_criteria:
    - When every row is copied, the system shall switch reads to the new table
```
EOF
no_spec="$("$DIGEST" constitution)"
assert_equals "$(spec_line_under "$no_spec" "wave 2 — cutover")" "    spec: (not set)" \
    "a wave that declares no spec at all says so in the words this digest uses for every field it did not find"
assert_not_contains "$(spec_line_under "$no_spec" "wave 2 — cutover")" "2026-08-14-row-migration" \
    "and does not borrow the document of the wave above it, which would read as a wave that named one"
assert_not_contains "$no_spec" "spec: —" \
    "nor is it reported as the em dash, which is a value a human wrote rather than a key nobody did"

# The runbook scenario this whole script feeds: a substituted verify_cmd has
# to be noticeable in the digest. Both directions are asserted, because
# "contains the new one" alone is also true of a digest that prints every
# verify_cmd it has ever seen.
write_constitution "true # the suite, honest"
swapped="$("$DIGEST" constitution)"
assert_contains "$swapped" "verify_cmd: true # the suite, honest" \
    "a substituted verify_cmd is what the digest prints"
assert_not_contains "$swapped" "npm test -- --runInBand" \
    "and the value it replaced is gone -- the digest reads the file each time"

# The same in the other value the agent composes and nobody may change
# afterwards. A wave quietly repointed at a document that asks less of it
# gets a plan, work and a spec-compliance review that all agree with each
# other and with nothing the human meant, and no gate has anything to say
# about it -- the digest is the only place that value is ever checked.
write_constitution "npm test" "docs/superpowers/specs/2026-08-14-a-shorter-brief.md"
respec="$("$DIGEST" constitution)"
assert_equals "$(spec_line_under "$respec" "wave 1 — exchange")" \
    "    spec: docs/superpowers/specs/2026-08-14-a-shorter-brief.md" \
    "a substituted spec is what the digest prints"
assert_not_contains "$respec" "2026-08-14-token-exchange" \
    "and the document it replaced is gone -- this value is read from the file too"

# Invoked from a subdirectory, the paths still resolve from the repository
# root. Without this the digest reads docs/baton/constitution.md relative to
# wherever the caller stood, which is nothing at all, and reports the
# constitution missing in a repository that has one.
write_constitution
mkdir -p sub/deeper
sub_out="$( cd sub/deeper && "$DIGEST" constitution )"
assert_contains "$sub_out" "Ship the token exchange, with nothing left stubbed behind it." \
    "a subdirectory invocation digests the same file, resolved from the repository root"
rm -rf sub

# --- stop: what is raised, and what is not ---
write_state false false "none"
assert_exit_code 0 "a run with nothing raised is exit 0 -- a finding, not a failure" "$DIGEST" stop
quiet="$("$DIGEST" stop)"
assert_contains "$quiet" "The run is waiting for nobody." \
    "with both flags down, the digest says so in as many words"
assert_not_contains "$quiet" "/baton:clear" \
    "and does not offer to lower a flag nobody raised"

write_state true false "wave 2 was claimed closed at a SHA no branch contains"
raised="$("$DIGEST" stop)"
assert_exit_code 0 "a raised flag is still exit 0 -- the script reports, it does not judge" "$DIGEST" stop
assert_contains "$raised" "Raised: suspect" \
    "the digest names which flag is up"
assert_contains "$raised" "wave 2 was claimed closed at a SHA no branch contains" \
    "and prints the Suspect line from state.md, in the words state.md uses"
assert_contains "$raised" "/baton:clear" \
    "a run waiting on a human names the command that releases it"

# Only the flag that is up. Two flags go up for different reasons, and a
# digest that mentioned the other one's evidence would invite lowering it
# alongside.
write_state false true "wave 2 was claimed closed at a SHA no branch contains"
human="$("$DIGEST" stop)"
assert_contains "$human" "Raised: needs_human" \
    "needs_human is named on its own"
assert_not_contains "$human" "wave 2 was claimed closed at a SHA no branch contains" \
    "the Suspect line stays out while suspect is down -- it is evidence for a flag nobody raised"

write_state true true "a claim diverged from the repository"
both="$("$DIGEST" stop)"
assert_contains "$both" "Raised: suspect, needs_human" \
    "both flags up are both named"

# A flag whose value is not true or false cannot be read, and the one
# reading that must never be reached for it is "down".
write_state maybe false "none"
assert_exit_code 3 "refuses a suspect that is neither true nor false" "$DIGEST" stop
unreadable="$("$DIGEST" stop 2>&1 >/dev/null || true)"
assert_contains "$unreadable" "suspect" \
    "the refusal names the field it could not read"

# --- a blocked wave, and what it waits on ---
# The status column says blocked; what it is blocked ON lives in the
# constitution's depends_on, which is why the digest reads both files.
write_constitution
write_state false false "none" "blocked"
blocked="$("$DIGEST" stop)"
assert_contains "$blocked" "wave 2 — refresh (depends_on: 1)" \
    "a blocked wave is named together with the wave it waits on"

# A state file blocked on a wave the constitution does not declare. The two
# files disagreeing about what the run consists of is the divergence baton
# exists to surface; reporting it as "depends_on: none declared" would read
# as a wave that simply waits on nothing.
write_state false false "none"
sed -i.bak 's/^| 2 | refresh | todo |/| 7 | ghost | blocked |/' docs/baton/state.md
rm -f docs/baton/state.md.bak
ghost="$("$DIGEST" stop)"
assert_contains "$ghost" "the constitution declares no wave 7" \
    "a blocked wave the constitution never declared is reported as unknown, not as waiting on nothing"

# The other two answers a blocked wave can get. All three fit the same
# sentence and two of them begin with the same word, so each has to be
# pinned to what tells it from the other two: an assertion on "unknown"
# alone is green against a digest that reaches for the wrong unknown.
#
# A wave the constitution does declare, with depends_on: []. It waits on
# nothing the files record -- which is not the same as a dependency nobody
# could look up. Wave 1 in the fixture is exactly that shape.
write_constitution
write_state false false "none"
sed -i.bak 's/^| 1 | exchange | done |/| 1 | exchange | blocked |/' docs/baton/state.md
rm -f docs/baton/state.md.bak
no_deps="$("$DIGEST" stop)"
assert_contains "$no_deps" "wave 1 — exchange (depends_on: none declared in the constitution)" \
    "a wave declared with depends_on: [] is reported as declaring none, not as an unknown"

# No constitution at all. The stop digest does not fail over it -- what is
# stopped is still worth printing -- and the dependency it could not look up
# names the reason, so that the reader is not left choosing between a
# constitution that is missing and one that disagrees with state.md.
write_state false false "none" "blocked"
rm -f docs/baton/constitution.md
no_constitution="$("$DIGEST" stop)"
assert_contains "$no_constitution" "wave 2 — refresh (depends_on: unknown, there is no constitution here to read it from)" \
    "with no constitution to read, the blocked wave is still printed and the unknown says which unknown it is"
write_constitution

write_state false false "none" "doing"
unblocked="$("$DIGEST" stop)"
assert_not_contains "$unblocked" "Blocked:" \
    "a wave that is merely in progress is not reported as blocked"

# --- the printer prints, and only prints ---
# Everything above ran against a dirty working tree by construction. Here the
# fixture is committed first, so that anything the tree holds afterwards was
# put there by baton-digest itself.
write_constitution
write_state true false "wave 2 was claimed closed at a SHA no branch contains"
git add docs/baton
git commit -q -m "baton: the fixture this digest is read from"
"$DIGEST" constitution > /dev/null
"$DIGEST" stop > /dev/null
assert_equals "$(git status --porcelain)" "" \
    "the working tree is untouched after both digests -- a printer that writes is not a printer"

# --- outside a repository ---
# A subshell cd rather than `env -C`, which BSD env does not have.
outside="$(mktemp -d)"
rc=0
( cd "$outside" && "$DIGEST" constitution ) >/dev/null 2>&1 || rc=$?
assert_equals "$rc" "1" "refuses to run outside a git repository"
rm -rf "$outside"

finish
