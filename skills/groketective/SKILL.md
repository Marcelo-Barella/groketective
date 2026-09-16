---
name: groketective
description: >-
  Grok Bot Detective. Deep read-only forensics on Grok Bot (internal codename
  sand) local install, Electron user-data, ~/.grokbot, app.asar, and
  sand-client-persistence slices. Also imports recovered Windows markdown
  transcript zips into live bots via /groketective import. Writes
  .cursor/plans/groketective-<theme>.plan.md. Use when the user invokes
  /groketective, /groketective import, or asks to reverse-engineer Grok Bot
  internals or restore recovered Grok Bot chats.
disable-model-invocation: true
mode: true
icon: cursor-logo
color: brand
reminder: Grok Bot Detective — read-only forensics by default; probe to max depth in one pass; write .cursor/plans/groketective-<theme>.plan.md; never modify ~/.grokbot, ~/.config/Grok Bot, or /opt/Grok Bot except explicit `/groketective import`; redact tokens/credentials in reports.
---

# groketective

Read-only investigation skill for **Grok Bot only**. Do not modify `~/.grokbot`, `~/.config/Grok Bot`, or `/opt/Grok Bot` except the named `/groketective import` write exception and the report under the **current workspace**.

Not for Cursor IDE forensics. Use **cursor-detective** for Cursor workbench / `state.vscdb`.

## Depth policy (mandatory)

Every run goes **as deep as evidence allows in one pass**. Do not stop at inventory when `app.asar`, persistence blobs, or daemon files are reachable.

**Always do without asking:**

- Resolve install (`/opt/Grok Bot`), binary `sand`, and `resources/app.asar`.
- Inventory `~/.grokbot` and `~/.config/Grok Bot` without dumping secret values.
- Decode `sand-client-persistence` base32 blob keys; list roster + transcript agents.
- Grep asar entrypoints for theme-relevant markers (`sand.client.slice`, `local-exec-daemon`, …).
- Launch parallel subagents when the theme is broad or probes are independent.

**Never:**

- Ask whether to go deeper or run extra probes.
- End the reply with permission prompts.
- Print tokens, credentials, `encrypted` gateway payloads, or `sand-secrets.json` values. Redact; record presence/size only.
- Cross into Cursor IDE paths (`~/.cursor` state DBs, Cursor workbench) unless the theme explicitly compares the two products.

Record blocked probes under **Gaps & follow-ups**.

## Invocation

`/groketective [theme]`

Empty theme → `general-scan`.

### `/groketective import` (write exception)

Named exception to read-only rules. Merges recovered Windows markdown zip into **live** `transcript.replicas` blobs by normalized roster name (not leftover UUID).

```text
/groketective import --zip PATH [--dry-run] [--persistence-root DIR]
```

Script: `./import-recovered.sh --zip PATH [--dry-run]`

**Before live run:** user must quit Grok Bot (`grok-bot` and `sand`). Script refuses if either process is running.

**Live run steps:** backup `sand-client-persistence/` to sibling `sand-client-persistence.import-backup-<utc>/`; merge matched chats; skip unmatched (no roster row); set `persistedAt` to now (replicas older than 7 days may be dropped by the client); cap merged tail at 200 entries and 768 KiB (newest kept; prints `trimmed=` when capped); set `restoredSeed` so UI can show imported history before server transcript installs.

**Resync warning:** replica-only writes are second-class. On connect, `replica_resync` / store-first hydration from box `store.db` can wipe import-only tails without gateway `CommitGrokBotTranscriptEntries`.

**Dry-run:** parse, match, print mapping table; no persistence writes. `--index-out` may write plan JSON only.

Leftover UUIDs in zip metadata are diagnostic only; blobs are written under **live** roster UUIDs.

## Theme normalization

Trim, lowercase, spaces/underscores → `-`, strip non `[a-z0-9-]`, collapse `-`, fallback `general-scan`.

Output: `.cursor/plans/groketective-<theme>.plan.md` (create `.cursor/plans/` if missing).

## Domain model (data shape)

| Layer | Path | Shape |
|-------|------|-------|
| Install | `/opt/Grok Bot/` | Electron app; binary `sand`; package name `sand`; `resources/app.asar` |
| App settings / daemon | `~/.grokbot/` | `settings.json`, `local-exec-daemon*.json`, logs |
| Electron user-data | `~/.config/Grok Bot/` | Chromium profile + `sand-*` app files |
| Client persistence | `…/sand-client-persistence/*.blob` | Filename = lowercase unpadded base32 of slice key; body = JSON `{schemaVersion, value}` |
| Slice keys | `sand.client.slice.…` | `account.<id>.transcript.replicas.<uuid>`, `…roster.last-roster`, `ui-layout`, `client-meta.account-slot`, … |

