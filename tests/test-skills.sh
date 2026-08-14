#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SKILLS="$REPO_ROOT/plugins/baton/skills"
. "$SCRIPT_DIR/helpers.sh"

# This list is hardcoded; test-budget.sh globs */SKILL.md. So a fifth skill
# gets no per-file cap here and is still counted there -- test-budget.sh is
# the backstop, and it is the one that would catch it, by failing on a total.
# Add the name here when a skill is added, or the cap it never had is the one
# nobody notices missing.
#
# The same is true of a skills/<name>/references/*.md file: nothing here
# gives it a per-file cap, and that is left as-is on purpose -- there is no
# floor to set one from until such a file exists, and inventing a number now
# would be a guess rather than a measurement. test-budget.sh does not have
# that problem: it walks every .md file under each skill directory, so a
# references file is counted in the total the moment it exists. Backstop
# again, not a second gap.
cap_total=0
for name in baton baton-checkpoint baton-resume baton-autopilot; do
    f="$SKILLS/$name/SKILL.md"

    # Per-file caps, not one flat convention. A single ceiling high enough
    # for the largest skill is no ceiling for the others, and the growth
    # this bounds arrived one justified paragraph at a time.
    #
    # Each cap is the file's measured floor plus about three lines -- room for
    # one restored rule, not for a paragraph -- and never a fraction of what the
    # file used to weigh. That second method is how baton-checkpoint got 305, a
    # number nobody had checked; reading the file with the cleanup invariant in
    # hand put its floor at 321, hence 324.
    #
    # The four floors as this branch left them: baton 172, baton-autopilot 333,
    # baton-resume 310, baton-checkpoint 321. Every cap below is its floor plus
    # three, set in one pass rather than one conversation per file -- the first
    # time these numbers moved they moved separately, and three separate
    # negotiations is how a ceiling turns into a running total.
    #
    # Two of those floors rose because a rule went back in: baton-resume states
    # the workspace preference to using-git-worktrees instead of letting it ask,
    # and baton-autopilot says what happens when the criteria walk finds a
    # criterion unmet -- the case the gate exists for, which was unwritten.
    # baton-autopilot had already paid for two restored rules by finding an
    # argument to cut and had nothing left to find, which is the signal a cap is
    # doing its job rather than the signal to shave the nearest sentence.
    #
    # Two of them moved again for the no-dead-ends rule: no place where the run
    # waits on a human may report that without naming the command that resolves
    # it, which is a clause on baton-autopilot's exit-3 stop, a sentence in its
    # end-of-run report, and one line in baton-resume's step 4. There was
    # nothing left to trade for them -- the alternative was cutting a
    # neighbouring sentence, which on the previous branch produced an
    # oscillation where the same sentence was deleted and restored twice.
    # Re-measured with those landed: baton-autopilot 338, baton-resume 313,
    # hence 341 and 316. The other two caps are untouched and their floors are
    # not re-derived here -- a cap nobody had a reason to move is a cap nobody
    # measured today, and a number carried over from a measurement is not one.
    #
    # Those two floors were right the day they were written and stopped being
    # right further down the same branch: ea7783d and 68868b8 each added a line
    # to the file they touched, and b064ed1 took baton-checkpoint from 320 to
    # 322, past the 321 called its floor above. Measured again here, all four
    # and not just the ones with a reason to move: baton 172, baton-autopilot
    # 339, baton-resume 314, baton-checkpoint 322. Every cap below still holds
    # over its file, so none of them moves in this commit -- but three of them
    # now stand at floor plus two rather than the plus three the paragraph
    # above describes, each having lost a line to the file growing under it.
    # Buying that line back moves three caps and test-budget.sh's BUDGET
    # together, which is a decision about what the layer may cost per run
    # rather than a measurement, so it is not taken here. What is written here
    # is what the room actually is.
    #
    # baton-autopilot's floor then moved for content, and this time the cap
    # had to move with it: the availability rule said a wave's `spec` must not
    # be `—`, which admitted a wave whose constitution has no `spec:` key at
    # all -- every wave of every run written before the field existed. Absent
    # and `—` are now one refusal, said in the same words in step 0, step 1,
    # condition 4 and the end-of-run report. Four lines, 339 to 343, and there
    # was nothing to trade for them: the rule the words carry is the one the
    # move into the constitution was for. Re-measured with them landed, all
    # four again: baton 172, baton-autopilot 343, baton-resume 314,
    # baton-checkpoint 322. Only baton-autopilot's cap moves, to its floor plus
    # three; the other three are the same numbers as above, standing over
    # floors that did not move.
    #
    # These four sum to 1161, which test-budget.sh carries as its budget, and
    # the assertion after this loop is what makes that a fact rather than a
    # claim. A cap that moves here moves that number too, in the same commit.
    case "$name" in
        baton)            cap=175 ;;
        baton-autopilot)  cap=346 ;;
        baton-resume)     cap=316 ;;
        baton-checkpoint) cap=324 ;;
    esac
    cap_total=$((cap_total + cap))

    assert_file_exists "$f" "skill $name exists"
    [ -f "$f" ] || continue

    body="$(cat "$f")"
    assert_equals "$(sed -n '1p' "$f")" "---" "skill $name starts with frontmatter"
    assert_contains "$body" "name: $name" "skill $name declares its name"
    assert_contains "$body" "description: Use when" "skill $name describes when to trigger"

    lines="$(wc -l < "$f" | tr -d ' ')"
    if [ "$lines" -le "$cap" ]; then
        pass "skill $name is within its $cap-line cap ($lines lines)"
    else
        fail "skill $name is within its $cap-line cap ($lines lines)"
    fi
