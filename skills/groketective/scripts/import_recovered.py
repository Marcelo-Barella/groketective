#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import uuid
import zipfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from slice_keys import b32_encode, list_blobs  # noqa: E402

BRT = timezone(timedelta(hours=-3))
MAX_ENTRIES = 200
MAX_BYTES = 768 * 1024
HEADER_RE = re.compile(
    r"^\*\*(User|Bot|Bot → (.+?)|From (.+?)|Event)\*\* · (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) BRT\s*$",
    re.MULTILINE,
)
LEFTOVER_RE = re.compile(r"Old leftover id:\*\* `([0-9a-f-]{36})`", re.IGNORECASE)
RENAME_EVENT_RE = re.compile(
    r"^Renamed \*\*(.+?)\*\* → \*\*(.+?)\*\*\s*$", re.MULTILINE
)


class QuitGateError(RuntimeError):
    pass


class PersistenceError(RuntimeError):
    pass


def normalize_bot_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", name.lower())


def stem_to_match_name(stem: str) -> str:
    s = stem
    if s.endswith("-cache"):
        s = s[: -len("-cache")]
    return s.replace("-", " ")


def parse_brt_ms(ts: str) -> int:
    dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S").replace(tzinfo=BRT)
    return int(dt.timestamp() * 1000)


