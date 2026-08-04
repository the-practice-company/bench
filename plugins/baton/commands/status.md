---
description: Show where the run stands, deviations first
---

Render the run for a human who just opened their laptop and wants to know
whether to intervene.

If `docs/baton/state.md` does not exist, this repository is not a baton run:
say so, suggest `/baton:init`, and stop. Do not offer to create anything.

Read `docs/baton/state.md` and the journal. Report in this order, because
deviations matter more than progress:

1. **Stopped or suspect.** If `needs_human: true`, say what stopped the run and
   what the human has to decide. If `suspect: true`, show the `Suspect` line.
   If neither is set, say nothing here rather than reporting "all good".
2. **Decisions awaiting review.** Entries live in `docs/baton/journal/`, named
   `NNNN-<slug>.md`; `baton-journal` allocates `NNNN` strictly increasing, so
   the numeric prefix is the order — sort on it, highest first. Not the
   frontmatter `timestamp`: the prefix is allocated by one script and cannot
   disagree with itself, while a timestamp is written by hand into the entry
   and can. List every entry with `needs_review: true` this way — one line
   each: id, what was decided, why it needs them. Include `incoming` entries:
   those are inputs that arrived mid-run and may need an amendment to the
   constitution.
3. **Now.** Current wave, `Next action`, `In flight`.
4. **Waves.** The table, one line per wave, statuses only.

Then verify and report:

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/baton-observe"
```

Compare `state.md`'s `observed_sha` against `baton-observe`'s `work_sha`, not
its `sha` — `sha` is raw `HEAD`, which moves on every checkpoint commit, so a
baseline recorded before that commit could never equal it, and comparing
against it would report a divergence on essentially every call. Say whether
they agree. State that agrees with itself but not with the repository is
exactly what this command exists to catch.

Keep it short. No progress bars, no percentages, no encouragement.
