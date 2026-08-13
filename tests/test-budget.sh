#!/usr/bin/env bash
# A ceiling on the total, not just on each file.
#
# Per-file caps in test-skills.sh stop any one skill running away. They do
# not stop four files each gaining twenty justified lines, which is how this
# plugin reached 1550 lines of skill against the 595 of the superpowers chain
# it wraps -- 38 of 122 commits were review findings, every one of them real,
# and not one of them removed anything.
#
# The skills are read by the primary session and returned to it after every
# compaction, so this number is context spent per run on the layer rather
# than on the work. Raising it is a decision, and it should have to be one.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SKILLS="$REPO_ROOT/plugins/baton/skills"
. "$SCRIPT_DIR/helpers.sh"

BUDGET=1135

total=0
for f in "$SKILLS"/*/SKILL.md; do
    n="$(wc -l < "$f" | tr -d ' ')"
    total=$((total + n))
    echo "  $(basename "$(dirname "$f")"): $n"
done

if [ "$total" -le "$BUDGET" ]; then
    pass "skills total $total lines, within the $BUDGET-line budget"
else
    fail "skills total $total lines, over the $BUDGET-line budget"
    echo "    Cutting is the default response. Raising BUDGET is a decision:"
    echo "    say in the commit message what was added and why it had to be resident."
fi

finish
