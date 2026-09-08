import json
import unittest

from unittest.mock import patch

from oneplus_buds.bluez import Device
from oneplus_buds.bridge import BudsFrontendBridge, serialize_snapshot
from oneplus_buds.models import (ControllerSnapshot, ControlResult, EqControlResult,
                                 EqStatusResult, StatusResult)
from oneplus_buds.protocol import EqBand, EqEntry
from oneplus_buds.service import ServiceState


DEVICE = Device(
    address="AA:BB:CC:DD:EE:FF",
    name="OnePlus Buds Pro 2",
    connected=True,
    uuids=("0000079a-d102-11e1-9b23-00025b00a5a5",),
    battery=80,
)
STATUS = StatusResult(
    device=DEVICE,
    product_id="062014",
    model="OnePlus Buds Pro 2",
    remote_version=(),
    firmware_version="196.196.101",
    battery={"left": {"percentage": 80, "charging": False}},
    anc="off",
    anc_level=None,
)
SNAPSHOT = ControllerSnapshot(
    status=STATUS,
    feature_switches={"multipoint": True},
    session_connected=True,
    advertised_event_codes=(1, 2),
    notification_event_codes=(4,),
    ignored_frames=3,
    reconnect_count=1,
    generation=2,
)
EQ_STATUS = EqStatusResult(
    DEVICE.name, "062014", DEVICE.name, 4, "Custom", "custom",
    ({"id": 0, "key": "balanced", "name": "Balanced"},),
    (EqEntry(4, "Custom", True, -6, 6, (EqBand(62, 3),)),), 1,
)
EQ_SNAPSHOT = ControllerSnapshot(
    status=STATUS, feature_switches={}, session_connected=True,
    advertised_event_codes=(), notification_event_codes=(), ignored_frames=0,
    reconnect_count=0, generation=3, eq_status=EQ_STATUS,
)


