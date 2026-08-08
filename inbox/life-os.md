# Headless Obsidian Vault Access & Sync for Twinkle: Landscape, Comparison, and Architecture Recommendation

## TL;DR
- **For Twinkle's VPS agents, adopt a file-level toolchain — not the real app.** Treat raw markdown + frontmatter as the source of truth; use `notesmd-cli` (Yakitrak, Go — explicitly "works without requiring Obsidian to be running") + `ripgrep`/`yq` for structured/metadata queries, `mdbasequery` (a genuine Obsidian-Bases-compatible query engine) to execute `.base` files headlessly, and `qmd` (Tobi Lütke) for token-efficient BM25+vector search. There is **no official GUI-free full CLI**, and the Obsidian team has made no 2026 commitment to build one.
- **For sync, run git as the Mac↔VPS backbone (obsidian-git on Mac, cron/systemd auto-commit on VPS) and layer Obsidian Sync only for the iPhone**, keeping the two systems on separate write domains to avoid double-sync loops. The official `obsidian-headless` `ob` client is a viable alternative backbone but requires an Obsidian Sync subscription and only does sync (no query).
- **Do not run the real Obsidian app under Xvfb on the VPS as core infrastructure.** It works (and is the only way to get the official `base:query`), but it is officially unsupported, fragile across updates, and heavy. Keep it, if at all, as an optional side-car — not the primary read/write path.

## Key Findings

### The headless landscape has matured, but splits into three cleanly separated tiers
1. **The official CLI (bundled in the desktop app, v1.12, Feb 2026)** is a "remote control" that talks to a *running* GUI instance over IPC. It has ~115 commands including `base:query`, but **requires the app to be running** — if it isn't, the first command launches it. This is fine on the Mac, useless as pure server infrastructure.
2. **The official `obsidian-headless` (`ob`) npm client (Feb 2026, open beta)** is standalone and needs no GUI, but it is **Sync/Publish only** — it cannot read, query, or execute bases. It requires an Obsidian Sync subscription.
3. **Everything else is file-level tooling** that treats the vault as what it is on disk — a folder of markdown — and works whether Obsidian runs or not. This is the correct tier for Twinkle's autonomous agents.

### A real Obsidian-Bases-compatible query engine now exists outside Obsidian
`mdbasequery` (intellectronica, MIT, self-described as "CLI and library for querying Markdown-Frontmatter bases (Obsidian-compatible)") is a TypeScript CLI + library that parses `.base` YAML and executes it against a markdown vault — filters, formulas, views, grouping, summaries — with the same expression language semantics ("global filter AND view filter", topologically-ordered formula dependencies). It runs on Node 20+/Bun/Deno 2.x and emits json/jsonl/yaml/csv/md. It is very new (v0.0.1 released Feb 18, 2026, later v0.0.3 on npm; 8 GitHub stars), but it is the single most important discovery for Twinkle's requirement to "execute .base queries" server-side.

### `qmd` is the token-efficiency win for agent retrieval
Tobi Lütke's `qmd` (repo tobi/qmd went public Dec 8, 2025; crossed 22.6k GitHub stars by April 2026; v2.1.0 shipped tree-sitter code chunking and intent disambiguation on April 5, 2026) gives local BM25 + vector (sqlite-vec) + optional LLM reranking over markdown, exposes an MCP server and `--json` output. Lütke describes it as "an on-device search engine for everything you need to remember." A documented deployment (Mercury VP of Product Ryan Wiggins) indexed 15,000 docs / 3.5 million words locally and wired Claude Code's `UserPromptSubmit` hook to call `qmd` on every prompt, injecting context "without cloud sync or an API key." It fits Twinkle's skepticism of token-heavy tooling: it returns snippets, not files.