done

# The caps above and test-budget.sh's BUDGET are one statement made twice, and
# until now only a comment said so. Raise a cap and forget the budget and both
# files stay green -- until the skills grow into the headroom, at which point
# the failure surfaces in test-budget.sh, naming a total rather than the cap
# that actually moved. Read out of that file rather than copied into this one:
# a second literal here would be a third place to forget.
budget="$(sed -n 's/^BUDGET=\([0-9][0-9]*\).*/\1/p' "$SCRIPT_DIR/test-budget.sh")"
assert_equals "$cap_total" "$budget" \
    "the per-file caps sum to the budget test-budget.sh enforces"

core="$(cat "$SKILLS/baton/SKILL.md")"
assert_contains "$core" "Red Flags" "core skill lists the rationalisations to catch"
assert_contains "$core" "git log" "core skill names git history as the event log"
# A field on neither list is read as claimed -- evidence to preserve rather
# than a grant to honour -- so the autopilot flag needs a kind of its own.
assert_contains "$core" "Granted fields" "core skill classifies the autopilot flag as a third kind of field"
assert_contains "$core" "toward more human involvement" \
    "core skill states which direction the agent may move a granted field"
# This is the canonical statement of the rule, and it named a command for one
# half of it only: the autopilot direction sent the reader to /baton:auto,
# while "clearing either is the human's" named nothing -- in the one paragraph
# an agent consults to learn who may move these fields. A runbook scenario now
# pins that a session finding needs_human names /baton:clear, and baton-resume
# step 4 is the other place it can come from; both are worth having, since a
# compacted session carries this file and need not be at step 4 when it meets
# the flag. Pinned to the clause: the file has other reasons to say the word.
assert_contains "$core" 'clearing either is the human'"'"'s, through `/baton:clear`' \
    "the granted-fields rule names the command for the flag half, as it already does for the autopilot half"
# NOT `assert_contains "$core" "auto"`: `auto` is a substring of `autopilot`,
# so the bare word goes green off the granted-fields bullet and stays green
# with the gate paragraph deleted outright. Pinned to the clause that says
# whose claim an `auto` verdict is instead.
assert_contains "$core" 'by the same agent that did the work' \
    "core skill says an auto verdict is the working agent's own claim"
# This guard used to pin "`pass` is a second party saying so", and it now
# watches for that second party's absence. The value went because nothing read
# it: no script, no hook. A mark that changes nothing, is written by hand once
# per wave, and has been written falsely once is not a review -- and the value
# an agent cannot name is the one it cannot claim.
assert_not_contains "$core" '`pass`' \
    "the core skill offers no second-party gate value to claim"
# An auto verdict is a claim: nobody but the agent that did the work has
# checked it. Left off the claimed list, it reads as repairable, which is the
# exact act the divergence policy exists to forbid.
assert_contains "$core" 'a gate marked `auto`' \
    "core skill counts an auto verdict among the claims it may never repair"

