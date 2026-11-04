#!/usr/bin/env python3
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DIFF = ROOT / "scripts" / "diff-build-extracts.py"


class DiffBuildExtractsTest(unittest.TestCase):
    def test_detects_modified_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            prev = t / "prev"
            new = t / "new"
            out = t / "out"
            prev.mkdir()
            new.mkdir()
            (prev / "resources").mkdir(parents=True)
            (new / "resources").mkdir(parents=True)
            (prev / "resources" / "app.asar").write_bytes(b"old")
            (new / "resources" / "app.asar").write_bytes(b"new")
            subprocess.run(
                [
                    sys.executable,
                    str(DIFF),
                    "--previous-dir",
                    str(prev),
                    "--new-dir",
                    str(new),
                    "--output-dir",
                    str(out),
                ],
                check=True,
            )
            manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
            self.assertTrue(manifest["app_asar_changed"])
            self.assertEqual(manifest["changed_count"], 1)


if __name__ == "__main__":
    unittest.main()