### The Obsidian team has NOT committed to a GUI-free full CLI
The forum feature request "A complete terminal based version of Obsidian (headless, no GUI)" (thread 111137, opened by the obsidian.nvim maintainer zzt42 on Feb 12, 2026) received **no core-developer reply**. An official forum moderator (WhiteNoise) clarified the CLI-vs-Headless split and, on March 27, 2026, called running the GUI app without a display "currently officially unsupported. So you are on your own if you choose to go down that path." Neither the roadmap nor kepano's 2026 posts promise a standalone full CLI. Plan as if it will never come.

## Details

### 1. Headless vault access tools — capability matrix

| Tool | Lang | Read | Write | FT search | Frontmatter query | Backlinks/links | Rename+link-fix | .base exec | Headless (no app) | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| **notesmd-cli** (Yakitrak, formerly obsidian-cli) | Go | ✅ | ✅ (create/update/append/move/delete/frontmatter edit) | ✅ (content + fuzzy) | partial (`frontmatter --print/--edit/--delete --key`) | ❌ | ❌ (move only, no backlink rewrite) | ❌ | ✅ | Active (v0.3.6, May 2026) |
| **obsidian-export** (zoni) | Rust | ✅ (export) | ❌ | ❌ | ❌ | resolves `[[ ]]`/`![[ ]]` on export | ❌ | ❌ | ✅ | Active (CalVer, 25.3.0) |
| **mdbasequery** (intellectronica) | TS | ✅ (query) | ❌ | via filters | ✅ (full Bases expr language) | file.links/backlinks per Bases spec | ❌ | ✅ **yes** | ✅ | New/immature (v0.0.1–0.0.3, 8★) |
| **qmd** (tobi) | TS/Node | ✅ (get/multi-get) | ❌ | ✅ BM25 | ❌ (content-oriented) | ❌ | ❌ | ❌ | ✅ | Very active (22.6k★, v2.1.0) |
| **mdq** (aaronshaf) | TS/Bun | ✅ | ❌ | ✅ (Meilisearch) + MCP | ❌ | ❌ | ❌ | ❌ | ✅ | Active |
| **mq** (harehare) | Rust | ✅ (AST slice) | ✅ (`-U` in-place) | selectors | frontmatter via YAML input | ❌ | ❌ | ❌ | ✅ | Very active (v0.6.0) |
| **obsidian-mcp** (lstpsche) | Rust | ✅ | ✅ | ✅ tantivy BM25 | ✅ (in-memory index: tags/links/headings) | ✅ (graph index) | partial | ❌ | ✅ | New; single binary, http/stdio |
| **obsidian-mcp-server** (cyanheads) | Node | ✅ | ✅ (surgical patch) | ✅ (text/JSONLogic) | ✅ (tags+frontmatter) | outgoing links | ❌ | reads .base as file | ✅ | Active; 14 tools, RBAC |
| **mcpvault** (bitbonsai) | Node | ✅ | ✅ (YAML-safe) | ✅ BM25 | validates frontmatter | ❌ | ❌ | reads .base as file | ✅ | Active |
| **Official CLI** | — | ✅ | ✅ | ✅ | ✅ | ✅ (`backlinks`, `orphans`) | ✅ (app does it) | ✅ `base:query` | ❌ (needs running app) | Official, v1.12 |
| **obsidian-headless `ob`** | Node | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ (sync only) | Official beta |

**notesmd-cli** is the workhorse for CRUD and simple frontmatter edits. Its README is explicit that it "works without requiring Obsidian to be running," and it was renamed from "Obsidian CLI" to "NotesMD CLI" precisely to avoid confusion after the official CLI shipped (latest v0.3.6, with Linux arm64/amd64 release assets). It respects Obsidian's Excluded Files for search, has JSON output for scripting, and supports an `--editor` flag for terminal-only environments. Its `move` command does *not* rewrite backlinks — link integrity is on you.

**Bases execution:** Besides `mdbasequery`, the practical fallbacks are (a) `yq`/`rg` + a Python script that reads the `.base` YAML filters and applies them to parsed frontmatter, or (b) a SQLite/FTS5 index rebuilt on write. Note the key Bases constraint: **Bases only reads YAML frontmatter, never inline Dataview-style `field:: value`** — so your strict-frontmatter discipline is exactly what makes headless base replication feasible. The `obsidian-query` Python skill pattern (a local HTTP API on :27180 exposing `/bases/:name?view=`, `/backlinks/:path`, `/frontmatter/:path`) is a good template for wrapping `mdbasequery` as a long-lived service for agents.

