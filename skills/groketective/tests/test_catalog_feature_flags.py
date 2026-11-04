#!/usr/bin/env python3
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CATALOG = ROOT / "scripts" / "catalog-feature-flags.py"
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "feature-flags-snippet.txt"


class CatalogFeatureFlagsTest(unittest.TestCase):
    def test_parse_fixture_via_extract_dir(self) -> None:
        tmp = Path("/tmp/groketective-catalog-test")
        asar_dir = tmp / "resources"
        asar_dir.mkdir(parents=True, exist_ok=True)
        asar = asar_dir / "app.asar"
        asar.write_bytes(FIXTURE.read_bytes())
        env = tmp / "version.env"
        env.write_text(
            "VERSION='0.0.1-test'\nCOMMIT_SHA='abc'\nDOWNLOAD_URL='https://example.com'\n",
            encoding="utf-8",
        )
        out = tmp / "out"
        proc = subprocess.run(
            [
                sys.executable,
                str(CATALOG),
                "--extract-dir",
                str(tmp),
                "--version-env",
                str(env),
                "--output-dir",
                str(out),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertIn("flag_count=", proc.stdout)
        inventory = __import__("json").loads(
            (out / "feature-flags-inventory.json").read_text(encoding="utf-8")
        )
        names = {f["name"] for f in inventory["flags"]}
        self.assertIn("legacy_flag", names)
        self.assertIn("grok_bot_task_subagent_roster", names)
        self.assertIn("composer_gc_safety_net_1s", names)


if __name__ == "__main__":
    unittest.main()
