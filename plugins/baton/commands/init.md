---
description: Start a baton run - decompose an umbrella spec into waves and write the constitution
---

Set up a baton run in this repository.

This is a conversation with the human, not a template fill. The umbrella spec
says what to build; it does not say how the work splits, what may run in
parallel, or what "closed" means for each piece. That is what we work out here.

## 1. Find the umbrella spec

Look in `docs/superpowers/specs/` for the design this run implements. If there
is more than one, ask which. If there is none, stop and say so: baton
decomposes an existing spec, it does not replace `superpowers:brainstorming`.

## 2. Check the companion plugin

Confirm the superpowers skills are available (`superpowers:brainstorming`,
`superpowers:writing-plans`). If they are not, warn the human: baton assumes
per-wave specs and plans come from superpowers, and without it they will have
to write those by hand. Continue anyway if they want to.

## 3. Run the decomposition dialogue

One question at a time. Cover, in this order:

- **The split.** What are the waves? A wave is a chunk that can be closed and
  verified on its own.
- **Dependencies.** For each wave, `depends_on`. Parallelism is what is left
  once the edges are drawn — do not ask about it directly, derive it and
  confirm.
- **Contracts.** For any wave with a non-empty `parallel_with`, what does it
  publish (`produces`) and what does it take (`consumes`)? Parallel waves that
  agree on an interface after the fact collide.
- **Exit criteria.** For each wave, what must be true for it to be closed.
  Write them in EARS with a mandatory "shall". Push back on anything that
  cannot be checked: "the API is solid" is not a criterion.
- **Non-negotiables.** What must no wave break.
- **Operating mode.** Confirm the default (orchestrator delegating to
  subagents and workflows) or take what they want instead.

## 4. Ask for the verification command

What command proves this repository works — `npm test`, `pytest -q`,
`cargo test`, a script. Ask what stub markers their language uses, and extend
the default `placeholder_patterns` accordingly.

Tell them plainly why this lives in the constitution and not a config file: the
gate trusts this command, and if the agent could edit it, the agent could
weaken the gate. The constitution is the human's file, so the threshold is out
of the agent's reach.

## 5. Write the artifacts

Fill `${CLAUDE_PLUGIN_ROOT}/templates/constitution.md` and
`${CLAUDE_PLUGIN_ROOT}/templates/state.md` from the conversation. Every
`REPLACE-` marker must be gone.

Add `.baton/` to `.gitignore` if it is not already there. Then write both files
through `baton-write` so they land atomically and get committed:

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/baton-write" -m "baton: constitution for <run>" docs/baton/constitution.md < /tmp/constitution.md
"${CLAUDE_PLUGIN_ROOT}/scripts/baton-write" -m "baton: initial state" docs/baton/state.md < /tmp/state.md
```

## 6. Hand it back for ratification

Ask the human to read `docs/baton/constitution.md` and change `status: draft`
to `status: ratified`, filling `ratified_by`, `ratified_at` and `git_anchor`.

Say why it matters rather than treating it as paperwork: from this point the
agent reads the constitution and never writes it, and everything downstream —
what the gate checks, what may not be broken, where the wave boundaries are —
is anchored to a document the human signed.
