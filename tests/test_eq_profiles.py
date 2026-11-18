import unittest

from unittest.mock import MagicMock

from oneplus_buds.bluez import Device
from oneplus_buds.profiles import PROFILES
from oneplus_buds.protocol import (
    QUERY_EQ,
    QUERY_EQ_ALL,
    RESPONSE_EQ,
    RESPONSE_EQ_ALL,
    RESPONSE_SET_EQ_DETAIL,
    SET_EQ_DETAIL,
    Frame,
)
from oneplus_buds.session import OpoSession, validate_eq_profile_name


DEVICE = Device(
    address="AA:BB:CC:DD:EE:FF",
    name="OnePlus Nord Buds 3 Pro",
    connected=True,
    uuids=("0000079a-d102-11e1-9b23-00025b00a5a5",),
    battery=80,
    modalias=None,
    services_resolved=True,
)

FREQUENCIES = (62, 250, 1000, 4000, 8000, 16000)
GAINS = (4, 6, 1, 0, 4, 6)


def entry_payload(selected, eq_id, name, gains=GAINS):
    encoded = name.encode("utf-8")
    payload = bytearray((selected, 0xFA, 6, eq_id, len(encoded)))
    payload.extend(encoded)
    payload.append(len(FREQUENCIES))
    for frequency, gain in zip(FREQUENCIES, gains, strict=True):
        payload.extend(frequency.to_bytes(2, "little"))
        payload.append(gain & 0xFF)
    return bytes(payload)


def catalogue(*entries):
    payload = bytearray((0, len(entries)))
    for entry in entries:
        payload.extend(entry)
    return bytes(payload)


ENTRY_7 = entry_payload(1, 7, "Test eq")
ENTRY_8 = entry_payload(0, 8, "Benutzerdefiniert1")
ENTRY_9 = entry_payload(0, 9, "Plugin Test", (0, 0, 0, 0, 0, 0))
CATALOGUE_78 = catalogue(ENTRY_7, ENTRY_8)
CATALOGUE_789 = catalogue(ENTRY_7, ENTRY_8, ENTRY_9)


class EqProfileNameTests(unittest.TestCase):
    def test_names_are_trimmed_and_bounded(self):
        self.assertEqual(validate_eq_profile_name("  Rock  "), "Rock")
        for invalid in ("", "   ", "with\nbreak", "x" * 256):
            with self.assertRaises(ValueError):
                validate_eq_profile_name(invalid)

    def test_multibyte_names_are_limited_by_the_wire_length(self):
        self.assertEqual(validate_eq_profile_name("Röck"), "Röck")
        with self.assertRaises(ValueError):
            validate_eq_profile_name("ä" * 128)


