---
description: Hand the run to the agent - readiness review, then work without a human present
disable-model-invocation: true
---

Put this run on the autopilot.

This command carries `disable-model-invocation: true` for the same reason
`/baton:init` does. A grant the agent can give itself bounds nothing, and
"turn the autopilot on" is exactly the grant that must stay with the human.
`/baton:checkpoint` and `/baton:status` remain open to the model; they write
nothing the agent is judged by.

`$ARGUMENTS`, if present, is a single wave number: put only that wave on the
autopilot. Empty means every wave still `todo`.

## 1. Refuse the cases that are not a run

If `docs/baton/state.md` does not exist, this repository is not a baton run:
say so, suggest `/baton:init`, and stop. If `docs/baton/constitution.md`'s
`status` is not `ratified`, or a `REPLACE-WITH` token remains in it, say so and
stop — nobody has signed the rules this run would be held to.

Take the writer lease before anything else:

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/baton-lock" acquire "${CLAUDE_CODE_SESSION_ID:-$CLAUDE_SESSION_ID}"
```

Exit 3 means another session holds a live lease: stop and report it. Exit 64
means the environment gave neither session-id name: report it and stop rather
than inventing an id.

Then check the tree is clean:

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/baton-observe"
```

`tree_clean` must be `true`; `dirty_count` names how much is outstanding if it
is not. Uncommitted work at the moment the human leaves is work that no later
session can tell apart from work in flight.

## 2. Establish the scope

No argument: every wave with status `todo`, ordered topologically by
`depends_on` from the constitution.

An argument: that wave alone. If any wave in its transitive `depends_on` is not
`done`, say which and stop — that is not a scope, it is a wish.

## 3. Run the readiness review

Not "do you have any questions". A question only covers a gap you already
know is there, and the gaps that cost a night are the ones you do not.

Lay out, wave by wave in execution order:

- **which waves, in what order**, and why that order — cite `depends_on`;
- **where each spec comes from**: the file named in the wave's `spec` cell, or
  "I will derive it from the constitution";
- **what closing it means**: the `exit_criteria` quoted from the constitution,
  word for word, not paraphrased;
- **what will check it**: `verify_cmd`;
- **where you are not sure** — a plain list, and the most useful part of this
  whole exercise.

Then hand it to the human. They correct it or say go. A correction is theirs
to state and yours to fold in and show again — do not argue it down.

## 4. On "go", record the grant

Three writes, in this order:

**The journal entry.** Allocate the id and path:

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/baton-journal" autopilot-grant
# id=DEC-0007
# path=docs/baton/journal/0007-autopilot-grant.md
```

`type: autopilot`, and the body carries the scope, the review as it stood when
approved, and the human's corrections. Write it through `baton-write` as
`baton-checkpoint` step 5 does. This entry is the grant; everything else points
at it.

**The state.** In the same checkpoint, and by `baton-checkpoint`'s procedure
rather than a bare `baton-write` — that skill owns the state write, and its
step 6 diff is what stops a draft assembled from memory from dropping a
section, committing the deletion, and leaving the tree clean behind it. Set
`autopilot: <all|N>`, `autopilot_grant: DEC-NNNN`, and a **Next action** that
names the first concrete step of the first wave.

**The session goal.** One English line, short, the thing this session is for.
Print it, and put it on the clipboard:

```bash
printf '%s' "<the goal line>" | { pbcopy || wl-copy || xclip -selection clipboard; } 2>/dev/null \
    || echo "(copy it by hand — no clipboard tool here)"
```

The copy failing stops nothing. It is a convenience, not part of the protocol.

## 5. Start

Use the `baton-autopilot` skill and begin. Do not wait for a further word — the
human has left; that was the point.