## Pipeline

### Phase 1 — Frame

1. Normalize theme.
2. Set `PLAN_PATH=".cursor/plans/groketective-<theme>.plan.md"`.
3. One paragraph: objective, scope, success criteria.
4. Bullet testable assumptions and unknowns.

### Phase 2 — Discover (scripts, in order)

Resolve this skill's directory (plugin install or `~/.cursor/skills/groketective`), then run from its `scripts/`:

1. `./locate-grokbot.sh`
2. `./scan-paths.sh`
3. `./list-persistence.sh`

Continue on non-fatal missing install; stop only if `python3` is missing when persistence decode is required.

### Phase 3 — Delegate (parallel probes)

When theme is broad (`general-scan`) or Phase 4 spans asar + persistence + daemon, launch up to four parallel subagents:

| Agent | Scope |
|-------|--------|
| Install/asar | `locate-grokbot.sh`, `grep-asar.sh` builtins + theme patterns |
| Persistence | `list-persistence.sh`; `inspect-slice.sh --kind roster.last-roster`; sample one transcript |
| Daemon | `inspect-daemon.sh` (redacted) |
| Compare | User paths: `compare-dirs.sh` |

Subagents paste script output; tag every finding. Never paste secret values.

### Phase 4 — Extract (by theme)

| Theme signal | Scripts |
|--------------|---------|
| persistence, transcript, roster, agent | `list-persistence.sh`, `inspect-slice.sh` |
| daemon, local-exec, gateway, vm | `inspect-daemon.sh`, `scan-paths.sh` |
| UI, renderer, asar, bundle | `grep-asar.sh` |
| compare, diff | `compare-dirs.sh` |
| inventory / general | all of the above with default limits |
| settings, mcp, themePreference | redacted `settings.json` via `scan-paths.sh` |

### Phase 4b — Asar deep extract (mandatory when asar reachable)

1. Confirm `APP_ASAR` from `locate-grokbot.sh`.
2. Run `grep-asar.sh --builtin` plus theme keywords.
3. Prefer extracted entrypoints: `dist/electron-main/main.cjs`, `dist/local-exec-daemon/main.cjs`, `dist/host/host-main.cjs`, `package.json`.
4. Cite at least one **Confirmed** snippet per major subsystem in findings.

If asar is unreachable, tag **Unknown** and list paths tried.

### Phase 5 — Synthesize

Write `PLAN_PATH` using **Report template**. Scripts before any **Confirmed** finding. Include **Internal code map** when Phase 4b ran or the theme concerns runtime/UI/persistence.

## Evidence model

| Tag | Use when |
|-----|----------|
| **Confirmed** | Script stdout or cited path + snippet |
| **Inferred** | Pattern in asar/JSON without runtime proof |
| **Unknown** | Probe ran; no evidence; say what was tried |

Forbidden: inventing keys, APIs, or paths not seen in probes. Forbidden: dumping secrets into the plan.

## Report template (required section order)

1. **Objective**
2. **Environment** (OS; locate-grokbot; asar path; version/productName)
3. **Scan checklist** (script, exit code, one-line result)
4. **Findings** (by subsystem; tagged bullets; secrets redacted)
5. **Internal code map** (asar entrypoints, slice key kinds, daemon files)
6. **Diagram** (mermaid: persistence and/or local-exec flow when in scope)
7. **Gaps & follow-ups** (blocked probes only)
8. **Workspace relevance** (optional)

## Script index

| Script | Purpose |
|--------|---------|
| `locate-grokbot.sh` | Install + `APP_ASAR` + version |
| `scan-paths.sh` | Config/data inventory; redacted settings |
| `list-persistence.sh` | Decode blob keys (`--kind`, `--agent-id`) |
| `inspect-slice.sh` | Read one slice |
| `inspect-daemon.sh` | Local-exec status; secrets redacted |
| `grep-asar.sh` | Pattern search in asar entrypoints |
| `compare-dirs.sh` | Shallow dir file compare |
| `slice_keys.py` | Encode/decode/list/read helpers |
| `import-recovered.sh` | Recovered zip → live replica merge (quit-gate + backup) |

See [reference.md](reference.md) for paths and slice kinds.

## Related skills

| Skill | Use instead when |
|-------|------------------|
| cursor-detective | Cursor IDE / workbench / `state.vscdb` |
| research | Open-repo code, not Grok Bot product |
| debugger | Repro + fix |
