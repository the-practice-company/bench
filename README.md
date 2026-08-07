# bench

A Claude Code marketplace: tools for agent work that outlives a single
context window.

## What is here

| Plugin | What it is |
|---|---|
| **[baton](plugins/baton)** | Keeps goal and state coherent across multi-day autonomous runs. Durable state in git, one-command checkpoint, verified resume after compaction, an append-only decision journal, and unattended execution gated against the run's own rules. |

## Install

```
/plugin marketplace add the-practice-company/bench
/plugin install baton@bench
```

The syntax is `<plugin-name>@<marketplace-name>`. Each plugin's own README,
under `plugins/`, covers what it does and what it needs alongside it.

To work against a checkout instead of the published repository, point the
first command at the directory:

```
/plugin marketplace add /path/to/this/checkout
```

Start a fresh session afterwards. A plugin's hooks, skills and commands only
take effect in a session that begins after the install, not the one you
installed from.

## What belongs here

Plugins written for this marketplace, and nothing else.

bench does not re-export third-party plugins. Where a plugin here wants a
companion — baton wants
[superpowers](https://github.com/obra/superpowers), installed as
`superpowers@claude-plugins-official` — it points at the marketplace that
already ships it rather than carrying a copy. A re-exported entry would
either drop the upstream's commit pin, handing whoever controls that
repository's default branch a say in what lands on your machine at install
and at every version bump, or carry a second pin someone has to keep in step
with the first by hand. Neither is worth owning to save a word.

## Requirements

`git`, `bash`, and the standard Unix text tools that ship with any Linux or
macOS install. No language runtime, no package manager, no server. (`python3`
is used by the test suite only; it never runs as part of any plugin here.)

## Licence

MIT — see [LICENSE](LICENSE).
