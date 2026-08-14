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
anything that crossed the threshold, checks the draft against the committed
file, and commits.

When it finishes, tell the human the following, and nothing more:

1. Whether the checkpoint landed intact, which is two checks and not one.
   First, the committed file still says everything it used to:
   `git show HEAD:docs/baton/state.md` must still carry the Goal, the
   Operating mode, the Non-negotiables, the Waves table with every row, Now
   and Pointers. `baton-write` replaces the whole file, so a draft that lost
   a section deletes it, commits the deletion, and leaves the tree clean —
   which is why `git status` cannot be the only check. Second, that
   `git status --porcelain docs/baton` is empty; a rollback that left the
   tree dirty, or a stray untracked file, shows up only here. Either check
   failing means the checkpoint did not happen — say that instead of
   reporting success.
2. The `Next action` line as written, so they can see what the next session
   will pick up and correct it now if it is wrong.

Lead with `suspect: true` if reconciliation set it, and name `/baton:clear`
with it: only a human lowers that flag, and every resume after this one stops
on it until one does. A divergence between what state claims and what the
repository shows is the one thing they need to see before they decide
anything else.
