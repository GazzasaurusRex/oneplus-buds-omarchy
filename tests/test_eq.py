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

    def test_unverified_custom_write_is_gated_before_transport(self):
        session = self.session("060C14")
        with self.assertRaises(ValueError):
            session.set_custom_eq(5, (0, 0, 0, 0, 0, 0))
        session._transport.request.assert_not_called()


if __name__ == "__main__":
    unittest.main()
