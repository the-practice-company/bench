---
description: Ratify the constitution - review its digest, then mark it ratified
disable-model-invocation: true
---

Ratify this run's constitution.

Ratification is when the run acquires rules nobody may edit afterwards: from
here `baton-gate` judges every wave against this file, and `baton-write`
refuses its path outright. The human reads it and says yes in chat; you write
the four fields. That is safe only because of `disable-model-invocation: true`
above — an agent that could run this command could sign the rules it is about
to be judged by.

## 1. Show what the file says

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/baton-digest" constitution
```

Post that output as it stands. Everything the human reads comes from
`baton-digest constitution` — do not summarise it, reorder it, shorten it, or
add what you make of it. Someone who approves your account of the constitution
has approved you and not the file, and that difference is the whole of this
command. The script prints so that you do not.

A non-zero exit stops this command; report what the script printed. Exit 3
means there is no constitution here, or one whose frontmatter block is never
closed — `/baton:init` is what writes a constitution, and nothing here can
ratify a file that is not there.

## 2. Stop if there is nothing to ratify yet

Both cases below stop before anything is written, and leave the file as they
found it.

**`Status:` already reads `ratified`.** Say so and stop. Refilling the fields
would move `git_anchor` onto today's HEAD and re-anchor the run to a commit
its signer never saw. A constitution that has to change afterwards changes by
amendment: the human appends to its `## Amendments` section, which is their
writing and not yours.

**An unfilled placeholder marker is still in the file.** `/baton:init` leaves
exactly three — the values of `ratified_by`, `ratified_at` and `git_anchor`,
which step 4 replaces. A marker anywhere else means the decomposition was
never finished, so stop, name the fields still carrying one, and say that
`/baton:init` is where they get filled in. Check it the way `baton-gate` does:
its exit-3 check is a whole-file match that refuses the constitution whatever
`status` says, so a run ratified over a marker stalls at its first gate. Read
the literal token out of that check in
`${CLAUDE_PLUGIN_ROOT}/scripts/baton-gate` rather than from memory, and never
write it into the constitution — the match covers the whole file, so a line
quoting it refuses that file forever.

## 3. Read the signature, then ask

```bash
git config user.name
git rev-parse HEAD
```

An empty first line means `user.name` is unset: ask what name to record, in
the same message as the confirmation below so it costs one reply and not two.
Do not substitute the git email, the system username, or the last committer —
`ratified_by` is a signature, and one nobody typed is not one. If they decline
to give a name, stop — and leave them the way back rather than at a wall:
`git config user.name "Their Name"` records it for this repository, and
`/baton:ratify` reads it the next time they type it. Signing for them is the
one thing this command must not do.

Then ask one question, phrased so that no is an available answer: does this
constitution say what they want this run held to? Name the signature and the
anchor SHA in the same message.

If they say no, write nothing. Do not offer to fix the constitution yourself,
since the only lines this command may touch are step 4's four; and do not
leave them at a dead end either — `/baton:init` is what rewrites a
constitution, and `/baton:ratify` signs it once it says what they meant.

## 4. Write the four fields

Directly, with plain git. `baton-write` refuses `docs/baton/constitution.md`
unconditionally, so this is the second and last write the plugin makes to that
path: `/baton:init` created the file, this signs it, and both go around
`baton-write` for the same reason, behind the same flag.

Edit `docs/baton/constitution.md` in place, changing these four values and
nothing else: `status` to `ratified`; `ratified_by` to the name from step 3;
`ratified_at` to the current time in ISO 8601 (`date -u +%Y-%m-%dT%H:%M:%SZ`);
`git_anchor` to the SHA from step 3, which is the repository as the human
approved it rather than the commit that records their approval. Then commit it
alone, so the signature carries nothing else in with it:

```bash
git add docs/baton/constitution.md
git commit -q -m "baton: ratify constitution"
```

## 5. Say what the run is anchored to

Report the name, the timestamp and the anchor SHA as written, and that the
constitution is read-only to you from here. Then what comes next:
`/baton:auto` hands the run over, `/baton:status` shows where it stands.
