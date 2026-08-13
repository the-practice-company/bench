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
# A field on neither list is read as claimed -- evidence to preserve rather
# than a grant to honour -- so the autopilot flag needs a kind of its own.
assert_contains "$core" "Granted fields" "core skill classifies the autopilot flag as a third kind of field"
assert_contains "$core" "toward more human involvement" \
    "core skill states which direction the agent may move a granted field"
# NOT `assert_contains "$core" "auto"`: `auto` is a substring of `autopilot`,
# which this same change introduces, so the bare word goes green off the
# granted-fields bullet and stays green with the gate paragraph deleted
# outright. Pinned to the sentence carrying the distinction instead.
assert_contains "$core" '`pass` is a second party saying so' \
    "core skill distinguishes the gate column's auto from its pass"
# An auto verdict is a claim -- more of one than pass, since no human checked
# it. Left off the claimed list, it reads as repairable, which is the exact
# act the divergence policy exists to forbid.
assert_contains "$core" 'a gate marked `auto` or `pass`' \
    "core skill counts an auto verdict among the claims it may never repair"

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
# Mutation survivor: deleting the whole second path left the suite green, since
# the assertions above pin only the first path's opener and the word autopilot.
assert_contains "$checkpoint" 'While `autopilot` names a scope' \
    "checkpoint describes the second closing path, not just the flag that selects it"
assert_contains "$checkpoint" '`auto`, not `pass`' \
    "checkpoint says which value the autopilot path writes into the gate column"
# Raised in task 6: the autopilot skill requires a blocked entry when a wave
# cannot close, and step 5 is the only place any entry's shape is written down.
assert_contains "$checkpoint" 'type: blocked' \
    "checkpoint documents the blocked entry the autopilot path requires"
assert_contains "$checkpoint" 'type: autopilot' \
    "checkpoint documents the grant entry autopilot_grant points at"
# This file was the one document telling an agent where to put base:, and it
# said the body. baton-autopilot reads the frontmatter and only the frontmatter,
# so an entry written from the old description puts the base where nothing
# looks, and the run falls back to the root commit against the human's wishes.
assert_contains "$checkpoint" '**`base:` in the frontmatter**' \
    "checkpoint sends base: to the frontmatter, where its only reader looks"
assert_contains "$checkpoint" '## The human'"'"'s corrections' \
    "the grant entry gets the section list every other entry type has"
# needs_human is a state.md granted field, not an entry envelope field, and it
# sat in the identical construction as incoming's needs_review, which is one.
assert_contains "$checkpoint" "This entry carries no \`needs_human\`" \
    "checkpoint separates the run-level flag from the blocked entry's envelope"
# Two ways this file silently resets the autopilot's attempt ceiling: its own
# definition of In flight ("what was interrupted, or nothing") and its rule
# sending a long In flight to a journal entry. Both are correct for every other
# use of that line and wrong for the one value that is a ceiling.
assert_contains "$checkpoint" "One exception: an" \
    "checkpoint excepts the attempt counter from the In flight nothing default"
assert_contains "$checkpoint" "never moves out" \
    "checkpoint keeps the attempt counter out of the journal-overflow rule"
# The gate column used to stay `—`, so closing was three edits and the column
# was not one of them. Now both paths write it. A stale count here does not
# fail loudly: it closes the wave and leaves the cell empty, which every
# reader downstream is entitled to read as "nothing closed this".
assert_contains "$checkpoint" "four edits to this checkpoint's draft" \
    "checkpoint counts the gate column among the edits that close a wave"
# The count and the enumeration are separate things, and pinning only the count
# was the same mistake as pinning "eleven keys" without the table: a mutation
# that keeps "four edits" and deletes the gate bullet leaves three bullets under
# a count of four, and the suite stays green -- which is the exact failure the
# four-edits change was made to prevent.
assert_contains "$checkpoint" 'the `gate` column → `pass` or `auto`' \
    "the fourth edit is actually enumerated, not just counted"