class BridgeTests(unittest.TestCase):
    def test_snapshot_serialization_is_json_compatible_and_address_free(self):
        payload = serialize_snapshot(SNAPSHOT)
        encoded = json.dumps(payload)
        self.assertNotIn(DEVICE.address, encoded)
        self.assertEqual(payload["status"]["model"], "OnePlus Buds Pro 2")
        self.assertEqual(payload["advertised_event_codes"], [1, 2])
        self.assertEqual(payload["feature_switches"], {"multipoint": True})
        self.assertEqual(payload["compatibility"], "verified")
        self.assertIn("anc", payload["capabilities"])
        self.assertIn("multipoint", payload["capabilities"])
        self.assertIn("transparency", payload["anc_modes"])

    def test_callbacks_are_marshaled_through_dispatcher(self):
        emitted = []
        queued = []
        bridge = BudsFrontendBridge(
            emitted.append,
            controller=FakeController(),
            dispatch=queued.append,
        )
        bridge._on_state(ServiceState("disconnected", 2, 4.0, "gone"))
        bridge._on_snapshot(SNAPSHOT)
        self.assertEqual(emitted, [])
        self.assertEqual(len(queued), 2)
        for callback in queued:
            callback()
        self.assertEqual(emitted[0]["type"], "connection")
        self.assertEqual(emitted[0]["retry_delay"], 4.0)
        self.assertEqual(emitted[1]["snapshot"]["generation"], 2)

    def test_run_delegates_to_service_runner(self):
        bridge = BudsFrontendBridge(lambda _event: None, controller=FakeController())
        runner = FakeRunner()
        bridge.runner = runner
        cancelled = object()
        self.assertIs(bridge.run(cancelled), SNAPSHOT)
        self.assertIs(runner.cancelled, cancelled)

    def test_snapshot_and_refresh_commands_use_controller(self):
        emitted = []
        controller = FakeController()
        bridge = BudsFrontendBridge(emitted.append, controller=controller)
        current = bridge.execute("snapshot", request_id=7)
        refreshed = bridge.execute("refresh")
        self.assertTrue(current["ok"])
        self.assertEqual(current["request_id"], 7)
        self.assertTrue(refreshed["ok"])
        self.assertEqual(controller.refreshes, 1)
        self.assertEqual(emitted[-1]["type"], "snapshot")

    def test_set_anc_returns_verified_result_and_emits_snapshot(self):
        emitted = []
        controller = FakeController()
        response = BudsFrontendBridge(emitted.append, controller=controller).execute(
            "set_anc", {"mode": "transparency"}, request_id="anc-1"
        )
        self.assertTrue(response["ok"])
        self.assertEqual(response["result"]["anc"], "transparency")
        self.assertTrue(response["result"]["verified"])
        self.assertEqual(controller.anc_modes, ["transparency"])
        self.assertEqual(emitted[-1]["type"], "snapshot")

    def test_eq_commands_are_typed_verified_and_emit_fresh_state(self):
        emitted = []
        controller = FakeController()
        bridge = BudsFrontendBridge(emitted.append, controller=controller)
        status = bridge.execute("eq_status")
        preset = bridge.execute("set_eq", {"preset": "balanced"})
        custom = bridge.execute("set_custom_eq", {"entry_id": 4, "gains_db": [3]})
        self.assertEqual(status["result"]["current_name"], "Custom")
        self.assertTrue(preset["result"]["verified"])
        self.assertTrue(custom["result"]["verified"])
        self.assertEqual(controller.eq_targets, ["balanced"])
        self.assertEqual(controller.custom_targets, [(4, (3,))])
        self.assertEqual(emitted[-1]["snapshot"]["eq"]["current_id"], 4)

    def test_malformed_custom_eq_never_reaches_controller(self):
        controller = FakeController()
        response = BudsFrontendBridge(lambda _event: None, controller=controller).execute(
            "set_custom_eq", {"entry_id": 4, "gains_db": [True]}
        )
        self.assertFalse(response["ok"])
        self.assertEqual(response["error"]["code"], "invalid_parameters")
        self.assertEqual(controller.custom_targets, [])

    def test_verified_response_does_not_reacquire_snapshot_during_recovery(self):
        controller = FakeController()
        with patch.object(controller, 'snapshot', side_effect=AssertionError('second lock acquisition')):
            response = BudsFrontendBridge(lambda _: None, controller=controller).execute(
                'set_anc', {'mode': 'off'})
        self.assertTrue(response['ok'])

    def test_invalid_commands_and_parameters_are_structured_errors(self):
        bridge = BudsFrontendBridge(lambda _event: None, controller=FakeController())
        unknown = bridge.execute("delete_everything")
        invalid = bridge.execute("set_anc", {})
        extra = bridge.execute("snapshot", {"raw": True})
        wrong_type = bridge.execute("refresh", ["unexpected"])
        self.assertEqual(unknown["error"]["code"], "unknown_command")
        self.assertEqual(invalid["error"]["code"], "invalid_parameters")
        self.assertEqual(extra["error"]["code"], "invalid_parameters")
        self.assertEqual(wrong_type["error"]["code"], "invalid_parameters")

    def test_command_errors_redact_device_address(self):
        controller = FakeController(error=RuntimeError(f"device {DEVICE.address} disappeared"))
        response = BudsFrontendBridge(lambda _event: None, controller=controller).execute("refresh")
        encoded = json.dumps(response)
        self.assertFalse(response["ok"])
        self.assertNotIn(DEVICE.address, encoded)
        self.assertIn("[device]", response["error"]["message"])


class FakeController:
    def __init__(self, error=None):
        self.address = DEVICE.address
        self.error = error
        self.refreshes = 0
        self.anc_modes = []
        self.eq_targets = []
        self.custom_targets = []
        self.current_snapshot = SNAPSHOT

    def snapshot(self):
        return self.current_snapshot

    def refresh(self):
        self.refreshes += 1
        if self.error:
            raise self.error
        return SNAPSHOT

    def set_anc(self, mode):
        self.anc_modes.append(mode)
        return ControlResult(
            name=DEVICE.name,
            product_id="062014",
            anc=mode,
            anc_level=None,
            set_status=0,
            verified=True,
        )

    def set_anc_with_snapshot(self, mode):
        return self.set_anc(mode), SNAPSHOT

    def eq_status(self):
        self.current_snapshot = EQ_SNAPSHOT
        return EQ_STATUS

    def set_eq(self, preset):
        self.eq_targets.append(preset)
        return EqControlResult(DEVICE.name, "062014", 0, "Balanced", 4, "Custom", 0, True)

    def set_custom_eq(self, entry_id, gains):
        self.custom_targets.append((entry_id, gains))
        return EqControlResult(DEVICE.name, "062014", entry_id, "Custom", 0, "Balanced", 0, True)


class FakeRunner:
    def run(self, cancelled):
        self.cancelled = cancelled
        return SNAPSHOT


if __name__ == "__main__":
    unittest.main()
