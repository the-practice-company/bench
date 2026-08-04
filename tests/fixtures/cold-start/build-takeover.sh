#!/usr/bin/env bash
# Build the same clean, mid-wave repository build.sh builds -- nothing about
# the run itself is broken here, see RUNBOOK.md's third scenario -- plus a
# .baton/lock file left behind by a session that is gone: the fixture for
# "the writer lease is stale, and the resuming agent has to notice, take it
# over deliberately, and journal who it displaced" instead of "cold start
# with no lease at all" (build.sh) or "state.md disagrees with the
# repository" (build-diverged.sh).
set -euo pipefail

dest="${1:?usage: build-takeover.sh <destination-dir>}"
mkdir -p "$dest"
cd "$dest"

git init -q -b main
git config user.name "baton fixture"
git config user.email "baton@example.invalid"
git config commit.gpgsign false

mkdir -p src docs/baton/journal

# .baton/ gitignored from the start, as a real /baton:init'd repository has
# it -- see build-diverged.sh's comment on the same lines. It matters most
# here of all three fixtures: the stale lease written below lives in
# .baton/, and without this it is untracked noise rather than the invisible
# leftover of a crashed session it is meant to be.
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
# Captured now, before the docs/baton commit below exists -- see build.sh's
# comment on the identical line for why this, not raw HEAD, is what
# observed_sha must record.
work_sha="$(git rev-parse HEAD)"

cat > docs/baton/constitution.md <<'EOF'
---
schema: baton/constitution/v1
run_id: fixture-auth-takeover
status: ratified
verify_cmd: "node --test"
placeholder_patterns: "TODO|FIXME|NotImplemented"
---

# Fixture run (takeover)

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
writer: ghost-session-from-a-crashed-run
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

# The stale lease itself. .baton/ is gitignored by a real /baton:init'd
# repository (see build-diverged.sh's comment on the same point), so this
# is written straight to the working tree, after the commit above, and
# never touches git history -- exactly how a real crashed session would
# leave it behind: mid-run, not checkpointed as part of any commit.
#
# session names a fixed, obviously-not-a-real-session id rather than
# anything derived from this script's own environment, so that whatever
# session id a real `claude` run generates when RUNBOOK.md's scenario 3 is
# actually exercised can never collide with it by accident.
#
# acquired_epoch is built from $(date -u +%s) arithmetic, not a hardcoded
# epoch -- test-lock.sh's expired-lease fixtures do the same, for the same
# reason: a fixed epoch is only "expired" depending on what time of day the
# suite happens to run. 24 hours (86400s) is used rather than encoding
# baton-lock's own STALE_SECONDS constant here: the point of this fixture is
# "unambiguously expired", not "exactly at the boundary" -- that exact
# boundary is what baton-lock's own tests already pin, in the one place a
# change to STALE_SECONDS should have to be noticed. 24 hours is comfortably
# past six-hour staleness under any plausible value of that constant, so
# this fixture keeps working even if it changes.
#
# acquired (the human-readable timestamp) is a fixed, cosmetic string, not
# derived from acquired_epoch: baton-lock never reads it back to decide
# anything (see baton-lock's own comment on write_lock), and deriving it
# would mean formatting an arbitrary epoch back into UTC, which needs GNU
# `date -d` or BSD `date -r` -- two different flags for the same job. Not
# worth the portability cost for a field nothing checks.
mkdir -p .baton
cat > .baton/lock <<EOF
session=ghost-session-from-a-crashed-run
pid=99999999
acquired=2026-08-03T00:00:00Z
acquired_epoch=$(( $(date -u +%s) - 86400 ))
EOF
