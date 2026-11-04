# Grok Bot Dogfood changelogs — daily automation

Mirrors Marcelo’s **Cursor Changelogs** automation logic (binary diff between consecutive builds—not cursor.com/changelog scraping). Download **Dogfood** via the same **`api2.cursor.sh` sand-dogfood feed** as Marcelo’s laptop `sync.py`, diff extracted trees against the previous dogfood build (Automation Memory + `current.prev` export), run **Groketective** on significant changes, write **Grok Bot Dogfood Changelogs** in Notion (`docs/notion-grok-bot-dogfood-changelogs.md`).

Skill reference: `.cursor/skills/install-grokbot-dogfood/SKILL.md`.

## Memory keys

- `dogfood_version`, `dogfood_commit_sha`, `dogfood_download_url` — last processed dogfood build (from sync export `version.env`)
- `GROKBOT_MACHINE_ID` — **required** for Cloud Agents without GNOME keyring (never commit; never log raw value)
- `notion_grok_bot_dogfood_changelogs_data_source_id`

Optional: `GROKBOT_DOGFOOD_SYNC_ROOT` (default `versions/grok-bot-dogfood` under repo)

## Pipeline

1. `bash scripts/setup-deps.sh`
2. `bash scripts/install-dogfood-pair.sh --first-run` or `--previous-commit "$dogfood_commit_sha"` from Memory  
   Uses `scripts/grokbot_dogfood/sync.py` (feed + download + sha256 + extract + swap). Exports `versions/dogfood-new` and `versions/dogfood-previous`.
3. If `skip=true` (no feed update / same commit), exit 0
4. `bash scripts/run-dogfood-changelog-pipeline.sh`
5. Read `build-diff.json` / `manifest.json`; rank `important_changes`
6. Groketective subagents per significant cluster → `plans/groketective-dogfood-*.plan.md`
7. Upsert **Grok Bot Dogfood Changelogs** Notion rows (schema in docs)
8. Update Memory `dogfood_*` from `versions/dogfood-new/version.env`
9. `dogfood-changelog-sync.md` summary

## Machine id

1. Automation Memory / env `GROKBOT_MACHINE_ID`
2. Else decrypt `sand-secrets.json` + keyring (local laptop only)
3. Else fail — run `bash scripts/grokbot-machine-id.sh --masked` to verify setup

If the feed returns 401/403, rotate or fix `GROKBOT_MACHINE_ID` (do not print it).

## First run

Baseline feed version `0.0.0` via `--first-run`. Previous export may mirror new until the second dogfood bump.

## Constraints

- No cursor.com/changelog HTML
- No raw machine id in logs, git, or Notion
- Work under `versions/` and `workspace/` only during automation
