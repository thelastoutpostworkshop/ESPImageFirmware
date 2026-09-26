import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("publish_release", SCRIPTS / "publish_release.py")
publisher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publisher)


class PublishTests(unittest.TestCase):
    def test_removed_prerelease_option_rejected_before_network_access(self):
        result = subprocess.run([sys.executable, str(SCRIPTS / "publish_release.py"),
            "--version", "1.2.3", "--prerelease"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("unrecognized arguments: --prerelease", result.stderr)

    def test_suffix_rejected_before_credentials_or_upload(self):
        with patch.object(publisher, "credentials") as credentials:
            for version in ("1.2.3-beta", "1.2.3+build"):
                with self.assertRaisesRegex(ValueError, "Invalid version"):
                    publisher.publish(version, Path("unused"))
            credentials.assert_not_called()

    def test_draft_and_published_releases_are_always_stable(self):
        for publish_now in (False, True):
            with self.subTest(publish_now=publish_now), tempfile.TemporaryDirectory() as directory:
                Path(directory, "release-notes.md").write_text("Changes", encoding="utf-8")
                with patch.object(publisher, "prepared_assets", return_value={}), \
                     patch.object(publisher, "credentials", return_value="test"), \
                     patch.object(publisher.subprocess, "check_output", return_value="commit"), \
                     patch.object(publisher, "GitHub") as github:
                    github.return_value.request.side_effect = [[], {"id": 1, "assets": []}, {"html_url": "fixture"}]
                    publisher.publish("1.2.3", directory, publish_now=publish_now)
                    calls = github.return_value.request.call_args_list
                    created = calls[1].args[2]
                    updated = calls[2].args[2]
                    self.assertTrue(created["draft"])
                    self.assertFalse(created["prerelease"])
                    self.assertFalse(updated["prerelease"])
                    self.assertEqual(updated["draft"], not publish_now)
                    self.assertEqual(updated["make_latest"], "true")
