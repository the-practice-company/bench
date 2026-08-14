#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CMD="$REPO_ROOT/plugins/baton/commands"
. "$SCRIPT_DIR/helpers.sh"

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
# Measured, never derived: 853 is what `wc -l plugins/baton/commands/*.md`
# reports with both new commands landed (auto 205, init 170, clear 140,
# continue 128, ratify 103, status 71, checkpoint 36), and 856 is that floor
# plus room for a line or two. A ceiling arrived at by arithmetic rather than
# measurement shipped on a previous branch here and was unreachable, which
# nobody noticed until review.
#
# Both numbers here were stale until this commit, in the way that is hardest
# to see: the floor said 850 while init and status had quietly grown three
# lines between them, so the budget sat at 853 -- exactly the total, a ceiling
# with no room to restore a single line. Re-measured rather than nudged.
#
# It grew from 620 because the human-never-opens-a-file work added two
# commands that did not exist: ratify.md and clear.md, the human's two halves
# of what the agent may not do to its own run. Both moves are now in; a third
# is drift, not the pattern continuing. Each is its own file because
# `disable-model-invocation` is a per-file flag -- the separate file is the
# barrier, not a presentational choice.
CMD_BUDGET=856
cmd_total=0
for f in "$CMD"/*.md; do
    n="$(wc -l < "$f" | tr -d ' ')"
    cmd_total=$((cmd_total + n))
done
if [ "$cmd_total" -le "$CMD_BUDGET" ]; then
    pass "commands total $cmd_total lines, within the $CMD_BUDGET-line budget"
else
    fail "commands total $cmd_total lines, over the $CMD_BUDGET-line budget"
    echo "    commands/ is not where prose evicted from skills/ belongs -- that"
    echo "    goes in plugins/baton/README.md, which is not loaded into context."
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
readme="$(cat "$README")"
for f in "$CMD"/*.md; do
    name="$(basename "$f" .md)"
    assert_contains "$readme" "\`/baton:$name" \
        "the README's Day to day table has a row for /baton:$name"

    # And the row says whose command it is. The flag is the barrier; the
    # README saying so is how a human knows before typing it.
    row="$(grep -F "| \`/baton:$name" "$README" || true)"
    if grep -q '^disable-model-invocation: true' "$f"; then
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
