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
