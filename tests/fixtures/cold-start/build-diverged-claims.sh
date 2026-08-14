#!/usr/bin/env bash
# Build a repository where two claims in state.md have diverged from the
# repository, and nothing on disk admits it: suspect and needs_human both
# read false, exactly as clean as the cold-start fixture. Finding the
# divergence anyway is the resuming agent's job, not something this fixture
# does for it -- see RUNBOOK.md's second scenario.
#
# Named build-diverged-claims.sh, not build-diverged.sh: this is not the
# general-purpose diverged fixture, and the old name invited exactly that
# reading once already -- a third divergence was added under it, which broke
# RUNBOOK scenario 2 because that divergence stopped the agent before it
# could reach the two below. What ties these two together, and what the name
# now says, is that both are **claimed** fields: plugins/baton/skills/baton/
# SKILL.md's divergence policy names "a wave marked `done` ... the
# `closed_at_sha` recorded against a closed wave" as claims `baton-resume`
# checks mechanically and never repairs silently. `observed_branch` -- the
# third divergence that was added here and then reverted -- is notably not
# one of those: the policy gives it its own bullet ("looks observed and is
# not"), and `baton-resume`'s branch check runs and stops before either
# claimed-field check below ever fires. That ordering is why it needed a
# fixture of its own, build-diverged-branch.sh, rather than a third
# divergence bolted onto this one.
#
# Two independent divergences, both claims disagreeing with the repository:
#
#   1. Wave 1 is marked done at a closed_at_sha that is NOT an ancestor of
#      main's HEAD. Built as a genuine, resolvable commit -- kept alive by a
#      branch ref that is never merged -- rather than a fabricated sha, so
#      the check this exercises is "not an ancestor" (exit 1), the real
#      divergence case, not "not a valid commit at all" (exit 128), a
#      different failure baton-resume treats the same way but which this
#      fixture is not testing.
#
#   2. observed_sha (what the last checkpoint recorded) is one commit behind
#      work_sha (what the repository actually holds): a commit landed after
#      that checkpoint that no later checkpoint captured. The sha itself is
#      an observed field and would be repaired silently -- what stops the
#      run is that wave 2's status, Next action and In flight were written
#      against the stale value and nobody has corrected them since, which is
#      the claim baton-resume's step 3 is actually checking. .baton/
#      precompact-facts is written recording the later state, the same way
#      the PreCompact hook would have -- that is what gives step 3 something
#      to find without a live hook run.
set -euo pipefail

dest="${1:?usage: build-diverged-claims.sh <destination-dir>}"
mkdir -p "$dest"
cd "$dest"

git init -q -b main
git config user.name "baton fixture"
git config user.email "baton@example.invalid"
git config commit.gpgsign false

mkdir -p src docs/baton/journal

# Match what a real /baton:init'd repository looks like: .baton/ gitignored
# from the start, so the precompact-facts file written below does not read
# as a dirty tree.
printf '.baton/\n' > .gitignore
git add .gitignore
git commit -q -m "baton: gitignore .baton/"
base_sha="$(git rev-parse HEAD)"

# --- divergence 1: an orphaned wave-1 commit -------------------------------
# A wave-1 commit made on a branch that is never merged into main -- the
# repository shape left behind when the commit that closed a wave gets
# rebased or force-pushed away after a checkpoint already recorded its sha.
# The branch ref keeps this a real, resolvable commit object rather than a
# sha nothing can look up.
git checkout -q -b wave1-orphaned "$base_sha"
cat > src/auth.js <<'EOF'
export function login(user) {
  return { user, token: "signed" };
}
EOF
git add src/auth.js
git commit -q -m "wave 1: login"
orphaned_wave1_sha="$(git rev-parse --short HEAD)"

# Back on main, wave 1's work exists too -- rebuilt independently: same
# content, a different commit, no ancestry relationship to the orphaned one
# above. Exactly what a real rebase produces. git checkout removes src/ on
# the way back since main's tree (still just base_sha) never had it, so it
# has to be recreated before writing into it.
git checkout -q main
mkdir -p src
cat > src/auth.js <<'EOF'
export function login(user) {
  return { user, token: "signed" };
}
EOF
git add src/auth.js
git commit -q -m "wave 1: login (rebased)"

# --- divergence 2: a checkpoint that is one commit behind -------------------
cat > src/session.js <<'EOF'
export function renew(token) {
  return token;
}
EOF
git add src/session.js
git commit -q -m "wave 2: session renewal, partial"
# The work_sha a checkpoint taken *here* would have recorded as observed_sha
# -- captured now, before the commit below, so state.md can cite this stale
# value deliberately instead of current HEAD's.
stale_work_sha="$(git rev-parse HEAD)"
stale_branch="$(git symbolic-ref --short HEAD)"

# Work lands after that checkpoint -- no new checkpoint captures it. This is
# exactly the case baton-resume step 3 exists to catch: a commit outside
# docs/baton/ with no corresponding entry in observed_sha.
cat >> src/session.js <<'EOF'

export function refresh(token) {
  return token;
}
EOF
git add src/session.js
git commit -q -m "wave 2: add refresh, uncheckpointed"
current_work_sha="$(git rev-parse HEAD)"

cat > docs/baton/constitution.md <<EOF
---
schema: baton/constitution/v1
run_id: fixture-auth-diverged
status: ratified
verify_cmd: "node --test"
placeholder_patterns: "TODO|FIXME|NotImplemented"
---

# Fixture run (diverged)

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

# state.md claims wave 1 closed at the orphaned commit (not an ancestor of
# main's HEAD) and observed_sha at the stale work_sha (one commit behind the
# current one). suspect and needs_human both read false -- nothing has
# flagged either divergence yet; that is the resuming agent's job.
cat > docs/baton/state.md <<EOF
---
schema: baton/state/v1
writer: fixture-session
updated_at: 2026-08-03T09:00:00Z
observed_sha: $stale_work_sha
observed_branch: $stale_branch
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
| 1 | login | done | — | — | $orphaned_wave1_sha | — |
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

# .baton/precompact-facts: what the PreCompact hook would have recorded at
# compaction time, after the uncheckpointed commit above had already landed
# -- its work_sha is current_work_sha, not the stale one state.md's
# observed_sha claims. This is what gives baton-resume's step 3 something to
# find without a live hook run: comparing this file's work_sha against
# state.md's observed_sha is exactly how it notices work landed that no
# checkpoint captured.
mkdir -p .baton
cat > .baton/precompact-facts <<EOF
recorded_at=2026-08-03T09:30:00Z
sha=$(git rev-parse HEAD)
short_sha=$(git rev-parse --short HEAD)
work_sha=$current_work_sha
branch=main
tree_clean=true
dirty_count=0
EOF
