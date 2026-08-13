---
schema: baton/state/v1
writer: REPLACE-WITH-SESSION-ID
updated_at: REPLACE-WITH-ISO8601
# baton-observe's work_sha, not its sha: the last commit that touched
# anything outside docs/baton/, so this checkpoint's own commit never moves it.
observed_sha: REPLACE-WITH-WORK-SHA
observed_branch: REPLACE-WITH-BRANCH
tree_clean: true
suspect: false
needs_human: false
# Granted, not observed and not claimed: only a human turns this on, with
# /baton:auto, and any party may turn it off. off | all | <wave number>.
autopilot: off
autopilot_grant: —
---

# State

**Goal:** one line, copied from the constitution
**Operating mode:** one line, copied from the constitution
**Non-negotiables:** the list from the constitution, verbatim

## Waves

| # | name | status | spec | plan | closed_at_sha | gate |
|---|------|--------|------|------|---------------|------|
| 1 | REPLACE-WITH-WAVE-NAME | todo | — | — | — | — |

**Status:** `todo | doing | done | blocked`.
`blocked` waits on a dependency; `needs_human: true` (frontmatter) stops the whole run.

**Gate:** `—` nothing produced a verdict; `auto` closed under the autopilot,
verdict in `docs/baton/gates/`; `pass` a human confirmed it.

**Current wave:** 1 — REPLACE-WITH-WAVE-NAME

## Now

- **Next action:** one deterministic sentence
- **In flight:** what was interrupted mid-way, or "nothing"
- **Suspect:** where a claim diverged from the repository, or "none"
- **Open questions:** or "none"

## Pointers

- Constitution: docs/baton/constitution.md
- Recent decisions: docs/baton/journal/
