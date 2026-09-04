# workflow-routing

Model-routing policy for the `Workflow` tool, and a procedure for running
stock workflows without letting their workers inherit the session model.

The session that orchestrates a workflow is the most expensive tier. Every
agent it dispatches inherits that tier unless the script names a cheaper one
on the call, and a stock workflow such as `deep-research` names none. In July
2026 one such run fanned ~100 workers out on Fable, spent about 2M tokens and
burned two session limits. This plugin is what was written from that
incident, kept in one place instead of copied into every repository by hand.

## What is here

Two skills.

**launching-workflows** — the policy. The orchestrator thinks, cheaper models
do: implementation on `sonnet`, mechanics on `haiku`, subtle work and
independent-lens audits on `opus`, nothing but the script body on the session
tier. Every `agent()` call names `opts.model`; deterministic work is plain
code, not an agent. Read before authoring or launching any workflow script.

**materialize-stock-workflow** — the procedure for a workflow invoked by
name. Launch it and stop it in the same turn to make the harness persist the
current script, diff that against the reference copy shipped here, patch
`model:` into a temporary copy per the routing table, launch the copy via
`scriptPath`, then verify the models the workers actually ran on. The
reference copy, `deep-research-routed.js`, lives under the skill's
`references/` as a diff baseline and cold-start fallback, not a maintained
fork.

## Install

```
/plugin marketplace add the-practice-company/bench
/plugin install workflow-routing@bench
```

Start a fresh session afterwards; a plugin's skills only take effect in a
session that begins after the install.

## Source of truth

Before this plugin existed the same two skills lived as `.claude/skills/`
copies in a dozen checkouts, in four versions that all called themselves
1.0. A repository that carries a local copy is on whatever version it was
copied from; installing the plugin and deleting the copy puts it on this
one. A `CLAUDE.md` that points at `/launching-workflows` should point at
`workflow-routing:launching-workflows` instead.

## Licence

MIT — see [LICENSE](LICENSE).
