"""Regression tests for the final whole-branch review findings.

Behavioral fixes (create/delete proof, bass read-back, best-effort restore,
deferred frames, unconfirmed-switch filter, Nord-only case cache) plus gate
pins that survive only while the authorization checks stay in place.
"""
import unittest
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from oneplus_buds.bluez import Device
from oneplus_buds.controller import BudsController
from oneplus_buds.models import EventBatch, StatusResult
from oneplus_buds.profiles import PROFILES
from oneplus_buds.protocol import (
    QUERY_EQ, QUERY_EQ_ALL, QUERY_BASS_ENGINE, RESPONSE_EQ, RESPONSE_EQ_ALL,
    RESPONSE_SET_EQ, RESPONSE_SET_EQ_DETAIL, RESPONSE_SET_BASS_ENGINE,
    RESPONSE_BASS_ENGINE, SET_EQ, SET_EQ_DETAIL, Frame,
)
from oneplus_buds.session import OpoSession
from oneplus_buds.touch import TouchBinding

DEVICE = Device(address="AA:BB:CC:DD:EE:FF", name="OnePlus Nord Buds 3 Pro",
                connected=True, uuids=("0000079a-d102-11e1-9b23-00025b00a5a5",), battery=80)
NORD = StatusResult(DEVICE, "064414", "OnePlus Nord Buds 3 Pro", (), None, None, "on", "deep")

FREQS = (62, 250, 1000, 4000, 8000, 16000)


def entry_payload(selected, eq_id, name, gains=(0, 0, 0, 0, 0, 0)):
    enc = name.encode()
    p = bytearray((selected, 0xFA, 6, eq_id, len(enc)))
    p.extend(enc)
    p.append(len(FREQS))
    for f, g in zip(FREQS, gains, strict=True):
        p.extend(f.to_bytes(2, "little"))
        p.append(g & 0xFF)
    return bytes(p)


def catalogue(*entries):
    p = bytearray((0, len(entries)))
    for e in entries:
        p.extend(e)
    return bytes(p)


E7 = entry_payload(1, 7, "Existing")
E8 = entry_payload(0, 8, "Other")
CAT78 = catalogue(E7, E8)


def session(product="064414"):
    s = OpoSession(DEVICE, PROFILES[product])
    s._connected = s._authenticated = True
    s._transport = MagicMock()
    return s


def controller_with(sess):
    backend = MagicMock()
    backend.start_session.return_value = (sess, NORD, EventBatch((), 0))
    c = BudsController(backend)
    c.start()
    return c


class CreateDeleteProofTests(unittest.TestCase):
    def test_create_with_colliding_name_and_rejected_write_is_not_verified(self):
        s = session()

        def responses(command, *a, **k):
            if command == QUERY_EQ:
                return Frame(RESPONSE_EQ, 1, b"\x00\x07")
            if command == QUERY_EQ_ALL:
                return Frame(RESPONSE_EQ_ALL, 2, CAT78)  # no fresh slot stored
            if command == SET_EQ_DETAIL:
                return Frame(RESPONSE_SET_EQ_DETAIL, 3, b"\x0e")
            raise AssertionError(command)

        s._transport.request.side_effect = responses
        with self.assertRaises(RuntimeError):
            s.create_custom_eq("Existing")  # name equals profile 7

    def test_delete_with_unparsable_catalogue_is_not_verified(self):
        s = session()
        calls = {"n": 0}

        def responses(command, *a, **k):
            if command == QUERY_EQ:
                return Frame(RESPONSE_EQ, 1, b"\x00\x07")
            if command == SET_EQ_DETAIL:
                return Frame(RESPONSE_SET_EQ_DETAIL, 3, b"\x0e")
            if command == QUERY_EQ_ALL:
                calls["n"] += 1
                return Frame(RESPONSE_EQ_ALL, 2, CAT78 if calls["n"] == 1 else b"\x00\x01\xff")
            raise AssertionError(command)

        s._transport.request.side_effect = responses
        with self.assertRaises(RuntimeError):
            s.delete_custom_eq(7)


class RestoreBestEffortTests(unittest.TestCase):
    def test_create_stays_verified_when_restore_targets_unknown_factory_id(self):
        s = session()
        newcat = catalogue(E7, E8, entry_payload(0, 9, "New"))
        s._transport.request.side_effect = [
            Frame(RESPONSE_EQ, 1, b"\x00\x00"),       # before: factory id 0 (not a Nord preset)
            Frame(RESPONSE_EQ_ALL, 2, CAT78),
            Frame(RESPONSE_SET_EQ_DETAIL, 3, b"\x00"),
            Frame(RESPONSE_EQ_ALL, 4, newcat),
            Frame(RESPONSE_EQ, 5, b"\x00\x09"),
            Frame(RESPONSE_EQ, 6, b"\x00\x09"),       # restore: current selection
            Frame(RESPONSE_EQ_ALL, 7, newcat),
            Frame(RESPONSE_SET_EQ, 8, b"\x00"),       # restore selects id 0 directly
        ]
        result, _ = s.create_custom_eq("New")
        self.assertTrue(result.verified)
        self.assertEqual(result.current_id, 9)
        cmds = [c.args[0] for c in s._transport.request.call_args_list]
        self.assertIn(SET_EQ, cmds)


