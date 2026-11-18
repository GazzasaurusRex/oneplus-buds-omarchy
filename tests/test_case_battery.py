"""Case readings survive unavailable samples without crossing device identities."""
from dataclasses import replace
import unittest
from unittest.mock import patch
from pathlib import Path
from tempfile import TemporaryDirectory

from oneplus_buds.bridge import BudsFrontendBridge
from oneplus_buds.controller import BudsController
from oneplus_buds.models import EventBatch, SafeEvent
from test_controller import STATUS
from test_device_switching import SwitchingBackend


NORD = replace(STATUS, product_id="064414", model="OnePlus Nord Buds 3 Pro",
               battery={"left": {"percentage": 100, "charging": False},
                        "case": {"percentage": 50, "charging": False}})


class CaseBatteryTests(unittest.TestCase):
    def setUp(self):
        # These tests exercise incoming samples, not the unrelated feature timer.
        clock = patch("oneplus_buds.controller.monotonic", return_value=0)
        clock.start()
        self.addCleanup(clock.stop)

    def test_missing_zero_and_invalid_samples_keep_last_case_reading(self):
        backend = SwitchingBackend(NORD, STATUS)
        controller = BudsController(backend)
        self.addCleanup(controller.shutdown)
        self.assertEqual(controller.start().status.battery["case"]["percentage"], 50)
        for sample in ({}, {"percentage": 0}, {"percentage": 127},
                       {"percentage": True}, {"percentage": "80"}):
            with self.subTest(sample=sample):
                backend.sessions[-1].polls = [EventBatch((SafeEvent("battery", {
                    "left": {"percentage": 80}, "case": sample}),), 0)]
                battery = controller.poll(0).status.battery
                self.assertEqual(battery["left"]["percentage"], 80)
                self.assertEqual(battery["case"], {
                    "percentage": 50, "charging": False, "last_known": True})

    def test_reconnect_retains_case_but_other_device_does_not_inherit_it(self):
        backend = SwitchingBackend(NORD, STATUS)
        controller = BudsController(backend)
        self.addCleanup(controller.shutdown)
        controller.start()
        backend.current = replace(NORD, battery={"right": {"percentage": 70}})
        cached = controller.refresh().status.battery["case"]
        self.assertEqual(cached["percentage"], 50)
        self.assertTrue(cached["last_known"])
        backend.current = replace(backend.current, device=replace(
            NORD.device, address="11:22:33:44:55:66"))
        self.assertNotIn("case", controller.refresh().status.battery)

    def test_fresh_reading_replaces_cache_and_restores_live_charging_state(self):
        backend = SwitchingBackend(NORD, STATUS)
        controller = BudsController(backend)
        self.addCleanup(controller.shutdown)
        controller.start()
        backend.sessions[-1].polls = [EventBatch((SafeEvent("battery", {
            "case": {"percentage": 90, "charging": True}}),), 0)]
        self.assertEqual(controller.poll(0).status.battery["case"], {
            "percentage": 90, "charging": True})
        backend.current = replace(NORD, battery={})
        self.assertEqual(controller.refresh().status.battery["case"], {
            "percentage": 90, "charging": False, "last_known": True})

    def test_unknown_case_does_not_appear_as_zero(self):
        backend = SwitchingBackend(replace(NORD, battery={"case": {
            "percentage": 0, "charging": False}}), STATUS)
        controller = BudsController(backend)
        self.addCleanup(controller.shutdown)
        self.assertNotIn("case", controller.start().status.battery)

    def test_bridge_remembers_case_after_process_restart(self):
        with TemporaryDirectory() as directory, patch.dict("os.environ", {
                "XDG_CACHE_HOME": directory}):
            first = BudsFrontendBridge(lambda event: None).controller
            first.backend = SwitchingBackend(NORD, STATUS)
            first.start()
            first.shutdown()
            second = BudsFrontendBridge(lambda event: None).controller
            second.backend = SwitchingBackend(replace(NORD, battery={}), STATUS)
            try:
                battery = second.start().status.battery
                self.assertEqual(battery.get("case"), {
                    "percentage": 50, "charging": False, "last_known": True})
                files = list(Path(directory).rglob("*.json"))
                self.assertTrue(files)
                self.assertNotIn(NORD.device.address, files[0].read_text())
            finally:
                second.shutdown()

    def test_bad_cache_or_unwritable_directory_does_not_break_control(self):
        for broken_directory in (False, True):
            with self.subTest(unwritable=broken_directory), TemporaryDirectory() as directory:
                cache_root = Path(directory) / "cache"
                if broken_directory:
                    cache_root.write_text("a file cannot contain a cache directory")
                with patch.dict("os.environ", {"XDG_CACHE_HOME": str(cache_root)}):
                    first = BudsFrontendBridge(lambda event: None).controller
                    first.backend = SwitchingBackend(NORD, STATUS)
                    self.assertEqual(first.start().status.battery["case"]["percentage"], 50)
                    first.shutdown()
                    for file in cache_root.rglob("*.json") if cache_root.is_dir() else []:
                        file.write_text("{broken json")
                    second = BudsFrontendBridge(lambda event: None).controller
                    second.backend = SwitchingBackend(replace(NORD, battery={}), STATUS)
                    try:
                        self.assertNotIn("case", second.start().status.battery)
                    finally:
                        second.shutdown()