**Indexing layer:** `qmd` is the strongest fit (local GGUF embeddings, RRF fusion, MCP server, daemon mode `qmd mcp --http --daemon`). It's file-based and can watch the vault. For pure keyword/structured needs, `ripgrep` over frontmatter + a nightly FTS5 rebuild is lighter still.

### 2. MCP vs raw grep for Claude Code agents
Be honest with yourself here: for an agent that already has a shell, **plain `rg`/`notesmd-cli`/`mdbasequery` calls are cheaper and more transparent than a token-heavy MCP layer.** The community consensus (and kepano's own line — "It's not because your agent can do something with 12 tool calls and 20k tokens that it should") is that filesystem/CLI access beats MCP for most read/write/search. MCP earns its place in exactly two cases for you: (1) `qmd`'s MCP server, where semantic retrieval genuinely saves tokens over reading files; (2) a shared HTTP MCP (e.g., obsidian-mcp Rust in `--http` mode) when multiple parallel agents need one warm in-memory index of tags/links/backlinks. Otherwise, skip MCP.

### 3. Link integrity when writing headless — the sharp edge
This is the biggest safety risk. Obsidian only auto-updates `[[wikilinks]]` when *it* performs the rename; any external move/rename (notesmd-cli, `mv`, an agent) **silently breaks every backlink.** There is no mature standalone tool that renames a note and rewrites all inbound wikilinks across the vault. Mitigations for Twinkle:
- **Forbid agents from renaming/moving linked notes.** Constrain autonomous writes to (a) creating new notes, (b) editing frontmatter/body of existing notes in place, (c) appending. Renames/moves go through the Mac app or a human-reviewed step.
- If agents must rename, build a tiny script: rename file → `rg -l "\[\[oldname"` → rewrite `[[oldname]]`/`[[oldname|alias]]`/`![[oldname]]` occurrences (handle aliases and headings `#`/blocks `^`). Test against a BOM/whitespace edge case that Obsidian itself has historically mangled.
- `obsidian-mcp` (Rust) and cyanheads' server advertise link-aware operations; if you want this automated, prefer one of those over `mv`.

### 4. The Xvfb/full-app-in-container approach — assessment
Projects: **obsidianless** (lucastraba — Xvfb + full Obsidian + `"cli": true` pre-injected, no Sync/Catalyst needed at runtime for the free app), **AdamsGH/obsidian-headless** (Docker + supplies a licensed `.asar` at build time, exposes CLI + interactive TUI via `docker exec`), and hand-rolled Xvfb+Openbox+systemd setups. A forum user documented running Obsidian 1.12.7 on headless Ubuntu 24.04 for AI workflows, needing `--disable-gpu --disable-software-rasterizer` to stop a Chromium GPU crash-loop, `PrivateTmp=false` for the IPC socket, and the `.deb` (not snap, whose confinement blocks the socket).

**Verdict:** This is the *only* way to get the genuine `base:query` and full official command set server-side. But it is officially unsupported, breaks on Obsidian auto-updates, carries Electron's RAM/CPU cost, and adds a fragile display/IPC layer. For Twinkle it is not worth it as core infrastructure. `mdbasequery` covers base execution without any of this. Keep the Xvfb path, if at all, as an optional, restartable side-car for occasional "ground-truth" base validation — never on the agent hot path.

### 5. Sync deep dive (Mac + VPS + optional iPhone)

**Official `ob` (obsidian-headless):** Node 22+, `ob login` → `ob sync-setup --vault` → `ob sync --continuous`. Sync modes: **bidirectional (default), pull-only (download, ignore local), mirror-remote (download, revert local changes)**. Config-category sync is granular (`app, appearance, hotkey, core-plugin, community-plugin`, etc.) and **`.obsidian/` config is NOT synced by default** — plugin/theme parity needs explicit `ob sync-config`. Runs cleanly as a `systemd --user` service (`ExecStart=ob sync --continuous`); healthy logs poll ~every 30s and report "Fully synced". Failure modes: Linux has no birthtime support (cosmetic); requires an active Sync subscription; being a client it inherits Sync's diff-match-patch conflict behavior. **`mirror-remote` mode is a valuable safety valve** if you ever want the VPS to be strictly downstream.

**Git backbone (recommended for Mac↔VPS):** obsidian-git on Mac (auto commit-and-sync every 10–15 min + on-file-stop, auto-pull on startup, Merge strategy). On the VPS, agents commit via a post-write hook or a cron/systemd `git add/commit/pull --rebase/push` loop. Conflicts are rare with a single committer per branch but real when Mac-human and VPS-agent edit the same file between syncs. Strategies:
- **Branch-per-agent or agent-only subfolders** to keep write domains disjoint.
- **File-level ownership conventions:** agents own their generated notes/folders; humans own hand-authored ones; frontmatter fields split by owner.
- **Custom merge drivers** for machine-generated JSON (the Readwise `data.json` pattern generalizes to any plugin state file).
- Pull-before-write and small frequent commits minimize the divergence window.
- **If git and Obsidian Sync ever touch the same vault on the Mac, set obsidian-git's Merge Strategy to "Other sync service"** — its docs specifically warn this prevents Git from overwriting files already synced by Obsidian.

**Git on iPhone (2026):** obsidian-git on mobile uses isomorphic-git and is, per its own README, verbatim: *"The Git implementation on mobile is very unstable! I would not recommend using this plugin on mobile, but try other syncing services. One such alternative is GitSync, which is available on both Android and iOS."* It also documents "No Submodules: Not supported on mobile" and "Memory Limits: Large repositories may cause Obsidian to crash or run indefinitely" (no SSH, no rebase). Workable paths: **Working Copy** (Pro, libgit2, link-repository-to-folder + Shortcuts automation) or newer libgit2 clients (**GitSync.md**, Weee). iSH/a-shell git also works. All require manual-ish pull-before-edit discipline and are fiddly.

**Syncthing:** reliable P2P for markdown, but Obsidian's frequent multi-file writes (including `.obsidian/*.json`) generate `.sync-conflict-*` files, especially on the config directory during initial device pairing (users reported losing hotkeys/having to re-enable plugins). No first-party iOS client — **Möbius Sync** fills that gap. Filtering `**/*sync-conflict*` and ignoring `.obsidian/` reduce noise. Good Mac↔VPS alternative to git if you don't want version history, but git gives you history + rollback, which matters when agents write autonomously.

**Hybrid topologies & the double-sync trap:** The universal rule from practitioners — **one primary sync method per vault; never stack two on the same folder.** Stacking (e.g., Syncthing + iCloud, or Obsidian Sync + a cloud drive on the same directory) causes conflict amplification and loops. The safe hybrid for you: **git as Mac↔VPS backbone, Obsidian Sync (or `ob`) bridging ONLY Mac↔iPhone**, with the Mac as the single junction node that owns both. The VPS never touches Obsidian Sync; the iPhone never touches git. All cross-flow happens through the Mac's two independent sync clients writing to the same local vault at different times.

**Agent-write conflict scenario:** Human edits a note's body on iPhone (→ Obsidian Sync → Mac) while a VPS agent rewrites that same note's frontmatter (→ git → Mac). On the Mac both land as edits to different regions; git's line merge usually succeeds if frontmatter and body don't overlap, but simultaneous frontmatter edits collide. Best practice: **agent write-windows** (agents write frontmatter during a defined window; reconcile on the Mac), **field-level ownership** (agents only touch agent-owned frontmatter keys), and **lock files / `.nosync` markers** on notes an agent is actively rewriting.

## Recommendations

**Stage 1 — Stand up the file-level agent layer on the VPS (do this first):**
1. Install `notesmd-cli` (CRUD + frontmatter edits), `ripgrep`, `yq`, and `mdbasequery` (base execution). Wrap `mdbasequery` behind a thin long-lived HTTP service (model it on the `obsidian-query` :27180 skill: `/bases/:name?view=`, `/frontmatter/:path`, `/backlinks/:path`).
2. Add `qmd` for semantic/BM25 retrieval; run `qmd mcp --http --daemon` and expose it to Claude Code agents. Benchmark token cost vs raw `rg` on your real vault before committing to it broadly.
3. Give agents a hard rule: **no rename/move of linked notes.** Constrain writes to create/edit-in-place/append. Everything else is human-gated.

**Stage 2 — Sync backbone:**
4. Put the vault under git. obsidian-git on Mac (commit-and-sync 10–15 min, auto-pull on startup, Merge strategy). VPS: systemd timer running `git pull --rebase && <agent work> && git add -A && git commit && git push`, scoped to agent-owned paths.
5. Establish write-domain separation: agent-owned folders/frontmatter keys vs human-owned. Add merge drivers for any plugin JSON that churns.

**Stage 3 — iPhone (only when you want it):**
6. Add Obsidian Sync between **Mac and iPhone only** (you're already open to the subscription). Keep the VPS entirely on git. The Mac is the sole bridge, with obsidian-git's Merge Strategy set to "Other sync service" so git doesn't clobber Sync-delivered files. Do **not** put Obsidian Sync on the VPS, and do **not** put git on the iPhone unless you accept Working Copy/GitSync.md fiddliness.

**Build-vs-adopt:** Adopt `notesmd-cli`, `mdbasequery`, and `qmd` — don't reinvent them. The **minimal surface worth building yourself** is: (a) a **link-integrity rename/move script** (nothing mature exists), (b) a **thin base-query HTTP wrapper** around `mdbasequery` for warm, low-latency agent access, and (c) a **git-commit orchestration wrapper** enforcing write-windows and path scoping. That's it — roughly a few hundred lines, not a full CLI.

**Thresholds that change the plan:**
- If Obsidian ships an *official* GUI-free full CLI (watch forum thread 111137 / roadmap) → collapse the file-level stack onto it and drop `mdbasequery`.
- If `mdbasequery` proves incomplete against your real `.base` files (formula gaps, custom views) → fall back to the Xvfb side-car for `base:query` ground-truth, or contribute fixes upstream (it's MIT, tiny).
- If git conflicts between Mac-human and VPS-agent become frequent → move VPS to `ob sync --continuous` in **pull-only or mirror-remote** mode so the VPS is strictly downstream, and push agent writes through a separate reconciliation path.
- If token cost from search dominates → lean harder on `qmd`; if it doesn't → stay with `rg` and skip the embedding overhead.

## Caveats
- **`mdbasequery` is brand new (v0.0.1 Feb 18, 2026; ~v0.0.3 on npm; 8 stars) and unproven at scale.** It claims Bases compatibility but has not been battle-tested against complex real-world `.base` files. Validate it against your actual vault before relying on it; keep the Xvfb `base:query` path as a correctness oracle during evaluation.
- The official `base:query` executes only against a **running** app via IPC and (per one hands-on report) needs the base's active tab — it is not a headless capability.
- Version/date specifics for the official CLI (v1.12, ~115 commands, Feb 2026) and `ob` come largely from third-party skill catalogs and blogs; the primary help docs confirm the command set and the "app must be running" constraint but exact command counts vary by source.
- Obsidian Sync's conflict resolution uses diff-match-patch and has historically, in rare cases, overwritten newer data — do not treat any single sync layer as backup. Keep git history (or independent versioned backups) as your recovery point.
- Running the real app headless is **officially unsupported**; Obsidian updates can break the Xvfb/asar approach without warning.
- iPhone git tooling (obsidian-git mobile) is explicitly "very unstable" in 2026 per its own docs; treat Working Copy/GitSync.md as the real options if you go git-on-iOS instead of Obsidian Sync.