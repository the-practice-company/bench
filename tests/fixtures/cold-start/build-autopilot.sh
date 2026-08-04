#!/usr/bin/env bash
# Build a run that was handed over and then hit a pat: wave 1 closed, wave
# 2 blocked, waves 3 and 4 still todo -- and only wave 4 available.
#
# The shape is the point. Wave 3's depends_on is [1], so the dependency
# graph alone says it may be taken; it is excluded only because it consumes
# the contract wave 2 was to produce. A fixture where the blocked wave was
# also a graph dependency would pass with an agent that never learned the
# third rule, which is the rule most likely to be dropped as pedantic.
set -euo pipefail

dest="${1:?usage: build-autopilot.sh <destination-dir>}"
mkdir -p "$dest"
cd "$dest"

git init -q -b main
git config user.name "baton fixture"
git config user.email "baton@example.invalid"
git config commit.gpgsign false

mkdir -p src docs/baton/journal

# Match what a real /baton:init'd repository looks like: .baton/ gitignored
# from the start -- see build.sh's comment on the identical lines.
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
git commit -q -m "wave 2: session renewal, incomplete"
# Captured now, before the docs/baton commit below exists -- see build.sh's
# comment on the identical line for why this, not raw HEAD, is what
# observed_sha must record.
work_sha="$(git rev-parse HEAD)"

cat > docs/baton/constitution.md <<'EOF'
---
schema: baton/constitution/v1
run_id: fixture-auth-autopilot
status: ratified
verify_cmd: "true"
placeholder_patterns: "TODO|FIXME|NotImplemented"
---

# Fixture run (autopilot)

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
  parallel_with: []
  exit_criteria:
    - The system shall return a token for a valid user

- wave: 2
  name: session
  depends_on: [1]
  parallel_with: [3]
  produces: [session-contract]
  exit_criteria:
    - When a token is renewed, the system shall preserve its subject

- wave: 3
  name: refresh
  depends_on: [1]
  parallel_with: [2]
  consumes: [session-contract]
  exit_criteria:
    - When a session expires, the system shall issue a refreshed token

- wave: 4
  name: docs
  depends_on: [1]
  parallel_with: []
  exit_criteria:
    - The system shall document the login endpoint
EOF

cat > docs/baton/journal/0001-autopilot-grant.md <<'EOF'
---
id: DEC-0001
type: autopilot
date: 2026-08-04
scope: all
---

# Autopilot granted for all remaining waves

The readiness review covered waves 2, 3 and 4, their exit criteria as
written in the constitution, and the two places the agent said it was
unsure. The human corrected the order and said go.
EOF

cat > docs/baton/state.md <<EOF
---
schema: baton/state/v1
writer: fixture-session
updated_at: 2026-08-04T02:14:00Z
observed_sha: $work_sha
observed_branch: $(git symbolic-ref --short HEAD)
tree_clean: true
suspect: false
needs_human: true
autopilot: all
autopilot_grant: DEC-0001
---

# State

**Goal:** Ship authentication.
**Operating mode:** Orchestrator; delegates implementation to subagents.
**Non-negotiables:** Never change the token format.

## Waves

| # | name | status | branch/worktree | spec | plan | closed_at_sha | gate |
|---|------|--------|-----------------|------|------|---------------|------|
| 1 | login | done | main | — | — | $wave1_sha | auto |
| 2 | session | blocked | main | — | — | — | — |
| 3 | refresh | todo | main | — | — | — | — |
| 4 | docs | todo | main | — | — | — | — |

**Current wave:** 2 — session

## Now

- **Next action:** take wave 4 (docs); wave 3 consumes the contract wave 2 was to publish
- **In flight:** wave 2: attempt 3 of 3, evidence unchanged since attempt 2
- **Suspect:** none
- **Open questions:** wave 2 needs a decision on where the subject is stored

## Pointers

- Constitution: docs/baton/constitution.md
- Recent decisions: docs/baton/journal/
EOF

git add docs/baton
git commit -q -m "baton: checkpoint at the pat on wave 2"
