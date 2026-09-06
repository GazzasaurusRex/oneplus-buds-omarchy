import io
import json
import unittest
from threading import Event, Thread

from oneplus_buds.bridge_host import BridgeProcessHost


class BridgeProcessHostTests(unittest.TestCase):
    def test_routes_ndjson_requests_and_stops_worker_at_eof(self):
        source = io.StringIO(
            '{"request_id":1,"command":"snapshot"}\n'
            '{"request_id":"a","command":"set_anc","parameters":{"mode":"off"}}\n'
        )
        output = io.StringIO()
        factory = FakeBridgeFactory()
        host = BridgeProcessHost(source, output, bridge_factory=factory)
        host.run()
        messages = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual([message["request_id"] for message in messages], [1, "a"])
        self.assertEqual(factory.bridge.commands, [("snapshot", None), ("set_anc", {"mode": "off"})])
        self.assertTrue(factory.bridge.started)
        self.assertTrue(factory.bridge.stopped)

    def test_rejects_malformed_requests_without_calling_bridge(self):
        source = io.StringIO(
            'not json\n'
            '[]\n'
            '{"request_id":false,"command":"snapshot"}\n'
            '{"command":""}\n'
            '{"command":"snapshot","extra":true}\n'
        )
        output = io.StringIO()
        factory = FakeBridgeFactory()
        BridgeProcessHost(source, output, bridge_factory=factory).run()
        messages = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual(len(messages), 5)
        self.assertTrue(all(message["error"]["code"] == "invalid_request" for message in messages))
        self.assertEqual(factory.bridge.commands, [])

    def test_internal_failures_return_generic_error(self):
        source = io.StringIO('{"request_id":2,"command":"refresh"}\n')
        output = io.StringIO()
        factory = FakeBridgeFactory(error=AssertionError("private implementation detail"))
        BridgeProcessHost(source, output, bridge_factory=factory).run()
        response = json.loads(output.getvalue())
        self.assertEqual(response["error"], {"code": "internal_error", "message": "bridge command failed"})
        self.assertNotIn("private implementation detail", output.getvalue())

    def test_writer_emits_compact_one_line_json(self):
        output = io.StringIO()
        host = BridgeProcessHost(io.StringIO(), output, bridge_factory=FakeBridgeFactory())
        host._write({"type": "snapshot", "value": {"answer": 42}})
        self.assertEqual(output.getvalue().count("\n"), 1)
        self.assertEqual(json.loads(output.getvalue())["value"]["answer"], 42)

    def test_stop_does_not_wait_for_blocked_input(self):
        source = BlockingInput()
        factory = FakeBridgeFactory()
        host = BridgeProcessHost(source, io.StringIO(), bridge_factory=factory)
        host_thread = Thread(target=host.run)
        host_thread.start()
        self.assertTrue(source.reading.wait(1.0))
        host.stop()
        host_thread.join(1.0)
        source.forever.set()
        self.assertFalse(host_thread.is_alive())
        self.assertTrue(factory.bridge.stopped)


class FakeBridgeFactory:
    def __init__(self, error=None):
        self.error = error
        self.bridge = None

    def __call__(self, emit):
        self.bridge = FakeBridge(emit, self.error)
        return self.bridge


class FakeBridge:
    def __init__(self, emit, error=None):
        self.emit = emit
        self.error = error
        self.commands = []
        self.started = False
        self.stopped = False

    def run(self, cancelled):
        self.started = True
        cancelled.wait()
        self.stopped = True

    def execute(self, command, parameters=None, *, request_id=None):
        self.commands.append((command, parameters))
        if self.error:
            raise self.error
        return {
            "schema_version": 1,
            "type": "command_response",
            "request_id": request_id,
            "command": command,
            "ok": True,
            "result": {},
            "error": None,
        }


class BlockingInput:
    def __init__(self):
        self.reading = Event()
        self.forever = Event()

    def __iter__(self):
        return self

    def __next__(self):
        self.reading.set()
        self.forever.wait()
        raise StopIteration


if __name__ == "__main__":
    unittest.main()
