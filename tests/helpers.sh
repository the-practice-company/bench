#!/usr/bin/env bash
# Assert helpers shared by every baton test file.

FAILURES=0

pass() { echo "  [PASS] $1"; }

fail() {
    echo "  [FAIL] $1"
    FAILURES=$((FAILURES + 1))
}

assert_equals() {
    if [ "$1" = "$2" ]; then
        pass "$3"
    else
        fail "$3"
        echo "    expected: $2"
        echo "    actual:   $1"
    fi
}

# Both assertions below match with `grep -F`, which is LINE-BASED. Two
# consequences, and neither is visible at the call site.
#
# A needle that spans lines is read as several independent patterns joined by
# OR. assert_contains then passes when EITHER line is present, and
# assert_not_contains fails when either is -- so the longer, more specific
# looking needle is the weaker assertion. That is a defect in the assertion
# rather than in the document under test, so it is refused outright rather than
# reported as a mismatch: there is no document for which such a call means what
# it appears to mean. At the time this went in, no call in tests/ had one.
needle_spans_lines() {
    case "$1" in
        *$'\n'*) return 0 ;;
        *) return 1 ;;
    esac
}

# The other direction: the needle is one line, but the text it is looking for
# wraps. The document is right and the assertion is red, which reads as a
# missing rule and is not. Four review cycles on this repository were spent
# rediscovering that, so the failure says it now. Whitespace is squeezed on
# both sides, since a wrapped line in prose carries the next line's indent.
found_only_across_lines() {
    local flat_haystack flat_needle
    flat_haystack="$(printf '%s' "$1" | tr -s '[:space:]' ' ')"
    flat_needle="$(printf '%s' "$2" | tr -s '[:space:]' ' ')"
    printf '%s' "$flat_haystack" | grep -Fq -- "$flat_needle"
}

assert_contains() {
    if needle_spans_lines "$2"; then
        fail "$3"
        echo "    the needle spans lines, so grep -F reads it as separate patterns joined by OR:"
        echo "    this passes when ANY one line matches, which is weaker than it looks."
        echo "    Pin a substring that fits on one line."
        return
    fi
    if printf '%s' "$1" | grep -Fq -- "$2"; then
        pass "$3"
    else
        fail "$3"
        echo "    expected to find: $2"
        if found_only_across_lines "$1" "$2"; then
            echo "    found, but split across a line break -- reflow the source, or pin a shorter substring"
        fi
    fi
}

assert_not_contains() {
    if needle_spans_lines "$2"; then
        fail "$3"
        echo "    the needle spans lines, so grep -F reads it as separate patterns joined by OR:"
        echo "    this fails when ANY one line matches, which is stricter than it looks."
        echo "    Pin a substring that fits on one line."
        return
    fi
    if printf '%s' "$1" | grep -Fq -- "$2"; then
        fail "$3"
        echo "    did not expect to find: $2"
    else
        pass "$3"
        # A pass here can be the wrong kind of quiet: the forbidden text may be
        # present and merely wrapped, which is the same false confidence the
        # line-based match gives assert_contains, arriving as a green tick.
        if found_only_across_lines "$1" "$2"; then
            echo "    NOTE: absent on any single line, but present across a line break --"
            echo "    this assertion passed on the wrapping, not on the text being gone."
        fi
    fi
}

assert_file_exists() {
    if [ -f "$1" ]; then pass "$2"; else fail "$2"; echo "    missing: $1"; fi
}

assert_exit_code() {
    # assert_exit_code <expected> <description> <command...>
    local expected="$1" description="$2"; shift 2
    local actual=0
    "$@" >/dev/null 2>&1 || actual=$?
    assert_equals "$actual" "$expected" "$description"
}

assert_valid_json() {
    if python3 -c "import json,sys; json.load(open(sys.argv[1]))" "$1" 2>/dev/null; then
        pass "$2"
    else
        fail "$2"
    fi
}

json_get() {
    python3 -c "import json,sys; print(json.load(open(sys.argv[1])).get(sys.argv[2], ''))" "$1" "$2"
}

# Create a throwaway git repository and cd into it. Sets $FIXTURE.
make_fixture_repo() {
    FIXTURE="$(mktemp -d)"
    trap cleanup_fixture EXIT
    cd "$FIXTURE" || return 1
    git init -q -b main
    git config user.name "baton test"
    git config user.email "baton@example.invalid"
    git config commit.gpgsign false
    echo "seed" > seed.txt
    git add seed.txt
    git commit -q -m "seed"
}

cleanup_fixture() {
    [ -n "${FIXTURE:-}" ] && [ -d "$FIXTURE" ] && rm -rf "$FIXTURE"
    return 0
}

finish() {
    cleanup_fixture
    if [ "$FAILURES" -gt 0 ]; then
        echo "  $FAILURES assertion(s) failed"
        exit 1
    fi
    exit 0
}
