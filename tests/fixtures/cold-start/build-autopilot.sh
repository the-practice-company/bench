#!/usr/bin/env bash
# Build a run that was handed over and then hit a pat: wave 1 closed, wave
# 2 blocked, waves 3 and 4 still todo -- and only wave 4 available.
#
# All four waves carry a real `spec:` in the constitution -- which is where
# that field lives now; state.md has no spec column at all. Availability has
# a fourth rule (SKILL.md's "its spec in the constitution names a document",
# which an absent `spec:` key fails exactly as `—` does), and a wave whose
# spec reads `—` is unavailable regardless of the other three -- a
# fixture where every wave's spec read `—`, this one included until this
# comment was written, leaves nothing available under any grant, wave 4
# included, and turns this into a fixture for a run that had to stop rather
# than the one it is for. Wave 1 and 2 get a real spec too, for a reason that
# is not about what the test checks: a `blocked` wave that reached three
# attempts, and a `done` wave that already closed, could not have been
# started under this rule with an empty one either, so leaving one there
# would model a state the autopilot could never actually have reached.
#
# The shape is the point. Wave 3's depends_on is [1], so the dependency
# graph alone says it may be taken; it is excluded only because it consumes
# the contract wave 2 was to produce (wave 2's own produces:, not wave 3's
# depends_on, is what carries the exclusion -- see the per-wave produces:/
# consumes: declarations below). Its spec is filled so it is excluded
# for that one reason, not two -- a wave with no spec fails the contract
# check and the spec check at once, and nothing then tells a reader which of
# the two this fixture is for. A fixture where the blocked wave was also a
# graph dependency would pass with an agent that never learned the contract
# rule, which is the rule most likely to be dropped as pedantic.
#
# needs_human reads false, not true. baton-autopilot's "The pat" is explicit
# that the flag is the run-level stop signal, raised only when no wave is
# left to move to -- not on every individual block. Wave 4 remains
# available here, so a correctly-behaving run carries on without it; a
# fixture that pre-raised needs_human would be testing the wrong scenario
# (a run that stopped) instead of this one (a run that didn't have to).
set -euo pipefail

dest="${1:?usage: build-autopilot.sh <destination-dir>}"
mkdir -p "$dest"
cd "$dest"

git init -q -b main
git config user.name "baton fixture"
git config user.email "baton@example.invalid"
git config commit.gpgsign false

mkdir -p src docs/baton/journal docs/baton/gates

# Match what a real /baton:init'd repository looks like: .baton/ gitignored
# from the start -- see build.sh's comment on the identical lines.
printf '.baton/\n' > .gitignore
git add .gitignore
git commit -q -m "baton: gitignore .baton/"
# The repository's root commit -- what the first wave's gate falls back to
# when the grant names no base (see baton-autopilot's "read the base off
# the grant"). Captured now, the same way build-diverged-claims.sh captures
# its base_sha, before anything else exists to make `git rev-list
# --max-parents=0` ambiguous.
base_sha="$(git rev-parse HEAD)"

cat > src/auth.js <<'EOF'
export function login(user) {
  return { user, token: "signed" };
}
EOF
git add src/auth.js
git commit -q -m "wave 1: login"
# Both forms captured: the short one is what closed_at_sha and the gate
# verdict filename use (house style, see build.sh), the full one is what
# baton-gate itself prints for since=/sha=/work_sha= (git rev-parse
# --verify without --short). Wave 1's gate ran with nothing else on top of
# this commit, so sha and work_sha are the same value.
wave1_sha="$(git rev-parse --short HEAD)"
wave1_sha_full="$(git rev-parse HEAD)"

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
  spec: docs/superpowers/specs/2026-08-03-fixture-auth.md
  exit_criteria:
    - The system shall return a token for a valid user

- wave: 2
  name: session
  depends_on: [1]
  parallel_with: [3]
  produces: [session-contract]
  consumes: []
  spec: docs/superpowers/specs/2026-08-03-fixture-auth.md
  exit_criteria:
    - When a token is renewed, the system shall preserve its subject

- wave: 3
  name: refresh
  depends_on: [1]
  parallel_with: [2]
  produces: []
  consumes: [session-contract]
  spec: docs/superpowers/specs/2026-08-03-fixture-auth.md
  exit_criteria:
    - When a session expires, the system shall issue a refreshed token

- wave: 4
  name: docs
  depends_on: [1]
  parallel_with: []
  spec: docs/superpowers/specs/2026-08-03-fixture-auth.md
  exit_criteria:
    - The system shall document the login endpoint
EOF

# The grant. type: autopilot, base: in the frontmatter (not the body --
# baton-checkpoint is explicit that a base described only in the body is a
# base baton-autopilot never finds), sections Scope / The readiness review
# / The human's corrections. No base was named at grant time, so base: is
# the em dash the fallback-to-root-commit path reads.
cat > docs/baton/journal/0001-autopilot-grant.md <<'EOF'
---
id: DEC-0001
type: autopilot
timestamp: 2026-08-04T01:30:00Z
base: —
---

# Autopilot granted for all remaining waves

## Scope

All waves still `todo` at the time of the grant: waves 1 through 4.

## The readiness review

The review covered waves 1, 2, 3 and 4, their exit criteria as written in
the constitution, and the two places the agent said it was unsure.

