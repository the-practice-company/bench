---
name: materialize-stock-workflow
tools:
  - Workflow
  - TaskStop
description: >
  Procedure for running any BUILT-IN (named) workflow — deep-research first of
  all — without letting its workers inherit the session model (Fable). Stock
  scripts omit opts.model on their agent() calls; launching by name in a Fable
  session multiplies the cost ~10x (the 2026-07 deep-research incident). This
  skill materializes the CURRENT stock script at invocation time (launch-and-
  stop), patches model inheritance into a TEMPORARY copy, and launches that —
  so the routed version never drifts from the evolving built-in. Use whenever
  a stock/named workflow is about to be invoked: "deep research", "запусти
  deep-research", "run the built-in workflow", "stock workflow".
---

Why this exists: stock workflow scripts (e.g. `deep-research`) do not set
`opts.model`, so every dispatched agent inherits the session model. In a Fable
session that is ~100 agents on the most expensive tier (~2M tokens/run — burned
two session limits in 2026-07). A committed fork fixes the cost but DRIFTS as
Claude Code evolves. This procedure gets the CURRENT script every time and
patches only the model seams. Routing policy itself lives in
`workflow-routing:launching-workflows` — do not restate it, apply it.

## Procedure (materialize → stop → patch → launch)

1. **Materialize by launch-and-stop.** The harness persists every workflow
   script at launch and returns its path in the tool result ("Script file:
   ..."). So: `Workflow({ name: "deep-research", args: "<question>" })` → read
   the Script file path AND the Task ID from the result → **`TaskStop` that
   task IMMEDIATELY, same turn, before doing anything else.** Damage window:
   at most one barely-started agent (seconds). The built-in source is NOT
   extractable from the installed binary (verified on 2.1.132) — this
   launch-and-stop is the only reliable way to read the current version.
2. **Diff against the last-known-good.** Compare the persisted script with the
   committed reference
   `${CLAUDE_PLUGIN_ROOT}/skills/materialize-stock-workflow/references/deep-research-routed.js`
   (which is the previous stock version + 5 model pins; ignore the meta/header
   lines and the `model:` additions when diffing).
   - **No drift** → just launch the committed reference via `scriptPath`; done.
   - **Drift** → continue.
3. **Patch a TEMPORARY copy.** Copy the persisted script to
   `/tmp/<name>-routed-<date>.js` (NEVER commit it — it is disposable by
   design). Add `model:` to EVERY `agent()` call per the `workflow-routing:launching-workflows`
   routing table (deep-research: scope→`sonnet`, search→`haiku`,
   fetch/extract→`sonnet`, verify votes→`sonnet`, synthesize→`opus`; for other
   workflows: mechanics→haiku, default work→sonnet, subtle/synthesis→opus).
   Gate before launch: `grep -n 'agent(' <tmp> ` — every call site must carry a
   `model:` in its opts; zero unpinned calls.
4. **Launch the patched copy**: `Workflow({ scriptPath: "/tmp/...-routed-....js",
   args: ... })`. Never resume the stopped by-name run.
5. **Verify actual worker models** (mandatory, after EVERY launch):
   `grep '"model"' <transcript-dir>/agent-*.jsonl | sort | uniq -c` — Fable
   appears → `TaskStop` immediately. Also check the stopped step-1 task's
   transcripts and report any Fable spend from the materialization window
   (usually zero).
6. **Optional refresh** (only when drift was found): update the committed
   reference `deep-research-routed.js` from the freshly patched copy in a
   normal reviewed commit — in bench, the repository this plugin ships from,
   not in the project you are working in — so the next materialization diffs
   against a closer baseline and every install picks it up.

## Notes

- The temporary script is the point: the plugin keeps ONE reference copy as
  a diff baseline and cold-start fallback, not a maintained fork.
- If the launch-and-stop result shows agents already running on Fable for more
  than one agent, stop, record the spend in the run log, and proceed with the
  patch — the procedure still nets ~10x cheaper than a full by-name run.
- Applies to ANY named workflow, not only deep-research; deep-research is the
  worked example because it is the largest fan-out (~100 agents).
