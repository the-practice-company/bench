#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TPL="$REPO_ROOT/plugins/baton/templates"
. "$SCRIPT_DIR/helpers.sh"

constitution="$(cat "$TPL/constitution.md")"
state="$(cat "$TPL/state.md")"

assert_contains "$constitution" "schema: baton/constitution/v1" "constitution declares its schema version"
assert_contains "$constitution" "verify_cmd:" "constitution carries verify_cmd, which the agent must not be able to edit"
assert_contains "$constitution" "placeholder_patterns:" "constitution carries the placeholder patterns"
assert_contains "$constitution" "## Operating mode" "constitution states who the agent is in this run"
assert_contains "$constitution" "## Non-negotiables" "constitution has the rules that survive into state"
assert_contains "$constitution" "exit_criteria" "constitution declares per-wave exit criteria"
assert_contains "$constitution" "The system shall" "constitution shows exit criteria in EARS form"
assert_contains "$constitution" "## Amendments" "constitution has an append-only amendments section"

assert_contains "$state" "schema: baton/state/v1" "state declares its schema version"
assert_contains "$state" "suspect: false" "state carries the suspect flag"
assert_contains "$state" "needs_human: false" "state carries the needs_human flag"
assert_contains "$state" "**Non-negotiables:**" "state restates the live constraints, not only the goal"
assert_contains "$state" "**Operating mode:**" "state restates who the agent is"
assert_contains "$state" "**Suspect:**" "state has a place to describe a divergence"
assert_not_contains "$state" "branch/worktree" "state's wave table carries no per-wave worktree column"

lines="$(wc -l < "$TPL/state.md" | tr -d ' ')"
if [ "$lines" -le 60 ]; then
    pass "state template is within the 60-line cap ($lines lines)"
else
    fail "state template is within the 60-line cap ($lines lines)"
fi

# The Waves section must be a fenced code block: the fence is the only
# unambiguous boundary a consumer can extract without guessing where the
# YAML ends and Markdown prose resumes.
assert_contains "$constitution" '```yaml' "constitution's wave list is fenced as a machine-readable block"

# Structurally parse the fenced block. PyYAML is not guaranteed to be
# installed wherever this suite runs, so this uses a small dependency-free
# parser (python3 stdlib only) that understands just enough of the YAML
# subset the template uses (block sequences of mappings, flow lists,
# nested block lists) to reject bad indentation or a missing colon, not
# just to grep for expected substrings.
fence_check_output="$(python3 - "$TPL/constitution.md" <<'PY'
import re, sys

def parse_scalar(s):
    s = s.strip()
    if s == '[]':
        return []
    m = re.fullmatch(r'\[(.*)\]', s)
    if m:
        inner = m.group(1).strip()
        return [] if not inner else [parse_scalar(x) for x in inner.split(',')]
    if re.fullmatch(r'-?\d+', s):
        return int(s)
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ('"', "'"):
        return s[1:-1]
    return s

def indent(line):
    return len(line) - len(line.lstrip(' '))

def parse_top_sequence(lines):
    items = []
    i, n = 0, len(lines)
    while i < n:
        if lines[i].strip() == '':
            i += 1
            continue
        if indent(lines[i]) != 0 or not lines[i].lstrip().startswith('- '):
            raise ValueError("expected top-level '- ' at line %d: %r" % (i, lines[i]))
        item = {}
        pending = lines[i].lstrip()[2:]
        i += 1
        item_indent = 2
        while True:
            key, sep, val = pending.partition(':')
            if not sep:
                raise ValueError("expected 'key: value' near line %d: %r" % (i, pending))
            key, val = key.strip(), val.strip()
            if val == '':
                sub = []
                while i < n and lines[i].strip() == '':
                    i += 1
                while i < n and indent(lines[i]) == item_indent + 2 and lines[i].lstrip().startswith('- '):
                    sub.append(parse_scalar(lines[i].lstrip()[2:]))
                    i += 1
                item[key] = sub
            else:
                item[key] = parse_scalar(val)
            while i < n and lines[i].strip() == '':
                i += 1
            if i < n and indent(lines[i]) == item_indent and not lines[i].lstrip().startswith('- '):
                pending = lines[i].strip()
                i += 1
                continue
            break
        items.append(item)
    return items

path = sys.argv[1]
text = open(path).read()
m = re.search(r'```yaml\n(.*?)\n```', text, re.S)
if not m:
    print("NO_FENCE")
    sys.exit(1)
lines = m.group(1).split('\n')
try:
    waves = parse_top_sequence(lines)
except Exception as e:
    print("PARSE_ERROR: %s" % e)
    sys.exit(1)

if len(waves) != 2:
    print("WRONG_COUNT: %d" % len(waves))
    sys.exit(1)
for w in waves:
    ec = w.get('exit_criteria')
    if not isinstance(ec, list) or not ec:
        print("MISSING_EXIT_CRITERIA: %r" % w)
        sys.exit(1)
print("OK")
PY
)"
if [ "$fence_check_output" = "OK" ]; then
    pass "constitution's fenced YAML wave block parses and yields two wave entries with exit_criteria"
