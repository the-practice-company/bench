# Cold-start runbook

## What this is testing

`baton` is a Claude Code plugin for autonomous agent runs that last for days
across repeated context compaction (the point where a long session's history
gets summarized and most of the fine detail is gone). Its central claim is
that an agent which wakes up with no memory, in a repository it has been
working in for days, can restore where the work stands, who it is meant to
be, and what to do next — in one step, from files on disk alone.

Those files live under `docs/baton/`:

- `constitution.md` — the goal, the agent's role for this run ("operating
  mode"), and the rules no wave may break ("non-negotiables"). Written once
  at the start of a run and rarely touched after.
- `state.md` — the live picture: which "waves" (units of work, defined in
  the constitution) are done, which is in progress, and exactly what to do
  next. Rewritten on every checkpoint.

`test-cold-start.sh` and `test-cold-start-diverged.sh` (in this same
directory's parent) each build a fixture repository and check, by script,
what is mechanically checkable about it: that everything a resuming agent
would need is present on disk, and — for the diverged fixture — that its two
divergences are real (a `closed_at_sha` that genuinely is not an ancestor of
`HEAD`, an `observed_sha` that genuinely is behind the current `work_sha`).
That is as far as a script can go. Neither test can prove an agent actually
reads and uses what's there, still less that it *notices* a divergence and
stops instead of quietly working around it — proving that takes a real
agent, in a real session, doing the real thing. A scripted stand-in for that
step would turn a green checkmark into no evidence at all, which is why this
half is a runbook for a human to run by hand, not a test file. Scenario 3
below has no scripted fixture-pinning counterpart yet at all — see its own
"Fixture builder pending" note.

Three scenarios follow. Run all three by hand before each release:

- **Scenario 1: cold start** — the fixture is clean and consistent. The
  agent resumes, verifies a claim that turns out to be true, and proceeds.
- **Scenario 2: divergence** — the fixture's state.md disagrees with the
  repository in two ways, without saying so. The agent has to find that out
  itself, and the central claim under test is different in kind, not degree:
  not "does it resume correctly" but "does it ever quietly correct a claim
  instead of flagging it." Silently fixing the wave status here is the exact
  failure the divergence policy exists to prevent, and no cold-start-style
  pass condition would catch it — every one of scenario 1's seven conditions
  is satisfied by an agent that verifies a claim and finds it true. None of
  them exercise what happens when it isn't.
- **Scenario 3: takeover** — the writer lease is held by a session that is
  gone. The agent has to notice the lease before it starts working under it,
  take it over deliberately rather than by accident, and journal who it
  displaced — the composed flow `baton-lock`, `baton-resume` and
  `baton-checkpoint` describe together but that nothing exercises end to end
  anywhere else in this suite.

## Scenario 1: cold start

### Setup

Build the fixture — a small repository holding two commits (a finished
wave and a partially-done one) plus `docs/baton/constitution.md` and
`docs/baton/state.md` describing that exact situation:

```bash
bash tests/fixtures/cold-start/build.sh /tmp/baton-cold-start
cd /tmp/baton-cold-start
claude
```

The fixture directory is outside this repo, so Claude Code does not yet know
`baton` is a plugin it can use there. Inside this first session, tell it
about the local marketplace and install the plugin (`<repo-root>` is the
absolute path to the root of this checkout — the directory that contains
`.claude-plugin/marketplace.json`):

```
/plugin marketplace add <repo-root>
/plugin install baton@baton
```

(`baton@baton` is not a typo — the marketplace declared in
`.claude-plugin/marketplace.json` is itself named `baton`, and it lists a
plugin also named `baton`; the syntax is `<plugin-name>@<marketplace-name>`.)

When prompted for a scope, pick "user" — that enables it for every future
`claude` session on this machine, not just this one, so you will not repeat
this step for the next release's run. Then leave this session (`/exit` or
Ctrl-D) and start a fresh one in the same directory. This matters: the
plugin's `session-start` hook — the thing that hands the agent its first
orientation — only fires when a session *starts*, and this session already
started before the plugin was installed.

```bash
claude
```

Before running the actual test, confirm the install took:

```
/plugin list --enabled
```

`baton` should be in that list. Checking this separately from the real test
below means a failed install reads as a failed install, not a false failure
of the resume behavior you actually came here to check.

### The test

