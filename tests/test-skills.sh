#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SKILLS="$REPO_ROOT/plugins/baton/skills"
. "$SCRIPT_DIR/helpers.sh"

for name in baton baton-checkpoint baton-resume baton-autopilot; do
    f="$SKILLS/$name/SKILL.md"
    assert_file_exists "$f" "skill $name exists"
    [ -f "$f" ] || continue

    body="$(cat "$f")"
    assert_equals "$(sed -n '1p' "$f")" "---" "skill $name starts with frontmatter"
    assert_contains "$body" "name: $name" "skill $name declares its name"
    assert_contains "$body" "description: Use when" "skill $name describes when to trigger"

    lines="$(wc -l < "$f" | tr -d ' ')"
    if [ "$lines" -le 500 ]; then
        pass "skill $name is within the 500-line convention ($lines lines)"
    else
        fail "skill $name is within the 500-line convention ($lines lines)"
    fi
done

core="$(cat "$SKILLS/baton/SKILL.md")"
assert_contains "$core" "Red Flags" "core skill lists the rationalisations to catch"
assert_contains "$core" "git log" "core skill names git history as the event log"

checkpoint="$(cat "$SKILLS/baton-checkpoint/SKILL.md")"
assert_contains "$checkpoint" "60 lines" "checkpoint skill states the state.md line cap"
# Closing a wave enumerates the edits it takes. Leaving the gate column out of
# that list is not neutral: the row above the one being written already
# carries a value, so an agent with nothing else to go on copies it, and
# writes a verdict no gate produced.
assert_contains "$checkpoint" 'The `gate` column takes one of three values' \
    "checkpoint skill says what the gate column holds and who fills it"
# There are now two ways a wave closes, and the dangerous misreading is not
# that an agent misses the second one -- it is that it applies the second one
# whenever a human is slow to answer. So what is pinned is the clause that
# gates it on the field, not the mention of the field.
assert_contains "$checkpoint" "autopilot" "checkpoint's closing rule knows about the second path"
assert_contains "$checkpoint" 'While `autopilot` reads `off`' \
    "checkpoint gates the second path on the flag, not on whether a human happens to be replying"
assert_contains "$checkpoint" '`auto`, not `pass`' \
    "checkpoint says which value the autopilot path writes into the gate column"
# Raised in task 6: the autopilot skill requires a blocked entry when a wave
# cannot close, and step 5 is the only place any entry's shape is written down.
assert_contains "$checkpoint" 'type: blocked' \
    "checkpoint documents the blocked entry the autopilot path requires"
# The gate column used to stay `—`, so closing was three edits and the column
# was not one of them. Now both paths write it. A stale count here does not
# fail loudly: it closes the wave and leaves the cell empty, which every
# reader downstream is entitled to read as "nothing closed this".
assert_contains "$checkpoint" "four edits to this checkpoint's draft" \
    "checkpoint counts the gate column among the edits that close a wave"
assert_contains "$checkpoint" "Read the current state, whole" "checkpoint skill instructs reading the current state file first"
assert_contains "$checkpoint" "baton-lock" "checkpoint skill mentions the lock script"
assert_contains "$checkpoint" "release" "checkpoint skill covers releasing the lease"

resume="$(cat "$SKILLS/baton-resume/SKILL.md")"
# Raising suspect and stopping looks, from inside, like the run needs a human
# -- which is a different flag with a different meaning. Saying nothing here
# leaves the agent to derive one from the other.
assert_contains "$resume" 'leave `needs_human` alone' \
    "resume skill says what happens to needs_human when this resume raises suspect"
# The event log is what a later session reads instead of the file. One fixed
# message for both outcomes makes a commit that raised the flag read as one
# that found nothing wrong.
assert_contains "$resume" "baton: resume found a divergence" \
    "resume skill gives the suspect-raising write its own commit message"
assert_contains "$resume" "128" "resume skill explains the merge-base exit-128 case"
assert_contains "$resume" "fatal:" "resume skill explains the merge-base fatal: message"
assert_contains "$resume" "is an ancestor of \`HEAD\`. The claim holds." "resume skill explains merge-base exit 0"

autopilot="$(cat "$SKILLS/baton-autopilot/SKILL.md")"

# The asymmetry is the whole safety story. Stated once in prose, it is the
# first thing to go when the file is next edited for length.
assert_contains "$autopilot" "may always turn it off, and never on" \
    "autopilot skill states the asymmetry: the agent clears the grant, never sets it"

