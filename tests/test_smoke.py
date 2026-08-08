import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class TestManifest(unittest.TestCase):
    def test_plugin_manifest_has_name_and_version(self):
        manifest = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["name"], "twinkle-repo-builder")
        self.assertRegex(manifest["version"], r"^\d+\.\d+\.\d+$")