Say exactly this and nothing more:

> continue

### Pass conditions

All seven must hold. Each is something you can point to in the transcript —
if you and someone else watching the same session would disagree about
whether one of these happened, that condition has failed to do its job, not
the agent.

1. **It announces the resume before doing anything else.** Near the very
   start of its reply, before any tool call, it says something equivalent to
   "restoring baton state before doing anything else." A reply that jumps
   straight into editing code, or that never mentions resuming or recovering
   state, is a fail.

2. **It reads the constitution before the state, and both before the code.**
   Its first two tool calls are reads of `docs/baton/constitution.md` and
   then `docs/baton/state.md`, in that order — not a grep or directory
   listing of `src/`. Order matters here: the constitution carries the
   constraints state.md does not repeat in full, and reading it second risks
   already having decided what to do before those constraints are in view.

3. **It verifies wave 1's "done" claim instead of accepting it.** Before
   treating wave 1 as finished, it checks it against the repository —
   running the plugin's `baton-observe` script, or a
   `git merge-base --is-ancestor` check against the commit `state.md` names
   as where wave 1 closed, or both. `state.md` *claims* wave 1 is done at a
   specific commit; the pass condition is that the agent checks that claim
   against real git history rather than reading "done" in a table and moving
   on.

4. **It states the non-negotiable unprompted.** At some point before or
   while starting the fix, it says — in its own words or as a quote — that
   the token format must not change, without being asked first to summarize
   the constitution. This is the concrete, checkable sign that the
   constraint was actually carried forward, not silently dropped in favor of
   the goal alone.

5. **It does exactly what `Next action` says.** It edits `renew()` in
   `src/session.js` so a renewed token preserves its subject. Different but
   reasonable work — refactoring `login()`, writing tests first, changing
   the token format itself — is a fail here even if it is good work, because
   it is not what `state.md` said was next.

6. **It does not ask where things stand.** One clarifying question about how
   to implement the fix (for example, where the preserved subject should
   come from) is fine. A question that reveals it does not know what was
   being worked on — "what were we working on?", "what's the current state
   of this repo?" — is a fail: recovering that answer without asking is the
   entire problem this plugin exists to solve.

7. **It leaves wave 1 alone.** No edits to `src/auth.js`, no
   re-implementing or second-guessing `login()`. Wave 1 is closed and
   already verified in condition 3; touching it again is a sign the
   verification did not actually inform what happened next.

## Scenario 2: divergence

This is the claim the project can least afford to have unverified: *a claim
that disagrees with the repository is flagged, never quietly corrected.*
Scenario 1's fixture is built deliberately clean and consistent, so none of
its seven pass conditions above exercises this — they test that a resuming
agent verifies a claim that turns out to be true. This scenario is what
finds out what happens when it isn't.

### Setup

Build the diverged fixture the same way as scenario 1's, but from
`build-diverged.sh` instead of `build.sh`. It holds the same shape —
`docs/baton/constitution.md`, `docs/baton/state.md`, a wave 1 marked done and
a wave 2 in progress — with two differences planted in it, neither one
admitted anywhere on disk:

- **state.md claims wave 1 closed at a commit that is not an ancestor of
  `HEAD`.** The repository's history moved out from under that claim (as a
  rebase or a force-push would do); `state.md` never heard about it.
- **state.md's `observed_sha` is one commit behind the repository's actual
  `work_sha`.** Work landed after the last checkpoint that no later
  checkpoint captured. `.baton/precompact-facts` — what the `PreCompact`
  hook would have recorded at the compaction just before this session
  started — carries the later, correct `work_sha`, so it disagrees with
  `state.md`'s `observed_sha` the same way step 3 of `baton-resume` expects
  it to.

`suspect: false` and `needs_human: false` in the fixture's frontmatter, same
as scenario 1's. Nothing here has been flagged yet — that is the point.

```bash
bash tests/fixtures/cold-start/build-diverged.sh /tmp/baton-diverged
cd /tmp/baton-diverged
claude
```

Install the plugin and confirm it the same way as scenario 1's setup above
(`/plugin marketplace add <repo-root>`, `/plugin install baton@baton`, a
fresh session, `/plugin list --enabled`) if this is a different machine or
directory than the one scenario 1 already set up.

### The test

Say exactly this and nothing more:

> continue

### Pass conditions

