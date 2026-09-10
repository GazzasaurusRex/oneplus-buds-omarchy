# Contributing

Start with the [README](README.md) and the recorded evidence under
[`docs/measurements`](docs/measurements). Keep changes focused; reuse verified
evidence rather than repeating hardware tests.

## Compatibility reports

Disable the plugin before using the CLI so only one process owns RFCOMM. Run
`./oneplus-buds diagnostics --report`, review it, and attach it to a compatibility
issue with model name, firmware, Omarchy version and exactly what you observed.
Distinguish a command response from an audible/physical change. Include whether
both earbuds were worn or in their case. Do not include Bluetooth addresses,
pairing data, unrelated devices or raw notification payloads. The latter can
contain information about peer devices. Redact personal text from device names.

Use the [GitHub issue templates](https://github.com/GazzasaurusRex/oneplus-buds-omarchy/issues/new/choose)
for bugs and compatibility reports.

## Adding a device or feature

1. Record transport/service evidence and product identity in `docs/devices/`.
2. Research primary implementations and their licenses; document wire-format
   facts independently. Do not copy code without compatible permission.
3. Add sanitized fixtures and parser/profile tests that run without hardware.
4. Expose only supported, observed data. Unknown feature IDs remain unnamed.
5. Introduce writes only after the command is understood and the user has agreed
   to the hardware test. Verify resulting state independently after each write.
6. Record hardware/firmware and failure cases. Mark community reports separately
   from maintainer hardware verification; do not mark an entire model family
   verified based on another model's result.

OPO framing must not depend on the transport. Add transport implementations below
that boundary; do not put Bluetooth protocol logic in QML. The controller must
remain the sole serialized owner of the RFCOMM session. Unknown products must not
inherit another model's write permissions. BLE transport is not implemented yet.

## Checks

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
python3 tests/run_qml_hover.py
python3 scripts/check_dependencies.py
omarchy plugin validate .
git diff --check
```

Node enables the JS model tests. Qt 6 qmltestrunner enables offscreen interaction
tests. Hardware timing scripts are explicit integration tools, not unit tests:
`scripts/measure_anc.py` changes settings and must not run alongside the plugin.

For a packaging check, export to a new directory with
`python3 scripts/export_plugin.py /tmp/oneplus-review`, validate the export, then
run its `./oneplus-buds --help`. Never publish local caches or private captures.
Live UI testing uses the existing shell and a unique temporary source path when
QML caching requires it; back up configuration, then disable/remove the test
plugin and restore the original configuration afterward. Never restart the user's
shell simply to flush development caches.

Keep docs, manifest and Python version metadata consistent. Add changes under
Unreleased in the changelog until a release is actually tagged. Contributions
are provided under this project's MIT license.
