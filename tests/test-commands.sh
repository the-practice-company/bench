#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CMD="$REPO_ROOT/plugins/baton/commands"
. "$SCRIPT_DIR/helpers.sh"

# The frontmatter block alone: line 1's --- up to the next one. A file whose
# first line is not --- yields nothing, which is the right answer here -- a
# flag Claude Code will not read is not a flag set. Same parser as
# test-skill-commands.sh's frontmatter_of_doc, and it is a copy rather than a
# shared helper because helpers.sh holds assertions, not readers.
frontmatter_of() {
    awk '
        NR == 1 && $0 == "---" { infm = 1; next }
        infm && $0 == "---"    { exit }
        infm
    ' "$1"
}

# ratify and clear landed on this branch and were added to neither this list
# nor the README's table -- the same omission in two places, and nothing said
# so, because a hardcoded list checks only what someone remembered to type
# into it. The budget below globs, so it counted them from the day they
# landed; this loop did not.
for name in init checkpoint status auto continue ratify clear; do
    assert_file_exists "$CMD/$name.md" "command $name exists"
done

# A ceiling on commands/ as a whole, not a per-file cap for each command the
# way test-skills.sh caps each skill. A command file is loaded only when it
# is invoked, not resident across every session the way a skill is, so
# per-file caps here would be more machinery than the risk warrants.
#
# The risk is not commands/ growing on its own merits -- it is commands/
# becoming the overflow bucket for skills/. The branch that cut the skills
# down moved evicted prose to plugins/baton/README.md, which genuinely is
# not loaded into context, but nothing in the tests distinguished that
# destination from auto.md, which is loaded every time it runs. This cap is
# what makes that distinction cost something to ignore.
#
# Measured, never derived: 856 is what `wc -l plugins/baton/commands/*.md`
# reports with both new commands landed (auto 205, init 170, clear 141,
# continue 128, ratify 103, status 71, checkpoint 38), and 859 is that floor
# plus room for a line or two. A ceiling arrived at by arithmetic rather than
# measurement shipped on a previous branch here and was unreachable, which
# nobody noticed until review.
#
# Both numbers here were stale once already, in the way that is hardest to
# see: the floor said 850 while init and status had quietly grown three lines
# between them, so the budget sat at 853 -- exactly the total, a ceiling with
# no room to restore a single line. Re-measured rather than nudged.
#
# The floor moved twice more, both times for content rather than for drift.
# The no-dead-ends rule reached an eighth place, and checkpoint.md's report
# now names `/baton:clear` beside the `suspect` it leads with: two lines,
# 853 to 855. Then clear.md's CRLF bullet stopped claiming the guard cannot
# read a carriage return -- true when written, false since 5eac836 -- and
# gives step 5's own check as the reason instead: one line, 855 to 856.
# Both ceilings move with the floor rather than absorbing it, which is what
# measuring rather than deriving costs when the measurement goes up: at 856
# this one would have had room for nothing at all, and its neighbour below
# room for two bytes, and the two would stop describing the same room.
#
# It grew from 620 because the human-never-opens-a-file work added two
# commands that did not exist: ratify.md and clear.md, the human's two halves
# of what the agent may not do to its own run. Both moves are now in; a third
# is drift, not the pattern continuing. Each is its own file because
# `disable-model-invocation` is a per-file flag -- the separate file is the
# barrier, not a presentational choice.
CMD_BUDGET=859

# A second ceiling, in bytes, because the first one cannot see a rewrap.
# `fmt -w 100` across these seven files takes them from 856 lines to 703 while
# the byte count moves by 46. No word is deleted and nothing is said more
# briefly: it opens 153 lines of headroom under CMD_BUDGET, and the roughly
# 7.5 KB of new prose that could then be poured into that headroom is exactly
# what the line cap exists to make someone argue for. The same trick was
# demonstrated on this plugin's skills before their byte budget went in, and
# still reproduces -- baton-autopilot rewraps from 339 lines to 298 while its
# bytes go UP, 15637 to 15639.
#
# So the two numbers see different things, and moving whichever one is in the
# way leaves the other still to be argued with. CMD_BUDGET sees a paragraph
# appended at the wrap width these files are written in; BYTE_BUDGET sees
# content arriving at any wrap width at all, and is blind in turn to a rewrap
# that genuinely does say less.
#
# Measured on a clean tree, like CMD_BUDGET: 43034 bytes (auto 10126, init
# 8736, clear 6863, continue 6558, ratify 4764, status 4028, checkpoint 1959),
# so this is that floor plus 154 -- three lines at the 50 bytes a line in
# these files averages, which is the room CMD_BUDGET's floor-plus-three
# describes. The two are set to agree, deliberately. A line ceiling saying
# three lines while the byte ceiling permitted less than one would make that
# `+ 3` decoration, discoverable only by going red on the other number, and a
# reader who cannot tell which of two ceilings is the real one moves whichever
# is in the way.
#
# The margin is worth knowing exactly, because 154 bytes is not three lines of
# every kind: three full-width lines, at the seventy-odd columns this prose
# wraps to, run about 210 and trip this. What the headroom buys is a restored
# line or two, which is what CMD_BUDGET's three were for as well. Content that
# is really new moves both numbers in one commit and argues for itself there.
#
# It is not set tighter than that, though test-budget.sh's own BYTE_BUDGET is
# -- 49 bytes over the skills floor as this lands. This ceiling is here to
# catch a rewrap that frees 153 lines while saying nothing new, and it does,
# by a margin measured rather than waved at: the rewrap itself lands at 42988
# bytes, and the 153 lines of prose that headroom invites weigh about 7650
# more at the 50 bytes a line above -- some 7.4 KB past this number. Metering
# single lines of prose is CMD_BUDGET's job, and it does it more legibly, in
# the unit the writer is working in.
BYTE_BUDGET=43188