# Likewise the three-value table: its lead sentence is pinned above, so
# deleting every row beneath it survived.
assert_contains "$checkpoint" '| `auto` | Closed under the autopilot' \
    "the gate table still has the auto row that its lead sentence promises"
assert_contains "$checkpoint" '## Why each attempt did not move it' \
    "the blocked entry keeps the section that earns it, not only its type"
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

# The grant is useless if the session that wakes up after a compaction does
# not know it exists. And it is dangerous if a session started to check one
# thing acts on it.
assert_contains "$resume" "autopilot" "resume reads the autopilot grant"

# Both source rows are pinned to the row, not to the bare word. "compact"
# occurs 19 times in this file already -- the description's "context
# compaction", the dot graph's precompact-facts nodes, hooks/pre-compact,
# step 3's prose -- so a bare-word assertion passes against the file as it
# stood before this feature existed, and would go on passing after the whole
# section had been deleted. "resume" is the same, for the obvious reason.
assert_contains "$resume" '| `compact`, `resume` | Continue.' \
    "resume names the compact source, where it continues silently"
assert_contains "$resume" '| `startup`, `clear`, `fork` | Do not start work.' \
    "resume names the startup source, where it waits"
assert_contains "$resume" "/baton:continue" \
    "resume tells the human the word that restarts it"
# The row that decides what happens when the hook could not tell. It resolves
# to the waiting side, and that asymmetry is the whole safety argument: one
# command lost, against an hour of unattended work nobody authorised.
assert_contains "$resume" 'Read it as `startup` and wait' \
    "resume treats an undetermined session source as the waiting case"
# A grant to work without a human is not a grant to work from an unverified
# state, and a section arriving after the divergence checks is exactly where
# that gets read as permission to skip them.
assert_contains "$resume" "not a grant to work from an unverified state" \
    "resume keeps the divergence checks in force under the autopilot"
# Why /baton:continue stops this skill short rather than letting step 7 decide.
# The first version of this paragraph justified it with "resume executes Next
# action unconditionally", which step 7 itself made false. The real reason is
# structural and survives: the source says how the session ARRIVED, and a human
# typing /baton:continue after a /clear is present while the source still reads
# clear. Left stale, the next editor reads a redundant hand-off and removes it.
assert_contains "$resume" "how this session **arrived**, not who is in it now" \
    "resume says why the session source cannot see a human who just typed the command"

autopilot="$(cat "$SKILLS/baton-autopilot/SKILL.md")"

# The asymmetry is the whole safety story. Stated once in prose, it is the
# first thing to go when the file is next edited for length.
assert_contains "$autopilot" "may always turn it off, and never on" \
    "autopilot skill states the asymmetry: the agent clears the grant, never sets it"

# The description is a model-invocable trigger. Worded as a state-file
# condition ("autopilot is not off") it fires on its own on a fresh startup,
# because the hook injects that very fact -- the skill authorising itself off a
# file read, which is what disable-model-invocation on /baton:auto exists to
# prevent. The trigger has to name the decision, which only baton-resume or a
# human's /baton:continue can make.
autopilot_desc="$(sed -n 's/^description: //p' "$SKILLS/baton-autopilot/SKILL.md")"
assert_contains "$autopilot_desc" "baton-resume has decided" \
    "autopilot triggers on the decision that the grant applies to this session"
assert_contains "$autopilot_desc" "/baton:continue" \
    "autopilot's other trigger is the human's command"
assert_not_contains "$autopilot_desc" "set to anything but off" \
    "autopilot does not trigger off a state.md condition it can read for itself"
# Single-line substring on purpose: assert_contains is grep -F, which reads a
# needle containing a newline as two independent patterns and matches EITHER --
# weaker than the one-line form, not stronger.
assert_contains "$autopilot" "Reading the field yourself is not the decision" \
    "autopilot's prerequisite refuses a grant inferred from the field alone"

