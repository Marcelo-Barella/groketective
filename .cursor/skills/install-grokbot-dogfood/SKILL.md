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

Resolution order (same as `scripts/grokbot_dogfood/machine_id.py`):

1. **`GROKBOT_MACHINE_ID`** — Automation Memory or env (preferred for Cloud Agents).
2. **Existing install** — decrypt `~/.config/Grok Bot/sand-secrets.json` → `cursor-machine-id` (`v11` + GNOME Keyring **Grok Bot Safe Storage**, PBKDF2/AES).
3. **Bootstrap** — if secrets are missing: download official **Linux stable** build (browser entry point [https://x.ai/bot](https://x.ai/bot); headless uses `cursor.com/api/download` with `appName=sand`), launch once under **xvfb** so Electron writes `sand-secrets.json`, then decrypt (step 2).
4. **Fail** with a clear error.

Disable bootstrap: `GROKBOT_DISABLE_BOOTSTRAP=1` or `grokbot-machine-id.sh --no-bootstrap`.

Check masked status only:

```bash
bash scripts/grokbot-machine-id.sh --masked
```

### Headless bootstrap (automation VM)

Requires:

- `xvfb-run` (virtual display)
- D-Bus session (`dbus-launch` or existing `DBUS_SESSION_BUS_ADDRESS`)
- **Unlocked GNOME keyring** with Grok Bot Safe Storage after first launch (`gnome-keyring-daemon --start --components=secrets`; login keyring may need `GROKBOT_KEYRING_PASSWORD` / manual unlock)

**Cannot work without:** keyring decrypt for `v11` secrets (set `GROKBOT_MACHINE_ID` instead), or a successful GUI/session launch on hosts that block Electron under xvfb.

Override official download URL: `GROKBOT_OFFICIAL_DOWNLOAD_URL` (+ optional `GROKBOT_OFFICIAL_VERSION`).

## Update feed

- **URL:** `https://api2.cursor.sh/updates/api/update/linux-{x64|arm64}/sand-dogfood/{installed_version}/{machine_id}/stable`
- **`trackChanged` (same as Marcelo `sync.py`):**  
  `prerelease_tag(version) = 'stable'` if `'-' not in version`, else `version.split('-',1)[1].split('.',1)[0] or 'stable'`; append `?trackChanged=1` when `prerelease_tag(version) != 'dogfood'`.
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
| `GROKBOT_MACHINE_ID` | Feed authentication (preferred for Cloud Agents) |
| `GROKBOT_DISABLE_BOOTSTRAP` | Skip official install + launch bootstrap |
| `GROKBOT_OFFICIAL_DOWNLOAD_URL` | Override Linux stable AppImage URL (default: API behind x.ai/bot) |
| `GROKBOT_BOOTSTRAP_WAIT_SEC` | Seconds to wait for sand-secrets after launch (default 180) |
| `GROKBOT_DOGFOOD_INSTALL_ROOT` | Sync root (default `~/.local/share/grok-bot`) |
| `GROKBOT_DOGFOOD_SYNC_ROOT` | Automation sync root (default `versions/grok-bot-dogfood`) |
| `GROKBOT_CONFIG_ROOT` | Override `~/.config/Grok Bot` for secrets path |

## launch.sh note (laptop only)

Marcelo’s `launch.sh` also sets `SAND_FEATURE_GATE_OVERRIDES` (appends `isAnysphereUsersetIsAnysphereUser=true`) before `exec current/AppRun`. Automation scripts do **not** launch the app; they only sync/build artifacts for Groketective and Notion.

## Dependencies

- `python3`, `curl` (via urllib), `npx @electron/asar` optional for version read
- `unsquashfs` or AppImage `--appimage-extract` (see `scripts/setup-deps.sh`)
- Keyring path: `python3-secretstorage`, `cryptography` (local decrypt only)
