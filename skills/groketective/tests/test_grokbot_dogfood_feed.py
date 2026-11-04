#!/usr/bin/env python3
import os
import unittest

from grokbot_dogfood._lib import build_feed_url, mask_id, needs_track_changed
from grokbot_dogfood.machine_id import MachineIdError, resolve_machine_id


class GrokbotDogfoodFeedTest(unittest.TestCase):
    def test_track_changed_for_stable_version(self) -> None:
        self.assertTrue(needs_track_changed("0.78.5"))
        url = build_feed_url("0.78.5", "test-machine-id-value")
        self.assertIn("trackChanged=1", url)
        self.assertIn("sand-dogfood", url)
        self.assertIn("linux-x64", url)

    def test_no_track_changed_when_dogfood_tag(self) -> None:
        self.assertFalse(needs_track_changed("0.78.5-dogfood"))
        url = build_feed_url("0.78.5-dogfood", "abc")
        self.assertNotIn("trackChanged", url)

    def test_mask_id(self) -> None:
        masked = mask_id("0123456789abcdef")
        self.assertNotIn("0123456789abcdef", masked)
        self.assertIn("…", masked)

    def test_env_machine_id(self) -> None:
        os.environ["GROKBOT_MACHINE_ID"] = "env-test-id-not-real"
        try:
            self.assertEqual(resolve_machine_id(allow_keyring=False), "env-test-id-not-real")
        finally:
            os.environ.pop("GROKBOT_MACHINE_ID", None)

    def test_missing_id_fails_without_env(self) -> None:
        os.environ.pop("GROKBOT_MACHINE_ID", None)
        with self.assertRaises(MachineIdError):
            resolve_machine_id(allow_keyring=False)


if __name__ == "__main__":
    unittest.main()
