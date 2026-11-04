# Grok Bot feature flags — extension of Cursor Feature Flags automation

**Extension** of the daily [cursor-detective feature-flag flow](https://github.com/Marcelo-Barella/cursor-detective/blob/main/prompts/daily-feature-flags.md). Grok Bot (`sand`) and Cursor share the **same client gate registry** (~1.1k keys). The Cursor automation catalogs `kFe` from Cursor dev builds and fills **Cursor Feature Flags** in Notion. This automation catalogs the same keys from a **Grok Bot stable** `app.asar` and **fills gaps only** in that **same Notion database**—never a separate Grok-only flags database.

## Relationship to cursor-detective

| Step | cursor-detective (Cursor) | groketective extension (Grok Bot) |
|------|---------------------------|-----------------------------------|
| Build | Cursor dev AppImage | Grok Bot stable AppImage (`appName=sand`) |
| Catalog source | workbench `kFe` | `resources/app.asar` strings scan |
| Notion | **Cursor Feature Flags** | **Same database** |
| Detective skill | Cursor Detective | Groketective |
| Work queue | Keys missing in Notion | **Dedupe**: skip Keys already **Done** with complete Cursor Detective rows; investigate missing Keys, stubs, or sand-only evidence |

Run this automation **after** the Cursor feature-flag automation (or on a staggered schedule). **Notion Keys are authoritative** for deduplication—not Memory alone.

## Memory keys (Grok stable extension)

- `grok_stable_version`, `grok_stable_commit_sha`, `grok_stable_download_url` — last processed **stable** sand build (optional split from Cursor Memory)
- `known_flag_names` — optional backup; Notion Keys win

Use the same Notion data source id as cursor-detective (**Cursor Feature Flags**).

## Pipeline

1. `bash scripts/setup-deps.sh`
2. `bash scripts/install-pair.sh --first-run` or with `--previous-url` / `--previous-version` / `--previous-commit` from Memory
3. If `skip=true`, exit 0
4. `bash scripts/run-feature-flags-pipeline.sh` — catalogs shared gates from Grok Bot extract
5. Query Notion **Cursor Feature Flags**. Build `gap_flags`:
   - Key **missing** from Notion, **or**
   - Row exists but Status ≠ Done / stub, **or**
   - Cursor row lacks sand-only fields you store (Statsig bootstrap path, `sand-feature-flag-overrides`, grep-asar evidence)
6. Optional local helper: export Notion Keys to a file and run  
   `bash scripts/run-feature-flags-pipeline.sh --notion-keys keys.txt --notion-done-keys done.txt`  
   → `notion-flag-gaps.json` / `gap-flag-names.txt`
7. If `gap_flags` empty, update Memory and exit 0
8. **One Groketective subagent per gap flag** (waves of 4). Theme: `feature-flag-<kebab>`. Output:  
   `workspace/runs/<timestamp>/plans/groketective-feature-flag-<kebab>.plan.md`
9. **Update existing Notion rows by Key** (create only when Key truly absent). Merge Grok Bot evidence into Evidence / Modules / Detective Plan; set Status=Done when complete. Page body may append Groketective plan sections—do not duplicate Cursor Detective content blindly.
10. `workspace/runs/<timestamp>/feature-flags-grok-extension.md` summary

## Groketective subagent prompt (per gap flag)

```
Extension run for shared client gate registry (Cursor Feature Flags Notion DB).
Theme: feature-flag-<kebab>
Flag: `<flag_name>`

Follow skills/groketective/SKILL.md. Focus sand-only observability:
- app.asar grep-asar for checkFeatureGate / gate name
- ~/.config/Grok Bot/sand-statsig-bootstrap.json (redacted)
- sand-feature-flag-overrides.json if present

Paths from parent:
- app_asar: <manifest>
- extract: workspace/runs/<timestamp>/extract/new/
- inventory: workspace/runs/<timestamp>/feature-flags-inventory.json
- plan: workspace/runs/<timestamp>/plans/groketective-feature-flag-<kebab>.plan.md

Tag Confirmed/Inferred/Unknown. Prefer inventory default when present.
If Cursor Detective already documented this Key, only add delta evidence.
```

## Constraints

- Same Notion database as cursor-detective; dedupe on Key; no parallel Grok flags DB
- Do not re-run Groketective for Keys already Done with complete Cursor coverage unless inventory default/client changed vs Notion
- Stable sand via public API; dogfood is for the **changelog** automation, not this extension
