#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from import_recovered import (  # noqa: E402
    build_import_plan,
    execute_import_plan,
    load_recovered_archive,
    load_live_roster,
    read_replica,
    replica_path,
)
from slice_keys import b32_encode  # noqa: E402

ACCOUNT_PREFIX = "sand.client.slice.account.test-user."
LIVE_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
LEFTOVER_ID = "0a3884bb-cdcd-4b6e-a4a4-af551041b5af"


def write_blob(root: Path, key: str, body: dict) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / f"{b32_encode(key)}.blob").write_text(json.dumps(body), encoding="utf-8")


def make_fixture_zip(path: Path) -> None:
    golden = """# Golden-Map

- **Old leftover id:** `0a3884bb-cdcd-4b6e-a4a4-af551041b5af`

---

**Bot** · 2026-08-30 19:47:08 BRT

First recovered line.

---

**Bot** · 2026-08-30 19:47:34 BRT

Second recovered line.
"""
    mapper = """# Gold-Mapper

- **Old leftover id:** `a8b8210a-1f92-4ddf-a271-9f2e40265173`

---

**Bot** · 2026-08-11 18:50:34 BRT

Should not match Golden Map.
"""
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("Golden-Map.md", golden)
        zf.writestr("Gold-Mapper.md", mapper)
        zf.writestr("INDEX.md", "# index\n")


def seed_persistence(root: Path) -> None:
    roster_key = f"{ACCOUNT_PREFIX}roster.last-roster"
    write_blob(
        root,
        roster_key,
        {
            "schemaVersion": 3,
            "value": {
                "rows": [
                    {
                        "id": LIVE_ID,
                        "name": "Golden Map",
                        "description": "test",
                        "path": f"/home/box/sand-data/agents/{LIVE_ID}/store.db",
                        "lastEntry": {"kind": "text", "text": "live"},
                        "lastMessageId": "live-1",
                        "newestEntryId": "live-1",
                        "lastActivityAt": 1000,
                        "updatedAt": 1000,
                    }
                ]
            },
        },
    )
    replica_key = f"{ACCOUNT_PREFIX}transcript.replicas.{LIVE_ID}"
    write_blob(
        root,
        replica_key,
        {
            "schemaVersion": 1,
            "value": {
                "entries": [
                    {
                        "kind": "send-message",
                        "id": "live-1",
                        "message": {"type": "text", "content": "existing live greeting"},
                        "timestampMs": 1000,
                        "requestId": "11111111-1111-1111-1111-111111111111",
                    }
                ],
                "epochHint": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
                "acceptedSequenceHint": 1,
                "persistedAt": 1000,
            },
        },
    )


class ImportRecoveredTest(unittest.TestCase):
    def test_import_flow(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            zip_path = td_path / "fixture.zip"
            pers = td_path / "pers"
            make_fixture_zip(zip_path)
            seed_persistence(pers)

            chats = load_recovered_archive(zip_path)
            self.assertEqual(len(chats), 2)
            golden = next(c for c in chats if c.source_stem == "Golden-Map")
            self.assertEqual(golden.leftover_uuid, LEFTOVER_ID)
            self.assertEqual(len(golden.lines), 2)

            roster = load_live_roster(pers)
            plan = build_import_plan(chats, roster, persistence_root=pers, dry_run=True)
            self.assertEqual(len(plan.matched), 1)
            self.assertEqual(len(plan.unmatched), 1)
            self.assertEqual(plan.unmatched[0]["zip_stem"], "Gold-Mapper")
            target = plan.matched[0]
            self.assertEqual(target.bot.id, LIVE_ID)
            self.assertEqual(target.added, 2)
            self.assertEqual(target.final_count, 3)

            before = read_replica(pers, ACCOUNT_PREFIX, LIVE_ID)
            dry = build_import_plan(chats, roster, persistence_root=pers, dry_run=True)
            self.assertEqual(dry.matched[0].added, 2)
            after = read_replica(pers, ACCOUNT_PREFIX, LIVE_ID)
            self.assertEqual(len(before["value"]["entries"]), len(after["value"]["entries"]))

            wrote, _ = execute_import_plan(plan)
            self.assertEqual(wrote, 1)
            blob = read_replica(pers, ACCOUNT_PREFIX, LIVE_ID)
            entries = blob["value"]["entries"]
            self.assertEqual(len(entries), 3)
            ids = {e["id"] for e in entries}
            self.assertIn("live-1", ids)
            self.assertTrue(any(e["id"].startswith("imp-") for e in entries))
            self.assertEqual(blob["value"]["epochHint"], "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
            self.assertTrue(blob["value"].get("restoredSeed"))

            plan2 = build_import_plan(chats, roster, persistence_root=pers, dry_run=True)
            self.assertEqual(plan2.matched[0].added, 0)

            idx_path = td_path / "nested" / "plan.json"
            from import_recovered import run_import
            run_import(
                zip_path=zip_path,
                persistence_root=pers,
                dry_run=True,
                index_out=idx_path,
            )
            self.assertTrue(idx_path.is_file())


if __name__ == "__main__":
    unittest.main()
