import importlib.util
import json
import os
from pathlib import Path
import tempfile
import tomllib
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("export_plugin", ROOT / "scripts/export_plugin.py")
exporter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exporter)


class PackagingTests(unittest.TestCase):
    def test_export_is_self_contained_and_preserves_launchers(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "plugin"
            exporter.export(destination)
            self.assertTrue(os.access(destination / "oneplus-buds", os.X_OK))
            self.assertTrue(os.access(destination / "oneplus-buds-bridge", os.X_OK))
            self.assertTrue((destination / "src/oneplus_buds/cli.py").is_file())
            self.assertEqual(
                (destination / "preview.png").read_bytes(),
                (ROOT / "preview.png").read_bytes(),
            )
            self.assertFalse((destination / ".git").exists())
            self.assertFalse(list(destination.rglob("__pycache__")))
            original = (destination / "manifest.json").read_bytes()
            with self.assertRaises(ValueError):
                exporter.export(destination)
            self.assertEqual((destination / "manifest.json").read_bytes(), original)

    def test_export_rejects_symlink_before_creating_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source"
            source.mkdir()
            (source / "README.md").symlink_to(ROOT / "README.md")
            destination = Path(directory) / "plugin"
            with patch.object(exporter, "ROOT", source), patch.object(exporter, "FILES", ("README.md",)), patch.object(exporter, "DIRECTORIES", ()):
                with self.assertRaises(ValueError):
                    exporter.export(destination)
            self.assertFalse(destination.exists())

    def test_metadata_versions_and_licenses_agree(self):
        from oneplus_buds import __version__
        manifest = json.loads((ROOT / "manifest.json").read_text())
        project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
        self.assertEqual(manifest["version"], __version__)
        self.assertEqual(project["version"], __version__)
        self.assertEqual(manifest["license"], project["license"])
        self.assertTrue((ROOT / "LICENSE").is_file())