class EqProfileSessionTests(unittest.TestCase):
    def session(self, product="064414"):
        session = OpoSession(DEVICE, PROFILES[product])
        session._connected = session._authenticated = True
        session._transport = MagicMock()
        return session

    def detail_payloads(self, session):
        return [call.args[1] for call in session._transport.request.call_args_list
                if call.args and call.args[0] == SET_EQ_DETAIL]

    def test_create_uses_the_next_free_slot_and_reads_the_stored_id_back(self):
        session = self.session()
        session._transport.request.side_effect = [
            Frame(RESPONSE_EQ, 1, b"\x00\x07"),
            Frame(RESPONSE_EQ_ALL, 2, CATALOGUE_78),
            Frame(RESPONSE_SET_EQ_DETAIL, 3, b"\x00"),
            Frame(RESPONSE_EQ_ALL, 4, CATALOGUE_789),
            Frame(RESPONSE_EQ, 5, b"\x00\x07"),
            Frame(RESPONSE_EQ, 6, b"\x00\x07"),
            Frame(RESPONSE_EQ_ALL, 7, CATALOGUE_789),
        ]
        result, _batch = session.create_custom_eq("Plugin Test")
        self.assertTrue(result.verified)
        self.assertEqual(result.current_id, 9)
        self.assertEqual(result.current_name, "Plugin Test")
        self.assertEqual(result.previous_id, 7)
        payloads = self.detail_payloads(session)
        self.assertEqual(len(payloads), 1)
        payload = payloads[0]
        self.assertEqual(payload[0], 1)  # create
        self.assertEqual(payload[3], 9)  # next free slot
        self.assertEqual(payload[4:5], b"\x0b")
        self.assertIn(b"Plugin Test", payload)

    def test_create_is_refused_without_a_device_declared_layout(self):
        session = self.session()
        session._transport.request.side_effect = [
            Frame(RESPONSE_EQ, 1, b"\x00\x03"),
            Frame(RESPONSE_EQ_ALL, 2, catalogue()),
        ]
        with self.assertRaises(RuntimeError):
            session.create_custom_eq("Plugin Test")
        self.assertEqual(self.detail_payloads(session), [])

    def test_create_uses_the_first_free_slot_of_the_measured_range(self):
        session = self.session()
        session._transport.request.side_effect = [
            Frame(RESPONSE_EQ, 1, b"\x00\x07"),
            Frame(RESPONSE_EQ_ALL, 2, CATALOGUE_78),
            Frame(RESPONSE_SET_EQ_DETAIL, 3, b"\x00"),
            Frame(RESPONSE_EQ_ALL, 4, CATALOGUE_789),
            Frame(RESPONSE_EQ, 5, b"\x00\x07"),
            Frame(RESPONSE_EQ, 6, b"\x00\x07"),
            Frame(RESPONSE_EQ_ALL, 7, CATALOGUE_789),
        ]
        session.create_custom_eq("Plugin Test")
        payloads = self.detail_payloads(session)
        self.assertEqual(len(payloads), 1)
        self.assertEqual(payloads[0][3], 9)

    def test_create_reuses_a_freed_low_slot(self):
        session = self.session()
        session._transport.request.side_effect = [
            Frame(RESPONSE_EQ, 1, b"\x00\x08"),
            Frame(RESPONSE_EQ_ALL, 2, catalogue(ENTRY_8)),
            Frame(RESPONSE_SET_EQ_DETAIL, 3, b"\x00"),
            Frame(RESPONSE_EQ_ALL, 4, catalogue(ENTRY_7, ENTRY_8)),
            Frame(RESPONSE_EQ, 5, b"\x00\x08"),
            Frame(RESPONSE_EQ, 6, b"\x00\x08"),
            Frame(RESPONSE_EQ_ALL, 7, catalogue(ENTRY_7, ENTRY_8)),
        ]
        session.create_custom_eq("Plugin Test")
        payloads = self.detail_payloads(session)
        self.assertEqual(len(payloads), 1)
        self.assertEqual(payloads[0][3], 7)

    def test_create_is_refused_when_every_slot_is_taken(self):
        session = self.session()
        session._transport.request.side_effect = [
            Frame(RESPONSE_EQ, 1, b"\x00\x08"),
            Frame(RESPONSE_EQ_ALL, 2, CATALOGUE_789),
        ]
        with self.assertRaises(RuntimeError) as caught:
            session.create_custom_eq("Plugin Test")
        self.assertIn("3 custom profiles", str(caught.exception))
        self.assertEqual(self.detail_payloads(session), [])

    def test_create_reports_an_unconfirmed_profile(self):
        session = self.session()

        def responses(command, *_args, **_kwargs):
            if command == QUERY_EQ:
                return Frame(RESPONSE_EQ, 1, b"\x00\x07")
            if command == QUERY_EQ_ALL:
                return Frame(RESPONSE_EQ_ALL, 2, CATALOGUE_78)
            if command == SET_EQ_DETAIL:
                return Frame(RESPONSE_SET_EQ_DETAIL, 3, b"\x00")
            raise AssertionError(command)

        session._transport.request.side_effect = responses
        with self.assertRaises(RuntimeError):
            session.create_custom_eq("Plugin Test")
        self.assertEqual(len(self.detail_payloads(session)), 1)

    def test_rename_keeps_the_curve_and_stores_the_new_name(self):
        session = self.session()
        renamed = entry_payload(1, 7, "Rock")
        session._transport.request.side_effect = [
            Frame(RESPONSE_EQ, 1, b"\x00\x07"),
            Frame(RESPONSE_EQ_ALL, 2, CATALOGUE_78),
            Frame(RESPONSE_SET_EQ_DETAIL, 3, b"\x00"),
            Frame(RESPONSE_EQ_ALL, 4, catalogue(renamed, ENTRY_8)),
            Frame(RESPONSE_EQ, 5, b"\x00\x07"),
            Frame(RESPONSE_EQ, 6, b"\x00\x07"),
            Frame(RESPONSE_EQ_ALL, 7, catalogue(renamed, ENTRY_8)),
        ]
        result, _batch = session.rename_custom_eq(7, "Rock")
        self.assertTrue(result.verified)
        self.assertEqual(result.current_name, "Rock")
        payloads = self.detail_payloads(session)
        self.assertEqual(len(payloads), 1)
        self.assertEqual(payloads[0][0], 2)  # update
        self.assertEqual(payloads[0][3], 7)
        self.assertIn(b"Rock", payloads[0])
        self.assertTrue(payloads[0].endswith(
            b"\x3e\x00\x04\xfa\x00\x06\xe8\x03\x01\xa0\x0f\x00\x40\x1f\x04\x80\x3e\x06"
        ))

    def test_rename_restores_the_previous_selection(self):
        session = self.session()
        renamed = entry_payload(0, 8, "Neu")
        session._transport.request.side_effect = [
            Frame(RESPONSE_EQ, 1, b"\x00\x07"),
            Frame(RESPONSE_EQ_ALL, 2, CATALOGUE_78),
            Frame(RESPONSE_SET_EQ_DETAIL, 3, b"\x00"),
            Frame(RESPONSE_EQ_ALL, 4, catalogue(ENTRY_7, renamed)),
            Frame(RESPONSE_EQ, 5, b"\x00\x08"),
            Frame(RESPONSE_EQ, 6, b"\x00\x08"),
            Frame(RESPONSE_EQ_ALL, 7, catalogue(ENTRY_7, renamed)),
            Frame(RESPONSE_EQ, 8, b"\x00\x08"),
            Frame(RESPONSE_EQ_ALL, 9, catalogue(ENTRY_7, renamed)),
            Frame(RESPONSE_SET_EQ_DETAIL, 10, b"\x00"),
            Frame(RESPONSE_EQ_ALL, 11, catalogue(ENTRY_7, renamed)),
            Frame(RESPONSE_EQ, 12, b"\x00\x07"),
        ]
        result, _batch = session.rename_custom_eq(8, "Neu")
        self.assertTrue(result.verified)
        payloads = self.detail_payloads(session)
        self.assertEqual(len(payloads), 2)
        self.assertEqual(payloads[0][3], 8)
        self.assertEqual(payloads[1][3], 7)

    def test_delete_removes_the_profile_and_is_verified(self):
        session = self.session()
        session._transport.request.side_effect = [
            Frame(RESPONSE_EQ, 1, b"\x00\x07"),
            Frame(RESPONSE_EQ_ALL, 2, CATALOGUE_789),
            Frame(RESPONSE_SET_EQ_DETAIL, 3, b"\x00"),
            Frame(RESPONSE_EQ_ALL, 4, CATALOGUE_78),
            Frame(RESPONSE_EQ, 5, b"\x00\x07"),
        ]
        result, _batch = session.delete_custom_eq(9)
        self.assertTrue(result.verified)
        payloads = self.detail_payloads(session)
        self.assertEqual(len(payloads), 1)
        self.assertEqual(payloads[0][0], 3)  # delete
        self.assertEqual(payloads[0][3], 9)

    def test_empty_name_is_refused_before_any_write(self):
        session = self.session()
        with self.assertRaises(ValueError):
            session.rename_custom_eq(7, "   ")
        with self.assertRaises(ValueError):
            session.create_custom_eq("")
        session._transport.request.assert_not_called()

    def test_profile_writes_are_gated_for_unverified_devices(self):
        session = self.session("060C14")
        with self.assertRaises(ValueError):
            session.create_custom_eq("Plugin Test")
        with self.assertRaises(ValueError):
            session.rename_custom_eq(4, "Rock")
        with self.assertRaises(ValueError):
            session.delete_custom_eq(4)
        session._transport.request.assert_not_called()

    def test_buds4_management_is_gated_despite_custom_update_permission(self):
        session = self.session("065414")
        with self.assertRaises(ValueError):
            session.create_custom_eq("Plugin Test")
        with self.assertRaises(ValueError):
            session.rename_custom_eq(4, "Rock")
        with self.assertRaises(ValueError):
            session.delete_custom_eq(4)
        session._transport.request.assert_not_called()


if __name__ == "__main__":
    unittest.main()
