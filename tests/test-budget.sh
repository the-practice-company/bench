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

# 1156 is the sum of the four per-file caps in test-skills.sh, which is where
# the reasoning for each of them lives. Keep the two in step: a budget that
# does not equal that sum is a second, quieter ceiling, and whichever is lower
# is the real one. test-skills.sh asserts the equality, reading this line, so
# the two now move together or fail together rather than drifting quietly.
#
# It grew from 1148 with two of those caps: baton-autopilot's exit-3 stop and
# end-of-run report, and baton-resume's step 4, now name the command that
# resolves the wait they report -- `/baton:ratify` and `/baton:clear`. A stop
# that names no command sends the human to the README, and under the autopilot
# the report is written at 03:40 to be read by someone who was not there.
#
# From 1156 with one of them: baton-autopilot's availability rule refused a
# `—` spec and, by saying only that, admitted a wave whose constitution has no
# `spec:` key at all -- which is every wave of every run written before 0.2.0
# moved the field there. Absent and `—` are now one refusal in all four places
# that phrase it. Four lines, and no argument was cut to pay for them.
BUDGET=1161

# What is actually scarce is tokens, and a line count is a wrap-width
# artifact, not a token count: `fmt -w 100` across the four skills removes
# 132 of their 1147 LINES, deletes no words, and would turn this budget
# and every per-file cap in test-skills.sh green with headroom -- headroom
# that could then be spent on real prose, landing well past what the caps
# were measuring when they were set. Reflowing to a wider column barely
# moves a byte count, so BYTE_BUDGET is set close to what the skills
# currently weigh, in bytes, rather than given the same proportional
# headroom as BUDGET above: it has to stay tight enough that rewrapping into
# the line budget's freed headroom, then filling that headroom with more
# content, still fails here even though it would pass the line-based caps.
# Neither budget replaces the other -- this one is blind to a paragraph
# that grows the word count without ever wrapping past its line.
#
# Measured, like BUDGET above, and for the same sentences: the skills weigh
# 60751 bytes with the no-dead-ends rule landed. The last 720 of them are two
# rows in baton-checkpoint's exit-3 table, for the two refusal families
# baton-write grew after that table was written -- the granted-flag guard and
# the four shapes of frontmatter it cannot read. A table read by looking up a
# message, that omits the message, answers wrongly rather than not at all, and
# a row is worth more bytes than a sentence for exactly that reason. So this
# is that floor plus about fifty bytes, as the last three moves were. It is
# deliberately not proportional headroom -- see the paragraph above for why a
# generous byte budget is the one that lets a rewrap buy real content.
#
# Re-measured for the same four lines BUDGET moved for: 60923 bytes, so 60973
# on the same floor-plus-fifty rule. Both ceilings move together here because
# the content is genuinely new -- a rewrap would have moved the line count
# alone, which is exactly the case the two numbers exist to tell apart.
BYTE_BUDGET=60973

total=0
total_bytes=0
# Every .md file under a skill directory, not just SKILL.md: a
# skills/<name>/references/*.md file is loaded into context exactly when the
# skill pointing at it is loaded, so it costs exactly as much context as
# prose that lived in SKILL.md itself. The budget rations context, and
# context does not care which filename it arrived in.
while IFS= read -r f; do
    n="$(wc -l < "$f" | tr -d ' ')"
    b="$(wc -c < "$f" | tr -d ' ')"
    total=$((total + n))
    total_bytes=$((total_bytes + b))
    echo "  ${f#$SKILLS/}: $n lines, $b bytes"
done < <(find "$SKILLS" -type f -name '*.md' | sort)

if [ "$total" -le "$BUDGET" ]; then
    pass "skills total $total lines, within the $BUDGET-line budget"
else
    fail "skills total $total lines, over the $BUDGET-line budget"
    echo "    Cutting is the default response. Raising BUDGET is a decision:"
    echo "    say in the commit message what was added and why it had to be resident."
fi

if [ "$total_bytes" -le "$BYTE_BUDGET" ]; then
    pass "skills total $total_bytes bytes, within the $BYTE_BUDGET-byte budget"
else
    fail "skills total $total_bytes bytes, over the $BYTE_BUDGET-byte budget"
    echo "    A rewrap can lower the line count without lowering this one."
    echo "    If lines are within budget and bytes are not, the content grew --"
    echo "    say in the commit message what was added and why it had to be resident."
fi

finish
