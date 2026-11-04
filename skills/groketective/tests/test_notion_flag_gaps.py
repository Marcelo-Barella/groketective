#!/usr/bin/env python3
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
GAPS = ROOT / "scripts" / "compute-notion-flag-gaps.py"
INVENTORY = ROOT / "skills/groketective/tests/fixtures/feature-flags-inventory-mini.json"


class NotionFlagGapsTest(unittest.TestCase):
    def test_missing_and_revisit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            keys = t / "keys.txt"
            done = t / "done.txt"
            out = t / "out"
            keys.write_text("legacy_flag\n", encoding="utf-8")
            done.write_text("legacy_flag\n", encoding="utf-8")
            subprocess.run(
                [
                    sys.executable,
                    str(GAPS),
                    "--inventory",
                    str(INVENTORY),
                    "--notion-keys",
                    str(keys),
                    "--notion-done-keys",
                    str(done),
                    "--output-dir",
                    str(out),
                ],
                check=True,
            )
            payload = json.loads((out / "notion-flag-gaps.json").read_text(encoding="utf-8"))
            names = {f["name"] for f in payload["gap_flags"]}
            self.assertIn("grok_bot_task_subagent_roster", names)
            self.assertNotIn("legacy_flag", names)


if __name__ == "__main__":
    unittest.main()
