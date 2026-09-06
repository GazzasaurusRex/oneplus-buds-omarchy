import unittest
from threading import Event

from oneplus_buds.models import ControllerSnapshot
from oneplus_buds.service import BudsServiceRunner


EMPTY_SNAPSHOT = ControllerSnapshot(
    status=None,
    feature_switches={},
    session_connected=False,
    advertised_event_codes=(),
    notification_event_codes=(),
    ignored_frames=0,
    reconnect_count=0,
    generation=0,
)


class ServiceRunnerTests(unittest.TestCase):
    def test_polls_until_cancelled_and_shuts_down(self):
        cancelled = Event()
        controller = FakeController(polls=[EMPTY_SNAPSHOT], cancel_after_poll=cancelled)
        states = []
        snapshots = []
        result = BudsServiceRunner(
            controller,
            on_state=states.append,
            on_snapshot=snapshots.append,
        ).run(cancelled)
        self.assertIs(result, EMPTY_SNAPSHOT)
        self.assertEqual([state.connection for state in states], ["connecting", "connected", "stopped"])
        self.assertEqual(controller.shutdowns, 1)
        self.assertEqual(len(snapshots), 3)

    def test_retries_with_capped_exponential_backoff(self):
        cancelled = RecordingEvent(cancel_after_waits=4)
        controller = FakeController(starts=[OSError("one"), OSError("two"), OSError("three"), OSError("four")])
        states = []
        BudsServiceRunner(
            controller,
            initial_retry_delay=0.25,
            maximum_retry_delay=1.0,
            on_state=states.append,
        ).run(cancelled)
        self.assertEqual(cancelled.waits, [0.25, 0.5, 1.0, 1.0])
        disconnected = [state for state in states if state.connection == "disconnected"]
        self.assertEqual([state.attempt for state in disconnected], [1, 2, 3, 4])
        self.assertEqual([state.error for state in disconnected], ["one", "two", "three", "four"])

    def test_success_resets_backoff_after_poll_failure(self):
        cancelled = RecordingEvent(cancel_after_waits=2)
        controller = FakeController(
            starts=[EMPTY_SNAPSHOT, EMPTY_SNAPSHOT],
            polls=[OSError("lost"), OSError("lost again")],
        )
        BudsServiceRunner(
            controller,
            initial_retry_delay=0.25,
            maximum_retry_delay=2.0,
        ).run(cancelled)
        self.assertEqual(cancelled.waits, [0.25, 0.25])

    def test_cancellation_interrupts_retry_wait(self):
        cancelled = RecordingEvent(cancel_after_waits=1)
        controller = FakeController(starts=[RuntimeError("not connected")])
        states = []
        BudsServiceRunner(controller, on_state=states.append).run(cancelled)
        self.assertEqual(cancelled.waits, [1.0])
        self.assertNotIn("reconnecting", [state.connection for state in states])
        self.assertEqual(states[-1].connection, "stopped")

    def test_connection_errors_redact_selected_device_address(self):
        cancelled = RecordingEvent(cancel_after_waits=1)
        controller = FakeController(
            starts=[RuntimeError("selected device AA:BB:CC:DD:EE:FF is disconnected")]
        )
        controller.address = "AA:BB:CC:DD:EE:FF"
        states = []
        BudsServiceRunner(controller, on_state=states.append).run(cancelled)
        error = next(state.error for state in states if state.connection == "disconnected")
        self.assertEqual(error, "selected device [device] is disconnected")

    def test_poll_waits_outside_controller(self):
        cancelled = RecordingEvent(cancel_after_waits=1)
        controller = FakeController(polls=[EMPTY_SNAPSHOT])
        BudsServiceRunner(controller, poll_interval=0.5).run(cancelled)
        self.assertEqual(controller.poll_waits, [0.0])
        self.assertEqual(cancelled.waits, [0.5])

    def test_rejects_invalid_timing(self):
        with self.assertRaises(ValueError):
            BudsServiceRunner(poll_interval=-1)
        with self.assertRaises(ValueError):
            BudsServiceRunner(initial_retry_delay=0)
        with self.assertRaises(ValueError):
            BudsServiceRunner(initial_retry_delay=2, maximum_retry_delay=1)


class FakeController:
    def __init__(self, starts=None, polls=None, cancel_after_poll=None):
        self.starts = list(starts or [EMPTY_SNAPSHOT])
        self.polls = list(polls or [])
        self.cancel_after_poll = cancel_after_poll
        self.address = None
        self.shutdowns = 0
        self.poll_waits = []

    def start(self):
        item = self.starts.pop(0) if self.starts else EMPTY_SNAPSHOT
        if isinstance(item, Exception):
            raise item
        return item

    def poll(self, _wait):
        self.poll_waits.append(_wait)
        item = self.polls.pop(0) if self.polls else EMPTY_SNAPSHOT
        if self.cancel_after_poll is not None:
            self.cancel_after_poll.set()
        if isinstance(item, Exception):
            raise item
        return item

    def shutdown(self):
        self.shutdowns += 1
        return EMPTY_SNAPSHOT


class RecordingEvent:
    def __init__(self, cancel_after_waits):
        self.cancel_after_waits = cancel_after_waits
        self.waits = []

    def is_set(self):
        return len(self.waits) >= self.cancel_after_waits

    def wait(self, delay):
        self.waits.append(delay)
        return self.is_set()


if __name__ == "__main__":
    unittest.main()
