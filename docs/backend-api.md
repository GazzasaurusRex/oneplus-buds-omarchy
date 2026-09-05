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

It caches an immutable `ControllerSnapshot`, serializes every operation with one lock, and owns at most one `OpoSession`. A refresh or verified write closes the event socket first and restores notification subscription afterward. A polling transport error triggers one immediate reconnect; repeated failures propagate to the caller for service-level backoff. Shutdown always releases the RFCOMM socket.

Safe battery, ANC, and named feature-switch events update cached typed state. Redacted notification codes are retained in a bounded 32-item history, ignored-frame counts are cumulative, and `generation` changes whenever meaningful state/event data is applied. The controller does not start threads or prescribe an event loop; a future daemon, QML bridge, or test harness controls polling cadence and backoff.
