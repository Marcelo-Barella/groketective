# Grok Bot changelog tests — daily automation

Detect new **Grok Bot–relevant** posts on [cursor.com/changelog](https://cursor.com/changelog), run one **Groketective** investigation per new entry, and upsert Done rows in the **Grok Bot Changelog Tests** Notion database (configure in Cursor Automation Memory).

Mirrors the Cursor-side changelog test automation pattern used with [cursor-detective](https://github.com/Marcelo-Barella/cursor-detective) (Cursor dev builds + changelog-driven detective runs). The Cursor repo ships the feature-flag pipeline scripts; changelog fetching for Grok Bot lives here.

## Memory keys

- `known_changelog_slugs` — newline-separated slugs already processed (Notion slugs/Keys are authoritative)
- Optional: `changelog_pages` — default `3` pages of `/changelog` pagination

## Pipeline

1. Run `bash scripts/run-changelog-pipeline.sh` (optional: `--pages N`, `--filter grokbot|all`, `--previous-slugs PATH`).
2. Read `workspace/runs/<timestamp>/manifest.json` and `changelog-entries.json`.
3. Build `new_entries` = entries whose `slug` is missing from Notion.
4. If empty, update Memory `known_changelog_slugs` from `changelog-slugs.txt` and exit 0.
5. For each new entry (parallel waves of up to **4**), spawn Groketective with theme `changelog-<slug>`:
   - Objective: map the shipped behavior to on-disk Grok Bot modules (asar grep, persistence, flags mentioned in the post).
   - Inputs: entry `title`, `url`, `body_text`, plus local install when available.
   - Output plan: `workspace/runs/<timestamp>/plans/groketective-changelog-<slug>.plan.md`
6. Upsert Notion rows (Title, Slug, Published At, URL, Status=`Done`, Groketective Plan on page body).
7. Update Memory `known_changelog_slugs`.
8. Write `workspace/runs/<timestamp>/changelog-sync.md` summary.

## Keyword filter

Default `--filter grokbot` keeps posts whose title or body matches Grok Bot / sand keywords (see `GROK_FILTER` in `scripts/fetch-changelog-entries.py`). Use `--filter all` temporarily to backfill, then narrow in Notion.

If Grok Bot ships release notes outside cursor.com/changelog, set Automation Memory `changelog_source_url` and extend `fetch-changelog-entries.py` (stub documented in README).

## Notion / credentials (Marcelo)

- Configure **Grok Bot Changelog Tests** database id in Automation Memory.
- Notion MCP auth on the Cloud Agent.

## Constraints

- Do not commit secrets.
- Changelog HTML parsing is best-effort; re-run with `--filter all` if a Grok post is missed by keywords.