cmd_total=0
cmd_bytes=0
for f in "$CMD"/*.md; do
    n="$(wc -l < "$f" | tr -d ' ')"
    b="$(wc -c < "$f" | tr -d ' ')"
    cmd_total=$((cmd_total + n))
    cmd_bytes=$((cmd_bytes + b))
done
if [ "$cmd_total" -le "$CMD_BUDGET" ]; then
    pass "commands total $cmd_total lines, within the $CMD_BUDGET-line budget"
else
    fail "commands total $cmd_total lines, over the $CMD_BUDGET-line budget"
    echo "    commands/ is not where prose evicted from skills/ belongs -- that"
    echo "    goes in plugins/baton/README.md, which is not loaded into context."
fi
if [ "$cmd_bytes" -le "$BYTE_BUDGET" ]; then
    pass "commands total $cmd_bytes bytes, within the $BYTE_BUDGET-byte budget"
else
    fail "commands total $cmd_bytes bytes, over the $BYTE_BUDGET-byte budget"
    echo "    A rewrap lowers the line count and not this one. If the lines are"
    echo "    within budget and the bytes are not, the content grew -- say in the"
    echo "    commit message what arrived and why a command file is where it goes."
fi

# The README's command table, checked against the directory rather than
# against itself. Both of its counts have now rotted on this branch: "four
# baton commands" survived the fifth landing, and "Three of the five are
# human-typed only" survived the sixth and seventh. A number in prose that
# nothing derives describes whichever release its author last read.
#
# Pinned per command rather than as a total, deliberately -- asserting "seven"
# would be a third literal to update, and the failure it produces names a
# count rather than the command that is missing from the table.
README="$REPO_ROOT/plugins/baton/README.md"
for f in "$CMD"/*.md; do
    name="$(basename "$f" .md)"

    # The table ROW, not the file: every one of these seven is named in the
    # README's prose as well, so a needle matched against the whole document
    # stays green with the row deleted. Mutation-tested that way -- with the
    # `/baton:checkpoint` row cut, a whole-file match passed off the closing
    # paragraph, which names the command while explaining why the model may
    # invoke it.
    row="$(grep -F "| \`/baton:$name" "$README" || true)"
    if [ -n "$row" ]; then
        pass "the README's Day to day table has a row for /baton:$name"
    else
        fail "the README's Day to day table has a row for /baton:$name"
        echo "    a command with no row is one a human reading the README never"
        echo "    learns they have."
    fi

    # And the row says whose command it is. The flag is the barrier; the
    # README saying so is how a human knows before typing it.
    #
    # Read out of the frontmatter block alone. Five of these files also name
    # the flag in prose, explaining why they carry it, and today the `^`
    # anchor happens to tell the two apart -- every one of those mentions is
    # backticked mid-sentence, so none of them starts a line. That is a fact
    # about where the paragraphs wrap, not about the rule, and a reflow would
    # end it silently. Two assertions on this branch were green against files
    # with the guarded thing deleted, both off prose that merely named it.
    if frontmatter_of "$f" | grep -q '^disable-model-invocation: true'; then
        case "$row" in
            *"Human-typed only"*)
                pass "the README marks /baton:$name human-typed only, as its frontmatter is" ;;
            *)
                fail "the README marks /baton:$name human-typed only, as its frontmatter is" ;;
        esac
    else
        case "$row" in
            *"Human-typed only"*)
                fail "the README does not call /baton:$name human-typed only, since the model may invoke it" ;;
            *)
                pass "the README does not call /baton:$name human-typed only, since the model may invoke it" ;;
        esac
    fi
done

# The README describes the guard that makes /baton:clear necessary, and it is
# the description a first-time reader meets. It said `baton-write` "refuses any
# state.md write that lowers suspect or needs_human" -- the rule by its value,
# where the tool tests for a transition: a flag already set in the committed
# file has to come back as a positive `true`, so writing `false`, dropping the
# line, and frontmatter it cannot read are one refusal and not three. The same
# value-framed wording sat in baton-resume's step 4 earlier on this branch and
# is pinned against there, at test-skills.sh's "resume states the refusal the
# way baton-write actually tests for it", for a concrete reason: an agent that
# reads the rule as being about the word `false` deletes the flag line instead
# -- it is resolving the flag, after all -- and meets a guard it was just told
# it was obeying.
#
# Two needles because the sentence carries two things, and losing either one
# restores the old reading: the transition, and that the three shapes are one
# refusal. The `assert_not_contains` guards the wording specifically rather
# than the topic -- the README says "lowers" elsewhere, correctly, about what
# the human does.
readme="$(cat "$README")"
assert_contains "$readme" '`state.md` write that does not carry a `suspect` or `needs_human` already set' \
    "the README states the refusal as the transition baton-write tests for"
assert_contains "$readme" 'leaving the line out, and frontmatter the tool cannot read are one refusal' \
    "the README says the three shapes of a dropped flag are one refusal"
assert_not_contains "$readme" 'write that lowers `suspect` or `needs_human`' \
    "the README no longer describes the guard by the value it refuses"

init="$(cat "$CMD/init.md")"
assert_contains "$init" "superpowers" "init checks for the companion plugin"
assert_contains "$init" "verify_cmd" "init asks for the verification command"
assert_contains "$init" "parallel_with" "init runs the decomposition dialogue"
assert_contains "$init" "ratif" "init ends by asking the human to ratify"

checkpoint="$(cat "$CMD/checkpoint.md")"
assert_contains "$checkpoint" "baton-checkpoint" "checkpoint command defers to the skill"
assert_contains "$checkpoint" "does not exist" "checkpoint covers the not-a-baton-run case"
assert_contains "$checkpoint" "ratified" "checkpoint covers the not-yet-ratified case"

status="$(cat "$CMD/status.md")"
assert_contains "$status" "needs_human" "status surfaces a stopped run first"
assert_contains "$status" "needs_review" "status surfaces decisions awaiting review"
assert_contains "$status" "does not exist" "status covers the not-a-baton-run case"
assert_contains "$status" "docs/baton/journal/" "status names the journal directory"
assert_contains "$status" "CLAUDE_PLUGIN_ROOT" "status invokes baton-observe via the plugin root"
assert_contains "$status" "work_sha" "status compares observed_sha against work_sha, not raw HEAD"
# NOT `assert_contains "$status" "autopilot"`: item 4's "a wave the autopilot
# closed" keeps that bare word green even with item 2 -- the whole
# unattended-run report -- deleted outright. Pinned to item 2's own heading.
assert_contains "$status" "Whether this run is unattended" \
    "status says whether the run is unattended"
# NOT the bare word "normalized": item 2's own opening sentence already uses
# it once for a different clause. Pinned to the tail of the normalization
# list, which nothing else in the file has any reason to repeat.
assert_contains "$status" "one layer of matching quotes, fold case" \
    "status normalizes autopilot before comparing, not literally"
assert_contains "$status" "the claim of a grant has nothing behind it" \
    "status refuses to report a dangling grant (autopilot on, autopilot_grant unset) as healthy"
# NOT the bare "docs/baton/gates/": item 4's other sentence, about the
# directory not existing yet, carries that same substring and would keep
# this green even with the verdict-naming instruction deleted.
assert_contains "$status" "Name the verdict file under" \
    "status points at the verdicts behind auto-closed waves"
# This used to pin the clause telling `auto` apart from `pass`. `pass` is gone
# -- nothing read it, and it was written falsely once -- so what item 4 has to
# keep apart is `auto` from `—`: the autopilot closed this wave and filed a
# verdict, against nothing closed it at all.
assert_contains "$status" "means nothing produced a verdict at all" \
    "status tells an auto-closed wave apart from one nothing closed"
assert_not_contains "$status" '`pass`' \
    "status names no gate value a human is expected to write"

auto="$(cat "$CMD/auto.md")"

# The one invariant that cannot be enforced by anything else: a command the
# model can invoke is a grant the model can give itself.
assert_contains "$auto" "disable-model-invocation: true" \
    "auto is human-invocable only, so the agent cannot grant itself autonomy"
assert_contains "$auto" "readiness review" "auto runs a readiness review rather than asking for questions"
assert_contains "$auto" "exit_criteria" "the review quotes the exit criteria it will close against"
assert_contains "$auto" "not sure" "the review has to say where the agent is unsure"
assert_contains "$auto" "autopilot_grant" "auto records which journal entry granted the run"
assert_contains "$auto" "pbcopy" "auto puts the session goal on the clipboard"
assert_contains "$auto" "does not exist" "auto covers the not-a-baton-run case"
assert_contains "$auto" "ratified" "auto covers the not-yet-ratified case"
assert_contains "$auto" "the third availability rule" \
    "auto checks a wave's consumes against every blocked wave's produces before accepting it as a scope"

continue_cmd="$(cat "$CMD/continue.md")"
assert_contains "$continue_cmd" "disable-model-invocation: true" \
    "continue is human-invocable only: resuming unattended work is the human's call"
assert_contains "$continue_cmd" "baton-resume" "continue verifies state before resuming anything"
assert_contains "$continue_cmd" "does not grant" \
    "continue uses an existing grant and never creates one"
assert_contains "$continue_cmd" "needs_human" \
    "continue refuses to resume over an unresolved stop"

finish
