# Typed backend API

Status: pre-UI backend boundary, verified 2026-09-05.

`BudsBackend` is the stable typed entry point for future integrations. Existing dictionary-returning functions remain as compatibility wrappers for the JSON CLI.

```python
from oneplus_buds import BudsBackend

backend = BudsBackend()
devices = backend.discover()          # cheap BlueZ D-Bus snapshot
status = backend.status()             # one-shot OPO query
capabilities = backend.capabilities() # authenticated feature probe
result = backend.set_anc("off")       # verified write
```

The return types are immutable dataclasses in `models.py`: `StatusResult`, `CapabilityResult`, and `ControlResult`. Each has an explicit `to_dict()` boundary for JSON presentation. Bluetooth transport and protocol objects do not leak into callers.

## Long-lived event session

`open_session()` returns an `OpoSession` context manager owning one RFCOMM connection:

```python
with backend.open_session() as session:
    initial = session.authenticate_and_subscribe()
    updates = session.poll(0.5)
```

Authentication and notification discovery happen once per session. Subscription requests contain only event codes advertised by that device. `poll()` returns an immutable `EventBatch` containing typed `SafeEvent` objects and a count of ignored frames.

The privacy boundary is intentionally strict:

- Battery, ANC, and feature-switch responses are decoded only by validated parsers.
- Unmapped `0x0204` notifications expose only their first-byte event code.
- Unknown responses are counted but their commands and payloads are not returned.
- Raw peer-device notifications are never included in API results, diagnostics, or fixtures.

Current limitation: asynchronous `0x0204` payload schemas are not sufficiently verified to expose state beyond their event code. A long-lived session also owns the earbuds' single RFCOMM control channel, so one-shot commands should not run concurrently with it. The future service layer should serialize operations through one session owner.

## Serialized controller

`BudsController` is the UI-independent state owner above `BudsBackend`:

```python
from oneplus_buds import BudsController

controller = BudsController()
snapshot = controller.start()
snapshot = controller.poll(0.5)
result = controller.set_anc("off")
snapshot = controller.shutdown()
```

It caches an immutable `ControllerSnapshot`, serializes every operation with one lock, and owns at most one `OpoSession`. Startup discovers a device, identifies its product/profile, authenticates, and reads essential battery/ANC state on one RFCOMM socket. The first usable snapshot is published at that point; subscription setup and firmware then populate on the same session. A refresh or legacy write closes the event socket first and restores notification subscription afterward. Main On/Off/Transparency writes on a running controller retain the authenticated socket and subscriptions, verify through fresh sequence-correlated state queries, and return immediately after verification. Explicit ANC levels and one-shot calls retain the legacy path. A polling transport error triggers one immediate reconnect; repeated failures propagate to the caller for service-level backoff. Shutdown always releases the RFCOMM socket.

Safe battery, ANC, and named feature-switch events update cached typed state. Redacted notification codes are retained in a bounded 32-item history, ignored-frame counts are cumulative, and `generation` changes whenever meaningful state/event data is applied. The controller does not start threads or prescribe an event loop; a future daemon, QML bridge, or test harness controls polling cadence and backoff.

## Service runner

`BudsServiceRunner` adds connection lifecycle policy without taking transport ownership away from `BudsController`. Its blocking `run(cancelled)` method can be hosted by a daemon thread, service process, or future frontend bridge:

```python
from threading import Event
from oneplus_buds import BudsServiceRunner

cancelled = Event()
runner = BudsServiceRunner(
    on_state=lambda state: print(state.connection),
    on_snapshot=lambda snapshot: render(snapshot),
)
runner.run(cancelled)
```

Connection failures publish a `disconnected` state with the attempt number, retry delay, and address-redacted error text. Retries start at one second, double to a 30-second ceiling, and reset after a successful connection. The plugin host's BlueZ availability watcher interrupts a pending wait when a compatible Device1 becomes connected, but fresh discovery remains authoritative and failed attempts continue normal backoff. If the optional watcher cannot start, timer recovery is unchanged. Cancellation interrupts backoff immediately; steady-state cancellation latency is bounded by the configured poll interval (0.5 seconds by default). `run()` always shuts down the controller and publishes a final `stopped` state and disconnected snapshot. The runner itself creates no thread or event loop; the process host owns and closes the watcher's GLib thread.

## Frontend bridge

`BudsFrontendBridge` converts service callbacks and controller results into versioned, address-free, JSON-compatible payloads. It exposes cached snapshot, refresh, and verified ANC commands while retaining `BudsController` as the only RFCOMM owner. Its dispatcher hook lets a future integration marshal service-thread callbacks onto the QML event loop without importing Bluetooth or protocol code into QML.

The complete schema and command rules are documented in [frontend-bridge.md](frontend-bridge.md).

