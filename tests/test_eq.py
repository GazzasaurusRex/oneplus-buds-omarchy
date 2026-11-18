import unittest
from dataclasses import replace
from unittest.mock import MagicMock

from oneplus_buds.bluez import Device
from oneplus_buds.profiles import PROFILES
from oneplus_buds.protocol import (
    EQ_ALL_QUERY_PAYLOAD,
    QUERY_EQ,
    QUERY_EQ_ALL,
    RESPONSE_EQ,
    RESPONSE_EQ_ALL,
    RESPONSE_SET_EQ,
    RESPONSE_SET_EQ_DETAIL,
    SET_EQ,
    SET_EQ_DETAIL,
    EqBand,
    EqEntry,
    Frame,
    encode_eq_detail_payload,
    parse_eq_entries,
    parse_eq_id,
)
from oneplus_buds.session import OpoSession


DEVICE = Device(
    address="AA:BB:CC:DD:EE:FF",
    name="OnePlus Buds Pro 2",
    connected=True,
    uuids=("0000079a-d102-11e1-9b23-00025b00a5a5",),
    battery=80,
    modalias=None,
    services_resolved=True,
)


def entry_payload(selected, eq_id, name, gains=(3, 1, 0, 0, 0, 0)):
    frequencies = (62, 250, 1000, 4000, 8000, 16000)
    encoded_name = name.encode()
    payload = bytearray((selected, 0xFA, 6, eq_id, len(encoded_name)))
    payload.extend(encoded_name)
    payload.append(len(frequencies))
    for frequency, gain in zip(frequencies, gains, strict=True):
        payload.extend(frequency.to_bytes(2, "little"))
        payload.append(gain & 0xFF)
    return bytes(payload)


EQ_PAYLOAD = b"\x00\x02" + entry_payload(1, 4, "Custom") + entry_payload(
    0, 5, "Custom1", (0, 0, 0, 0, 0, 0)
)


class EqProtocolTests(unittest.TestCase):
    def test_observed_pro_2_custom_catalogue(self):
        entries = parse_eq_entries(Frame(RESPONSE_EQ_ALL, 1, EQ_PAYLOAD))
        self.assertIsNotNone(entries)
        selected = entries[0]
        self.assertEqual((selected.eq_id, selected.name, selected.selected), (4, "Custom", True))
        self.assertEqual((selected.min_gain_db, selected.max_gain_db), (-6, 6))
        self.assertEqual(
            [(band.frequency_hz, band.gain_db) for band in selected.bands],
            [(62, 3), (250, 1), (1000, 0), (4000, 0), (8000, 0), (16000, 0)],
        )

    def test_malformed_catalogues_are_rejected(self):
        for payload in (
            EQ_PAYLOAD[:-1],
            EQ_PAYLOAD + b"\x00",
            b"\x01\x00",
            b"\x00\x01" + entry_payload(1, 4, "Custom", (7, 0, 0, 0, 0, 0)),
        ):
            self.assertIsNone(parse_eq_entries(Frame(RESPONSE_EQ_ALL, 1, payload)))

    def test_current_id_parser_requires_success_and_exact_shape(self):
        self.assertEqual(parse_eq_id(Frame(RESPONSE_EQ, 1, b"\x00\x04")), 4)
        self.assertIsNone(parse_eq_id(Frame(RESPONSE_EQ, 1, b"\x01\x04")))
        self.assertIsNone(parse_eq_id(Frame(RESPONSE_EQ, 1, b"\x00\x04\x00")))

    def test_custom_encoder_uses_device_definition_and_validates(self):
        entry = EqEntry(5, "Custom1", False, -6, 6, (EqBand(62, 0), EqBand(250, 0)))
        self.assertEqual(
            encode_eq_detail_payload(entry, (-6, 6)),
            b"\x02\xfa\x06\x05\x07Custom1\x02\x3e\x00\xfa\xfa\x00\x06",
        )
        for gains in ((0,), (-7, 0), (0, 7), (0.5, 0)):
            with self.assertRaises(ValueError):
                encode_eq_detail_payload(entry, gains)

    def test_custom_encoder_action_byte_and_name_override(self):
        entry = EqEntry(7, "Old", False, -6, 6, (EqBand(62, 0),))
        for action in (1, 2, 3):
            self.assertEqual(encode_eq_detail_payload(entry, (0,), action=action)[0], action)
        renamed = encode_eq_detail_payload(entry, (0,), action=2, name="New")
        self.assertIn(b"\x03New", renamed)
        self.assertNotIn(b"Old", renamed)
        with self.assertRaises(ValueError):
            encode_eq_detail_payload(entry, (0,), action=4)

    def test_custom_encoder_rejects_empty_or_non_string_name_and_non_int_action(self):
        entry = EqEntry(7, "Old", False, -6, 6, (EqBand(62, 0),))
        for bad in ("", "   ", 5):
            with self.assertRaises(ValueError):
                encode_eq_detail_payload(entry, (0,), name=bad)
        with self.assertRaises(ValueError):
            encode_eq_detail_payload(entry, (0,), action=True)


