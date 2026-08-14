#!/usr/bin/env bash
# Build a repository that is clean and consistent in every respect except
# one: state.md's observed_branch names a branch this checkout is not on and
# never was. Deliberately -- not a companion to build-diverged.sh's two
# divergences, but their opposite. baton-resume's branch check ("Report it
# and stop, write nothing") runs and answers before the claimed-field checks
# that catch build-diverged.sh's divergences ever get a chance to fire, so a
# fixture carrying the branch mismatch alongside those two would never let an
# agent reach them -- see RUNBOOK.md scenario 5, which explains why this is a
# separate fixture rather than a third divergence bolted onto that one.
# Everything else here matches build.sh's cold-start fixture exactly: wave 1
# genuinely closed at an ancestor of HEAD, observed_sha genuinely equal to
# the current work_sha, tree_clean true, no .baton/precompact-facts. The
# branch mismatch has to be the only thing to find.
set -euo pipefail

dest="${1:?usage: build-diverged-branch.sh <destination-dir>}"
mkdir -p "$dest"
cd "$dest"

git init -q -b main
git config user.name "baton fixture"
git config user.email "baton@example.invalid"
git config commit.gpgsign false

mkdir -p src docs/baton/journal

# Match what a real /baton:init'd repository looks like: .baton/ gitignored
# from the start.
printf '.baton/\n' > .gitignore
git add .gitignore
git commit -q -m "baton: gitignore .baton/"

cat > src/auth.js <<'EOF'
export function login(user) {
  return { user, token: "signed" };
}
EOF
git add src/auth.js
git commit -q -m "wave 1: login"
wave1_sha="$(git rev-parse --short HEAD)"

cat > src/session.js <<'EOF'
export function renew(token) {
  return token;
}
EOF
git add src/session.js
git commit -q -m "wave 2: session renewal, partial"
# The last commit that touches anything outside docs/baton/, i.e.
# baton-observe's work_sha. state.md's observed_sha records this genuinely --
# nothing about the checkpoint staleness divergence belongs in this fixture.
work_sha="$(git rev-parse HEAD)"

cat > docs/baton/constitution.md <<EOF
---
schema: baton/constitution/v1
run_id: fixture-auth-diverged-branch
status: ratified
verify_cmd: "node --test"
placeholder_patterns: "TODO|FIXME|NotImplemented"
---

# Fixture run (diverged branch)

## Goal
Ship authentication.

## Operating mode
Orchestrator; delegates implementation to subagents.

## Non-negotiables
Never change the token format.

## Waves
- wave: 1
  name: login
  depends_on: []
  exit_criteria:
    - The system shall return a token for a valid user
- wave: 2
  name: session
  depends_on: [1]
  exit_criteria:
    - When a token is renewed, the system shall preserve its subject
EOF

# state.md is otherwise identical in shape to build.sh's clean fixture --
# closed_at_sha genuinely an ancestor of HEAD, observed_sha genuinely equal
# to work_sha, suspect and needs_human both false -- except observed_branch,
# which names a branch never created in this checkout. Do not create that
# branch; the point is that it does not exist.
cat > docs/baton/state.md <<EOF
---
schema: baton/state/v1
writer: fixture-session
updated_at: 2026-08-03T09:00:00Z
observed_sha: $work_sha
observed_branch: baton/run-that-is-not-here
tree_clean: true
suspect: false
needs_human: false
---

# State

**Goal:** Ship authentication.
**Operating mode:** Orchestrator; delegates implementation to subagents.
**Non-negotiables:** Never change the token format.

## Waves

| # | name | status | spec | plan | closed_at_sha | gate |
|---|------|--------|------|------|---------------|------|
| 1 | login | done | — | — | $wave1_sha | — |
| 2 | session | doing | — | — | — | — |

**Current wave:** 2 — session

## Now

- **Next action:** add a subject field to the object returned by renew() in src/session.js so a renewed token preserves its subject
- **In flight:** renew() returns the token unchanged and drops the subject
- **Suspect:** none
- **Open questions:** none

## Pointers

- Constitution: docs/baton/constitution.md
- Recent decisions: docs/baton/journal/
EOF

git add docs/baton
git commit -q -m "baton: checkpoint at wave 2"
