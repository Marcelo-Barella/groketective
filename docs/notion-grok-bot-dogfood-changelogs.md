# Notion: Grok Bot Dogfood Changelogs

Grok Bot dogfood automation writes to its **own** Notion database, separate from **Cursor Changelogs**. The Grok database must **mirror** the Cursor Changelogs database: same property names, types, select options, and page body section order. Create it by duplicating **Cursor Changelogs** in Notion, then rename and point the automation at the new data source id.

Feature flags continue to use the shared **Cursor Feature Flags** database (see `prompts/daily-feature-flags-grokbot.md`).

## Setup (Marcelo)

1. In Notion, duplicate the existing **Cursor Changelogs** database.
2. Rename the duplicate to **Grok Bot Dogfood Changelogs** (display name is flexible; property schema must match).
3. Copy the duplicated database **data source id** into Cursor Automation Memory (see below). Do not commit real ids to git.

## Automation Memory stubs

```json
{
  "notion_grok_bot_dogfood_changelogs_database_id": "00000000-0000-0000-0000-000000000000",
  "notion_grok_bot_dogfood_changelogs_data_source_id": "00000000-0000-0000-0000-000000000000"
}
```

Use the data source id for Notion MCP `query-data-sources` / page create APIs. The database id is optional metadata for humans in the Notion UI.

Canonical example file: `scripts/automation-memory.example.json`.

## Database properties (mirror Cursor Changelogs)

These names and types must match **Cursor Changelogs** row-for-row. If your Cursor database uses slightly different titles, rename Grok columns to match Cursor—not the other way around—so one automation prompt pattern works for both products.

| Property | Type | Role |
|----------|------|------|
| **Name** | title | Short label, e.g. `0.79.0 → 0.80.0 (dogfood)` or topic title for a split row |
| **Key** | rich_text | Stable dedupe key: `{new_commit_sha}` or `{new_version}-{new_commit_sha}` |
| **Status** | select | `Not started`, `In progress`, `Done` (same options as Cursor Changelogs) |
| **Version** | rich_text | New dogfood build version from `version.env` |
| **Previous Version** | rich_text | Previous dogfood version from Memory / diff pair |
| **Commit SHA** | rich_text | New build commit |
| **Previous Commit SHA** | rich_text | Previous build commit |
| **Release Track** | select | Set to `Dogfood` for Grok rows (Cursor rows use `Dev` or equivalent in your Cursor DB) |
| **Product** | select | Set to `Grok Bot` (Cursor rows use `Cursor`) |
| **App Asar Changed** | checkbox | From `build-diff.json` → `app_asar_changed` |
| **Changed Paths** | rich_text | Top N paths from `important_changes` (one path per line) |
| **Change Summary** | rich_text | Agent-inferred user-facing summary |
| **Confidence** | select | Same options as Cursor Changelogs (e.g. Confirmed / Inferred / Unknown) |
| **Evidence** | rich_text | Pointers to diff hashes, grep-asar hits, file paths |
| **Modules** | rich_text | asar / main / daemon / renderer modules touched |
| **Detective Plan** | rich_text | Filename only, e.g. `groketective-dogfood-<topic>.plan.md` |
| **Last Verified** | date | UTC date of automation run |

Optional columns present on **Cursor Changelogs** should be duplicated on the Grok database even if left empty for early runs (e.g. **Download URL**, **PR / Linear link**, **Screenshot**).

## Page body layout (mirror Cursor Changelogs)

Each Done row’s Notion page content should follow the same section order as Cursor Changelogs pages:

1. **Build pair** — version/commit new vs previous; dogfood download metadata (no secrets).
2. **Diff highlights** — table or bullet list from `build-diff.json` → `important_changes` (path, change type, importance).
3. **Inferred changes** — what shipped or changed in product terms (from Groketective + diff).
4. **Groketective plan** — full markdown from `workspace/runs/<timestamp>/plans/groketective-dogfood-*.plan.md` (primary narrative, same as Cursor putting the detective plan on the page body).

Do not store only a link to the local plan file; inline the markdown like the Cursor Changelogs automation.

## Dedupe rules

- **Key** is authoritative: one row per new dogfood commit (or per agent-defined topic Key if you split a large diff into multiple rows).
- Skip creating a row when `skip=true` (same commit as Memory).
- On re-run with the same Key, **update** the existing page rather than creating duplicates.

## Dogfood download

Dogfood builds use **`scripts/grokbot_dogfood/sync.py`** (see skill above), not `cursor.com/api/download?releaseTrack=dogfood`.

## Related files

| File | Purpose |
|------|---------|
| `prompts/daily-dogfood-changelog-grokbot.md` | Cloud Agent instructions |
| `scripts/run-dogfood-changelog-pipeline.sh` | Produces `build-diff.json` + manifest |
| `scripts/automation-memory.example.json` | Stub ids and Memory field names |
