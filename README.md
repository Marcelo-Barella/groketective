# Groketective

Cursor plugin that packages the **groketective** skill: deep read-only forensics on local **Grok Bot** installs (internal package name `sand`), Electron user-data, `~/.grokbot`, `app.asar`, and `sand-client-persistence` slices.

**Linux primary.** macOS paths are documented as unknown/partial in v1.

## What's inside

| Component | Path |
|-----------|------|
| Skill | `skills/groketective/` |
| Probe scripts | `skills/groketective/scripts/` |
| Smoke tests | `skills/groketective/tests/smoke.sh` |
| Path/reference notes | `skills/groketective/reference.md` |

Invoke with `/groketective [theme]` (empty theme → `general-scan`). Reports land at `.cursor/plans/groketective-<theme>.plan.md` in the current workspace.

Recovered Windows markdown zips import into live bots with `/groketective import --zip PATH`. That is a write exception. Quit Grok Bot first. Dry-run with `--dry-run`.

## Requirements

- Linux (primary)
- Host tools: `bash`, `python3`, and common Unix utilities (`find`, `grep`, `sed`, `awk`, `comm`, `stat`, `pgrep`)
- Optional: `npx` (for `@electron/asar` entrypoint extract; otherwise strings fallback)

## Install

### Marketplace

Search **Groketective** in Cursor **Customize** after the listing is approved, or open [the GitHub repository](https://github.com/Marcelo-Barella/groketective) from the Cursor Marketplace.

### Local (user-level)

Cursor rejects symlinks whose target is outside `~/.cursor/plugins/local`. Copy the plugin there:

```bash
git clone https://github.com/Marcelo-Barella/groketective.git
mkdir -p ~/.cursor/plugins/local
rm -rf ~/.cursor/plugins/local/groketective
rsync -a --delete \
  --exclude '.git/' \
  --exclude '.cursor/' \
  "$(pwd)/groketective/" \
  ~/.cursor/plugins/local/groketective/
```

Then **Developer: Reload Window**. Confirm `groketective` under Settings → Plugins (user scope).

## Usage

```text
/groketective
/groketective persistence
/groketective local-exec-daemon
/groketective transcript
/groketective import --zip ~/Downloads/recovered-transcripts.zip --dry-run
```

The skill runs locate/scan/list scripts, optional parallel probes (asar, slices, daemon), and writes a tagged evidence report. Forensics do **not** modify Grok Bot trees except the workspace plan file. `/groketective import` is the named exception (replica merge after quit-gate + backup). Tokens and credentials are redacted.

## Scripts

| Script | Purpose |
|--------|---------|
| `locate-grokbot.sh` | Install root + `APP_ASAR` + version |
| `scan-paths.sh` | Config/data inventory |
| `list-persistence.sh` | Decode persistence blob keys |
| `inspect-slice.sh` | Read one slice |
| `inspect-daemon.sh` | Local-exec status (redacted) |
| `grep-asar.sh` | Pattern search in asar entrypoints |
| `compare-dirs.sh` | Shallow dir file compare |
| `import-recovered.sh` | Recovered zip → live replica merge |

Run smoke tests:

```bash
./skills/groketective/tests/smoke.sh
./scripts/smoke-automation.sh
```

## Cloud automations (Grok Bot tests)

Extends [cursor-detective](https://github.com/Marcelo-Barella/cursor-detective) daily flows. Client gates are **shared** between Cursor and Grok Bot (~1.1k keys); Grok work **fills gaps** in the same **Cursor Feature Flags** Notion database. Dogfood **binary diff** replaces any changelog web scraping.

| Automation | Prompt | Pipeline |
|------------|--------|----------|
| Feature flags (Notion gap-fill) | `prompts/daily-feature-flags-grokbot.md` | `install-pair.sh` → `run-feature-flags-pipeline.sh` (+ optional `--notion-keys`) |
| Dogfood changelogs | `prompts/daily-dogfood-changelog-grokbot.md` | `install-dogfood-pair.sh` → `run-dogfood-changelog-pipeline.sh` |

Notion layout for dogfood rows: [`docs/notion-grok-bot-dogfood-changelogs.md`](docs/notion-grok-bot-dogfood-changelogs.md). Stub data source ids: `scripts/automation-memory.example.json`.

### Feature flags extension (stable sand)

```bash
bash scripts/setup-deps.sh
bash scripts/install-pair.sh --first-run
bash scripts/run-feature-flags-pipeline.sh
# Optional dry-run gap list after exporting Notion Keys to /tmp/keys.txt:
bash scripts/run-feature-flags-pipeline.sh --notion-keys /tmp/keys.txt --notion-done-keys /tmp/done.txt
```

### Dogfood changelog (binary diff)

```bash
# Requires dogfood URL in env/Memory when public API fails (see prompt)
export GROKBOT_DOGFOOD_DOWNLOAD_URL='https://...'
export GROKBOT_DOGFOOD_VERSION='0.0.0'
bash scripts/install-dogfood-pair.sh --first-run
bash scripts/run-dogfood-changelog-pipeline.sh
```

Artifacts under `workspace/runs/<timestamp>/`. `versions/` holds AppImages (gitignored).

### Cursor Automation setup

1. **Feature flags:** second automation using `daily-feature-flags-grokbot.md`; same Notion **Cursor Feature Flags** as cursor-detective; run after Cursor catalog pass.
2. **Dogfood changelogs:** automation using `daily-dogfood-changelog-grokbot.md`; duplicate **Cursor Changelogs** in Notion → **Grok Bot Dogfood Changelogs**; set Memory ids per `docs/notion-grok-bot-dogfood-changelogs.md`.
3. Enable Notion MCP; never commit database ids or dogfood URLs.

**Stub:** `releaseTrack=dogfood` on the public download API returns 500 for `appName=sand`—set `GROKBOT_DOGFOOD_*` / Memory `dogfood_download_url` from your internal dogfood channel.

## Related skills (not bundled)

| Skill | When |
|-------|------|
| cursor-detective | Cursor IDE forensics (not Grok Bot) |
| research | Open-repo code |
| debugger | Repro + fix |

## Plugin layout

```text
groketective/
├── .cursor-plugin/plugin.json
├── assets/logo.svg
├── docs/
├── prompts/
├── scripts/
├── skills/groketective/
│   ├── SKILL.md
│   ├── reference.md
│   ├── scripts/
│   └── tests/
├── LICENSE
└── README.md
```

## License

MIT. See [LICENSE](./LICENSE).

## Author

Marcelo Barella.