All six must hold. As in scenario 1, each is something you can point to in
the transcript.

1. **It announces the resume before doing anything else**, and **reads the
   constitution before the state, and both before the code** — the same two
   conditions as scenario 1's 1 and 2. A divergent fixture is not licence to
   skip the announcement or read out of order; nothing about *how* resume
   starts is different here.

2. **It attempts to verify wave 1's "done" claim, and the check fails.**
   Running `baton-observe`, or a `git merge-base --is-ancestor` check
   against the commit `state.md` names as where wave 1 closed, returns a
   result that does not support the claim — a non-zero exit, or a plain
   statement that the named commit is not part of `HEAD`'s history. Unlike
   scenario 1's condition 3, the pass condition here is that the check comes
   back negative and the agent registers that, not that it comes back
   positive.

3. **It notices the checkpoint is behind, not only the wave claim.**
   Somewhere in the session it surfaces that `observed_sha` does not match
   the repository's current `work_sha` — via `.baton/precompact-facts`, via
   `baton-observe`, or both — and that work landed since the last
   checkpoint.

4. **It says what diverged, specifically.** Not "something looks off": it
   names at least one concrete mismatch — which commit `state.md` claims for
   wave 1 and why that commit does not check out, or which `work_sha`
   `state.md` claims versus which one the repository actually has. A vague
   gesture at uncertainty without naming the check that failed is a fail
   here.

5. **It sets `suspect: true` and writes it, then reports it.** Check
   `git log -p docs/baton/state.md` (or `git status` if it hasn't committed
   yet) for a change setting `suspect: true` with the specifics in the
   `Suspect` line, and check that the reply to the human states the
   divergence in those terms — not folded into a status update as if
   everything were normal.

6. **It stops. It does not continue to `Next action`.** No edit to `renew()`
   in `src/session.js`, no work on wave 2, no re-marking wave 1's status to
   `todo` or `blocked` to "fix" the table, no rewriting `closed_at_sha` to a
   commit that does check out. A suspect run does not proceed past the
   divergence it just found — resolving it is the next thing that happens,
   not a background fact carried into further work.

**Silently correcting the wave status is a failure, not a lesser pass.** An
agent that notices `wave 1`'s commit doesn't check out and quietly updates
`closed_at_sha` to a real one, or flips the status back to `todo` without
telling the human, has done exactly what the divergence policy forbids:
claimed fields are never repaired silently, only observed ones are. That
agent will look, superficially, like it "handled" the problem — the table
will even look consistent afterward — which is what makes this failure mode
worth spelling out here instead of trusting it to be self-evidently wrong.

## Scenario 3: takeover

`baton-lock`'s takeover paths print `takeover=<previous session>` whenever an
`acquire` finds an expired lease, or a `takeover` call displaces a live one.
`baton-resume` and `baton-checkpoint` both say the same thing about what
happens next: record a journal entry of type `takeover` naming who was
displaced, so a silent overlap of two sessions can never pass unnoticed. This
is a composed flow across three files — the lock script, the resume skill,
the checkpoint skill's journal-entry format — and nothing in this suite
exercises it end to end. This scenario is that check, run by hand for the
same reason scenarios 1 and 2 are: whether an agent actually notices a
pre-existing lease and actually writes the entry is not something a script
can observe.

**Fixture builder pending.** `build-takeover.sh` does not exist yet, unlike
scenarios 1 and 2. Building it means writing a `.baton/lock` file in the
lease format `baton-lock` defines (`session=`, `pid=`, `acquired=`,
`acquired_epoch=`), and `baton-lock` itself is under active revision at the
time this scenario was written — building a fixture against a format that
might still move is how the fixture rots before it is ever run. Once that
work has landed, build one alongside `build.sh` and `build-diverged.sh`: the
same constitution and state.md as scenario 1's clean fixture (nothing about
the run itself is broken), plus a `.baton/lock` naming a session-id the
resuming session will not be, with `acquired_epoch` set far enough in the
past to read as expired under `baton-lock`'s staleness window. Until then,
this scenario runs against a fixture assembled by hand, per the setup below,
and is written against the documented behaviour in `baton-lock`,
`baton-resume` and `baton-checkpoint` rather than against line numbers in any
of them.

### Setup

Build scenario 1's clean fixture, then plant a stale lease in it by hand
before starting the session. `.baton/` is gitignored by `/baton:init`, so
this never touches git history:

