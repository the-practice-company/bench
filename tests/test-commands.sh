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

finish