# Eligibility has three conditions and the third is the one that would be
# dropped as pedantic -- two waves can be independent in the graph and
# still share a contract the blocked wave was to define. Which is why the
# third is pinned to its whole clause: `consumes` alone also appears where
# the skill derives a spec, so the bare word would stay green after the
# condition it is meant to defend had been deleted.
assert_contains "$autopilot" "transitive" \
    "autopilot skill requires the whole transitive dependency closure to be done"
assert_contains "$autopilot" 'nothing in its `consumes` appears in the `produces`' \
    "autopilot skill excludes a wave that consumes what a blocked wave produces"

# The pat is bounded by evidence first and a counter second.
assert_contains "$autopilot" "unchanged evidence" \
    "autopilot skill names unchanged evidence as the signal that fixing has stopped being fixing"
assert_contains "$autopilot" "three attempts" "autopilot skill states the absolute ceiling"
assert_contains "$autopilot" "In flight" \
    "autopilot skill keeps the attempt counter in state.md, not in the session"

# What autonomy never covers.
assert_contains "$autopilot" "contradicts the constitution" "autopilot skill stops on a constitution contradiction"
# Both of the next two are pinned to the whole clause rather than to the bare
# word. "suspect" appears in the Red Flags and in the divergence prose alike,
# and "exit 3" now names two different scripts in this one file -- baton-lock's
# held lease and baton-gate's unfit constitution. A bare-substring assertion
# would go green on either occurrence while its message claims the other, which
# is worse than no assertion: it reports that the rule is present after the
# sentence carrying it has been deleted.
assert_contains "$autopilot" '`suspect: true` and stop' "autopilot skill stops on a diverged claim"
assert_contains "$autopilot" '`baton-lock` exit 3' "autopilot skill stops when another session holds the lease"
assert_contains "$autopilot" "weaken the gate" "autopilot skill forbids weakening the gate"

assert_contains "$autopilot" "baton-gate" "autopilot skill calls the evidence script"
assert_contains "$autopilot" "docs/baton/gates/" "autopilot skill files the verdict"

# The three readings of baton-gate's output that no script can enforce and
# nothing else in the plugin writes down. Each is one sentence in the skill,
# and each is silently expensive to lose: a wave failed over a missing test
# runner, a scan run over the wrong range, a verdict whose only account of the
# failure was overwritten by the attempt that followed it.
assert_contains "$autopilot" "did not run, not did not pass" \
    "autopilot skill reads verify_exit 127 as the suite not running, not as the code being wrong"
assert_contains "$autopilot" 'resolves from `work_sha`, not from `sha`' \
    "autopilot skill sends the next wave's --since to work_sha rather than to HEAD"
assert_contains "$autopilot" "truncated on every run" \
    "autopilot skill says the verify log does not survive the next attempt"

# The evidence block gained a tenth key in 7929bd2. Two places in the skill
# count the keys, and the verdict template's "copy them verbatim" is the one
# that bites: an agent working from a stale count copies nine and drops
# tree_clean -- the one key that says whether the sha it filed alongside names
# the tree the suite ran against. Asserting that the word tree_clean appears
# somewhere would not catch that, because the count is the thing that goes
# stale, so the count is what is pinned -- in both directions, since the
# template's line and the prose's line rot independently.
assert_contains "$autopilot" "ten keys" \
    "autopilot skill counts the evidence block as ten keys"
assert_not_contains "$autopilot" "nine key" \
    "no stale nine-key count survives anywhere in the autopilot skill"
assert_contains "$autopilot" "tree_clean" \
    "autopilot skill reads the tree fact that qualifies sha"
# A dirty tree splits into ordinary work and a stop, and only the second is
# load-bearing: the first is what an agent does anyway.
assert_contains "$autopilot" "cannot account for as this wave" \
    "autopilot skill stops on an uncommitted path it cannot attribute to the wave"

# Verified against the script's behaviour, not its header comment: an absent
# verify_cmd exits 4 (reported as "empty"), an absent placeholder_patterns
# exits 3. Reading across from one field to the other is the natural mistake,
# the two rows hand the human different jobs, and a tidying edit that merges
# them back into one parenthetical is exactly how this was wrong before.
assert_contains "$autopilot" "Absence is not symmetric" \
    "autopilot skill keeps the two fields' absence causes on their own exit codes"
# An empty pattern list is a legitimate constitution, so a zero here can mean
# the scan was never asked anything -- indistinguishable, in the output, from
# a scan that read every changed file and found nothing.
assert_contains "$autopilot" "only evidence if the scan was asked anything" \
    "autopilot skill refuses to read placeholder_hits=0 as clean when patterns are empty"

finish