## ANC phase timing

Verified `ControlResult` now includes additive `timings_ms` data, automatically
included in CLI JSON and bridge results. Durations use a monotonic clock; keys
are fixed phase names and values are elapsed milliseconds. No absolute timestamp,
Bluetooth address, user-supplied label, or raw frame is added to timing records.

Backend phases cover discovery, write connection (including retries), profile
queries, HELLO, REGISTER, SET exchange, write close, independent verifier
connection (including retries), verifier query, and verifier close. Exchanges
include the existing conservative waits and receive-burst drain time.
`backend_total` also includes parsing and validation overhead.

Controller results add `controller_lock_wait`, `monitor_close`,
`backend_request`, `monitor_resume`, and `controller_total`. `backend_request`
contains the backend phases: do not add it or the totals to those phases when
computing a breakdown. Controller total ends after notification resubscription;
it excludes bridge dispatch, process I/O, and QML rendering. This separates
verified hardware latency from the additional wait before the UI receives success.

Expected failures raise `AncRequestError` (a `RuntimeError`) with `timings_ms`.
The bridge includes it in `error.timings_ms`. Completed phases remain available;
`failed_phase`/`failed_controller_phase` measure the uncompleted tail since the
last checkpoint, including exception cleanup. `monitor_recovery` measures the
existing recovery attempt, which may itself fail; its presence is not evidence
of a connected session. Existing error strings are not part of the privacy-safe
timing export.

### Hardware measurement

With only the selected reference model connected, both earbuds out of the case
and in use, and no other plugin/helper owning RFCOMM, run from the checkout:

```sh
PYTHONPATH=src python scripts/measure_anc.py --product 062014 --run
```

Use `060C14` for original Buds Pro. The explicit hardware command checks product
identity before writing and performs two Off → Transparency → On → Off cycles,
including an initial Off request per cycle. Each write retains independent
read-back verification and monitoring resubscription. Output is restricted to
product/firmware, requested/observed modes, SET status, verification, and phase
durations. It stops on the first failure, releases the controller, and does not
attempt an unverified restoration; successful completion ends Off.

The Pro 2 baseline was collected on 2026-09-06: all eight requests verified,
including six actual transitions, ending Off. Median controller duration was
15.13 seconds (8.43 seconds backend and 6.70 seconds monitoring resumption).
Original Buds Pro also passed all eight requests with the same rounded medians,
ending Off. Both baselines are complete; see [baseline findings](measurements/anc-baseline.md)
for the completed optimization and before/after comparison.
Confirm one physical test sequence with the user before running. Compare repeated successful transitions on both
models before proposing delay changes. These measurements instrument the
already-verified control path; they are not a repeat of baseline compatibility
or shell-lifecycle testing.


### Persistent-session result timings

For main modes on a running controller, `set_response`, `verify_query`, and
`session_total` replace the legacy backend phase breakdown. `command_sent_elapsed`
and `verified_elapsed` are cumulative milliseconds from the session method's
entry; they are not additive phases and exclude controller lock wait/setup.
`controller_total` includes those outer costs. `verification_queries` is a separate
integer count, not a duration. There is no `monitor_resume` on a successful warm
request because its session/subscriptions remain connected.

The service polls without blocking inside the controller lock and waits its
interval outside it. A failed fast transaction closes its uncertain session,
clears cached ANC, and returns failure without replaying the write or waiting for
monitoring restoration; polling handles recovery. `set_anc_with_snapshot()` returns
a result/snapshot pair captured under the same lock, used by the bridge to avoid
waiting behind a later reconnect just to serialize already-verified state.

## Switching physical devices

Automatic selection is a lifecycle policy, separate from the active Bluetooth
address. After a polling transport failure, the controller closes the old
session, clears its status, feature switches, advertised/observed event codes,
and ignored-frame count, then reruns BlueZ connected-device selection. A newly
selected device gets fresh product/battery/ANC queries and a new profile-specific
authenticated session. Subscription and firmware follow on that same socket
after the usable snapshot. No model-pair special case is involved. Recovery
after a failed control session follows the same path.

Failed discovery or authentication leaves an empty disconnected snapshot. The
runner publishes that snapshot before retry backoff, so the frontend removes the
old model, batteries and controls while no compatible device is available.
Retries retain the existing one-to-30-second interruptible backoff. Generation
and reconnect counters describe the controller lifetime; device data does not.
Shutdown also clears device state. Refresh starts a fresh authenticated lifecycle.

An explicitly supplied controller address remains pinned across retries. Automatic
selection still rejects multiple simultaneously connected compatible devices;
it does not arbitrarily choose one. Error redaction works after active identity
has been cleared. The read-only widget IPC status includes address-free device
status, session connection and generation for lifecycle verification.