checkpoint="$(cat "$SKILLS/baton-checkpoint/SKILL.md")"
assert_contains "$checkpoint" "60 lines" "checkpoint skill states the state.md line cap"
# The exit-3 message table is what an agent reads when a checkpoint is
# refused, and it is read by looking up the message. Two families of refusal
# were missing from it -- the granted-flag guard, and the four shapes of
# frontmatter baton-write cannot read -- both added to that tool after this
# table was written. A reader who does not find their message in a table whose
# whole purpose is that lookup concludes theirs is not an exit 3 at all, which
# is worse than the table's absence: it answers, wrongly.
#
# Pinned twice per row, because the trigger and the instruction rot
# separately: a row whose key no longer matches the message is unfindable, and
# a row found but silent about `/baton:clear` sends the agent to retry the one
# write no retry can land.
assert_contains "$checkpoint" 'is set in HEAD`, or refusing to clear' \
    "the exit-3 table has a row for the granted-flag refusal, keyed on what the tool prints"
assert_contains "$checkpoint" 'lowering it is `/baton:clear`'"'"'s, and not yours' \
    "that row sends the agent to the human's command instead of to a retry"
# The count and the enumeration in one needle, the same lesson as "eleven
# keys" and "four edits": a row saying four while naming two is read as two,
# and the shape an agent does not find named is the one it decides it does not
# have.
assert_contains "$checkpoint" 'four shapes it is — nothing arrived at all, line 1 is not a bare' \
    "the unreadable-frontmatter row names the shapes it counts"
# Closing a wave enumerates the edits it takes. Leaving the gate column out of
# that list is not neutral: the row above the one being written already
# carries a value, so an agent with nothing else to go on copies it, and
# writes a verdict no gate produced.
assert_contains "$checkpoint" 'The `gate` column takes one of two values' \
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
# The sentence this replaces said the autopilot path writes `auto` and not
# `pass`, and carried a second rule in its second half: the row above the one
# you are filling in is the previous wave's value, not an instruction. That is
# the rule the v0.1.0 runbook run actually broke -- the agent copied the row
# above -- and it outlives the value that was copied, so it is what is pinned.
assert_contains "$checkpoint" "carries the previous run's value" \
    "checkpoint tells the agent not to copy the gate cell from the row above"
assert_not_contains "$checkpoint" '`pass`' \
    "the checkpoint skill offers no third gate value to write"
# `pass` was where a wave closed with a human's confirmation and no autopilot
# landed. Delete the value and say nothing else and that path has no cell to
# write, leaving `auto` as the only value the table names -- and the row above
# already carries it.
assert_contains "$checkpoint" 'and no autopilot stays `—`' \
    "the table says where a wave closed by hand lands, now that pass is gone"
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
assert_contains "$checkpoint" 'the `gate` column → `auto` or `—`' \
    "the fourth edit is actually enumerated, not just counted"
# Likewise the three-value table: its lead sentence is pinned above, so
# deleting every row beneath it survived.
assert_contains "$checkpoint" '| `auto` | Closed under the autopilot' \
    "the gate table still has the auto row that its lead sentence promises"
assert_contains "$checkpoint" '## Why each attempt did not move it' \
    "the blocked entry keeps the section that earns it, not only its type"
# This ordering lived only as an edge in the process digraph -- write -> verify
# -> over -> release -- while the prose puts `## Verify before claiming success`
# two sections after step 8. So the digraph was the only artefact in the file
# saying the checkpoint is confirmed BEFORE the lease goes, and deleting it as a
# 1:1 restatement of the steps took the rule with it. No assertion could have
# caught that: nothing pins an edge, and no prose reviewer misses a sentence
# that was never in the prose. Release first and a failed verification finds you
# without the lease you need to act on it.
assert_contains "$checkpoint" "Verify before you release, never after" \
    "checkpoint confirms the write landed before it gives up the lease"
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
# Step 4 is where a resume meets a flag someone else raised, and it is the one
# stop a human is guaranteed to read: the session halts there and reports.
# It used to end by telling the agent to write `suspect: false` itself, which
# `baton-write` now refuses outright -- so the instruction cost a refusal and
# still left the human without the command. Pinned to the naming clause, not to
# `/baton:clear`, which a later mention anywhere in the file would satisfy.
assert_contains "$resume" 'Then name the command that lowers it: `/baton:clear`' \
    "the flag found on disk is reported with the command that lowers it"