class EqProfileTests(unittest.TestCase):
    def test_factory_presets_are_model_specific(self):
        pro = PROFILES["060C14"].eq
        pro_2 = PROFILES["062014"].eq
        self.assertEqual(
            [(item.eq_id, item.name) for item in pro.presets],
            [(0, "Balanced"), (1, "Deep Sea Bass"), (2, "Pure Vocals"),
             (3, "Bright & Crisp")],
        )
        self.assertEqual(
            [(item.eq_id, item.name) for item in pro_2.presets],
            [(0, "Balanced"), (1, "Bass"), (2, "Serenade"), (3, "Bold"),
             (7, "Hans Zimmer Soundscape Tuning")],
        )

    def test_pro_2_accepts_current_and_legacy_preset_keys(self):
        profile = PROFILES["062014"].eq
        self.assertEqual(profile.preset_for("serenade").eq_id, 2)
        self.assertEqual(profile.preset_for("pure-vocals").eq_id, 2)
        self.assertEqual(profile.preset_for("hans-zimmer-soundscape-tuning").eq_id, 7)

    def test_buds_4_swaps_pro_2_bass_and_serenade_ids(self):
        profile = PROFILES["065414"].eq
        self.assertEqual(
            [(item.eq_id, item.name) for item in profile.presets],
            [(0, "Balanced"), (1, "Serenade"), (2, "Bass")],
        )
        self.assertEqual(profile.preset_for("pure-vocals").eq_id, 1)
        self.assertEqual(profile.preset_for("deep-sea-bass").eq_id, 2)
        self.assertTrue(profile.supports_custom)

    def test_custom_management_is_nord_only_evidence(self):
        self.assertTrue(PROFILES["064414"].eq.custom_manage_verified)
        self.assertFalse(PROFILES["062014"].eq.custom_manage_verified)
        self.assertFalse(PROFILES["065414"].eq.custom_manage_verified)

    def test_nord_presets_are_the_three_measured_factory_ids(self):
        eq = PROFILES["064414"].eq
        self.assertEqual(
            [(item.eq_id, item.name) for item in eq.presets],
            [(3, "Balanced (Default)"), (4, "Serenade"), (5, "Bass")],
        )
        self.assertTrue(eq.write_verified)
        self.assertTrue(eq.supports_custom)
        self.assertTrue(eq.custom_write_verified)


