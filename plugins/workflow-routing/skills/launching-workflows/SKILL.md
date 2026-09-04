---
name: launching-workflows
tools:
  - Workflow
description: >
  Model-routing policy for the Workflow tool (multi-agent orchestration). Read
  this BEFORE authoring or launching any Workflow script, i.e. before writing
  agent() / parallel() / pipeline() calls. The session running the orchestrator
  is Fable (expensive); this skill says which cheaper tier each dispatched agent
  must get so workers never silently inherit Fable. Use whenever you are about to
  call the Workflow tool, build a workflow script, fan out subagents inside a
  workflow, or decide "which model should this workflow agent run on".
  Trigger phrases: "запусти workflow", "напиши workflow", "раскидай агентов",
  "orchestrate this", "fan out agents", "multi-agent", "ultracode".
---

Model-routing policy for the `Workflow` tool. Scope is **Workflow only** — the
plain `Agent` tool and the main loop are out of scope here.

## The one principle

**Fable thinks, cheap models do.** The orchestrator (this session) is already
Fable, so it is right where it needs to be. Every agent you *dispatch* from a
workflow is doing work Fable decomposed — so it should run one or more tiers
*down*, on the cheapest model that can do that specific step reliably.

This is why the routing matters: a workflow that fans out 20 agents on Fable
costs ~20× a workflow that routes those same 20 agents to Sonnet/Haiku and keeps
only the planning and final synthesis on Fable. The savings come entirely from
*not* letting workers inherit the orchestrator tier.

## Set model explicitly on every dispatched agent

The `Workflow` tool's own guidance says "omit `opts.model`, the agent inherits
the session model." **Override that here.** In this workspace the session model
is Fable, so inheriting means every worker silently runs on Fable — the exact
waste this policy exists to prevent. So:

```js
agent(prompt, { model: 'sonnet', ... })   // always name the tier
```

Name `opts.model` on every `agent()` call. The only agent that stays on Fable is
the orchestrator itself, and that is the script body — not an `agent()` call.

`opts.model` accepts the short aliases `'fable' | 'opus' | 'sonnet' | 'haiku'`
(full IDs: `claude-fable-5-1`, `claude-opus-5`, `claude-sonnet-5`,
`claude-haiku-4-5-20251001`).

## Routing table

| Role in the workflow | Model |
|---|---|
| Orchestrator — planning, decomposition, synthesis, final adversarial verify. This is the script body itself, not a dispatched agent. | **fable** (already the session) |
| **Default implementation** — feature builds, test generation, moderate analysis | **sonnet** |
| Complex implementation Sonnet can't reliably do — multi-file ports, subtle integrators, deep security review | **opus** |
| Mechanics — search, grep-style conformance, summarization, doc updates, running commands, log parsing, classification | **haiku** |
| Targeted one-shot subtle audit on an independent lens — semantic audit vs spec, ambiguous requirements | **opus**, as a dedicated single-purpose agent with distinct framing |

## Rules

- **Implementation defaults to `sonnet`, not `opus`.** Route to `opus` only when
  the task is genuinely multi-file, subtle, or cascading-on-error. Reaching for
  Opus by default is the most common way this policy gets diluted.
- **Reserve `fable` for orchestration only:** spec + plan authorship, synthesis,
  final verify. That work lives in the script body. Never dispatch a `fable`
  worker for implementation or mechanics.
- **Independent-lens audits run on `opus`, not `fable`.** The value is fresh
  context + distinct review framing *plus* genuine tier-independence from the
  Fable orchestrator auditing its own reasoning. Same-tier self-audit (Fable
  checking Fable) costs 2× and buys less independence.
- **Escalate exactly one tier up** only for a step that failed twice or proved
  genuinely ambiguous. Don't pre-escalate on a hunch.
- **Deterministic work is not an agent.** Dedup, set logic, formatting, path
  math, counting — plain JavaScript in the script body, never an `agent()` call.
- **If a workload keeps tripping the safety classifier and silently falling back
  to Opus** (>5% of calls), route that workload to `opus` directly. The premium
  you pay for a lower tier that never actually runs is wasted.

## agentType interacts with model

`opts.agentType` picks a subagent's *system prompt / toolset*, `opts.model`
picks its *tier* — they are independent, so always set both intentionally.
Watch the mismatch: `agentType: 'Explore'` defaults to **Haiku**, which is
correct for cheap search but wrong the moment you ask it to critique, judge, or
synthesize. If a dispatched agent does reasoning, name `model: 'opus'` (or
`sonnet`) explicitly regardless of its agentType — never let a reasoning-heavy
agent ride a weak default.

## Stock workflows: NEVER run by name — use materialize-stock-workflow

The bundled `deep-research` skill says `Workflow({ name: "deep-research" })`.
Do NOT follow it as-is: stock scripts omit `opts.model` on their `agent()`
calls, so all ~100+ subagents silently inherit Fable (~2M tokens/run — this
burned two session limits in 2026-07).

Instead follow the `workflow-routing:materialize-stock-workflow` skill: it materializes the
CURRENT stock script (launch-and-stop), patches `opts.model` into a TEMPORARY
copy per this skill's routing table, launches via `scriptPath`, and verifies
worker models — so the routed run never drifts from the evolving built-in.
`${CLAUDE_PLUGIN_ROOT}/skills/materialize-stock-workflow/references/deep-research-routed.js`
remains the committed last-known-good (diff baseline + fallback), not a
maintained fork.
After EVERY workflow launch verify actual worker models:
`grep '"model"' <transcript-dir>/agent-*.jsonl | sort | uniq -c` — if Fable
appears, TaskStop immediately.

## Quick check before you launch

1. Does every `agent()` call name `opts.model`? (No silent Fable inheritance.)
2. Is anything on `fable` that isn't the orchestrator body? → move it down.
3. Is anything on `opus` that Sonnet could do? → move it to `sonnet`.
4. Is any "agent" doing pure dedup/formatting/counting? → make it plain code.
5. Do audit/verify agents run on a *different* tier than the orchestrator? →
   `opus`, for real independence.
6. Is it a STOCK workflow invoked by `name`? → stop; follow
   `workflow-routing:materialize-stock-workflow` (launch-and-stop → patch a
   temp copy → route).
