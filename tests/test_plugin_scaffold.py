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
        self.assertIn('Qt.resolvedUrl("oneplus-buds-bridge")', service)
        self.assertIn("Component.onCompleted: startHelper()", service)
        self.assertNotIn("__sourceDir", service)
        self.assertIn('helper.write(JSON.stringify({', service)
        self.assertIn("helper.running = false", service)
        self.assertNotIn("IpcHandler", service)

    def test_status_widget_resolves_shared_service_and_uses_native_primitives(self):
        widget = (ROOT / "BarWidget.qml").read_text()
        self.assertIn("import Quickshell.Io", widget)
        self.assertIn("bar.shell.serviceFor(moduleName)", widget)
        self.assertIn('import "BarModel.js" as BarModel', widget)
        self.assertIn("root.bar.barForeground", widget)
        self.assertIn("root.bar.fontFamily", widget)
        self.assertIn("root.bar.showTooltip", widget)
        self.assertIn("PopupCard {", widget)
        self.assertIn("delegate: Button {", widget)
        self.assertIn("budsService.setAnc(mode)", widget)
        self.assertIn("response.result.verified === true", widget)
        self.assertIn('objectName: "reportAction"', widget)
        self.assertIn('objectName: "saveDiagnosticReportAction"', widget)
        self.assertIn("FileDialog.SaveFile", widget)
        self.assertIn("FileDialog.DontUseNativeDialog", widget)
        self.assertIn('defaultSuffix: "txt"', widget)
        self.assertIn("root.openReportFileDialog()", widget)
        self.assertIn("root.openReportIssue()", widget)
        self.assertIn("Number(response.request_id) !== pendingRequestId", widget)
        self.assertEqual(widget.count("IpcHandler {"), 1)
        self.assertIn('target: "oneplus-buds.control"', widget)
        self.assertIn("function status(): string", widget)
        self.assertIn("visible: true", widget)

    @unittest.skipUnless(shutil.which("node"), "node is needed for JavaScript model tests")
    def test_bar_model_is_capability_driven_and_rejects_invalid_battery(self):
        script = r'''
const model = require(process.argv[1]);
const snapshot = {status: {model: "OnePlus Buds Pro 2", battery: {
  left: {percentage: 83, charging: false},
  right: {percentage: 41.6, charging: true},
  case: {percentage: null, charging: true},
  unknown: {percentage: 99, charging: false}
}}};
const shown = model.presentation("connected", snapshot);
if (shown.label !== "L 83%  R 42%⚡") process.exit(1);
if (!shown.tooltip.includes("OnePlus Buds Pro 2") || !shown.tooltip.includes("Right: 42% (charging)")) process.exit(2);
if (shown.tooltip.includes("Case:") || shown.label.includes("99")) process.exit(3);
const disconnected = model.presentation("reconnecting", snapshot);
if (disconnected.connected || disconnected.label !== "" || !disconnected.tooltip.includes("Reconnecting")) process.exit(4);
if (model.validPercentage(-1) || model.validPercentage(101) || model.validPercentage("80")) process.exit(5);
const groups = model.ancGroups({anc_modes: ["off", "on", "smart", "future"]});
if (groups.map(g => g.title).join(",") !== "Noise control,ANC strength,Other modes") process.exit(9);
if (groups[0].options[1].label !== "Noise cancellation") process.exit(10);
if (model.ancGroups({}).length !== 0) process.exit(11);
const controls = model.ancModes({anc_modes: ["smart", "off", "future", "off", "transparency"]});
if (controls.map(x => x.value).join(",") !== "off,transparency,smart,future") process.exit(6);
if (model.currentAncMode({status: {anc: "on", anc_level: "deep"}}) !== "deep") process.exit(7);
if (model.currentAncMode({status: {anc: "transparency", anc_level: null}}) !== "transparency") process.exit(8);
const eq = {eq: {presets: [{id: 0, name: "Balanced"}], custom_entries: [{eq_id: 4}]}};
if (model.eqPresets(eq).length !== 1 || model.customEqEntries(eq)[0].eq_id !== 4) process.exit(12);
if (model.eqPresets({}).length || model.customEqEntries({}).length) process.exit(13);
if (model.compatibility({compatibility:"verified"}) !== "verified") process.exit(14);
if (model.compatibilityLabel({compatibility:"community_tested"}) !== "Community tested") process.exit(15);
if (model.compatibility({compatibility:"something-new"}) !== "experimental") process.exit(16);
if (model.reportActionLabel({compatibility:"verified"}) !== "Report a problem") process.exit(17);
if (model.reportActionLabel({compatibility:"community_tested"}) !== "Report a problem") process.exit(18);
if (model.reportActionLabel({compatibility:"experimental"}) !== "Report compatibility") process.exit(19);
const date = new Date(2026, 8, 16);
if (model.reportFilename(snapshot, date) !== "oneplus-buds-pro-2-report-2026-09-16.txt") process.exit(20);
if (model.reportFilename({status:{model:"OnePlus Nord Buds 3"}}, date) !== "oneplus-nord-buds-3-report-2026-09-16.txt") process.exit(21);
if (model.reportFilename({status:{model:"Alice's OnePlus Buds / AA:BB:CC:DD:EE:FF"}}, date) !== "oneplus-buds-report-2026-09-16.txt") process.exit(22);
if (model.reportFilename({status:{model:null}}, date) !== "oneplus-buds-report-2026-09-16.txt") process.exit(23);
if (model.textReportUrl("file:///tmp/report.json") !== "file:///tmp/report.txt") process.exit(24);
const issue = "https://github.com/GazzasaurusRex/oneplus-buds-omarchy/issues/new?template=compatibility.md&title=%5BCompatibility%5D%20OnePlus%20Buds%20Pro%202";
if (model.compatibilityIssueUrl(snapshot) !== issue) process.exit(25);
if (model.compatibilityIssueUrl({status:{model:null}}) !== model.COMPATIBILITY_ISSUE_URL) process.exit(26);
if (model.compatibilityIssueUrl(snapshot).includes("report=") || model.compatibilityIssueUrl(snapshot).includes("path=")) process.exit(27);
if (model.reportLocationLabel("file:///home/test/Documents/report.txt", "report.txt", "file:///home/test") !== "~/Documents/report.txt") process.exit(28);
'''
        subprocess.run(
            ["node", "-e", script, str(ROOT / "BarModel.js")],
            check=True,
            capture_output=True,
            text=True,
        )

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