else
    fail "constitution's fenced YAML wave block parses and yields two wave entries with exit_criteria"
    echo "    $fence_check_output"
fi

# Regression check for the spurious-heading bug: outside the fenced block
# (and other than the document's own title, its first non-blank line), no
# line may start with a bare "# " -- that is Markdown ATX-heading syntax,
# and a "#"-prefixed line meant as a YAML comment renders as a heading the
# same weight as the document title once it leaves the fence.
heading_check_output="$(python3 - "$TPL/constitution.md" <<'PY'
import re, sys

path = sys.argv[1]
text = open(path).read()

fm = re.match(r'^---\n.*?\n---\n', text, re.S)
if not fm:
    print("NO_FRONTMATTER")
    sys.exit(1)
body = text[fm.end():]

body_no_fence = re.sub(r'```yaml\n.*?\n```\n?', '', body, flags=re.S)

lines = body_no_fence.split('\n')
first_nonblank = None
for idx, line in enumerate(lines):
    if line.strip() != '':
        first_nonblank = idx
        break

offenders = []
for idx, line in enumerate(lines):
    if idx == first_nonblank:
        continue
    if re.match(r'^# ', line):
        offenders.append((idx, line))

if offenders:
    print("SPURIOUS_HEADINGS:")
    for idx, line in offenders:
        print("  line %d: %r" % (idx, line))
    sys.exit(1)

print("OK")
PY
)"
if [ "$heading_check_output" = "OK" ]; then
    pass "no line in the constitution body outside the fenced block renders as a spurious heading"
else
    fail "no line in the constitution body outside the fenced block renders as a spurious heading"
    echo "    $heading_check_output"
fi

assert_contains "$state" "todo | doing | done | blocked" "state names all four wave statuses"
assert_contains "$state" "blocked\` waits on a dependency; \`needs_human: true\` (frontmatter) stops the whole run" "state distinguishes a blocked wave from a needs_human stop, in the same breath"

lines2="$(wc -l < "$TPL/state.md" | tr -d ' ')"
if [ "$lines2" -le 60 ]; then
    pass "state template is still within the 60-line cap after the status legend ($lines2 lines)"
else
    fail "state template is still within the 60-line cap after the status legend ($lines2 lines)"
fi

# The grant has to live on disk or it does not survive the compaction it
# exists to survive. Frontmatter, not prose, because baton-resume and the
# session-start hook both read it without parsing the body.
assert_contains "$state" "autopilot: off" "state carries the autopilot flag, defaulting to off"
assert_contains "$state" "autopilot_grant:" "state points at the journal entry that granted autonomy"

# Two values. `pass` was the third and it is gone: no script and no hook ever
# read this column, so the mark changed nothing, was maintained by hand once
# per wave, and had already been written falsely once -- see the v0.1.0
# runbook run, where an agent wrote it into a column nothing claimed
# ownership of. What `pass` was there to contrast with survives it, and is
# what this still pins: `auto` says the wave closed with no human in the room
# and the verdict is on disk.
assert_contains "$state" "auto\` closed under the autopilot" "state's gate legend still says what auto means"
# The other half of that pair, inverted rather than dropped. The guard used to
# watch that the legend named the third value; it now watches that it does
# not. A value the legend does not offer is one no agent can claim falsely.
assert_not_contains "$state" "\`pass\`" "state's gate legend offers no pass to claim"

lines3="$(wc -l < "$TPL/state.md" | tr -d ' ')"
if [ "$lines3" -le 60 ]; then
    pass "state template is still within the 60-line cap after the autopilot fields ($lines3 lines)"
else
    fail "state template is still within the 60-line cap after the autopilot fields ($lines3 lines)"
fi

# Declared once, per run, so using-git-worktrees never has to ask under the
# autopilot -- its Step 0 honours a declared preference without a prompt.
assert_contains "$constitution" "workspace: in-place" "constitution declares the workspace preference, defaulting to in-place"
assert_contains "$constitution" "in-place | worktree" "constitution names both workspace values"
assert_contains "$constitution" "subagent-driven-development" "constitution's operating mode names the procedure work is delegated to"

# The seeded spec cell used to be `—`, and `—` is not a `REPLACE-` marker, so
# init's sweep for leftover markers passed straight over it. An agent filling
# the template mechanically then shipped a state.md whose every wave the
# autopilot reads as unavailable, and nothing said so until /baton:auto refused
# the entire scope. Seeded as a marker, the existing sweep covers it.
#
# Both assertions, and the second is the one doing the work: the first goes
# green off any mention of the marker anywhere in the file -- including a
# comment about this rule -- while the second fails on a re-seed, which is the
# regression. Deleting the "redundant" one deletes the coverage.
assert_contains "$state" "REPLACE-WITH-SPEC-DOC" \
    "the seeded wave row makes its spec cell a marker init has to clear"
assert_not_contains "$state" "| todo | — |" \
    "the seeded spec cell is not the em dash the autopilot reads as unavailable"

finish
