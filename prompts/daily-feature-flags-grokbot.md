# Grok Bot feature flags — daily automation

Detect new **Grok Bot (sand)** client feature gates in `resources/app.asar`, run one full **Groketective** investigation per new flag, and upsert Done rows in the **Grok Bot Feature Flags** Notion database (configure in Cursor Automation Memory).

Reference implementation: [cursor-detective `prompts/daily-feature-flags.md`](https://github.com/Marcelo-Barella/cursor-detective/blob/main/prompts/daily-feature-flags.md).

## Memory keys

Store and read these from Automation Memory (local dry-runs: copy `scripts/automation-memory.example.json` to `workspace/automation-memory.json`):

- `version` — last processed Grok Bot version
- `commit_sha` — last processed commit
- `download_url` — last processed download URL
- `known_flag_names` — newline-separated catalog backup (Notion Keys remain authoritative for "new")

**First run** (version fields empty): `install-pair.sh --first-run`.

**Subsequent runs**: reinstall previous from Memory URL; skip if `commit_sha` unchanged.

## Pipeline

1. Run `bash scripts/setup-deps.sh`
2. Install pair:
   - First run: `bash scripts/install-pair.sh --first-run`
   - Else: `bash scripts/install-pair.sh --previous-url "$download_url" --previous-version "$version" --previous-commit "$commit_sha"`
3. Parse stdout. If `skip=true`, log "No new Grok Bot build" and exit 0.
4. Run `bash scripts/run-feature-flags-pipeline.sh` (optionally `--previous-names` from Memory `known_flag_names`). Extracts the **new** AppImage and catalogs client gates from `app.asar`.
5. Read the latest `workspace/runs/*/manifest.json` and `feature-flags-inventory.json`.
6. Query Notion **Grok Bot Feature Flags** (data source id in Memory). Build `new_flags` = catalog names **missing** from Notion `Key`.
7. If `new_flags` is empty, update Memory version/commit/download_url, refresh `known_flag_names`, exit 0.
8. Spawn **one Groketective subagent per new flag** (parallel waves of up to **4**). Each subagent must:
   - Follow `skills/groketective/SKILL.md` fully
   - Theme: `feature-flag-<kebab-flag-name>`
   - Use `app_asar` from the manifest (extract dir under the same run)
   - Prefer inventory `client` / `default` from `feature-flags-inventory.json`
   - Write plan to `workspace/runs/<timestamp>/plans/groketective-feature-flag-<kebab>.plan.md`
9. For each completed run, create or update the Notion row (Name, Key, Category, Client, Bundled Default, What it changes, Confidence, Evidence, Modules, Detective Plan, Status=`Done`, Grok Bot Version, Last Verified). Page body = full plan markdown.
10. Update Memory: `version`, `commit_sha`, `download_url`, `known_flag_names`.
11. Write backup summary to `workspace/runs/<timestamp>/feature-flags-sync.md`

## Groketective subagent prompt (per flag)

```
You are running a COMPLETE Groketective investigation.
Theme: feature-flag-<kebab>

MANDATORY: Follow skills/groketective/SKILL.md fully. Do NOT shortcut.

Flag under study: `<flag_name>`

Fixed paths from parent:
- Skill scripts: skills/groketective/scripts/
- App asar: <app_asar from manifest>
- Extract tree: workspace/runs/<timestamp>/extract/new/
- Inventory: workspace/runs/<timestamp>/feature-flags-inventory.json
- Output plan: workspace/runs/<timestamp>/plans/groketective-feature-flag-<kebab>.plan.md

Confirm registry entry, grep-asar call sites (or registry-only), Statsig bootstrap / local overrides when probeable, modules touched, and Confirmed/Inferred/Unknown tags.
```

## Notion / credentials (Marcelo)

- Create or point Automation Memory at the **Grok Bot Feature Flags** Notion database id.
- Enable Notion MCP (or equivalent) on the Cloud Agent automation.
- Do **not** commit database ids or integration tokens to git.

## Constraints

- Do not commit or push to git from the automation run unless explicitly instructed.
- Use `scripts/` for download/extract/catalog; do not modify host Grok Bot install trees outside `versions/` and `workspace/`.
- Grok Bot `releaseTrack=dev` is unavailable on the public download API; this pipeline uses **stable** only.
