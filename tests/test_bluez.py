import unittest
from unittest.mock import patch

from oneplus_buds.bluez import BATTERY_INTERFACE, DEVICE_INTERFACE, connected_devices, select_device


OBJECTS = {
    "/org/bluez/hci0/dev_AA_BB_CC_DD_EE_01": {
        DEVICE_INTERFACE: {
            "Address": "AA:BB:CC:DD:EE:01",
            "Name": "Laptop",
            "Connected": True,
            "UUIDs": ["0000110b-0000-1000-8000-00805f9b34fb"],
        }
    },
    "/org/bluez/hci0/dev_AA_BB_CC_DD_EE_02": {
        DEVICE_INTERFACE: {
            "Address": "AA:BB:CC:DD:EE:02",
            "Name": "OnePlus Buds Pro 2",
            "Connected": True,
            "UUIDs": ["0000079A-D102-11E1-9B23-00025B00A5A5"],
            "Modalias": "bluetooth:v02B0p0000d001F",
            "ServicesResolved": True,
        },
        BATTERY_INTERFACE: {"Percentage": 80},
    },
    "/org/bluez/hci0/dev_AA_BB_CC_DD_EE_03": {
        DEVICE_INTERFACE: {
            "Address": "AA:BB:CC:DD:EE:03",
            "Alias": "OnePlus Buds Pro",
            "Connected": False,
            "UUIDs": ["00001107-d102-11e1-9b23-00025b00a5a5"],
        }
    },
}


class BluezTests(unittest.TestCase):
    @patch("oneplus_buds.bluez._managed_objects", return_value=OBJECTS)
    def test_connected_devices_uses_object_manager_snapshot(self, managed_objects):
        devices = connected_devices()
        self.assertEqual(len(devices), 2)
        buds = devices[1]
        self.assertEqual(buds.name, "OnePlus Buds Pro 2")
        self.assertEqual(buds.battery, 80)
        self.assertEqual(buds.modalias, "bluetooth:v02B0p0000d001F")
        self.assertTrue(buds.services_resolved)
        self.assertTrue(buds.looks_compatible)
        managed_objects.assert_called_once_with()

    @patch("oneplus_buds.bluez._managed_objects", return_value=OBJECTS)
    def test_explicit_selection_is_case_insensitive(self, _managed_objects):
        self.assertEqual(select_device("aa:bb:cc:dd:ee:02").name, "OnePlus Buds Pro 2")

    @patch("oneplus_buds.bluez._managed_objects")
    def test_ambiguous_automatic_selection_fails(self, managed_objects):
        second = dict(OBJECTS)
        second["/org/bluez/hci0/dev_AA_BB_CC_DD_EE_04"] = {
            DEVICE_INTERFACE: {
                "Address": "AA:BB:CC:DD:EE:04",
                "Name": "OnePlus Buds Pro",
                "Connected": True,
                "UUIDs": ["00001107-d102-11e1-9b23-00025b00a5a5"],
            }
        }
        managed_objects.return_value = second
        with self.assertRaisesRegex(RuntimeError, "--device"):
            select_device()


if __name__ == "__main__":
    unittest.main()
