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

assert_contains() {
    if printf '%s' "$1" | grep -Fq -- "$2"; then
        pass "$3"
    else
        fail "$3"
        echo "    expected to find: $2"
    fi
}

assert_not_contains() {
    if printf '%s' "$1" | grep -Fq -- "$2"; then
        fail "$3"
        echo "    did not expect to find: $2"
    else
        pass "$3"
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
