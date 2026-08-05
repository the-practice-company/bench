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

`$ARGUMENTS`, if present, holds up to two things, in either order: a wave
number and `--since <ref>`. A wave number puts only that wave on the
autopilot; empty means every wave still `todo`. `--since <ref>` names the base
the first wave's gate should diff from — parsed and validated in step 2,
recorded in step 4.

## 1. Refuse the cases that are not a run

If `docs/baton/state.md` does not exist, this repository is not a baton run:
say so, suggest `/baton:init`, and stop. If `docs/baton/constitution.md`'s
`status` is not `ratified`, or a `REPLACE-WITH` token remains in it, say so and
stop — nobody has signed the rules this run would be held to.

Then, before spending any time on scope or a readiness review, find out
whether that time would be wasted:

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/baton-lock" check "${CLAUDE_CODE_SESSION_ID:-$CLAUDE_SESSION_ID}"
```

`check` is read-only — it takes nothing, so there is nothing to release if
what follows stops.

| Exit | Meaning | What to do |
|---|---|---|
| 0 | This session already holds it. | Continue. |
| 3 | Another session holds it live. | Stop and report. This is the whole reason to check this early: telling the human now costs them nothing; telling them after a readiness review costs the review. |
| 4 | A lease exists but has expired. | Continue — step 4's `acquire` takes over an expired lease cleanly, and journals it. |
| 5 | No lease at all. | Continue. |

## 2. Parse `$ARGUMENTS` and establish the scope

`$ARGUMENTS`, if present, holds up to two things, in either order: a bare wave
number, and `--since <ref>`. Split on whitespace; anything that is not one of
those two forms — a second bare number, a token that is neither a number nor
`--since` nor the ref immediately after one — is not an argument this command
understands: say what was passed and stop, rather than guessing at intent.

**The wave.** No number: every wave with status `todo`, the constitution's
wave order, restricted to waves in scope — not a topological sort of
`depends_on`; see step 3 for why. A number: that wave alone, and it has to
actually be a scope, not a wish:

- it must name a wave that exists in the constitution's Waves list — say which
  wave numbers do exist if it does not;
- its status must be `todo` — `doing` is someone else's work already in
  flight, `done` is a review with nothing left to approve, `blocked` needs a
  human before anything runs on it at all; say which of these it is and stop
  rather than handing a readiness review a wave that was never a candidate;
- every wave in its transitive `depends_on` must be `done` — say which is not.
  That is not a scope, it is a wish;
- nothing in its `consumes` may appear in the `produces` of any wave that is
  currently `blocked` — the third availability rule `baton-autopilot` applies
  per wave, and skipping it here is how a scope gets accepted that the loop
  immediately finds unavailable: it checks all three, finds nothing to work
  on, writes `autopilot: off`, and hands the grant back one step after a
  human sat through a review and said go. Most waves declare no `consumes` at
  all and pass this trivially; where one does and a `blocked` wave's
  `produces` names it, say which wave is blocked and which contract they
  share, and stop.

**The base**, `--since <ref>`, is independent of the wave and optional either
way. It exists for exactly the case `baton-autopilot` stops on: a multi-root
repository, where the first wave's gate cannot infer where history begins and
needs a human to say so. Resolve it before anything downstream depends on it:

```bash
git rev-parse --verify "<ref>^{commit}"
```

Anything other than one resolved commit — `<ref>` names nothing in this
repository, or names something that is not a commit — is the same kind of
wish as a wave number that does not exist: say what was passed and stop,
rather than recording a base the first wave's gate cannot use either.

## 3. Run the readiness review

Not "do you have any questions". A question only covers a gap you already
know is there, and the gaps that cost a night are the ones you do not.

Lay out, wave by wave in execution order:

- **which waves, in what order** — the constitution's wave order, restricted
  to waves in scope. `depends_on` is a constraint that order has to satisfy,
  not what generates it: cite it to show the order is safe. If a wave in the
  constitution's own list precedes one of its own dependencies, that is a
  stop, not a reordering — say which waves and which dependency. The
  constitution is the human's; picking a different order than the one they
  wrote, silently, is not this command's call to make;
- **where each spec comes from**: the file named in the wave's `spec` cell, or
  "I will derive it from the constitution";
- **what closing it means**: the `exit_criteria` quoted from the constitution,
  word for word, not paraphrased;
- **what will check it**: `verify_cmd`;
- **where you are not sure** — a plain list, and the most useful part of this
  whole exercise.

Then hand it to the human. They correct it or say go. A correction is theirs
to state and yours to fold in and show again — do not argue it down.

## 4. On "go", take the lease and record the grant

Nothing before this point writes anything, so nothing before this point needs
the lease — every stop above holds nothing, and there is nothing to release.

Confirm the tree is still clean. The review can run long, and this is the
moment that matters — the moment the human actually leaves — not the moment
step 1 happened to check it:

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/baton-observe"
```

`tree_clean` must be `true`; `dirty_count` names how much is outstanding if it
is not. Uncommitted work at the moment the human leaves is work that no later
session can tell apart from work in flight — say so and stop. Nothing has been
acquired yet, so there is nothing to release.

Then take the lease:

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/baton-lock" acquire "${CLAUDE_CODE_SESSION_ID:-$CLAUDE_SESSION_ID}"
```

Exit 3 means another session took it in the window since step 1's check — a
real possibility, and the right one to have: it fails loudly, with the human
still here to see it and retry, rather than the alternative of taking the
lease back at step 1 and stranding it for six hours if this stop had happened
there instead. Stop and report; a second `/baton:auto` starts from a clean
readiness review. Exit 64 means the environment gave neither session-id name:
report it and stop rather than inventing an id.

If `acquire` prints `takeover=<previous session>` — it does when it displaces
an expired lease — journal it as a `takeover` entry the way `baton-resume`
does: `${CLAUDE_PLUGIN_ROOT}/scripts/baton-journal` hands back the id and
path, frontmatter `type: takeover`, sections `## Who was displaced` and
`## Why it was believed safe`, written through `baton-write`. An expired lease
is entirely plausible this deep into a run — do not skip this because nothing
here looks like a resume.

Three writes now, in this order:

**The journal entry.** Allocate the id and path:

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/baton-journal" autopilot-grant
# id=DEC-0007
# path=docs/baton/journal/0007-autopilot-grant.md
```

`type: autopilot`, and the body carries the scope, the review as it stood when
approved, and the human's corrections. Add `base:` to the frontmatter too: the
commit step 2's `--since` resolved to, or `—` if none was given — the first
wave's gate needs a field to read later, not a sentence to parse. Write it
through `baton-write` as `baton-checkpoint` step 5 does. This entry is the
grant; everything else points at it.

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