# Eligibility has three conditions and the third is the one that would be
# dropped as pedantic -- two waves can be independent in the graph and
# still share a contract the blocked wave was to define. Which is why the
# third is pinned to its whole clause: `consumes` alone also appears where
# the skill derives a spec, so the bare word would stay green after the
# condition it is meant to defend had been deleted.
assert_contains "$autopilot" "transitive" \
    "autopilot skill requires the whole transitive dependency closure to be done"
# The eligibility rule existed but governed only the post-block search, so the
# main loop could start a wave whose depends_on was still todo and nothing in
# the file caught it. Both halves of the fix are pinned: the order, which must
# match /baton:auto's so the human reviews the sequence that actually runs, and
# the check itself being applied before a wave is started at all.
assert_contains "$autopilot" "the constitution's wave order, restricted to waves in scope" \
    "autopilot walks waves in the order the human reviewed, not a re-derived one"
assert_contains "$autopilot" "**Check it is available.**" \
    "autopilot checks availability before starting a wave, not only after a block"
assert_contains "$autopilot" 'nothing in its `consumes` appears in the `produces`' \
    "autopilot skill excludes a wave that consumes what a blocked wave produces"

# The pat is bounded by evidence first and a counter second.
assert_contains "$autopilot" "unchanged evidence" \
    "autopilot skill names unchanged evidence as the signal that fixing has stopped being fixing"
assert_contains "$autopilot" "three attempts" "autopilot skill states the absolute ceiling"
assert_contains "$autopilot" "In flight" \
    "autopilot skill keeps the attempt counter in state.md, not in the session"
# The counter only exists once a checkpoint writes it, so "checkpoint between
# waves" left a compaction mid-attempt handing the next session a free one --
# a ceiling that resets, which is the one thing a ceiling must not do. The two
# other reset paths are in baton-checkpoint and pinned below.
assert_contains "$autopilot" "And between attempts, not only between waves" \
    "autopilot checkpoints per attempt, so the ceiling survives a compaction"

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

# Pinned to the invocation, not the name. Mutation-tested: deleting the whole
# ```bash block, --since argument and all, left the suite green off two
# incidental prose mentions of baton-gate elsewhere in the file.
assert_contains "$autopilot" 'scripts/baton-gate" --since' \
    "autopilot skill calls the evidence script, with the argument that scopes it"
# /baton:auto resolves --since and records it as base: on the grant entry, and
# this skill is the only thing that reads it. Unread, the human sets a base
# because the root-commit fallback is wrong for their repository, and the run
# silently uses the fallback anyway -- a disagreement with the human that
# nothing downstream surfaces.
assert_contains "$autopilot" "read the base off the grant" \
    "autopilot takes the first wave's --since from the grant before deriving one"
# The multi-root block was compressed to make room and had no assertion on it,
# which is how the inverted claim it once carried survived a review. What must
# not come back: the sibling root's files are NOT what escapes. Pinned on the
# call and the stop, the two things the compression had to keep.
assert_contains "$autopilot" "git rev-list --max-parents=0 HEAD | tail -1" \
    "autopilot still names the command that finds the fallback base"
assert_contains "$autopilot" 'root'"'"'s tree is exempt is' \
    "autopilot says it is the picked root's own tree that escapes, not the sibling's"
# An absent base: has no branch in an is-a-sha/is-a-dash enumeration, so it
# falls through to the fallback -- the silent disagreement with the human that
# the paragraph above exists to forbid.
assert_contains "$autopilot" "is absent entirely" \
    "autopilot gives an absent base its own branch rather than letting it fall through"
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
# the tree the suite ran against.
#
# Both lines are pinned, because they rot independently and an earlier version
# of this block only pinned the prose. Mutation-tested: rewriting the template
# line to "<the key=value lines, verbatim>" -- exactly the edit that makes an
# agent drop a key -- left the whole suite green.
assert_contains "$autopilot" "eleven keys" \
    "autopilot skill counts the evidence block as eleven keys"