class EqSessionTests(unittest.TestCase):
    def session(self, product="062014"):
        session = OpoSession(DEVICE, PROFILES[product])
        session._connected = session._authenticated = True
        session._transport = MagicMock()
        return session

    def test_status_uses_fresh_current_and_device_catalogue(self):
        session = self.session()
        session._transport.request.side_effect = [
            Frame(RESPONSE_EQ, 1, b"\x00\x04"),
            Frame(RESPONSE_EQ_ALL, 2, EQ_PAYLOAD),
        ]
        status, _ = session.eq_status()
        self.assertEqual((status.current_id, status.current_name, status.current_kind), (4, "Custom", "custom"))
        self.assertEqual(status.gain_step_db, 1)
        self.assertEqual(
            [call.args[:3] for call in session._transport.request.call_args_list],
            [(QUERY_EQ, b"", RESPONSE_EQ),
             (QUERY_EQ_ALL, EQ_ALL_QUERY_PAYLOAD, RESPONSE_EQ_ALL)],
        )

    def test_preset_write_records_old_state_and_verifies_without_replay(self):
        session = self.session()
        session._transport.request.side_effect = [
            Frame(RESPONSE_EQ, 1, b"\x00\x04"),
            Frame(RESPONSE_EQ_ALL, 2, EQ_PAYLOAD),
            Frame(RESPONSE_SET_EQ, 3, b"\x00"),
            Frame(RESPONSE_EQ, 4, b"\x00\x00"),
            Frame(RESPONSE_EQ, 5, b"\x00\x00"),
            Frame(RESPONSE_EQ_ALL, 6, EQ_PAYLOAD),
        ]
        result, _ = session.set_eq("balanced")
        self.assertTrue(result.verified)
        self.assertEqual((result.previous_id, result.current_id), (4, 0))
        commands = [call.args[0] for call in session._transport.request.call_args_list]
        self.assertEqual(commands.count(SET_EQ), 1)
        self.assertEqual(commands, [QUERY_EQ, QUERY_EQ_ALL, SET_EQ, QUERY_EQ, QUERY_EQ, QUERY_EQ_ALL])

    def test_unknown_preset_is_gated_before_transport(self):
        session = self.session()
        session._transport.request.side_effect = [
            Frame(RESPONSE_EQ, 1, b"\x00\x04"),
            Frame(RESPONSE_EQ_ALL, 2, EQ_PAYLOAD),
        ]
        with self.assertRaises(ValueError):
            session.set_eq("unverified-preset")
        self.assertEqual(session._transport.request.call_count, 2)

    def test_custom_write_uses_existing_entry_and_fresh_curve_verification(self):
        session = self.session()
        session.profile = replace(
            session.profile,
            eq=replace(session.profile.eq, custom_write_verified=True),
        )
        changed = b"\x00\x02" + entry_payload(0, 4, "Custom") + entry_payload(
            1, 5, "Custom1", (1, 0, -1, 0, 1, -1)
        )
        session._transport.request.side_effect = [
            Frame(RESPONSE_EQ, 1, b"\x00\x04"),
            Frame(RESPONSE_EQ_ALL, 2, EQ_PAYLOAD),
            Frame(RESPONSE_SET_EQ_DETAIL, 3, b"\x00"),
            Frame(RESPONSE_EQ_ALL, 4, changed),
            Frame(RESPONSE_EQ, 5, b"\x00\x05"),
        ]
        result, _ = session.set_custom_eq(5, (1, 0, -1, 0, 1, -1))
        self.assertTrue(result.verified)
        self.assertEqual((result.previous_id, result.current_id), (4, 5))
        commands = [call.args[0] for call in session._transport.request.call_args_list]
        self.assertEqual(commands.count(SET_EQ_DETAIL), 1)

    def test_buds_4_factory_preset_write_is_authorized_and_verified(self):
        session = self.session("065414")
        session._transport.request.side_effect = [
            Frame(RESPONSE_EQ, 1, b"\x00\x04"),
            Frame(RESPONSE_EQ_ALL, 2, EQ_PAYLOAD),
            Frame(RESPONSE_SET_EQ, 3, b"\x00"),
            Frame(RESPONSE_EQ, 4, b"\x00\x01"),
            Frame(RESPONSE_EQ, 5, b"\x00\x01"),
            Frame(RESPONSE_EQ_ALL, 6, EQ_PAYLOAD),
        ]
        result, _ = session.set_eq("serenade")
        self.assertEqual((result.current_id, result.current_name), (1, "Serenade"))
        set_call = next(call for call in session._transport.request.call_args_list
                        if call.args[0] == SET_EQ)
        self.assertEqual(set_call.args[1], b"\x01")

    def test_buds_4_custom_eq_write_is_authorized_and_verified(self):
        session = self.session("065414")
        changed = b"\x00\x02" + entry_payload(0, 4, "Custom") + entry_payload(
            1, 5, "Custom1", (1, 0, -1, 0, 1, -1)
        )
        session._transport.request.side_effect = [
            Frame(RESPONSE_EQ, 1, b"\x00\x04"),
            Frame(RESPONSE_EQ_ALL, 2, EQ_PAYLOAD),
            Frame(RESPONSE_SET_EQ_DETAIL, 3, b"\x00"),
            Frame(RESPONSE_EQ_ALL, 4, changed),
            Frame(RESPONSE_EQ, 5, b"\x00\x05"),
        ]
        result, _ = session.set_custom_eq(5, (1, 0, -1, 0, 1, -1))
        self.assertEqual((result.current_id, result.current_name), (5, "Custom1"))
        self.assertTrue(result.verified)

    def test_buds_4_custom_entry_selection_uses_custom_permission(self):
        session = self.session("065414")
        session._transport.request.side_effect = [
            Frame(RESPONSE_EQ, 1, b"\x00\x04"),
            Frame(RESPONSE_EQ_ALL, 2, EQ_PAYLOAD),
            Frame(RESPONSE_SET_EQ, 3, b"\x00"),
            Frame(RESPONSE_EQ, 4, b"\x00\x05"),
            Frame(RESPONSE_EQ, 5, b"\x00\x05"),
            Frame(RESPONSE_EQ_ALL, 6, EQ_PAYLOAD),
        ]
        result, _ = session.set_eq("custom:5")
        self.assertEqual((result.current_id, result.current_name), (5, "Custom1"))
        set_call = next(call for call in session._transport.request.call_args_list
                        if call.args[0] == SET_EQ)
        self.assertEqual(set_call.args[1], b"\x05")

    def test_nord_factory_preset_write_uses_empty_catalogue_and_verifies(self):
        session = self.session("064414")
        session._transport.request.side_effect = [
            Frame(RESPONSE_EQ, 1, b"\x00\x05"),
            Frame(RESPONSE_EQ_ALL, 2, b"\x00\x00"),
            Frame(RESPONSE_SET_EQ, 3, b"\x00"),
            Frame(RESPONSE_EQ, 4, b"\x00\x03"),
            Frame(RESPONSE_EQ, 5, b"\x00\x03"),
            Frame(RESPONSE_EQ_ALL, 6, b"\x00\x00"),
        ]
        result, _ = session.set_eq("balanced")
        self.assertTrue(result.verified)
        self.assertEqual((result.previous_id, result.current_id, result.current_name),
                         (5, 3, "Balanced (Default)"))
        set_call = next(call for call in session._transport.request.call_args_list
                        if call.args[0] == SET_EQ)
        self.assertEqual(set_call.args[1], b"\x03")

    def test_nord_preset_aliases_resolve_to_measured_ids(self):
        eq = PROFILES["064414"].eq
        self.assertEqual(eq.preset_for("ausgewogen").eq_id, 3)
        self.assertEqual(eq.preset_for("serenade").eq_id, 4)
        self.assertEqual(eq.preset_for("bass").eq_id, 5)
        self.assertEqual(eq.preset_for("3").eq_id, 3)
        self.assertIsNone(eq.preset_for("bold"))

    def test_nord_custom_selection_writes_the_curve_back(self):
        session = self.session("064414")
        # Nord ignores the plain preset command for custom entries; selecting
        # one writes its unchanged curve back (0x0418), never 0x0406.
        catalogue = b"\x00\x01" + entry_payload(1, 7, "Custom")
        session._transport.request.side_effect = [
            Frame(RESPONSE_EQ, 1, b"\x00\x03"),
            Frame(RESPONSE_EQ_ALL, 2, catalogue),
            Frame(RESPONSE_EQ, 3, b"\x00\x03"),
            Frame(RESPONSE_EQ_ALL, 4, catalogue),
            Frame(RESPONSE_SET_EQ_DETAIL, 5, b"\x00"),
            Frame(RESPONSE_EQ_ALL, 6, catalogue),
            Frame(RESPONSE_EQ, 7, b"\x00\x07"),
        ]
        result, _ = session.set_eq("custom:7")
        self.assertTrue(result.verified)
        self.assertEqual(result.current_id, 7)
        commands = [call.args[0] for call in session._transport.request.call_args_list]
        self.assertNotIn(SET_EQ, commands)
        self.assertIn(SET_EQ_DETAIL, commands)

    def test_nord_custom_eq_writes_are_authorized(self):
        session = self.session("064414")
        # Nord holds custom-EQ evidence now: the gate must let the write reach
        # device I/O (curve verification itself is covered by the CRUD tests).
        session._transport.request.side_effect = RuntimeError("reached device I/O")
        with self.assertRaisesRegex(RuntimeError, "reached device I/O"):
            session.set_custom_eq(7, (0, 0, 0, 0, 0, 0))

    def test_nord_anc_permission_does_not_authorize_eq_writes(self):
        profile = replace(
            PROFILES["064414"],
            community_write_permissions=frozenset({"anc"}),
        )
        session = OpoSession(DEVICE, profile)
        session._connected = session._authenticated = True
        session._transport = MagicMock()
        with self.assertRaises(ValueError):
            session.set_eq("balanced")
        session._transport.request.assert_not_called()

    def test_community_eq_permissions_are_independent(self):
        profile = replace(
            PROFILES["065414"],
            community_write_permissions=frozenset({"anc"}),
        )
        session = OpoSession(DEVICE, profile)
        session._connected = session._authenticated = True
        session._transport = MagicMock()
        with self.assertRaises(ValueError):
            session.set_eq("balanced")
        with self.assertRaises(ValueError):
            session.set_custom_eq(5, (0, 0, 0, 0, 0, 0))
        self.assertNotIn(
            SET_EQ,
            [call.args[0] for call in session._transport.request.call_args_list],
        )

        factory_only = replace(
            PROFILES["065414"],
            community_write_permissions=frozenset({"eq_preset"}),
        )
        session = OpoSession(DEVICE, factory_only)
        session._connected = session._authenticated = True
        session._transport = MagicMock()
        session._transport.request.side_effect = [
            Frame(RESPONSE_EQ, 1, b"\x00\x04"),
            Frame(RESPONSE_EQ_ALL, 2, EQ_PAYLOAD),
        ]
        with self.assertRaises(ValueError):
            session.set_eq("custom:5")
        self.assertNotIn(
            SET_EQ,
            [call.args[0] for call in session._transport.request.call_args_list],
        )

    def test_unverified_custom_write_is_gated_before_transport(self):
        session = self.session("060C14")
        with self.assertRaises(ValueError):
            session.set_custom_eq(5, (0, 0, 0, 0, 0, 0))
        session._transport.request.assert_not_called()


if __name__ == "__main__":
    unittest.main()