def strip_body(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


@dataclass
class TranscriptLine:
    speaker: str
    agent_name: str | None
    timestamp_ms: int
    body: str


@dataclass
class RecoveredChat:
    source_stem: str
    source_path_in_zip: str
    leftover_uuid: str | None
    lines: list[TranscriptLine]


@dataclass
class LiveBot:
    id: str
    name: str
    normalized_name: str
    row: dict[str, Any]


@dataclass
class RosterSnapshot:
    schema_version: int
    account_prefix: str
    bots: list[LiveBot]
    raw_rows: list[dict[str, Any]]
    roster_path: Path
    roster_key: str


@dataclass
class BotImportTarget:
    chat: RecoveredChat
    bot: LiveBot
    existing_count: int
    incoming_count: int
    added: int
    skipped_dup: int
    trimmed: int
    final_count: int
    merged_entries: list[dict[str, Any]]


@dataclass
class ImportPlan:
    matched: list[BotImportTarget]
    unmatched: list[dict[str, Any]]
    dry_run: bool
    persistence_root: Path
    roster: RosterSnapshot


def parse_recovered_markdown(text: str, *, source_stem: str, source_path_in_zip: str) -> RecoveredChat:
    leftover = None
    m = LEFTOVER_RE.search(text)
    if m:
        leftover = m.group(1)
    lines: list[TranscriptLine] = []
    matches = list(HEADER_RE.finditer(text))
    for i, hm in enumerate(matches):
        start = hm.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip("\n")
        kind = hm.group(1)
        if kind == "User":
            speaker = "user"
            agent_name = None
        elif kind == "Bot":
            speaker = "bot"
            agent_name = None
        elif kind.startswith("Bot"):
            speaker = "bot_to"
            agent_name = hm.group(2)
        elif kind.startswith("From"):
            speaker = "from"
            agent_name = hm.group(3)
        else:
            speaker = "event"
            agent_name = None
        lines.append(
            TranscriptLine(
                speaker=speaker,
                agent_name=agent_name,
                timestamp_ms=parse_brt_ms(hm.group(4)),
                body=body,
            )
        )
    return RecoveredChat(source_stem, source_path_in_zip, leftover, lines)


def load_recovered_archive(zip_path: Path) -> list[RecoveredChat]:
    chats: list[RecoveredChat] = []
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            name = info.filename
            if not name.lower().endswith(".md"):
                continue
            stem = Path(name).stem
            if stem.upper() == "INDEX":
                continue
            text = zf.read(info).decode("utf-8", errors="replace")
            chats.append(parse_recovered_markdown(text, source_stem=stem, source_path_in_zip=name))
    chats.sort(key=lambda c: c.source_stem.lower())
    return chats


def load_live_roster(persistence_root: Path) -> RosterSnapshot:
    rows = list_blobs(persistence_root)
    roster_row = next((r for r in rows if r.get("kind") == "roster.last-roster"), None)
    if not roster_row:
        raise PersistenceError(f"roster.last-roster not found under {persistence_root}")
    data = json.loads(Path(roster_row["path"]).read_text(encoding="utf-8"))
    key = roster_row["key"]
    prefix = key.split("roster.last-roster")[0]
    raw_rows = data["value"]["rows"]
    bots: list[LiveBot] = []
    for row in raw_rows:
        bots.append(
            LiveBot(
                id=row["id"],
                name=row["name"],
                normalized_name=normalize_bot_name(row["name"]),
                row=dict(row),
            )
        )
    return RosterSnapshot(
        schema_version=data["schemaVersion"],
        account_prefix=prefix,
        bots=bots,
        raw_rows=raw_rows,
        roster_path=Path(roster_row["path"]),
        roster_key=key,
    )


def roster_index_by_name(roster: RosterSnapshot) -> dict[str, LiveBot]:
    idx: dict[str, LiveBot] = {}
    for bot in roster.bots:
        if bot.normalized_name in idx:
            raise PersistenceError(f"duplicate roster normalized name: {bot.normalized_name}")
        idx[bot.normalized_name] = bot
    return idx


def replica_key(account_prefix: str, agent_id: str) -> str:
    return f"{account_prefix}transcript.replicas.{agent_id}"


def replica_path(persistence_root: Path, account_prefix: str, agent_id: str) -> Path:
    return persistence_root / f"{b32_encode(replica_key(account_prefix, agent_id))}.blob"


def read_replica(persistence_root: Path, account_prefix: str, agent_id: str) -> dict[str, Any] | None:
    path = replica_path(persistence_root, account_prefix, agent_id)
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def find_any_epoch_hint(persistence_root: Path, account_prefix: str) -> str | None:
    for r in list_blobs(persistence_root):
        if r.get("kind") != "transcript.replicas":
            continue
        if not r["key"].startswith(account_prefix):
            continue
        data = json.loads(Path(r["path"]).read_text(encoding="utf-8"))
        hint = data.get("value", {}).get("epochHint")
        if hint:
            return hint
    return None


def resolve_agent(name: str | None, roster_idx: dict[str, LiveBot]) -> dict[str, Any] | None:
    if not name:
        return None
    bot = roster_idx.get(normalize_bot_name(name))
    if bot:
        return {"id": bot.id, "name": bot.name}
    return {"name": name}


def parse_event_body(body: str) -> dict[str, Any]:
    m = RENAME_EVENT_RE.search(body.strip())
    if m:
        return {"type": "name-changed", "from": m.group(1), "to": m.group(2)}
    first = body.strip().split("\n", 1)[0]
    return {"type": "imported", "from": first[:120], "to": ""}


def map_chat_to_entries(
    chat: RecoveredChat,
    home_bot: LiveBot,
    roster_idx: dict[str, LiveBot],
    id_start: int = 1,
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    n = id_start
    for line in chat.lines:
        eid = f"imp-{n}"
        n += 1
        if line.speaker == "user":
            entries.append(
                {
                    "kind": "message",
                    "id": eid,
                    "role": "user",
                    "content": line.body,
                    "timestampMs": line.timestamp_ms,
                }
            )
        elif line.speaker == "bot":
            entries.append(
                {
                    "kind": "send-message",
                    "id": eid,
                    "message": {"type": "text", "content": line.body},
                    "timestampMs": line.timestamp_ms,
                    "requestId": str(uuid.uuid4()),
                }
            )
        elif line.speaker == "bot_to":
            entry: dict[str, Any] = {
                "kind": "send-message",
                "id": eid,
                "message": {"type": "text", "content": line.body},
                "timestampMs": line.timestamp_ms,
                "requestId": str(uuid.uuid4()),
            }
            ref = resolve_agent(line.agent_name, roster_idx)
            if ref:
                entry["toAgent"] = {**ref, "kind": "agent"} if "id" in ref else ref
            entries.append(entry)
        elif line.speaker == "from":
            entry = {
                "kind": "message",
                "id": eid,
                "role": "assistant",
                "content": line.body,
                "timestampMs": line.timestamp_ms,
            }
            ref = resolve_agent(line.agent_name, roster_idx)
            if ref:
                entry["fromAgent"] = ref
            entries.append(entry)
        else:
            entries.append(
                {
                    "kind": "event",
                    "id": eid,
                    "event": parse_event_body(line.body),
                    "timestampMs": line.timestamp_ms,
                }
            )
    return entries


def entry_text(entry: dict[str, Any]) -> str:
    kind = entry.get("kind")
    if kind == "message":
        return strip_body(str(entry.get("content", "")))
    if kind == "send-message":
        msg = entry.get("message") or {}
        return strip_body(str(msg.get("content", "")))
    if kind == "event":
        ev = entry.get("event") or {}
        return strip_body(f"{ev.get('type','')}|{ev.get('from','')}|{ev.get('to','')}")
    return ""


def agent_ref_name(ref: dict[str, Any] | None) -> str:
    if not ref:
        return ""
    return normalize_bot_name(str(ref.get("name", "")))


def content_key(entry: dict[str, Any]) -> str:
    kind = entry.get("kind", "")
    role = entry.get("role", "")
    from_n = agent_ref_name(entry.get("fromAgent"))
    to_n = agent_ref_name(entry.get("toAgent"))
    return f"{kind}|{role}|{from_n}|{to_n}|{entry_text(entry)}"


def merge_entries(
    existing: list[dict[str, Any]], incoming: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], int, int]:
    seen = {content_key(e) for e in existing}
    merged = list(existing)
    added = 0
    skipped = 0
    for e in incoming:
        k = content_key(e)
        if k in seen:
            skipped += 1
            continue
        seen.add(k)
        merged.append(e)
        added += 1
    merged.sort(key=lambda x: x.get("timestampMs", 0))
    return merged, added, skipped


def envelope_bytes(value: dict[str, Any]) -> int:
    return len(json.dumps({"schemaVersion": 1, "value": value}, ensure_ascii=False).encode("utf-8"))


def trim_entries(
    entries: list[dict[str, Any]],
    *,
    epoch_hint: str | None,
    accepted_hint: int,
    persisted_at: int,
    restored_seed: bool,
) -> tuple[list[dict[str, Any]], int]:
    trimmed = 0
    cur = entries
    if len(cur) > MAX_ENTRIES:
        drop = len(cur) - MAX_ENTRIES
        cur = cur[-MAX_ENTRIES:]
        trimmed += drop

    def build() -> dict[str, Any]:
        v: dict[str, Any] = {
            "entries": cur,
            "epochHint": epoch_hint,
            "acceptedSequenceHint": max(accepted_hint, len(cur)),
            "persistedAt": persisted_at,
        }
        if restored_seed:
            v["restoredSeed"] = True
        return v

    while envelope_bytes(build()) > MAX_BYTES and len(cur) > 1:
        cur = cur[1:]
        trimmed += 1
    return cur, trimmed


def last_entry_payload(entry: dict[str, Any]) -> dict[str, Any]:
    text = entry_text(entry)
    if entry.get("kind") == "event":
        ev = entry.get("event") or {}
        text = f"{ev.get('type', 'event')}: {ev.get('from', '')} → {ev.get('to', '')}".strip()
    return {"kind": "text", "text": text[:500]}


def update_roster_row(row: dict[str, Any], newest: dict[str, Any]) -> None:
    row["lastEntry"] = last_entry_payload(newest)
    row["lastMessageId"] = newest.get("id", row.get("lastMessageId"))
    row["newestEntryId"] = newest.get("id", row.get("newestEntryId"))
    ts = newest.get("timestampMs", row.get("lastActivityAt"))
    row["lastActivityAt"] = ts
    row["updatedAt"] = ts


def assert_grokbot_quit() -> None:
    self_pid = str(os.getpid())
    patterns = [
        ["pgrep", "-x", "sand"],
        ["pgrep", "-x", "grok-bot"],
        ["pgrep", "-f", "/opt/Grok Bot/sand"],
        ["pgrep", "-f", "/opt/Grok Bot/grok-bot"],
    ]
    pids: list[str] = []
    for cmd in patterns:
        try:
            out = subprocess.run(cmd, capture_output=True, text=True, check=False)
            for line in out.stdout.splitlines():
                line = line.strip()
                if line and line not in pids and line != self_pid:
                    pids.append(line)
        except OSError:
            pass
    if pids:
        raise QuitGateError(f"Grok Bot still running (pids={','.join(pids)})")


def backup_persistence_root(persistence_root: Path) -> Path:
    parent = persistence_root.parent
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = parent / f"sand-client-persistence.import-backup-{ts}"
    shutil.copytree(persistence_root, dest)
    return dest


def build_import_plan(
    chats: list[RecoveredChat],
    roster: RosterSnapshot,
    *,
    persistence_root: Path,
    dry_run: bool,
) -> ImportPlan:
    roster_idx = roster_index_by_name(roster)
    matched: list[BotImportTarget] = []
    unmatched: list[dict[str, Any]] = []
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    fallback_epoch = find_any_epoch_hint(persistence_root, roster.account_prefix)

    for chat in chats:
        norm = normalize_bot_name(stem_to_match_name(chat.source_stem))
        bot = roster_idx.get(norm)
        if not bot:
            unmatched.append(
                {
                    "zip_stem": chat.source_stem,
                    "normalized": norm,
                    "leftover_uuid": chat.leftover_uuid,
                    "reason": "no_roster_name",
                }
            )
            continue
        blob = read_replica(persistence_root, roster.account_prefix, bot.id)
        existing: list[dict[str, Any]] = []
        epoch_hint = fallback_epoch
        accepted_hint = 0
        if blob:
            value = blob.get("value") or {}
            existing = list(value.get("entries") or [])
            if value.get("epochHint") is not None:
                epoch_hint = value.get("epochHint")
            accepted_hint = int(value.get("acceptedSequenceHint") or 0)
        incoming = map_chat_to_entries(chat, bot, roster_idx)
        merged, added, skipped = merge_entries(existing, incoming)
        restored = added > 0 or not blob
        merged, trimmed = trim_entries(
            merged,
            epoch_hint=epoch_hint,
            accepted_hint=accepted_hint,
            persisted_at=now_ms,
            restored_seed=restored,
        )
        matched.append(
            BotImportTarget(
                chat=chat,
                bot=bot,
                existing_count=len(existing),
                incoming_count=len(incoming),
                added=added,
                skipped_dup=skipped,
                trimmed=trimmed,
                final_count=len(merged),
                merged_entries=merged,
            )
        )
    return ImportPlan(matched=matched, unmatched=unmatched, dry_run=dry_run, persistence_root=persistence_root, roster=roster)


def format_plan_table(plan: ImportPlan) -> str:
    lines = [
        "zip_stem              normalized          live_agent_id                         action",
    ]
    for t in plan.matched:
        action = f"merge +{t.added} entries ({t.skipped_dup} dup)"
        if t.trimmed:
            action += f" trimmed={t.trimmed}"
        lines.append(
            f"{t.chat.source_stem:<22}{normalize_bot_name(stem_to_match_name(t.chat.source_stem)):<20}{t.bot.id:<38}{action}"
        )
    for u in plan.unmatched:
        lines.append(
            f"{u['zip_stem']:<22}{u['normalized']:<20}{'—':<38}skip (no roster match)"
        )
    return "\n".join(lines)


def plan_index(plan: ImportPlan) -> dict[str, Any]:
    return {
        "dry_run": plan.dry_run,
        "matched": [
            {
                "zip_stem": t.chat.source_stem,
                "normalized": normalize_bot_name(stem_to_match_name(t.chat.source_stem)),
                "live_agent_id": t.bot.id,
                "leftover_uuid": t.chat.leftover_uuid,
                "entries_added": t.added,
                "entries_skipped_duplicate": t.skipped_dup,
                "trimmed": t.trimmed,
            }
            for t in plan.matched
        ],
        "unmatched": plan.unmatched,
    }


def execute_import_plan(plan: ImportPlan) -> tuple[int, int]:
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    roster_rows = {r["id"]: dict(r) for r in plan.roster.raw_rows}
    wrote = 0
    for t in plan.matched:
        if t.added == 0 and t.existing_count > 0:
            continue
        blob = read_replica(plan.persistence_root, plan.roster.account_prefix, t.bot.id)
        epoch_hint = find_any_epoch_hint(plan.persistence_root, plan.roster.account_prefix)
        accepted_hint = 0
        if blob:
            value = blob.get("value") or {}
            if value.get("epochHint") is not None:
                epoch_hint = value.get("epochHint")
            accepted_hint = int(value.get("acceptedSequenceHint") or 0)
        restored = t.added > 0 or not blob
        value: dict[str, Any] = {
            "entries": t.merged_entries,
            "epochHint": epoch_hint,
            "acceptedSequenceHint": max(accepted_hint, len(t.merged_entries)),
            "persistedAt": now_ms,
        }
        if restored:
            value["restoredSeed"] = True
        path = replica_path(plan.persistence_root, plan.roster.account_prefix, t.bot.id)
        path.write_text(
            json.dumps({"schemaVersion": 1, "value": value}, ensure_ascii=False),
            encoding="utf-8",
        )
        wrote += 1
        row = roster_rows.get(t.bot.id)
        if row and t.merged_entries:
            update_roster_row(row, t.merged_entries[-1])
    roster_updated = 0
    if wrote:
        out = {
            "schemaVersion": plan.roster.schema_version,
            "value": {"rows": list(roster_rows.values())},
        }
        plan.roster.roster_path.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
        roster_updated = sum(1 for t in plan.matched if t.added > 0 or t.existing_count == 0)
    return wrote, roster_updated


def verify_import(plan: ImportPlan) -> dict[str, int]:
    counts: dict[str, int] = {}
    for t in plan.matched:
        if t.added == 0:
            continue
        blob = read_replica(plan.persistence_root, plan.roster.account_prefix, t.bot.id)
        n = len((blob or {}).get("value", {}).get("entries") or [])
        counts[t.bot.id] = n
    return counts


def run_import(
    *,
    zip_path: Path,
    persistence_root: Path,
    dry_run: bool = False,
    index_out: Path | None = None,
) -> ImportPlan:
    chats = load_recovered_archive(zip_path)
    roster = load_live_roster(persistence_root)
    plan = build_import_plan(chats, roster, persistence_root=persistence_root, dry_run=dry_run)
    matched_n = len(plan.matched)
    unmatched_n = len(plan.unmatched)
    print(f"matched={matched_n} unmatched={unmatched_n} dry_run={str(dry_run).lower()}")
    print(format_plan_table(plan))
    idx = plan_index(plan)
    if index_out:
        index_out.parent.mkdir(parents=True, exist_ok=True)
        index_out.write_text(json.dumps(idx, indent=2), encoding="utf-8")
        print(f"index_out={index_out}")
    if dry_run:
        print("quit_gate=skipped(dry_run)")
        print("backup=skipped(dry_run)")
        return plan
    assert_grokbot_quit()
    print("quit_gate=ok")
    backup = backup_persistence_root(persistence_root)
    print(f"backup={backup}")
    wrote, roster_touch = execute_import_plan(plan)
    counts = verify_import(plan)
    added_total = sum(t.added for t in plan.matched)
    print(f"verification=ok wrote_blobs={wrote} roster_updated={roster_touch} added_total={added_total}")
    for agent_id, n in sorted(counts.items()):
        print(f"verify_agent={agent_id} entries={n}")
    return plan


def main() -> int:
    ap = argparse.ArgumentParser(description="Import recovered transcript zip into live replicas")
    ap.add_argument("--zip", required=True, type=Path)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--persistence-root", type=Path, default=None)
    ap.add_argument("--index-out", type=Path, default=None)
    args = ap.parse_args()
    root = args.persistence_root
    if root is None:
        root = Path.home() / ".config/Grok Bot/sand-client-persistence"
    if not args.zip.is_file():
        print(f"error=zip_missing path={args.zip}", file=sys.stderr)
        return 1
    if not root.is_dir():
        print(f"error=persistence_root_missing path={root}", file=sys.stderr)
        return 1
    try:
        run_import(
            zip_path=args.zip,
            persistence_root=root,
            dry_run=args.dry_run,
            index_out=args.index_out,
        )
    except QuitGateError as e:
        print(f"error=quit_gate {e}", file=sys.stderr)
        return 2
    except PersistenceError as e:
        print(f"error=persistence {e}", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
