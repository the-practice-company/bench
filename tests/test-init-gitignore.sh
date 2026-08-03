#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
INIT_MD="$REPO_ROOT/plugins/baton/commands/init.md"
. "$SCRIPT_DIR/helpers.sh"

# /baton:init's markdown carries one executable shell snippet: appending
# .baton/ to .gitignore in a way that tolerates a missing trailing newline
# (a bare `>>` onto a file that doesn't end in one glues onto the last line
# instead of adding a new one). Nothing runs this markdown, so nothing has
# ever run the snippet either. Extract it verbatim from the command file and
# execute it against real fixtures, rather than duplicating it by hand here
# -- a hand-copied duplicate rots silently the moment one copy changes and
# the other doesn't.
extract_gitignore_snippet() {
    awk '
        /^```bash$/ { in_block=1; buf=""; next }
        /^```$/ {
            if (in_block && buf ~ /grep -qxF/) { printf "%s", buf; exit }
            in_block=0; buf=""; next
        }
        in_block { buf = buf $0 "\n" }
    ' "$1"
}

snippet="$(extract_gitignore_snippet "$INIT_MD")"
if [ -n "$snippet" ]; then
    pass "extracted the .gitignore snippet from init.md"
else
    fail "extracted the .gitignore snippet from init.md"
fi
assert_contains "$snippet" "grep -qxF" "the extracted text is the real snippet, not an empty match"

run_snippet() {
    # Runs the extracted snippet in the current directory, exactly as
    # /baton:init would from a repository root.
    bash -c "$snippet"
}

# The property that matters is that .baton/ actually ends up ignored --
# checked the way git itself resolves ignore rules, not by grepping for a
# line we hope git also honours. That distinction is exactly what the
# trailing-newline bug broke: the append "succeeded" (a line landed in the
# file) while the rule it produced did not match anything, because it had
# been glued onto the previous line.
assert_ignored() {
    local description="$1" out rc
    rc=0
    out="$(git check-ignore -v .baton/ 2>&1)" || rc=$?
    if [ "$rc" -eq 0 ] && printf '%s' "$out" | grep -q '\.gitignore:'; then
        pass "$description"
    else
        fail "$description"
        echo "    git check-ignore -v .baton/ -> exit $rc"
        printf '%s\n' "$out" | sed 's/^/    /'
    fi
}

make_fixture_repo

# --- case 1: no .gitignore at all ---
rm -f .gitignore
run_snippet
assert_ignored "a missing .gitignore ends up ignoring .baton/"
assert_equals "$(cat .gitignore)" ".baton/" \
    "a missing .gitignore is created holding exactly the one line"

# --- case 2: an empty .gitignore ---
: > .gitignore
run_snippet
assert_ignored "an empty .gitignore ends up ignoring .baton/"
assert_equals "$(cat .gitignore)" ".baton/" \
    "an empty .gitignore ends up holding exactly the one line"

# --- case 3: a .gitignore with no trailing newline -- the exact bug this
# snippet exists to avoid. A bare `>>` here would produce
# "node_modules.baton/" on a single line, which ignores nothing real. ---
printf 'node_modules' > .gitignore
if [ -z "$(tail -c1 .gitignore)" ]; then
    fail "sanity: the case-3 fixture .gitignore is missing its trailing newline"
else
    pass "sanity: the case-3 fixture .gitignore is missing its trailing newline"
fi
run_snippet
assert_ignored ".baton/ is ignored even when .gitignore had no trailing newline"
assert_contains "$(cat .gitignore)" "node_modules" \
    "the pre-existing entry survives the append"
if git check-ignore -q node_modules 2>/dev/null; then
    pass "the pre-existing entry still works as its own rule, not glued to the new one"
else
    fail "the pre-existing entry still works as its own rule, not glued to the new one"
fi
assert_equals "$(wc -l < .gitignore | tr -d ' ')" "2" \
    ".gitignore ends with two clean lines, not one line with both entries glued together"

# --- case 4: a .gitignore that already contains the entry -- must not
# duplicate it ---
printf '.baton/\n' > .gitignore
run_snippet
assert_ignored ".baton/ stays ignored when the entry was already present"
assert_equals "$(grep -c '^\.baton/$' .gitignore)" "1" \
    "an already-present entry is not duplicated"

finish
