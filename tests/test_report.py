import json
import socket
import tempfile
import unittest
from pathlib import Path

from oneplus_buds.bluez import Device
from oneplus_buds.models import ControllerSnapshot, StatusResult
from oneplus_buds.report import build_snapshot_report, write_report


class DiagnosticReportTests(unittest.TestCase):
    def setUp(self):
        self.device = Device(
            address="AA:BB:CC:DD:EE:FF",
            name=f"{Path.home().name}'s secret earbuds",
            connected=True,
            uuids=("0000079a-d102-11e1-9b23-00025b00a5a5",),
            battery=72,
            modalias="bluetooth:v02B0p0000d001F",
            services_resolved=True,
        )
        self.status = StatusResult(
            device=self.device,
            product_id="062014",
            model="OnePlus Buds Pro 2",
            remote_version=(),
            firmware_version="196.196.101",
            battery={"left": {"percentage": 72, "charging": False}},
            anc="on",
            anc_level="smart",
        )
        self.snapshot = ControllerSnapshot(
            status=self.status,
            feature_switches={"multipoint": True},
            session_connected=True,
            advertised_event_codes=(1, 2, 4),
            notification_event_codes=(4,),
            ignored_frames=2,
            reconnect_count=1,
            generation=7,
        )

    def test_sensitive_values_are_omitted_or_redacted(self):
        home_path = str(Path.home() / "private" / "capture.txt")
        username = Path.home().name
        hostname = socket.gethostname()
        report = build_snapshot_report(
            self.snapshot,
            recent_errors=(
                f"device {self.device.address} failed at {home_path}",
                f"user={username} host={hostname} github_token=super-secret",
                "request used ghp_abcdefghijklmnopqrstuvwxyz123456 and Bearer abc.def.ghi",
            ),
        )
        rendered = json.dumps(report)
        for secret in (
            self.device.address,
            self.device.name,
            str(Path.home()),
            username,
            hostname,
            "super-secret",
            "ghp_abcdefghijklmnopqrstuvwxyz123456",
            "abc.def.ghi",
        ):
            self.assertNotIn(secret, rendered)
        self.assertIn("[device]", rendered)
        self.assertIn("[home]", rendered)
        self.assertEqual(report["device"]["compatibility"], "verified")
        self.assertTrue(report["feature_support"]["battery"])
        self.assertTrue(report["feature_support"]["anc"])
        self.assertTrue(report["connection"]["authenticated"])

    def test_report_file_is_private_and_contains_no_environment(self):
        report = build_snapshot_report(self.snapshot)
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "report.json"
            filename = write_report(report, str(destination))
            stored = json.loads(destination.read_text())
            mode = destination.stat().st_mode & 0o777
        self.assertEqual(filename, "report.json")
        self.assertEqual(mode, 0o600)
        self.assertNotIn("environment", stored)
        self.assertNotIn("service_uuids", stored["device"])

    def test_non_local_report_destination_is_rejected(self):
        with self.assertRaises(ValueError):
            write_report(build_snapshot_report(self.snapshot), "https://example.com/report.json")


if __name__ == "__main__":
    unittest.main()
