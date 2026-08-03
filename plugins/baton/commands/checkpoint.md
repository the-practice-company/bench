---
description: Persist run state now - use before compacting context manually
---

Checkpoint the baton run.

If `docs/baton/state.md` does not exist, this repository is not a baton run:
say so, suggest `/baton:init`, and stop. If `docs/baton/constitution.md`'s
`status` is not `ratified`, or a `REPLACE-WITH` token remains in it, say so
and stop — checkpointing a run that has not been handed over records state
for a run that does not exist yet.

Use the **baton-checkpoint** skill and follow it exactly. It snapshots the
repository, reconciles state against it, updates the narrative fields, journals
anything that crossed the threshold, and commits.

When it finishes, tell the human the following, and nothing more:

1. Whether `git status --porcelain docs/baton` is empty. If it is not, the
   checkpoint did not happen — say that instead of reporting success.
2. The `Next action` line as written, so they can see what the next session
   will pick up and correct it now if it is wrong.

If `suspect: true` was set during reconciliation, lead with that. A divergence
between what state claims and what the repository shows is the one thing they
need to know before compacting.
