# Frontend bridge contract

Status: pre-QML bridge boundary, schema version 1, 2026-09-06.

`BudsFrontendBridge` is the UI-toolkit-neutral boundary between the hardware-verified service runner and a future Omarchy frontend. It does not create a process, thread, socket, D-Bus name, or QML object. Those deployment choices remain deliberately open until current Omarchy integration requirements are inspected.

The bridge owns one `BudsServiceRunner`, and the runner and all routed commands share one `BudsController`. The controller remains the sole RFCOMM session owner and serializes polling, refreshes, and verified writes.

## Lifecycle and event dispatch

`run(cancelled)` blocks until the supplied `threading.Event` is set. The bridge accepts two frontend integration callbacks:

- `emit(event)` receives schema-versioned, JSON-compatible dictionaries.
- `dispatch(callback)` schedules delivery onto the consumer's event loop. If omitted, delivery is synchronous. A QML integration must supply a queued dispatcher rather than touching UI state from the service thread.

Events have `schema_version: 1` and one of these shapes:

```json
{
  "schema_version": 1,
  "type": "connection",
  "connection": "connected",
  "attempt": 0,
  "retry_delay": null,
  "error": null
}
```

```json
{
  "schema_version": 1,
  "type": "snapshot",
  "snapshot": { "generation": 3 }
}
```

Connection values are `connecting`, `connected`, `disconnected`, `reconnecting`, and `stopped`. Errors are address-redacted.

## Snapshot contract

`serialize_snapshot()` includes device/status data, compatibility, static and device-observed capabilities, supported ANC modes, named feature-switch state, session state, safe numeric event-code history, reconnect/ignored-frame counters, and generation. Tuples are converted to JSON arrays and mappings are copied.

Bluetooth addresses, raw OPO frames, pairing data, and raw notification payloads are never included. Unknown products are marked `experimental` and receive no inferred write modes or static capabilities.

## Commands

`execute(command, parameters, request_id=...)` currently accepts only:

- `snapshot` with no parameters: returns the cached state without Bluetooth I/O.
- `refresh` with no parameters: performs a serialized one-shot refresh and emits the resulting snapshot.
- `set_anc` with exactly `{"mode": "..."}`: uses the existing authenticated, profile-gated, query-after-write verified controller path and emits the resulting snapshot.

Every call returns a `command_response` dictionary containing the schema version, request ID, command, `ok`, `result`, and `error`. Unknown commands and malformed parameter objects are rejected without hardware access. Runtime command errors are address-redacted. The bridge does not add unverified controls or bypass backend capability/profile checks.

This is an in-process contract, not yet a public IPC protocol. If a later service process is required, its D-Bus or socket surface should carry these versioned payloads rather than exposing Python transport objects.
