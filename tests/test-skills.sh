#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SKILLS="$REPO_ROOT/plugins/baton/skills"
. "$SCRIPT_DIR/helpers.sh"

for name in baton baton-checkpoint baton-resume; do
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
assert_contains "$checkpoint" "Read the current state, whole" "checkpoint skill instructs reading the current state file first"
assert_contains "$checkpoint" "baton-lock" "checkpoint skill mentions the lock script"
assert_contains "$checkpoint" "release" "checkpoint skill covers releasing the lease"

resume="$(cat "$SKILLS/baton-resume/SKILL.md")"
assert_contains "$resume" "128" "resume skill explains the merge-base exit-128 case"
assert_contains "$resume" "fatal:" "resume skill explains the merge-base fatal: message"
assert_contains "$resume" "is an ancestor of \`HEAD\`. The claim holds." "resume skill explains merge-base exit 0"

finish
