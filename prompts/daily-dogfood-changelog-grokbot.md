# Grok Bot Dogfood changelogs — daily automation

Mirrors Marcelo’s **Cursor Changelogs** automation logic (binary diff between consecutive builds—not cursor.com/changelog scraping). For Grok Bot: download the **Dogfood** track build, extract AppImage contents, **diff against the previous Dogfood version** stored in Automation Memory, inspect important file changes, and infer shipped features/changes. Run **Groketective** on each significant change cluster and record results in a **dedicated Notion database: Grok Bot Dogfood Changelogs** (separate from Cursor Changelogs; **same property and page layout**—see `docs/notion-grok-bot-dogfood-changelogs.md`).

## Memory keys

- `dogfood_version`
- `dogfood_commit_sha`
- `dogfood_download_url`
- `notion_grok_bot_dogfood_changelogs_data_source_id` — Notion data source for the Grok database (stub in `scripts/automation-memory.example.json`)
- Optional: `notion_grok_bot_dogfood_changelogs_database_id` — UI database id for humans

**Dogfood download stub:** Public API `releaseTrack=dogfood&appName=sand` returns **500** without internal credentials. Until configured, set Memory (or env):

- `GROKBOT_DOGFOOD_DOWNLOAD_URL`
- `GROKBOT_DOGFOOD_VERSION`
- `GROKBOT_DOGFOOD_COMMIT_SHA` (optional)

`scripts/install-dogfood-pair.sh` uses those when the API fails (exit code **2** with instructions).

## Pipeline

1. `bash scripts/setup-deps.sh`
2. `bash scripts/install-dogfood-pair.sh --first-run` or with `--previous-url` / `--previous-version` / `--previous-commit` from Memory
3. If `skip=true` (same commit), exit 0
4. `bash scripts/run-dogfood-changelog-pipeline.sh`
5. Read `workspace/runs/<timestamp>/build-diff.json` and `manifest.json`
6. Rank `important_changes` (prioritizes `resources/app.asar`, main/daemon/host bundles, renderer assets)
7. For each significant change (or logical group: asar changed → extract inner entrypoints and diff semantically), spawn Groketective:
   - Theme: `dogfood-changelog-<kebab-path-or-topic>`
   - Infer **what feature or behavior changed** from diffs + grep-asar on new extract
   - Plan: `workspace/runs/<timestamp>/plans/groketective-dogfood-<topic>.plan.md`
8. Upsert rows in Notion **Grok Bot Dogfood Changelogs** (not Cursor Changelogs). Use the property schema and page sections in `docs/notion-grok-bot-dogfood-changelogs.md`. Set **Product** = Grok Bot, **Release Track** = Dogfood. **Key** = new commit SHA (or agreed topic key). Status = Done when complete; page body = sections 1–4 from the doc with full Groketective markdown in section 4.
9. Update Memory with new `dogfood_*` fields from `versions/dogfood-new/version.env`
10. Write `workspace/runs/<timestamp>/dogfood-changelog-sync.md`

## First run

`install-dogfood-pair.sh --first-run` copies new → previous; diff is empty. Record baseline Memory only; Groketective runs begin on the **second** dogfood bump.

## Groketective focus areas after diff

When `app_asar_changed=true`:

- Extract/compare `package.json` version inside asar
- `grep-asar.sh` on changed gate names or modules hinted by path changes
- Persistence/daemon paths under `sand-client-persistence`, `~/.grokbot` reference (read-only)

When only unpacked natives changed, document packaging/deps impact vs user-visible features.

## Constraints

- **No** cursor.com/changelog HTML fetch
- Dogfood credentials never committed
- Work only under `versions/` and `workspace/` during automation
