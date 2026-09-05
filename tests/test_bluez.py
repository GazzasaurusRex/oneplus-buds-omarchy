import unittest
from unittest.mock import patch

from oneplus_buds.bluez import connected_devices, select_device


LISTING = """\
Device AA:BB:CC:DD:EE:01 OnePlus Buds Pro
Device AA:BB:CC:DD:EE:02 OnePlus Buds Pro 2
"""

INFO = {
    "AA:BB:CC:DD:EE:01": """\
Name: OnePlus Buds Pro
Connected: yes
UUID: Vendor specific (00001107-d102-11e1-9b23-00025b00a5a5)
Battery Percentage: 0x5a (90)
""",
    "AA:BB:CC:DD:EE:02": """\
Name: OnePlus Buds Pro 2
Connected: yes
UUID: Vendor specific (0000079a-d102-11e1-9b23-00025b00a5a5)
Battery Percentage: 0x50 (80)
""",
}


def fake_bluetoothctl(*arguments):
    if arguments == ("devices", "Connected"):
        return LISTING
    if arguments[0] == "info":
        return INFO[arguments[1]]
    raise AssertionError(arguments)


class BluezTests(unittest.TestCase):
    @patch("oneplus_buds.bluez._bluetoothctl", side_effect=fake_bluetoothctl)
    def test_connected_devices(self, _mock):
        devices = connected_devices()
        self.assertEqual([(device.name, device.battery) for device in devices], [("OnePlus Buds Pro", 90), ("OnePlus Buds Pro 2", 80)])
        self.assertTrue(all(device.looks_compatible for device in devices))

    @patch("oneplus_buds.bluez._bluetoothctl", side_effect=fake_bluetoothctl)
    def test_explicit_selection_is_case_insensitive(self, _mock):
        self.assertEqual(select_device("aa:bb:cc:dd:ee:02").name, "OnePlus Buds Pro 2")

    @patch("oneplus_buds.bluez._bluetoothctl", side_effect=fake_bluetoothctl)
    def test_ambiguous_automatic_selection_fails(self, _mock):
        with self.assertRaisesRegex(RuntimeError, "multiple compatible devices"):
            select_device()


if __name__ == "__main__":
    unittest.main()
