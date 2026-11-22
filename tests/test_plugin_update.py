"""A plugin update notice is only valid for a clean fast-forward install."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "check_plugin_update", ROOT / "scripts/check_plugin_update.py"
)
assert SPEC and SPEC.loader
UPDATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(UPDATE)


def git(path: Path, *args: str) -> str:
    return subprocess.run(
        ("git", "-C", str(path), *args), check=True,
        capture_output=True, text=True,
    ).stdout.strip()


class PluginUpdateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.home = root / "home"
        self.origin = root / "origin.git"
        self.publisher = root / "publisher"
        self.install = (
            self.home / ".config" / "omarchy" / "plugins" / "oneplus-buds.control"
        )

        subprocess.run(("git", "init", "--bare", str(self.origin)), check=True,
                       capture_output=True)
        subprocess.run(("git", "init", "-b", "main", str(self.publisher)), check=True,
                       capture_output=True)
        git(self.publisher, "config", "user.name", "Test")
        git(self.publisher, "config", "user.email", "test@example.invalid")
        (self.publisher / "manifest.json").write_text("{}\n")
        git(self.publisher, "add", "manifest.json")
        git(self.publisher, "commit", "-m", "initial")
        git(self.publisher, "remote", "add", "origin", str(self.origin))
        git(self.publisher, "push", "-u", "origin", "main")
        git(self.origin, "symbolic-ref", "HEAD", "refs/heads/main")
        self.install.parent.mkdir(parents=True)
        subprocess.run(("git", "clone", "--quiet", str(self.origin), str(self.install)),
                       check=True)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def publish(self, message: str) -> None:
        path = self.publisher / "manifest.json"
        path.write_text(path.read_text() + message + "\n")
        git(self.publisher, "add", "manifest.json")
        git(self.publisher, "commit", "-m", message)
        git(self.publisher, "push", "origin", "main")

    def test_notice_stays_hidden_for_current_install(self) -> None:
        result = UPDATE.check_checkout(self.install, home=self.home)
        self.assertTrue(result["eligible"])
        self.assertFalse(result["available"])

    def test_local_origin_shows_notice_without_comparison_when_fast_forwardable(self) -> None:
        self.publish("upstream change")
        result = UPDATE.check_checkout(self.install, home=self.home)
        self.assertTrue(result["available"])
        self.assertEqual(result["commits_behind"], 1)
        self.assertEqual(result["view_url"], "")
        self.assertEqual(result["manual_command"],
                         "omarchy plugin update oneplus-buds.control")

        git(self.install, "config", "user.name", "Test")
        git(self.install, "config", "user.email", "test@example.invalid")
        (self.install / "local.txt").write_text("local\n")
        git(self.install, "add", "local.txt")
        git(self.install, "commit", "-m", "local divergence")
        self.assertFalse(UPDATE.check_checkout(self.install, home=self.home)["available"])

    def test_github_fork_comparison_uses_configured_origin_and_commit_hashes(self) -> None:
        installed = git(self.install, "rev-parse", "HEAD")
        self.publish("fork change")
        fetched = git(self.publisher, "rev-parse", "HEAD")
        github_origin = "https://github.com/fork-owner/custom-buds.git"
        git(self.install, "remote", "set-url", "origin", github_origin)
        git(self.install, "config", f"url.{self.origin.as_uri()}.insteadOf", github_origin)

        result = UPDATE.check_checkout(self.install, home=self.home)

        self.assertTrue(result["available"])
        self.assertEqual(
            result["view_url"],
            f"https://github.com/fork-owner/custom-buds/compare/{installed}...{fetched}",
        )

    def test_github_https_and_ssh_origin_formats(self) -> None:
        expected = "https://github.com/fork-owner/custom-buds"
        for origin in (
            "https://github.com/fork-owner/custom-buds",
            "https://github.com/fork-owner/custom-buds.git",
            "https://github.com/fork-owner/custom-buds.git/",
            "git@github.com:fork-owner/custom-buds.git",
            "ssh://git@github.com/fork-owner/custom-buds.git",
            "ssh://git@github.com/fork-owner/custom-buds.git/",
        ):
            with self.subTest(origin=origin):
                self.assertEqual(UPDATE._github_repository(origin), expected)

        for origin in (str(self.origin), "https://gitlab.example/fork/custom-buds.git"):
            with self.subTest(origin=origin):
                self.assertIsNone(UPDATE._github_repository(origin))

    def test_temporary_export_and_development_clone_are_skipped(self) -> None:
        export = Path(self.temporary.name) / "temporary-export"
        export.mkdir()
        development = Path(self.temporary.name) / "oneplus-buds"
        subprocess.run(("git", "clone", "--quiet", str(self.origin), str(development)),
                       check=True)
        # Eligibility is decided before any git command, so neither path can
        # fetch merely because the shell happened to load it.
        with patch.object(UPDATE, "_git", side_effect=AssertionError("must not run")):
            self.assertEqual(UPDATE.check_checkout(export, home=self.home), UPDATE.hidden())
            self.assertEqual(UPDATE.check_checkout(development, home=self.home), UPDATE.hidden())


if __name__ == "__main__":
    unittest.main()