assert_contains "$autopilot" "<the eleven key=value lines, verbatim>" \
    "the verdict template tells the agent to copy all eleven, not an unnumbered some"
# Every superseded count, not just the last one. This block has been wrong at
# nine and at ten; a negative that only chases the previous value goes stale
# the same way the positive did.
assert_not_contains "$autopilot" "nine key" \
    "no stale nine-key count survives anywhere in the autopilot skill"
assert_not_contains "$autopilot" "ten key" \
    "no stale ten-key count survives anywhere in the autopilot skill"
# placeholder_patterns is printed beside placeholder_hits precisely so a zero
# can be told apart from a scan nobody asked for, without opening another
# file. If the verdict does not carry it, the morning is back to guessing.
assert_contains "$autopilot" "placeholder_patterns: <the placeholder_patterns= from the evidence>" \
    "the verdict records what the scan was asked, beside what it found"
# The prose count and the table are separate things: "eleven keys" stays true
# to the eye with ten rows under it. Mutation-tested -- deleting this row left
# the suite green.
assert_contains "$autopilot" "what the scan was asked to look for" \
    "the key table has a row for placeholder_patterns, not just a count that includes it"
assert_contains "$autopilot" "tree_clean" \
    "autopilot skill reads the tree fact that qualifies sha"
# The resolving command must ask the same question baton-observe asked when it
# produced tree_clean=false. Plain `git status --porcelain` reports nothing
# under status.showUntrackedFiles=no, and an empty list makes "every path is
# accounted for" vacuously true -- the agent takes the ordinary branch over a
# file it never saw, or reads the empty list as proof the fact was spurious.
assert_contains "$autopilot" "status --porcelain -uall --ignore-submodules=none" \
    "autopilot resolves dirty paths with the same flags that produced tree_clean"
# produces is a contract name, required only of waves with a non-empty
# parallel_with, so a rule resting on it alone finds an empty set for an
# ordinary serial wave -- every path lands outside it and the ordinary case
# becomes the stop. The union is what keeps the night from ending on wave one.
assert_contains "$autopilot" "union" \
    "autopilot accounts for a dirty path against a union of sets that actually exist"
# The gate writes .baton/gate-verify.log on every run, and tree_clean goes
# false on it in any repository whose .gitignore lost the .baton/ line.
# Reproduced: changed_files=0 placeholder_hits=0 tree_clean=false, the only
# dirty path being the gate's own log. Unstated, the rule above attributes it
# to no wave and stops the night over the tool that just ran.
assert_contains "$autopilot" "Discount \`.baton/\` before anything else" \
    "autopilot does not put the gate's own log on trial as unattributable work"
# A dirty tree splits into ordinary work and a stop, and only the second is
# load-bearing: the first is what an agent does anyway.
# The pat used to raise needs_human on a parked wave AND carry on. But
# baton-resume and /baton:continue both halt on finding it set, so the run
# stopped at its next compaction and stayed stopped -- the exact failure the
# feature exists to prevent, reached by parking one wave and continuing
# correctly. The flag now belongs only to the branch where nothing is left.
assert_contains "$autopilot" "Do not raise \`needs_human\` here" \
    "the pat does not raise the run-level stop flag on a wave it is stepping past"
assert_contains "$autopilot" "if anything is \`blocked\`" \
    "the flag is raised where the run actually ends, and only if a wave was parked"
assert_contains "$autopilot" "Name every blocked wave in that report" \
    "a run that parked a wave and finished the rest does not read as a clean night"
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

# Observed fields are repaired silently; this one is not, because it does not
# describe the tree -- it answers whether this is the tree at all.
assert_contains "$core" "observed_branch" "core skill names the branch field"
assert_contains "$core" "a stop, not a repair" "core skill makes a diverged observed_branch a stop"
assert_contains "$core" "superpowers:subagent-driven-development" "core skill names the procedure that executes a wave"

finish
