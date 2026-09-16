# Backend and CLI proof of concept

Status: Phase 1 backend-hardening milestone, 2026-09-05.

## Architecture

- `bluez.py`: connected-device discovery and explicit selection through BlueZ's D-Bus ObjectManager API.
- `transport.py`: Bluetooth Classic RFCOMM sockets, response bursts, and bounded retry for transient `EBUSY` errors.
- `protocol.py`: transport-independent 0xAA framing and response parsers.
- `profiles.py`: product identity, verified compatibility, capabilities, ANC write indices, read aliases, and levels.
- `backend.py`: query/control orchestration and query-after-write verification.
- `api.py` / `models.py`: typed public backend results with JSON compatibility boundaries.
- `session.py`: authenticated long-lived RFCOMM ownership and privacy-safe event polling.
- `cli.py`: argument parsing and JSON presentation only.

See `backend-api.md` for the typed integration API intended for the future frontend.

Unknown products may be queried safely, but ANC writes require a known profile marked hardware-verified. SET response status `00` is observed on successful changes, while Buds Pro 2 returned `0e` for an already-active mode. Status values are reported but not treated as proof of success or failure: a fresh state query must match the requested mode or level.

`status` also sends the read-only `0x0105` remote-version query. Valid responses retain every numeric component/kind/value record. Firmware display is derived only from kind-2 left/right records, with the case appended when present. This produced `541.541.510` on Buds Pro and `196.196.101` on Buds Pro 2, exactly matching HeyMelody for both verified profiles.

`capabilities` performs authenticated notification negotiation, subscribes only to event codes advertised by the selected device, and requests the profile's read-only feature-switch list. Recognised returned IDs are exposed twice: their presence extends the capability set, while `feature_switches` reports current boolean state. Unrecognised IDs and unsolicited payloads are not included, preventing peer-device data from leaking into reports.

Discovery uses the system `dbus-python` binding already supplied by Omarchy/Arch rather than parsing `bluetoothctl` output. One ObjectManager snapshot provides Device1 and Battery1 properties, including connection state, UUIDs, aggregate battery, modalias, and service-resolution state. The Python package itself adds no PyPI dependency.

## Commands

Run from the repository root during development. The executable `./oneplus-buds`
now provides the same interface without setting PYTHONPATH. Disable the Omarchy
plugin before running queries or writes so it does not compete for RFCOMM; re-enable
it afterward. See the root README for dependency and installation instructions.

Equivalent module invocations:

```bash
PYTHONPATH=src python -m oneplus_buds.cli devices
PYTHONPATH=src python -m oneplus_buds.cli status
PYTHONPATH=src python -m oneplus_buds.cli capabilities
PYTHONPATH=src python -m oneplus_buds.cli anc status
PYTHONPATH=src python -m oneplus_buds.cli anc off
PYTHONPATH=src python -m oneplus_buds.cli anc transparency
PYTHONPATH=src python -m oneplus_buds.cli anc on
PYTHONPATH=src python -m oneplus_buds.cli eq status
PYTHONPATH=src python -m oneplus_buds.cli eq list
PYTHONPATH=src python -m oneplus_buds.cli eq set bass
PYTHONPATH=src python -m oneplus_buds.cli eq set custom:4
PYTHONPATH=src python -m oneplus_buds.cli eq custom 5 0 0 0 0 0 0
PYTHONPATH=src python -m oneplus_buds.cli diagnostics --report
```

EQ is earbud-native OPO control, not PipeWire/software processing. `eq status`
returns fresh current state, factory presets and any device-declared custom
definitions. `eq set` accepts listed keys, numeric factory IDs, or `custom:<id>`.
`eq custom` updates only an existing device-returned entry and requires exactly
one whole-dB value per returned band, within its returned limits. Every write
pre-reads state, sends once, and verifies with fresh queries. Unknown devices and
unverified feature/model combinations cannot write.

Select among multiple connected compatible devices by putting the global option before the command:

```bash
PYTHONPATH=src python -m oneplus_buds.cli --device AA:BB:CC:DD:EE:FF status
```

`devices` prints addresses for connected compatible devices because they are needed for explicit selection. `diagnostics --report` deliberately omits Bluetooth addresses, device aliases, user/host identity, home paths, credentials, unrelated devices and raw frames. The panel uses the same dedicated report layer and adds safe cached connection/protocol counters without issuing a hardware command.

## Tests and fixtures

`tests/fixtures/opo_sessions.json` contains sanitised representative frames for both verified products. It contains no Bluetooth addresses or pairing material. Automated tests cover framing, fragmented/concatenated response bursts, product and battery parsing, one- and two-byte ANC bitmaps, write acknowledgements, profile mappings, discovery, selection, diagnostics privacy, and RFCOMM busy retries.

Run:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```