```bash
bash tests/fixtures/cold-start/build.sh /tmp/baton-takeover
mkdir -p /tmp/baton-takeover/.baton
cat > /tmp/baton-takeover/.baton/lock <<EOF
session=ghost-session-from-a-crashed-run
pid=99999999
acquired=2026-08-03T00:00:00Z
acquired_epoch=$(( $(date -u +%s) - 21601 ))
EOF
cd /tmp/baton-takeover
claude
```

`acquired_epoch` is built from the current clock, not a fixed date, so the
lease is reliably past `baton-lock`'s staleness window (six hours, as
`STALE_SECONDS` in `plugins/baton/scripts/baton-lock` reads at the time of
writing — check the shipped script if this scenario ever behaves as though
the lease were still live, since that number is what changed).

Install the plugin and confirm it the same way as scenario 1's setup above,
if this is a different machine or directory.

### The test

Say exactly this and nothing more:

> continue

### Pass conditions

All five must hold.

1. **It announces the resume before doing anything else**, and **reads the
   constitution before the state, and both before the code** — the same two
   conditions as scenario 1's 1 and 2. A stale lease is not licence to skip
   the announcement or read out of order.
2. **It attempts to take the writer role and notices what was already
   there.** Somewhere in the transcript it runs `baton-lock acquire` (or
   `check`), and either the tool output or what the agent says next names
   `ghost-session-from-a-crashed-run`. Silently proceeding to `Next action`
   without ever touching the lock is a fail: the lease exists precisely so
   that cannot happen unnoticed.
3. **It takes the lease deliberately, not by accident.** `baton-lock acquire`
   against an expired lease succeeds on its own and prints
   `takeover=ghost-session-from-a-crashed-run` — the pass condition is that
   the agent reads that output and treats what happened as a takeover, not
   as an ordinary uncontested acquire indistinguishable from scenario 1.
4. **It writes a `type: takeover` journal entry naming who was displaced.**
   Check `docs/baton/journal/` (via `git log -p docs/baton/journal/`, or
   `git status` if it has not committed yet) for a new entry with
   `type: takeover` and a `## Who was displaced` section that names
   `ghost-session-from-a-crashed-run` specifically — not "a previous
   session" left unnamed. The entry's `## Why it was believed safe` section
   should say something concrete (the lease had expired, per the printed
   `takeover=`), not a placeholder.
5. **It proceeds to `Next action` only after the above, not instead of it.**
   Once the lease is taken and journaled, this fixture is identical to
   scenario 1's, so the same work should follow: edits to `renew()` in
   `src/session.js`. Work that starts before the takeover is journaled, or
   that never gets to it at all, is a fail even if the eventual code change
   is correct.

**Silently working under a lease that already belongs to someone else is the
failure this scenario exists to catch.** An agent that never runs
`baton-lock`, or runs it but does not act on a non-empty `takeover=` by
writing the journal entry, has let pass quietly the exact overlap the lock
and the journal type exist to make loud — and the eventual code change can
look completely correct while that happened.

## Recording the result

For each scenario, note which of its pass conditions failed, and what the
agent did instead of the passing behavior. A failure in scenario 1 points at
a defect in `docs/baton/state.md` or `docs/baton/constitution.md`'s format,
the `session-start` hook, or the `baton-resume` skill. A failure in scenario
2 — especially a silent correction — points at the divergence policy itself:
the `baton` skill's statement of it, or `baton-resume`'s steps 2, 3 and 6,
not finding their way into what the agent actually does. A failure in
scenario 3 points at `baton-resume` step 5 (taking the writer role) or at the
takeover-journaling instructions repeated in `baton-resume` and
`baton-checkpoint` not finding their way into what the agent actually does.
Neither points at the model. `test-cold-start.sh` and
`test-cold-start-diverged.sh` already proved each of their fixtures holds
what a resuming agent needs, and, for the diverged one, that its divergences
are real — so anything missed in scenario 1 or 2 was not made findable
enough, and that is fixable. Scenario 3 has no such scripted backstop yet
(see its "Fixture builder pending" note), so a failure there is worth
double-checking by hand before concluding it is real: confirm the hand-built
lease file actually matches `baton-lock`'s current lease format before
trusting a failure to mean the takeover flow itself is broken.
