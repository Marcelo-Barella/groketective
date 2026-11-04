#!/usr/bin/env python3
import os
import unittest

from grokbot_dogfood.feed import (
    build_feed_url,
    needs_track_changed,
    prerelease_tag,
)
from grokbot_dogfood._lib import mask_id
from grokbot_dogfood.machine_id import MachineIdError, resolve_machine_id


class GrokbotDogfoodFeedTest(unittest.TestCase):
    def test_prerelease_tag_stable(self) -> None:
        self.assertEqual(prerelease_tag("0.78.5"), "stable")
        self.assertEqual(prerelease_tag("1.0.0"), "stable")

    def test_prerelease_tag_dogfood(self) -> None:
        self.assertEqual(prerelease_tag("0.78.5-dogfood"), "dogfood")
        self.assertEqual(prerelease_tag("0.78.5-dogfood.1"), "dogfood")

    def test_prerelease_tag_nightly(self) -> None:
        self.assertEqual(prerelease_tag("0.78.5-nightly.2"), "nightly")

    def test_prerelease_tag_empty_suffix(self) -> None:
        self.assertEqual(prerelease_tag("0.78.5-"), "stable")

    def test_track_changed_matches_sync_rule(self) -> None:
        self.assertTrue(needs_track_changed("0.78.5"))
        self.assertFalse(needs_track_changed("0.78.5-dogfood"))
        self.assertTrue(needs_track_changed("0.78.5-nightly"))

    def test_build_feed_url(self) -> None:
        url = build_feed_url("0.78.5", "test-machine-id-value")
        self.assertIn("trackChanged=1", url)
        url2 = build_feed_url("0.78.5-dogfood", "abc")
        self.assertNotIn("trackChanged", url2)

    def test_mask_id(self) -> None:
        masked = mask_id("0123456789abcdef")
        self.assertNotIn("0123456789abcdef", masked)
        self.assertIn("…", masked)

    def test_env_machine_id(self) -> None:
        os.environ["GROKBOT_MACHINE_ID"] = "env-test-id-not-real"
        try:
            self.assertEqual(
                resolve_machine_id(allow_keyring=False, allow_bootstrap=False),
                "env-test-id-not-real",
            )
        finally:
            os.environ.pop("GROKBOT_MACHINE_ID", None)

    def test_missing_id_fails_without_env(self) -> None:
        os.environ.pop("GROKBOT_MACHINE_ID", None)
        os.environ["GROKBOT_DISABLE_BOOTSTRAP"] = "1"
        try:
            with self.assertRaises(MachineIdError):
                resolve_machine_id(allow_keyring=False, allow_bootstrap=True)
        finally:
            os.environ.pop("GROKBOT_DISABLE_BOOTSTRAP", None)


if __name__ == "__main__":
    unittest.main()
