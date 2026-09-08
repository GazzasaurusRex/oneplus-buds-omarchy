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
- `eq_status` with no parameters: freshly reads native EQ state and device-declared
  custom capabilities on the existing authenticated session.
- `set_eq` with exactly `{"preset": "..."}`: selects only a verified factory key
  or device-declared custom ID and refreshes the emitted state after read-back.
- `set_custom_eq` with exactly `{"entry_id": number, "gains_db": [integers...]}`:
  delegates strict band-count/range validation to the device capability layer,
  sends once, and emits only freshly verified state.

Every call returns a `command_response` dictionary containing the schema version, request ID, command, `ok`, `result`, and `error`. Unknown commands and malformed parameter objects are rejected without hardware access. Runtime command errors are address-redacted. The bridge does not add unverified controls or bypass backend capability/profile checks.

## Process adapter

`python -m oneplus_buds.bridge_host` carries the same contract over newline-delimited JSON for the future Omarchy QML service. Asynchronous connection/snapshot events and command responses share stdout and are distinguished by `type`; requests arrive on stdin. EOF, `SIGINT`, and `SIGTERM` cancel the runner and wait for controller shutdown.

The deployment rationale and Omarchy lifecycle are documented in [omarchy-integration.md](omarchy-integration.md). This is a private child-process protocol owned by the plugin, not a public system-wide IPC service.

ANC responses now carry additive `result.timings_ms` on success and
`error.timings_ms` on expected timed failures. See [ANC phase timing](backend-api.md#anc-phase-timing)
for units, nested totals, privacy scope, and the completed two-model hardware measurements.
Timing values do not imply successful verification; consumers must still check
`ok` and `result.verified`.

Main On/Off/Transparency requests now reuse the running controller's authenticated
session and existing subscriptions. Success still requires a fresh, correlated
state query. The result and matching snapshot are captured atomically, and no
monitoring restoration blocks successful response delivery. Cold/legacy paths
retain conservative authentication; see the timing documentation for scope.