class BassVerificationTests(unittest.TestCase):
    def test_rejected_bass_write_is_not_published_as_device_state(self):
        sess = MagicMock()
        sess.set_bass_level.return_value = (14, True)        # ACK 0x0e
        sess.bass_engine_status.return_value = (-10, 10, -1)  # device still at -1
        c = controller_with(sess)
        self.addCleanup(c.shutdown)
        result = c.set_bass_level(5)
        self.assertFalse(result["verified"])
        self.assertEqual(c.snapshot().bass_level, -1)

    def test_confirmed_bass_write_publishes_read_back_level(self):
        sess = MagicMock()
        sess.set_bass_level.return_value = (0, True)
        sess.bass_engine_status.return_value = (-10, 10, 5)
        c = controller_with(sess)
        self.addCleanup(c.shutdown)
        result = c.set_bass_level(5)
        self.assertTrue(result["verified"])
        self.assertEqual(c.snapshot().bass_level, 5)


class DeferredFrameTests(unittest.TestCase):
    def test_feature_read_does_not_drop_unrelated_firmware_frame(self):
        firmware = Frame(0x8105, 7, b"\x00\x02" + b"1,2,155,2,2,155")

        class T:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                pass

            def request(self, command, payload, response, *, on_frames=None, **k):
                if on_frames:
                    on_frames([firmware])
                if command == QUERY_BASS_ENGINE:
                    return Frame(RESPONSE_BASS_ENGINE, 1, bytes((0, 0xF6, 0x0A, 0xFF)))
                raise AssertionError(command)

            def receive(self, wait):
                return []

            def send_query(self, command):
                return 1

        s = OpoSession(DEVICE, PROFILES["064414"], transport=T())
        s._connected = s._authenticated = True
        s._version_sequence = 7
        s.bass_engine_status()
        batch = s.poll(0)
        self.assertTrue(any(e.kind == "firmware" for e in batch.events))


class UnconfirmedSwitchFilterTests(unittest.TestCase):
    def test_controller_feature_switches_exclude_unconfirmed_names(self):
        sess = MagicMock()
        sess.feature_switches.return_value = {0x04: True, 0x06: False, 0x0B: False, 0x1D: True}
        c = controller_with(sess)
        self.addCleanup(c.shutdown)
        named = c.feature_switches()
        self.assertIn("wear_detection", named)
        self.assertIn("bass_engine", named)
        self.assertNotIn("low_latency", named)
        self.assertNotIn("hearing_enhancement", named)


class CaseCacheScopeTests(unittest.TestCase):
    def test_background_battery_query_is_nord_only(self):
        from test_session import FakeTransport
        for product, expected in (("064414", 1), ("062014", 0)):
            t = FakeTransport({})
            with patch("oneplus_buds.session.monotonic", return_value=0):
                s = OpoSession(DEVICE, PROFILES[product], transport=t)
            with s, patch("oneplus_buds.session.monotonic", return_value=11):
                s.poll(0)
            battery_queries = [q for q in t.queries if q[0] == 0x0106]
            self.assertEqual(len(battery_queries), expected, product)

    def test_case_cache_filename_does_not_contain_address(self):
        from oneplus_buds.case_battery import CaseBatteryCache
        with TemporaryDirectory() as d:
            cache = CaseBatteryCache(Path(d))
            cache.merge(NORD, {"case": {"percentage": 50, "charging": False}})
            files = list(Path(d).glob("*.json"))
            self.assertTrue(files)
            self.assertNotIn(DEVICE.address, files[0].name)
            self.assertNotIn(DEVICE.address.replace(":", "").lower(), files[0].name.lower())


class OperationGateTests(unittest.TestCase):
    def _assert_all_refused(self, s):
        with self.assertRaises(ValueError):
            s.set_touch_binding(TouchBinding(1, 1, 2, 5))
        with self.assertRaises(ValueError):
            s.set_feature_switch(4, True)
        with self.assertRaises(ValueError):
            s.find_earbuds(True)
        with self.assertRaises(ValueError):
            s.set_bass_level(0)
        with self.assertRaises(ValueError):
            s.set_hold_cycle(("anc", "off"))
        s._transport.request.assert_not_called()

    def test_buds4_refuses_every_new_write_before_io(self):
        self._assert_all_refused(session("065414"))

    def test_pro2_refuses_new_writes_without_support_data(self):
        self._assert_all_refused(session("062014"))

    def test_nord_with_stripped_permission_refuses(self):
        s = session()
        s.profile = replace(s.profile, community_write_permissions=frozenset())
        self._assert_all_refused(s)

    def test_eq_command_rejects_foreign_device_token(self):
        sess = MagicMock()
        c = controller_with(sess)
        self.addCleanup(c.shutdown)
        with self.assertRaises(ValueError):
            c.set_custom_eq(7, (0, 0, 0, 0, 0, 0), device_id="0" * 64)
        sess.set_custom_eq.assert_not_called()

    def test_service_qml_restarts_exited_helper(self):
        text = (Path(__file__).resolve().parents[1] / "Service.qml").read_text()
        self.assertIn("scheduleHelperRestart", text)
        self.assertIn("restartTimer", text)


if __name__ == "__main__":
    unittest.main()
