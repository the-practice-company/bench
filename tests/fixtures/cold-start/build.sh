#!/usr/bin/env bash
# Build a repository sitting mid-wave, as it would be found after a session
# died: wave 1 closed, wave 2 in progress, one interrupted edit.
set -euo pipefail

dest="${1:?usage: build.sh <destination-dir>}"
mkdir -p "$dest"
cd "$dest"

git init -q -b main
git config user.name "baton fixture"
git config user.email "baton@example.invalid"
git config commit.gpgsign false

mkdir -p src docs/baton/journal

# Match what a real /baton:init'd repository looks like: .baton/ gitignored
# from the start. The scenario this fixture is for writes a lease there the
# moment the agent takes the writer role, and an untracked .baton/ in every
# git status it runs afterwards is noise it did not put there and may try to
# tidy away.
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
# Captured now, before the docs/baton commit below exists: this is the last
# commit that touches anything outside docs/baton/, i.e. baton-observe's
# work_sha. state.md's observed_sha must record this, not the checkpoint
# commit's own SHA -- raw HEAD moves on every checkpoint, so a baseline
# taken from it would never again equal HEAD and every comparison against
# it would be a false positive.
work_sha="$(git rev-parse HEAD)"

cat > docs/baton/constitution.md <<'EOF'
---
schema: baton/constitution/v1
run_id: fixture-auth
status: ratified
verify_cmd: "node --test"
placeholder_patterns: "TODO|FIXME|NotImplemented"
---

# Fixture run

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

cat > docs/baton/state.md <<EOF
---
schema: baton/state/v1
writer: fixture-session
updated_at: 2026-08-03T09:00:00Z
observed_sha: $work_sha
observed_branch: $(git symbolic-ref --short HEAD)
tree_clean: true
suspect: false
needs_human: false
---

# State

**Goal:** Ship authentication.
**Operating mode:** Orchestrator; delegates implementation to subagents.
**Non-negotiables:** Never change the token format.

## Waves

| # | name | status | branch/worktree | spec | plan | closed_at_sha | gate |
|---|------|--------|-----------------|------|------|---------------|------|
| 1 | login | done | main | — | — | $wave1_sha | — |
| 2 | session | doing | main | — | — | — | — |

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
