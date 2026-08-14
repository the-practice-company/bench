---
schema: baton/constitution/v1
run_id: REPLACE-WITH-SLUG
status: draft
# status must be `ratified` before any wave starts. A constitution with any
# unfilled placeholder marker left in it has not been ratified, regardless of
# what this field says. That check scans the whole file for the marker text,
# so this comment deliberately does not spell one out: a warning that quoted
# the token would itself trip the check on every resume, forever, asking for a
# ratification that already happened.
ratified_by: REPLACE-WITH-NAME
ratified_at: REPLACE-WITH-ISO8601
git_anchor: REPLACE-WITH-SHA
umbrella_spec: docs/superpowers/specs/REPLACE-WITH-SPEC.md
verify_cmd: "REPLACE-WITH-TEST-COMMAND"
placeholder_patterns: "TODO|FIXME|NotImplemented|unimplemented|raise NotImplementedError"
# in-place | worktree. Where the run works. Declared here so
# superpowers:using-git-worktrees honours it without asking -- under the
# autopilot there is nobody to answer a consent prompt. baton needs no tree
# of its own; this protects your other work in this repository, not the run.
workspace: in-place
---

# REPLACE-WITH-THE-NAME-OF-THIS-RUN

## Goal

One or two sentences. What counts as success for the whole run.

## Operating mode

Who the agent is in this run. Default: orchestrator. It does not write code in
the primary session, and it is answerable for carrying the work to completion.

Delegation goes through the named procedures, not through whatever tool is at
hand: `superpowers:writing-plans` for the wave's plan, then
`superpowers:subagent-driven-development` to execute it. A wave executed by
some other means loses that skill's two-stage review, and the first stage is
the one that catches work drifting from the spec.

## Non-negotiables

Rules no wave may break. These are restated in state.md on every resume,
because an agent that keeps the goal but loses the constraints will serve the
current request while quietly violating the original brief.

## Waves

```yaml
- wave: 1
  name: REPLACE-WITH-WAVE-NAME
  depends_on: []
  parallel_with: []
  exit_criteria:
    - The system shall REPLACE-WITH-VERIFIABLE-BEHAVIOUR

- wave: 2
  name: REPLACE-WITH-WAVE-NAME
  depends_on: [1]
  parallel_with: []
  exit_criteria:
    - When REPLACE-WITH-TRIGGER, the system shall REPLACE-WITH-BEHAVIOUR
```

Exit criteria use EARS. Five patterns, "shall" is mandatory:

- The system shall `<behaviour>`
- When `<trigger>`, the system shall `<behaviour>`
- While `<state>`, the system shall `<behaviour>`
- Where `<feature is enabled>`, the system shall `<behaviour>`
- If `<condition>`, then the system shall `<behaviour>`

The gate judges against these lines. A criterion open to two readings is a
criterion the agent will read in its own favour.

Waves with a non-empty `parallel_with` must also declare `produces:` (the
contract published to downstream waves) and `consumes:` (the contract taken
from upstream waves). Parallelism is only safe when the contract is declared
before implementation.

## Decision authority

What the agent decides alone, and what it escalates.

Default: reversible decisions with low or medium blast radius are the agent's
own, recorded in the journal. Irreversible decisions, or anything with high
blast radius, are escalated. A reversible decision is made on roughly 70% of
the information you would like, not 90% - waiting for completeness on a
reversible call is slow, not careful.

## Amendments

Append only. Each amendment: date, what changed, who ratified it.
