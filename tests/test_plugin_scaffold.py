import json
import os
import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PluginScaffoldTests(unittest.TestCase):
    def test_manifest_declares_combined_service_widget(self):
        manifest = json.loads((ROOT / "manifest.json").read_text())
        self.assertEqual(manifest["schemaVersion"], 1)
        self.assertEqual(manifest["id"], "oneplus-buds.control")
        self.assertEqual(set(manifest["kinds"]), {"service", "bar-widget"})
        self.assertEqual(manifest["entryPoints"]["service"], "Service.qml")
        self.assertEqual(manifest["entryPoints"]["barWidget"], "BarWidget.qml")
        self.assertEqual(manifest["barWidget"]["defaultSection"], "right")

    def test_checkout_launcher_is_executable_and_resolves_local_source(self):
        launcher = ROOT / "oneplus-buds-bridge"
        self.assertTrue(os.access(launcher, os.X_OK))
        contents = launcher.read_text()
        self.assertIn('parent / "src"', contents)
        self.assertIn("oneplus_buds.bridge_host import main", contents)

    def test_service_owns_one_bidirectional_helper(self):
        service = (ROOT / "Service.qml").read_text()
        self.assertEqual(service.count("Process {"), 1)
        self.assertIn("stdinEnabled: true", service)
        self.assertIn('sourceDir + "/oneplus-buds-bridge"', service)
        self.assertIn('helper.write(JSON.stringify({', service)
        self.assertIn("helper.running = false", service)

    def test_placeholder_widget_resolves_shared_service_and_stays_hidden(self):
        widget = (ROOT / "BarWidget.qml").read_text()
        self.assertIn("bar.shell.serviceFor(moduleName)", widget)
        self.assertIn("visible: false", widget)
        self.assertIn("implicitWidth: 0", widget)

    @unittest.skipUnless(shutil.which("node"), "node is needed for JavaScript model tests")
    def test_bridge_model_parses_and_reduces_messages(self):
        script = r'''
const model = require(process.argv[1]);
let state = model.initialState();
const connection = model.parseLine('{"schema_version":1,"type":"connection","connection":"connected","error":null}');
if (!connection.ok) process.exit(1);
state = model.applyMessage(state, connection.message);
const snapshot = model.parseLine('{"schema_version":1,"type":"snapshot","snapshot":{"generation":4}}');
state = model.applyMessage(state, snapshot.message);
if (state.connection !== "connected" || state.snapshot.generation !== 4) process.exit(2);
if (model.parseLine('{').ok) process.exit(3);
if (model.parseLine('{"schema_version":2}').ok) process.exit(4);
'''
        subprocess.run(
            ["node", "-e", script, str(ROOT / "BridgeModel.js")],
            check=True,
            capture_output=True,
            text=True,
        )


if __name__ == "__main__":
    unittest.main()