# A sixth place of the same shape, found while doing the five the plan lists:
# step 1 stops on a constitution nobody ratified and used to say "ask for
# ratification", which is the wait without the words. It is the first stop a
# fresh session can hit, so it is the likeliest of all of them to be read by
# someone who has not seen this plugin before.
assert_contains "$resume" 'not finished writing it — `/baton:ratify`' \
    "the unratified-constitution stop names the command that ratifies"
# And the write that no longer works is gone rather than merely supplemented:
# an agent reading both would try the refused one first.
assert_not_contains "$resume" 'field set to what they said and `suspect: false`' \
    "resume no longer tells the agent to lower the flag through baton-write"
# Stated as the guard states it, and not as "refuses a write that lowers a
# flag": the tool tests for a positive `true` in what arrives, so spelling the
# flag `false`, leaving the line out, and writing frontmatter it cannot read
# are one refusal and not three. The step still prescribes a write of its own
# -- the claimed field, set to what the human said -- and an agent that reads
# the rule as being about the word `false` drops the flag line from that draft
# and is refused by a guard it was just told it was obeying.
assert_contains "$resume" 'carry the raised flag forward as a positive `true`' \
    "resume states the refusal the way baton-write actually tests for it"
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

# Eligibility has four conditions and the `consumes` one is what would be
# dropped as pedantic -- two waves can be independent in the graph and
# still share a contract the blocked wave was to define. Which is why it is
# pinned to its whole clause: `consumes` alone also appears in step 0's
# shorthand of these same conditions, so the bare word would stay green
# after the condition it is meant to defend had been deleted.
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
# The availability list is what the end-of-run branch reads: it ends the run
# when nothing is available. A spec-less wave that step 1 refuses but this
# list still calls available is a wave the loop can take, skip, and take
# again, with "if no wave is available" never becoming true. So the refusal
# has to live HERE, not only in step 1.
#
# The needle names where the field is read from, and it is chosen so the old
# text cannot satisfy it: the rule used to say "cell", meaning a column of
# state.md the agent writes at every checkpoint. It now says the constitution,
# which `baton-write` refuses outright -- so an agent that wrote its own spec
# could no longer put the path where the rule looks.
assert_contains "$autopilot" 'its `spec` in the constitution **names a document**' \
    "a wave with no spec is unavailable, not merely skipped once it has been taken"
# The needle above used to read "is not `—`", and that phrasing had a hole in
# it that only shows up on an upgrade: a constitution written before the field
# moved into it has no `spec:` key on any wave, and absent is not `—`. The
# rule as written admitted every one of those waves -- the autopilot taking a
# wave whose document nobody named, which is the loop the move was meant to
# close, arriving through the one door left open. `/baton:auto`'s own scope
# rule said "must name a document" and refused them correctly, so the two
# files disagreed about the same wave. Pinned on the sentence that closes it,
# not on the positive half above, which a rephrasing could satisfy while
# saying nothing about an absent key.
assert_contains "$autopilot" '`spec:` key are one refusal, not two — absent is not permission' \
    "an absent spec key is refused exactly as a — is, so an upgraded run is not admitted by default"
