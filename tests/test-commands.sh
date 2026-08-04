#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CMD="$REPO_ROOT/plugins/baton/commands"
. "$SCRIPT_DIR/helpers.sh"

for name in init checkpoint status auto continue; do
    assert_file_exists "$CMD/$name.md" "command $name exists"
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
assert_contains "$status" "already confirmed it" \
    "status distinguishes an auto verdict (unreviewed) from a pass (a human confirmed it)"

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
