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

Mirrors the [cursor-detective](https://github.com/Marcelo-Barella/cursor-detective) daily pipelines (Cursor dev builds + feature flags + changelog-driven detective runs). This repo adds the **Grok Bot** side: download stable sand builds, diff client gates, and track Grok-relevant changelog posts.

| Automation | Prompt | Pipeline script |
|------------|--------|-----------------|
| Feature flags | `prompts/daily-feature-flags-grokbot.md` | `scripts/run-feature-flags-pipeline.sh` |
| Changelog / release notes | `prompts/daily-changelog-grokbot.md` | `scripts/run-changelog-pipeline.sh` |

### Manual dry-run (feature flags)

```bash
bash scripts/setup-deps.sh
bash scripts/install-pair.sh --first-run
bash scripts/run-feature-flags-pipeline.sh
```

Artifacts land under `workspace/runs/<timestamp>/` (`manifest.json`, inventories, `extract/new/`). `versions/` holds downloaded AppImages. Both paths are gitignored.

### Manual dry-run (changelog)

```bash
bash scripts/run-changelog-pipeline.sh --pages 3 --filter grokbot
```

### Cursor Automation setup

1. Create two Cursor Automations (scheduled daily or on your preferred trigger).
2. Paste the corresponding prompt from `prompts/` as the agent instructions.
3. Enable Notion MCP and set Memory fields from `scripts/automation-memory.example.json` (database ids are **not** committed).
4. Optional: subscribe to stable Grok Bot commits via the same Memory keys as the feature-flag prompt.

**Open decisions for Marcelo:** Notion database ids/names, whether changelog should use `--filter all` with manual Notion triage, and any dedicated Grok Bot release-notes URL if posts are not on cursor.com/changelog.

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