# The count and the enumeration rot independently -- the same lesson as
# "eleven keys" over the key table, and "four edits" over the gate bullet. A
# list of four under a lead sentence saying three is read as three, and the
# fourth condition is the one an agent stops evaluating.
assert_contains "$autopilot" "all four hold" \
    "the lead sentence counts the spec condition among the conditions beneath it"

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
# The end-of-run report is not the only place this skill stops on the flag:
# the unattributable dirty path and every bullet below raise it MID-RUN, and
# when one of those fires the end-of-run report is never written at all. So the
# place already fixed cannot cover them, and a human meeting one of these gets
# the flag, no command, and no later report that would have named one. Stated
# once at the section lead rather than six times: the rule is the same rule,
# and six copies of it is how a section gets tidied back down to five.
assert_contains "$autopilot" '`needs_human` — here or above — names `/baton:clear`' \
    "every stop that raises the flag names the command that lowers it, not only the last one"
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
# --since is chosen here, two sections before `work_sha` is defined under
# "Reading the evidence". Without this clause the cell is a forward reference
# to a term the reader does not have yet, and the agent reaches for `sha`,
# which is the one field the next wave's scan must not start from. Deleted
# once already -- by me, to buy a line against the cap, which is the wrong
# reason to spend a sentence that tells you what a field is for.
assert_contains "$autopilot" "the last commit that moved the work" \
    "closed_at_sha says what it names, where --since is actually chosen"
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
# The end-of-run report is written at 03:40 and read in the morning, and it is
# the only place the raised flag is explained to anyone. A report that says the
# run stopped without saying what un-stops it sends the human to the README --
# and `baton-write` refuses the write that would lower it, so guessing costs
# them a refusal too. Pinned to the flag and the command on one line: both
# `needs_human` and `/baton:clear` appear elsewhere in this file, so either
# alone would go green with this sentence deleted.
assert_contains "$autopilot" 'If you raised `needs_human`, name `/baton:clear` too' \
    "the end-of-run report names the command that lowers the flag it raised"
assert_contains "$autopilot" "cannot account for as this wave" \
    "autopilot skill stops on an uncommitted path it cannot attribute to the wave"
# The commit-and-regate branch is explicitly exempt from the three-attempt
# ceiling -- correctly, since no verdict was rendered -- so it is the one loop
# in this skill with no counter bounding it. Unbounded, a repository writing
# files nothing accounts for keeps it committing and regating with nobody
# watching. The bound is the second occurrence routing to the stop instead.
assert_contains "$autopilot" "take the stop below" \
    "a tree still dirty after the regate takes the stop, not the loop again"

# Verified against the script's behaviour, not its header comment: an absent
# verify_cmd exits 4 (reported as "empty"), an absent placeholder_patterns
# exits 3. Reading across from one field to the other is the natural mistake,
# the two rows hand the human different jobs, and a tidying edit that merges
# them back into one parenthetical is exactly how this was wrong before.
assert_contains "$autopilot" "Absence is not symmetric" \
    "autopilot skill keeps the two fields' absence causes on their own exit codes"
# Exit 3 is a stop AND a flag. A stop without the flag does not stick under
# the autopilot: the next /baton:continue resumes, hits exit 3 again, stops
# again, and nothing on disk ever says a human must clear it.
# NOT `assert_contains "$autopilot" "needs_human: true"`: that string appears
# six times in this file already -- the multi-root stop, the pat, the never-
# covers list -- so the bare form was green before exit 3 said anything about
# the flag, and stays green with this clause deleted. Pinned to the clause.
assert_contains "$autopilot" '`3` also takes `needs_human: true`' \
    "exit 3 raises the run-level flag, not just a stop"
# And exit 3's commonest cause is a constitution nobody ratified -- which the
# agent cannot fix, since `baton-write` refuses that path, and which the human
# fixes with one command they have to be told the name of. Named conditionally,
# because exit 3 is a family: the script's message says which member, and only
# the unratified one is `/baton:ratify`'s. Pinned to the flag beside the
# command, since the file names `/baton:ratify` nowhere else and `needs_human:
# true` half a dozen times.
assert_contains "$autopilot" 'takes `needs_human: true` — say `/baton:ratify`' \
    "the exit-3 stop names the command that ratifies, beside the flag it raises"
# The parent's exit-4 row forbade this and the compression dropped it with the
# row. Exit 4 is the gate saying it could not run verify_cmd -- the one moment
# an agent has both a reason and an obvious way to run something else, and the
# whole point of the field living in a file baton-write refuses to touch is
# that the agent does not choose it. Pinned to the imperative: `verify_cmd`
# alone appears a dozen times in this file and would pin nothing.
assert_contains "$autopilot" "Never substitute a command of your own" \
    "the agent does not run a command it thinks equivalent to verify_cmd"
