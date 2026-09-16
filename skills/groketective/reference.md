# groketective reference

Read-only path tables and slice-key notes. Pipeline lives in `SKILL.md`.

## Platform paths

| Artifact | Linux | Notes |
|----------|-------|-------|
| Install root | `/opt/Grok Bot/` | Debian package name `sand`; productName `Grok Bot` |
| Binary | `/opt/Grok Bot/sand` | Electron main + helper processes |
| App archive | `/opt/Grok Bot/resources/app.asar` | Main code; unpacked natives under `app.asar.unpacked/` |
| Electron user-data | `~/.config/Grok Bot/` | Chromium profile + sand app files |
| App data root | `~/.grokbot/` | Settings + local-exec daemon state |
| Client persistence | `~/.config/Grok Bot/sand-client-persistence/` | `*.blob` slice store |
| Statsig bootstrap | `~/.config/Grok Bot/sand-statsig-bootstrap.json` | Cached initializeResponse (`config` string; djb2-hashed gates) |
| Feature-flag overrides | `~/.config/Grok Bot/sand-feature-flag-overrides.json` | Optional local boolean overrides (TTL 24h); often absent |

## Dev vs packaged variants

| Variant | Condition | Notes |
|---------|-----------|-------|
| `sand-dev` | `SAND_PACKAGED !== "1"` | Unpackaged Electron (`app.isPackaged === false`); `isDevBuild=true` |
| `sand-lab` | packaged + `package.json.sandLab === true` | Sets `SAND_LAB=1` |
| `sand` | packaged production | Default `/opt/Grok Bot` install (`sandTrack` often `stable`) |

Startup always sets `SAND_PACKAGED` from `app.isPackaged` (and attach-prod-box); env alone cannot force `sand-dev` on a packaged install. Dev controls / `SAND_DEV_CAPABILITY` require unpackaged.

macOS v1: treat as **Unknown** after documenting attempts; expected Application Support dir is `~/Library/Application Support/Grok Bot`.

## Package identity

From `app.asar` → `package.json` (Confirmed on 0.16.0):

- `name`: `sand`
- `productName`: `Grok Bot`
- `main`: `dist/electron-main/main.cjs`
- Vendor/homepage strings may point at SpaceXAI / cursor.com

## `sand-client-persistence`

Each file `*.blob`:

1. Stem = lowercase RFC4648 base32 of the slice key, padding stripped.
2. Body = JSON envelope `{"schemaVersion": N, "value": …}`.

Decode/list via `slice_keys.py` / `list-persistence.sh`.

### Known slice kinds

| Kind | Key suffix / pattern | Typical value |
|------|----------------------|---------------|
| `transcript.replicas` | `…transcript.replicas.<uuid>` | Chat/agent transcript entries (client tail; ≤200 entries, ≤768 KiB; `persistedAt` refreshed on write; optional `restoredSeed`) |
| `roster.last-roster` | `…roster.last-roster` | Agent list (id, name, description) |
| `composer-drafts` | `…composer-drafts` | Draft state |
| `sidebar.last-sections` | `…sidebar.last-sections` | UI sidebar |
| `selection.last-agent` | `…selection.last-agent` | Selected agent id |
| `ui-agent-refs` | `…ui-agent-refs` | UI refs |
| `send-journal` | `…send-journal` | Send journal |
| `ui-layout` | `sand.client.slice.ui-layout` | Layout |
| `client-meta` | `sand.client.slice.client-meta.account-slot` | Account slot meta |

Account-scoped keys look like:

`sand.client.slice.account.<urlencoded-account-id>.…`

Account ids may contain `%7C` (`|`) after URL encoding.

## Asar entrypoints

Prefer grepping extracted files over the whole 190MB archive:

| Path inside asar | Role |
|------------------|------|
| `dist/electron-main/main.cjs` | Electron main |
| `dist/local-exec-daemon/main.cjs` | Local exec over gateway |
| `dist/host/host-main.cjs` | Host services |
| `dist/electron-preload/preload.cjs` | Preload bridge |
| `dist/renderer/assets/*` | UI chunks (large; theme-filter) |
| `package.json` | Version / productName |

`grep-asar.sh` extracts the main/daemon/host/preload entrypoints when `npx @electron/asar` works.

## Daemon / gateway files (`~/.grokbot`)

| File | Safe to print | Notes |
|------|---------------|-------|
| `settings.json` | Yes after redact | MCP prefs, theme, permissions |
| `local-exec-daemon.json` | Yes | pid, startedAt |
| `local-exec-supervisor.json` | Yes | supervisor pid |
| `local-exec-daemon.log` | Yes | startup/shutdown lines |
| `local-exec-daemon-connection.json` | Presence + host only | Contains tokens / VM URLs |
| `local-exec-daemon-credential.json` | Presence only | Contains credentials |

`~/.config/Grok Bot/gateway-descriptor.json` and `sand-secrets.json`: presence/size only.

## `grep-asar.sh` defaults

Built-in patterns:

- `sand.client.slice`
- `sand-client-persistence`
- `local-exec-daemon`
- `transcript.replicas`
- `roster.last-roster`
- `gateway-descriptor`
- `@anysphere/grok-bot`

## Recovered transcript import

| Script | Role |
|--------|------|
| `import-recovered.sh` | CLI: quit-gate, backup, merge recovered zip into live replicas |
| `import_recovered.py` | Parse zip markdown, name-match roster, content-key merge |

Join key is **normalized display name** (`Golden-Map` → `goldenmap` = roster `Golden Map`). Zip **leftover UUID** metadata is diagnostic only; writes use the **live** roster UUID. Do not fuzzy-match distinct names (`Gold-Mapper` ≠ `Golden Map`). Unmatched zip stems are skipped (no invented roster rows).

## Versus cursor-detective

| Concern | cursor-detective | groketective |
|---------|------------------|--------------|
| Product | Cursor IDE | Grok Bot (`sand`) |
| Bundle | `workbench.desktop.main.js` | `app.asar` |
| Persistence | `state.vscdb` / `store.db` | base32 `*.blob` slices |
| Report path | `detective-<theme>.plan.md` | `groketective-<theme>.plan.md` |
