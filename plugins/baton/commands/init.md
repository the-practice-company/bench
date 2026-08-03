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

Check the skills listing already in your context for `superpowers:brainstorming`
and `superpowers:writing-plans`. If that listing is unavailable, run
`/plugin list` instead. If either is missing, warn the human: baton assumes
per-wave specs and plans come from superpowers, and without it they will have
to write those by hand. Continue anyway if they want to.

## 3. Run the decomposition dialogue

One question at a time. Cover, in this order:

- **Goal.** One or two sentences: what counts as success for the whole run.
  A run needs a definition of success before it can be split into waves.
- **Name.** What this run is called. Becomes the constitution's title, and,
  slugified, its `run_id`.
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

Ask what command proves this repository works — `npm test`, `pytest -q`,
`cargo test`, a script. That answer becomes `verify_cmd` in the constitution's
frontmatter. Then ask what stub markers their language uses, and extend the
default `placeholder_patterns` — also a constitution frontmatter field —
accordingly.

Tell them plainly why these two fields live in the constitution and not a
config file: the gate trusts `verify_cmd`, and if the agent could edit it, the
agent could weaken the gate. The constitution is the human's file, so the
threshold is out of the agent's reach.

## 5. Take the writer lease, then write the artifacts

Before writing anything, acquire the writer lease. The one-writer-for-the-
session invariant every later checkpoint and resume relies on should not be
left unestablished for the entire decomposition dialogue that just
happened — it starts here, at the first write, not whenever something later
happens to trigger `baton-resume`:

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/baton-lock" acquire "$CLAUDE_SESSION_ID"
```

`${CLAUDE_PLUGIN_ROOT}/templates/constitution.md` and
`${CLAUDE_PLUGIN_ROOT}/templates/state.md` are read-only: they are the shipped
shape for every run on this machine, not this run's draft, and editing them in
place would corrupt every future `/baton:init`. Read them for the frontmatter
fields and sections required, then compose the filled document from the
conversation and write it to a scratch file of your own — `/tmp/constitution.md`,
`/tmp/state.md` — rather than the template path. Every `REPLACE-` marker must
be gone except `ratified_by`, `ratified_at` and `git_anchor`: those three are
the human's to fill at ratification in step 6, not the agent's to invent.

Add `.baton/` to `.gitignore` if it is not already there — check first, and
append in a way that tolerates a missing trailing newline, since a bare `>>`
onto a file that doesn't end in one glues onto the last line instead of adding
a new one and silently ignores nothing:

```bash
grep -qxF '.baton/' .gitignore 2>/dev/null || {
    [ -s .gitignore ] && [ -n "$(tail -c1 .gitignore)" ] && printf '\n' >> .gitignore
    printf '.baton/\n' >> .gitignore
}
```

`docs/baton/constitution.md` is the one path `baton-write` refuses outright,
unconditionally — that refusal is the entire point of keeping `verify_cmd`
and `placeholder_patterns` in the constitution rather than a config file:
once the file exists, no tool the agent has can rewrite it, ever again. This
step, right now, is the one moment the constitution is created — from here
on it is read-only to the agent. Place it directly, with plain git, not
through `baton-write`:

```bash
mkdir -p docs/baton
cp /tmp/constitution.md docs/baton/constitution.md
git add docs/baton/constitution.md
git commit -q -m "baton: constitution for <run>"
```

Then write the initial state through `baton-write` so it lands atomically and
gets committed, the same way every checkpoint after it will:

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/baton-write" -m "baton: initial state" docs/baton/state.md < /tmp/state.md
```

## 6. Hand it back for ratification

Ask the human to read `docs/baton/constitution.md` and change `status: draft`
to `status: ratified`, filling `ratified_by`, `ratified_at` and `git_anchor`.

Say why it matters rather than treating it as paperwork: from this point the
agent reads the constitution and never writes it — `baton-write` refuses the
path outright, so this is now a mechanical fact, not a convention — and
everything downstream — what the gate checks, what may not be broken, where
the wave boundaries are — is anchored to a document the human signed.