# The gate's central case, and it was unwritten: the file said green evidence
# was necessary but not sufficient, said to walk the exit_criteria, and never
# said what an unmet one does. Both halves are pinned because they are only
# correct together. An unmet criterion counting as an attempt is what makes
# the ceiling bound the walk at all; scoping the unchanged-evidence stop is
# what stops that same ceiling collapsing to one. A criteria walk leaves
# verify_exit=0 and the failing set empty every time, so the unchanged-evidence
# test fires on attempt 2 of every criteria failure -- which the plugin's own
# autopilot fixture contradicts: build-autopilot.sh records three attempts on
# exactly this case, evidence unmoved throughout.
assert_contains "$autopilot" "An unmet criterion is" \
    "a criterion the walk finds unmet is a failed attempt, not a close"
assert_contains "$autopilot" "**Evidence-red attempts only.**" \
    "the unchanged-evidence stop does not fire on a failed criteria walk"
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

assert_contains "$resume" "Repair both silently" "resume still repairs the two fields baton-observe can speak to"
assert_contains "$resume" "observed_branch" "resume checks the branch"
assert_contains "$resume" "do not repair it" "resume does not silently repair a diverged branch"
# Step 6's write list used to say `observed_branch` is set "from what
# baton-observe reported", which silently undoes step 2's refusal to repair
# it -- the second half of the skill re-granting what the first half denied.
assert_not_contains "$resume" '`observed_branch` and `tree_clean` set from what' \
    "step 6 does not write back a field step 2 refused to repair"

assert_contains "$core" "A field named nowhere above is claimed" \
    "core skill's catch-all does not sweep in the field with its own policy"

# Was `assert_not_contains "$autopilot" "derive one from"`, pinned to the exact
# wording of a sentence deleted in aa3d41f -- so it forbade one phrasing of a
# derivation branch and passed any rephrasing of it, which is the opposite of
# what it claimed. The rule is that the skill refuses to derive a spec at all,
# so pin the refusal: a re-introduced branch has to remove or contradict it.
assert_contains "$autopilot" "Never derive that document yourself" \
    "the autopilot refuses to write a wave's spec, however a branch is worded"
assert_contains "$autopilot" "superpowers:subagent-driven-development" \
    "the work step names the procedure that executes it"
assert_contains "$autopilot" "not a second review of the code" \
    "the gate is framed as a record of closure"
assert_contains "$autopilot" "superpowers:finishing-a-development-branch" \
    "the end-of-run report names the skill that closes the run"

assert_contains "$resume" "Write nothing, not even" \
    "the branch stop writes no flag into a state.md it cannot establish is this run's"

# Step 1 skips a wave whose spec is `—` rather than deriving one, and a
# skipped wave stays `todo` -- so nothing on disk records that it was passed
# over. The end-of-run report is the only place it can appear, and the run it
# appears in is the one that most wants a human: what the wave needs is a
# brainstorming session.
assert_contains "$autopilot" "skipped for want of a spec" \
    "a wave skipped for an empty spec is named in the end-of-run report"

# Where step 1 reads the document from, which is the whole of this change. The
# refusal above ("Never derive that document yourself") was already there and
# stayed green while the path came off a state.md column the agent writes at
# every checkpoint: it could write its own spec, put the path in the cell, and
# take the wave at the next checkpoint -- the self-judging loop rebuilt one
# level up. Naming the constitution is what closes that, because `baton-write`
# refuses that path, so this needle cannot pass off the old wording.
assert_contains "$autopilot" "The wave's \`spec\` in the constitution names" \
    "the autopilot reads a wave's spec from the file it cannot write"

# The same failure the workspace preference had: step 1 enumerates what it
# takes from the constitution, and a field missing from that list is a field
# the resumed session never loads. Found only by final review last time.
assert_contains "$resume" "each wave's \`spec\`" \
    "resume step 1 takes the per-wave spec off the constitution with the rest"

# The workspace preference was a field nothing read: /baton:init collected it,
# the constitution declared it, baton/SKILL.md called using-git-worktrees
# "settled once" by it, and no procedure ever handed it over -- that skill reads
# the agent's instructions, not the constitution. Pinned to the hand-off and not
# to the word: `workspace` goes green the moment step 1 lists the field, and
# listing a field is not conveying it.
assert_contains "$resume" "superpowers:using-git-worktrees" \
    "resume names the skill the workspace preference has to reach"
assert_contains "$resume" "state it to that skill rather than letting it ask" \
    "resume states the preference unasked, since the autopilot has nobody to answer a consent prompt"

finish
