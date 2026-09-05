import unittest
from unittest.mock import patch

from oneplus_buds.backend import diagnostics_report, query_capabilities, query_feature_switches, query_status, set_anc
from oneplus_buds.bluez import Device
from oneplus_buds.profiles import PROFILES
from oneplus_buds.protocol import QUERY_ANC, QUERY_BATTERY, QUERY_BROADCAST_CODES, QUERY_CAPABILITIES, QUERY_PRODUCT_ID, QUERY_REMOTE_VERSION, QUERY_STATUS, SET_ANC, SUBSCRIBE_BROADCAST, Frame


DEVICE = Device(
    address="AA:BB:CC:DD:EE:FF",
    name="OnePlus Buds Pro 2",
    connected=True,
    uuids=("0000079a-d102-11e1-9b23-00025b00a5a5",),
    battery=80,
    modalias="bluetooth:v02B0p0000d001F",
    services_resolved=True,
)
STATUS = {
    "model": "OnePlus Buds Pro 2",
    "product_id": "062014",
    "remote_version": [{"component": 1, "kind": 2, "value": "123"}],
    "firmware_version": "123.123",
    "battery": {"left": {"percentage": 80, "charging": False}},
    "anc": "on",
    "anc_level": "smart",
}


class BackendTests(unittest.TestCase):
    def test_firmware_capability_is_verified_on_both_reference_models(self):
        self.assertIn("firmware", PROFILES["060C14"].capabilities)
        self.assertIn("firmware", PROFILES["062014"].capabilities)

    @patch("oneplus_buds.backend.query_feature_switches", return_value={"wear_detection": True})
    @patch("oneplus_buds.backend.query_status", return_value=STATUS)
    def test_capabilities_combine_profile_and_device_switches(self, _status, _switches):
        result = query_capabilities()
        self.assertEqual(result["compatibility"], "verified")
        self.assertIn("smart_anc", result["capabilities"])
        self.assertNotIn("adaptive_anc", result["capabilities"])
        self.assertIn("wear_detection", result["capabilities"])
        self.assertEqual(result["feature_switches"], {"wear_detection": True})
        self.assertIn("smart", result["anc_modes"])

    @patch("oneplus_buds.backend.select_device", return_value=DEVICE)
    def test_feature_switch_probe_subscribes_only_to_advertised_codes(self, _device):
        transport = FakeTransport(
            {
                QUERY_CAPABILITIES: [],
                QUERY_BROADCAST_CODES: [Frame(0x8200, 1, b"\x00\x02\x04\x06")],
                SUBSCRIBE_BROADCAST: [Frame(0x8205, 2, b"\x00")],
                QUERY_STATUS: [Frame(0x810D, 0, b"\x00\x02\x04\x01\x06\x00")],
            }
        )
        with patch("oneplus_buds.backend.RfcommTransport", return_value=transport):
            result = query_feature_switches()
        self.assertEqual(result, {"wear_detection": True, "low_latency": False})
        self.assertIn((SUBSCRIBE_BROADCAST, b"\x02\x04\x06"), transport.queries)

    @patch("oneplus_buds.backend.query_status", return_value=STATUS)
    @patch("oneplus_buds.backend.select_device", return_value=DEVICE)
    def test_diagnostics_omits_address(self, _device, _status):
        report = diagnostics_report()
        rendered = repr(report)
        self.assertNotIn(DEVICE.address, rendered)
        self.assertEqual(report["device"]["product_id"], "062014")
        self.assertEqual(report["device"]["firmware_version"], "123.123")
        self.assertEqual(report["device"]["discovery"], "BlueZ D-Bus ObjectManager")
        self.assertTrue(report["device"]["services_resolved"])
        self.assertEqual(report["state"]["anc_level"], "smart")
        self.assertIn("address", report["privacy"].lower())

    @patch("oneplus_buds.backend.select_device", return_value=DEVICE)
    def test_query_status_orchestrates_generic_transport(self, _device):
        transport = FakeTransport(
            {
                QUERY_CAPABILITIES: [],
                QUERY_PRODUCT_ID: [Frame(0x8103, 1, b"\x00\x14\x20\x06")],
                QUERY_REMOTE_VERSION: [
                    Frame(0x8105, 2, b"\x00\x02" + b"1,2,123,2,2,123")
                ],
                QUERY_BATTERY: [Frame(0x8106, 2, b"\x02\x01\x50\x02\x4f")],
                QUERY_ANC: [Frame(0x810C, 3, bytes.fromhex("00 01 01 80"))],
            }
        )
        with patch("oneplus_buds.backend.RfcommTransport", return_value=transport):
            result = query_status()
        self.assertEqual(result["product_id"], "062014")
        self.assertEqual(result["remote_version"][0]["value"], "123")
        self.assertEqual(result["firmware_version"], "123.123")
        self.assertEqual(result["battery"]["left"]["percentage"], 80)
        self.assertEqual((result["anc"], result["anc_level"]), ("on", "smart"))

    @patch("oneplus_buds.backend.select_device", return_value=DEVICE)
    def test_nonzero_set_status_still_requires_matching_verification(self, _device):
        control = FakeTransport(
            {
                QUERY_CAPABILITIES: [],
                QUERY_PRODUCT_ID: [Frame(0x8103, 1, b"\x00\x14\x20\x06")],
                SET_ANC: [Frame(0x8404, 2, b"\x0e")],
            }
        )
        verifier = FakeTransport({QUERY_ANC: [Frame(0x810C, 3, b"\x00\x01\x01\x01")]})
        with patch("oneplus_buds.backend.RfcommTransport", side_effect=(control, verifier)):
            result = set_anc("off")
        self.assertEqual(result["anc"], "off")
        self.assertEqual(result["set_status"], 14)


class FakeTransport:
    def __init__(self, responses):
        self.responses = responses
        self.queries = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def query(self, command, *_args, **_kwargs):
        payload = _args[0] if _args else b""
        self.queries.append((command, payload))
        return self.responses.get(command, [])

    def exchange_raw(self, *_args, **_kwargs):
        return []


if __name__ == "__main__":
    unittest.main()
