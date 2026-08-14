---
description: Clear the flag that stopped the run - review why it was raised, then lower it
disable-model-invocation: true
---

Lower a stop flag on this run.

`suspect` and `needs_human` are granted fields: the agent raises them and never
lowers them. `baton-write` enforces that — a `docs/baton/state.md` write that
does not carry a flag already set in HEAD forward as a positive `true` exits 3.
This command is that one transition and nothing else, which is why it writes
with plain git rather than through `baton-write`: the tool refuses exactly this,
and refusing it is its job. That is safe only because of
`disable-model-invocation: true` above. An agent that could run this command
would have no stop at all, since the thing lowering the flag would be the run
the flag was raised to halt.

## 1. Show what stopped the run

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/baton-digest" stop
```

Post that output as it stands. Everything the human reads about the stop comes
from `baton-digest stop` — do not summarise it, reorder it, shorten it, or add
what you make of it. Someone who lowers a flag on your account of `state.md`
has taken your word for the very thing the flag was raised to preserve, and
that difference is the whole of this command. The script prints so that you do
not.

A non-zero exit stops this command; report what the script printed. Exit 3
means there is no `state.md` here, or its frontmatter block is never closed, or
a flag reads as neither `true` nor `false`. None of the three is a raised flag
you can lower: the first is a repository with no run in it, where `/baton:init`
is what starts one, and the other two are a file whose stop nobody can read,
which has to be repaired by hand before this command or `baton-write` can act
on it at all. Step 4 says what that frontmatter has to look like.

## 2. Stop if nothing is raised

The digest says it in as many words — `Nothing is raised`. Say that back and
stop: there is no flag here to lower, and the run is waiting for nobody. Leave
them somewhere rather than nowhere — `/baton:status` shows where the run
actually stands, and `/baton:continue` picks it back up if it was left
unattended.

## 3. Ask about each raised flag, one at a time

The digest names what is up on its `Raised:` line. Ask about all of them in a
single message, so it costs one reply and not two, but ask about each as its
own question with its own yes or no. The two flags go up for different reasons
— `suspect` says a claim in `state.md` diverged from what the repository
shows, `needs_human` says the run stops here — so lowering both off one answer
lowers the one nobody was asked about.

Before they answer about `suspect`, tell them the part the digest cannot show
them: lowering it does not settle the divergence its `Suspect:` line describes.
If what raised it is still true of the repository, the next resume that checks
that claim raises it again and they are back here. Said now, that is a choice
between clearing the flag and settling what it points at first; said afterwards
it reads as a defect.

For `needs_human`, say what lowering it does and does not do. It un-stops the
run. It does not move the wave the digest reports on its `Blocked:` line, nor
the dependency named there — this command writes the flag lines and nothing
else, and the status column moves as the work moves.

If they say no, or say anything you cannot read as a yes, write nothing. Say
which flags are still up and that the run is still stopped, then name what
would come first: the divergence to settle, or the dependency the blocked wave
is waiting on. `/baton:clear` is what they type once that is done.

## 4. Lower the flags they confirmed, with plain git

Only the flags they confirmed. Edit `docs/baton/state.md` in place, changing
the confirmed `suspect: true` or `needs_human: true` to `false` and nothing
else in the file. Leave `writer` and `updated_at` as they stand: those record
the run's last checkpoint, and this edit is not one.

Then commit it alone, naming the flag that came down:

```bash
git add docs/baton/state.md
git commit -q -m "baton: clear needs_human"
```

### What this write must not break

Nothing checks it. The guard that would is the one being stepped around, and it
reads a flag's previous value out of `HEAD:docs/baton/state.md` with a parser
anchored on line 1 — so a `state.md` in HEAD that the parser cannot read is a
guard that finds no flag set and refuses nothing, for this write and every
write after it, for the rest of the run. That failure is silent: it leaves a
file that still looks right and an enforcement mechanism that has quietly
stopped running. This command is the only writer left that can produce one,
because it is the only one that goes around the tool. So what you write keeps
all of this:

- the frontmatter block opening on the very first line with `---`, no blank
  line and no byte of anything ahead of it;
- that block closed by a `---` line of its own;
- both flags present as an explicit `true` or `false` line inside it. Lowering
  a flag means writing `false` — deleting the line lowers it too, and lowers it
  where nothing can see it any more;
- no CRLF line endings introduced. The guard compares line 1 against `---`
  exactly and does not strip a carriage return first, so a file saved with
  Windows endings goes unreadable to it while `baton-digest`, which does strip
  them, carries on printing the flags as though nothing had happened.

`state.md` also stays within 60 lines, which is `baton-write`'s cap. You are
around that tool for the flag, not for the size, and the cap is a property of
the file rather than of the tool that usually enforces it.

## 5. Check what landed is still readable, then say what is left

Confirm it by applying the guard's own test to what was just committed —
nothing else will:

```bash
git show HEAD:docs/baton/state.md | awk '
    NR==1 && $0=="---" { infm=1; next }
    infm && $0=="---"  { closed=1; exit }
    infm && /^(suspect|needs_human):[ \t]*(true|false)[ \t]*$/ { seen++ }
    END { exit !(closed && seen==2) }
'
```

Non-zero there means the frontmatter you just committed no longer reads as
frontmatter. Fix it against the list above and commit again immediately,
before anything else in the run gets a chance to write. Then re-run the digest:

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/baton-digest" stop
```

Report what it prints rather than what you did — which flags are still raised,
or that none are. If `needs_human` is still up the run is still stopped, and
`/baton:clear` is how the rest of it comes down. If nothing is raised,
`/baton:continue` picks the run back up and `/baton:status` shows where it
stands.
