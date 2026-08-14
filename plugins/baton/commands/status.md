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
   With either flag up, name `/baton:clear`: only a human lowers one, and this
   report is where they find out what to type. If neither is set, say nothing
   here rather than reporting "all good".
2. **Whether this run is unattended.** Read `autopilot` from the frontmatter,
   normalized the way the session-start hook already does before comparing
   it, not compared literally: trim whitespace, strip a trailing `\r`, strip
   one layer of matching quotes, fold case. `state.md` is written by an
   agent, not validated input, so `off`, `"OFF"`, `off ` and a CRLF-terminated
   line are all the same value, and the dangerous direction is a false
   positive here — reporting "unattended" for a run the human turned off
   tells them the opposite of the truth, which is worse than saying nothing.

   If, once normalized, it is not `off`, check `autopilot_grant` before
   reporting anything: `—`, or any value that names no journal entry, means
   the claim of a grant has nothing behind it, and that disagreement between
   the two fields is itself what the human needs to see — say so plainly,
   rather than printing `Autopilot: all` as though the grant were sound.
   Otherwise say so on its own line, with the scope and the granting journal
   entry: `Autopilot: all (DEC-0007)`. If `autopilot` is `off`, say nothing
   here — an `Autopilot: off` line in every report is noise in the one place
   that has to stay short enough to be read in full.
3. **Decisions awaiting review.** Entries live in `docs/baton/journal/`, named
   `NNNN-<slug>.md`; `baton-journal` allocates `NNNN` strictly increasing, so
   the numeric prefix is the order — sort on it, highest first. Not the
   frontmatter `timestamp`: the prefix is allocated by one script and cannot
   disagree with itself, while a timestamp is written by hand into the entry
   and can. List every entry with `needs_review: true` this way — one line
   each: id, what was decided, why it needs them. Include `incoming` entries:
   those are inputs that arrived mid-run and may need an amendment to the
   constitution.
4. **Waves closed without a human.** Any row in the Waves table whose `gate`
   reads `auto` was closed under the autopilot, on the word of the same agent
   that did the work. Name the verdict file under `docs/baton/gates/` for each
   one, so a human who wants to look has somewhere to start.
   `—` means nothing produced a verdict at all. Neither value is a question
   waiting on an answer — a run that is waiting on one says so at item 1. A
   run that has never closed a wave under the autopilot has no
   `docs/baton/gates/` directory yet — that is the ordinary case, not a
   fault to report; say nothing here rather than reporting an error.
5. **Now.** Current wave, `Next action`, `In flight`.
6. **Waves.** The table, one line per wave, statuses only.

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
