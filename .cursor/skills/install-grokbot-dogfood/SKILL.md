---
name: install-grokbot-dogfood
description: Install or update Grok Bot on the sand-dogfood channel using the api2.cursor.sh update feed, machine id resolution, and local sync layout under ~/.local/share/grok-bot (or GROKBOT_DOGFOOD_INSTALL_ROOT).
---

# install-grokbot-dogfood

Use this skill when automation or a user needs a **Grok Bot Dogfood** build the same way Marcelo’s laptop does (`sync.py` + `launch.sh`), without the public `cursor.com/api/download` dogfood track.

## Layout (default `~/.local/share/grok-bot`)

| Path | Role |
|------|------|
| `cache/dogfood-<sha12>-0.AppImage` | Verified download cache |
| `staging/` | Temporary extract (during sync) |
| `current/` | Active squashfs extract (AppRun lives here on laptop) |
| `current.prev/` | Previous extract after swap |
| `installed.json` | `{version, sha256, track, channel, url, appimage}` |

Automation exports copies to repo `versions/dogfood-new` and `versions/dogfood-previous` via `scripts/install-dogfood-pair.sh`.

## Machine id (never log raw value)

Resolution order:

1. **`GROKBOT_MACHINE_ID`** — Automation Memory or env (preferred for Cloud Agents).
2. **Decrypt** `~/.config/Grok Bot/sand-secrets.json` → `cursor-machine-id` (base64, `v11` prefix) using GNOME Keyring **Grok Bot Safe Storage** + PBKDF2/AES (see `scripts/grokbot_dogfood/machine_id.py`).
3. **Fail** with a clear error; do not guess.

Check masked status only:

```bash
bash scripts/grokbot-machine-id.sh --masked
```

## Update feed

- **URL:** `https://api2.cursor.sh/updates/api/update/linux-{x64|arm64}/sand-dogfood/{installed_version}/{machine_id}/stable`
- **Query:** `?trackChanged=1` when installed version is not already a dogfood-tagged build
- **Header:** `User-Agent: sand-dogfood`
- **204 / empty:** no update
- **JSON:** `version`, `url`, `sha256hash` — `url` must contain `/dogfood/` and `/linux/`

## Commands

```bash
# Full dogfood sync (laptop layout)
bash scripts/grokbot-dogfood-sync.sh --install-root ~/.local/share/grok-bot

# Automation pair (new + previous exports for changelog diff)
bash scripts/install-dogfood-pair.sh --first-run
bash scripts/install-dogfood-pair.sh --previous-commit "$dogfood_commit_sha"

# Changelog diff pipeline (after pair)
bash scripts/run-dogfood-changelog-pipeline.sh
```

## Environment

| Variable | Purpose |
|----------|---------|
| `GROKBOT_MACHINE_ID` | Feed authentication (required in CI/cloud without keyring) |
| `GROKBOT_DOGFOOD_INSTALL_ROOT` | Sync root (default `~/.local/share/grok-bot`) |
| `GROKBOT_DOGFOOD_SYNC_ROOT` | Automation sync root (default `versions/grok-bot-dogfood`) |
| `GROKBOT_CONFIG_ROOT` | Override `~/.config/Grok Bot` for secrets path |

## launch.sh note (laptop only)

Marcelo’s `launch.sh` also sets `SAND_FEATURE_GATE_OVERRIDES` (appends `isAnysphereUsersetIsAnysphereUser=true`) before `exec current/AppRun`. Automation scripts do **not** launch the app; they only sync/build artifacts for Groketective and Notion.

## Dependencies

- `python3`, `curl` (via urllib), `npx @electron/asar` optional for version read
- `unsquashfs` or AppImage `--appimage-extract` (see `scripts/setup-deps.sh`)
- Keyring path: `python3-secretstorage`, `cryptography` (local decrypt only)
