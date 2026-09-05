# Backend and CLI proof of concept

Status: Phase 1 backend-hardening milestone, 2026-09-05.

## Architecture

- `bluez.py`: connected-device discovery and explicit selection through BlueZ's D-Bus ObjectManager API.
- `transport.py`: Bluetooth Classic RFCOMM sockets, response bursts, and bounded retry for transient `EBUSY` errors.
- `protocol.py`: transport-independent 0xAA framing and response parsers.
- `profiles.py`: product identity, verified compatibility, capabilities, ANC write indices, read aliases, and levels.
- `backend.py`: query/control orchestration and query-after-write verification.
- `cli.py`: argument parsing and JSON presentation only.

Unknown products may be queried safely, but ANC writes require a known profile marked hardware-verified. SET response status `00` is observed on successful changes, while Buds Pro 2 returned `0e` for an already-active mode. Status values are reported but not treated as proof of success or failure: a fresh state query must match the requested mode or level.

`status` also sends the read-only `0x0105` remote-version query. Valid responses retain every numeric component/kind/value record. Firmware display is derived only from kind-2 left/right records, with the case appended when present. On the original Buds Pro this produced `541.541.510`, exactly matching HeyMelody; firmware remains unverified for other profiles.

Discovery uses the system `dbus-python` binding already supplied by Omarchy/Arch rather than parsing `bluetoothctl` output. One ObjectManager snapshot provides Device1 and Battery1 properties, including connection state, UUIDs, aggregate battery, modalias, and service-resolution state. The Python package itself adds no PyPI dependency.

## Commands

Run from the repository root during development:

```bash
PYTHONPATH=src python -m oneplus_buds.cli devices
PYTHONPATH=src python -m oneplus_buds.cli status
PYTHONPATH=src python -m oneplus_buds.cli capabilities
PYTHONPATH=src python -m oneplus_buds.cli anc status
PYTHONPATH=src python -m oneplus_buds.cli anc off
PYTHONPATH=src python -m oneplus_buds.cli anc transparency
PYTHONPATH=src python -m oneplus_buds.cli anc on
PYTHONPATH=src python -m oneplus_buds.cli diagnostics --report
```

Select among multiple connected compatible devices by putting the global option before the command:

```bash
PYTHONPATH=src python -m oneplus_buds.cli --device AA:BB:CC:DD:EE:FF status
```

`devices` prints addresses for connected compatible devices because they are needed for explicit selection. `diagnostics --report` deliberately omits the Bluetooth address and does not enumerate unrelated devices.

## Tests and fixtures

`tests/fixtures/opo_sessions.json` contains sanitised representative frames for both verified products. It contains no Bluetooth addresses or pairing material. Automated tests cover framing, fragmented/concatenated response bursts, product and battery parsing, one- and two-byte ANC bitmaps, write acknowledgements, profile mappings, discovery, selection, diagnostics privacy, and RFCOMM busy retries.

Run:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```