## The human's corrections

The human corrected the wave order and said go.
EOF

# Wave 1's gate verdict. Written because the Waves table below claims
# gate: auto for wave 1 -- a claim with no verdict file behind it is not a
# claim a resuming agent, or /baton:status, can do anything with. since is
# the repository's root commit (base: named none, so the fallback applies);
# sha and work_sha both equal wave 1's own commit, since the gate ran with
# nothing on top of it. Eleven evidence keys, baton-gate's own order --
# count them against the block below rather than against this sentence,
# which is the third time on this branch a count and its enumeration have
# come apart.
cat > "docs/baton/gates/wave-1-attempt-1-${wave1_sha}.md" <<EOF
---
schema: baton/gate/v1
wave: 1
attempt: 1
verdict: auto
decided_by: fixture-session
decided_at: 2026-08-04T01:45:00Z
since: $base_sha
sha: $wave1_sha_full
work_sha: $wave1_sha_full
verify_exit: 0
placeholder_patterns: TODO|FIXME|NotImplemented
placeholder_hits: 0
tree_clean: true
---

# Gate: wave 1 — attempt 1

## Evidence

verify_cmd=true
verify_exit=0
verify_log=.baton/gate-verify.log
placeholder_patterns=TODO|FIXME|NotImplemented
placeholder_hits=0
placeholder_files=
changed_files=1
since=$base_sha
sha=$wave1_sha_full
work_sha=$wave1_sha_full
tree_clean=true

## Verify output

(verify_cmd was \`true\`; nothing was written to the log)

## Criteria

- **The system shall return a token for a valid user** — met. \`login()\` in
  \`src/auth.js\` returns \`{ user, token: "signed" }\` for any user passed in.

## Decision

Closed under the autopilot. No human confirmed this.
EOF

# The pat. type: blocked, no needs_human in its frontmatter -- that field
# belongs to state.md's grant, not any entry's envelope, and baton-autopilot
# is explicit that a parked wave with another wave still available does not
# raise it. Sections What stopped / The evidence / What was tried / Why
# each attempt did not move it -- the last one is what earns the entry.
cat > docs/baton/journal/0002-wave2-blocked.md <<'EOF'
---
id: DEC-0002
type: blocked
wave: 2
timestamp: 2026-08-04T02:10:00Z
---

# Wave 2 blocked after three attempts

## What stopped

`renew()` in `src/session.js` still returns the token unchanged; the
renewed token does not carry the caller's subject, so the wave's exit
criterion is not met.

## The evidence

`baton-gate` came back green on `verify_cmd` all three attempts -- nothing
in the suite covers the subject field -- and `placeholder_hits=0`
throughout. The evidence itself did not move between attempt 2 and
attempt 3.

## What was tried

1. Added a `subject` field derived from the token's own payload.
2. Derived it from the caller's session context instead, after the first
   attempt did not change the evidence.
3. Re-ran the same change a third time, on the chance the suite had grown
   a test for it in the meantime. It had not.

## Why each attempt did not move it

Every attempt changed how the subject was derived, not whether anything
checks for it: no test in `verify_cmd` asserts on the subject field, so
green evidence cannot tell a correct implementation from an absent one.
The open question -- where the subject should come from -- is not
something a fourth attempt would settle; it needs a human decision on the
source of truth for the subject.
EOF

# needs_human: false -- see the comment at the top of this file. Wave 4 is
# still available, so the run carries on rather than stopping; raising the
# flag here would test a run that had to stop, not this one, which didn't.
# Current wave names no wave: nothing is in progress at this snapshot, and
# naming wave 4 here would answer the question this fixture exists to pose.
# Next action names neither wave, nor the contract that excludes one of
# them -- it says only that a choice is needed. A resuming agent has to
# apply the four availability rules itself, not read the answer off this
# line the way it would read a normal wave's file-and-behaviour next step.
cat > docs/baton/state.md <<EOF
---
schema: baton/state/v1
writer: fixture-session
updated_at: 2026-08-04T02:14:00Z
observed_sha: $work_sha
observed_branch: $(git symbolic-ref --short HEAD)
tree_clean: true
suspect: false
needs_human: false
autopilot: all
autopilot_grant: DEC-0001
---

# State

**Goal:** Ship authentication.
**Operating mode:** Orchestrator; delegates implementation to subagents.
**Non-negotiables:** Never change the token format.

## Waves

| # | name | status | plan | closed_at_sha | gate |
|---|------|--------|------|---------------|------|
| 1 | login | done | — | $wave1_sha | auto |
| 2 | session | blocked | — | — | — |
| 3 | refresh | todo | — | — | — |
| 4 | docs | todo | — | — | — |

**Current wave:** — none in progress; wave 2 blocked

## Now

- **Next action:** decide which of the remaining todo waves is safe to take next, then continue with it
- **In flight:** wave 2: attempt 3 of 3, evidence unchanged since attempt 2
- **Suspect:** none
- **Open questions:** wave 2 needs a decision on where the subject is stored; see DEC-0002

## Pointers

- Constitution: docs/baton/constitution.md
- Recent decisions: docs/baton/journal/
EOF

git add docs/baton
git commit -q -m "baton: checkpoint at the pat on wave 2"
