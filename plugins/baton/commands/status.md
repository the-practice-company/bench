---
description: Where the run stands - deviations first, for a human with thirty seconds
---

Render the run for a human who just opened their laptop and wants to know
whether to intervene.

Read `docs/baton/state.md` and the journal. Report in this order, because
deviations matter more than progress:

1. **Stopped or suspect.** If `needs_human: true`, say what stopped the run and
   what the human has to decide. If `suspect: true`, show the `Suspect` line.
   If neither is set, say nothing here rather than reporting "all good".
2. **Decisions awaiting review.** Journal entries with `needs_review: true`,
   newest first — one line each: id, what was decided, why it needs them.
   Include `incoming` entries: those are inputs that arrived mid-run and may
   need an amendment to the constitution.
3. **Now.** Current wave, `Next action`, `In flight`.
4. **Waves.** The table, one line per wave, statuses only.

Then verify and report: run `baton-observe` and say whether `observed_sha`
matches the repository. State that agrees with itself but not with the
repository is exactly what this command exists to catch.

Keep it short. No progress bars, no percentages, no encouragement.
