# OnePlus Buds Control for Omarchy

A native Omarchy bar widget and Linux backend for OnePlus earbuds. Check battery
levels and change noise control from a compact, theme-aware panel.

**Status: pre-release 0.0.1.** Buds Pro and Buds Pro 2 have hardware-verified basic
controls. This is an independent project, unaffiliated with OnePlus or OPPO.

## What works

- Automatic selection of one connected compatible OnePlus device.
- Connection status, left/right battery, case battery when returned, and firmware.
- Independently verified ANC On, Off, Transparency and profile-supported strengths.
- Native earbud EQ presets on both models, plus device-defined custom EQ on Pro 2.
- Icon-only idle widget; hover reveals known batteries, with delayed collapse.
- Portrait panel with grouped, full-width controls, theme integration and vertical scrolling.
- A privacy-safe diagnostic report for compatibility investigations.

| Device | Evidence | Tested firmware | ANC strengths |
|---|---|---|---|
| OnePlus Buds Pro | Verified on hardware | 541.541.510 | Light, Deep, Smart |
| OnePlus Buds Pro 2 | Verified on hardware | 196.196.101 | Light, Medium, Deep, Smart |
| Other OnePlus devices | Experimental if recognised; no verified controls | Unknown | Not exposed |

See [compatibility and limitations](docs/devices/compatibility.md). Gestures,
spatial audio and other HeyMelody features are not implemented controls.

## Requirements

Tested with Omarchy **4.0.2-1**, its Quickshell/Quattro shell, BlueZ 5.87 and Python
3.14.7. Python 3.11+ is required; older Python releases have not been tested here.
The native widget needs Omarchy's `qs.Ui` and `qs.Commons` modules, not a standalone
Quickshell session. Other desktop environments can use the CLI only.

Runtime dependencies are system Python, `python-dbus`, BlueZ and the running
Omarchy shell. `bluez-utils` provides Bluetooth setup/diagnostic commands. No PyPI
packages, separate daemon, root access or audio-configuration changes are needed
for normal operation. Check prerequisites from this checkout:

```bash
python3 scripts/check_dependencies.py
systemctl is-active bluetooth
```

If the binding is missing on Omarchy, `omarchy pkg add python-dbus` installs the
Arch package and may request administrator authorization. Use system Python;
isolated virtual environments generally do not see that binding. The preflight
checks availability only and does not connect to the earbuds.

## Install and remove

Install from GitHub using Omarchy's supported installer:

```bash
omarchy plugin add https://github.com/GazzasaurusRex/oneplus-buds-omarchy.git
python3 "$HOME/.config/omarchy/plugins/oneplus-buds.control/scripts/check_dependencies.py"
omarchy plugin enable oneplus-buds.control --section right
```

If the installer offers to enable immediately, decline until the dependency check
passes. This is a development snapshot; no tagged release is available yet.

For an existing local checkout, copy it into the user plugin directory without
Git internals or caches. The destination must not already exist:

```bash
python3 scripts/export_plugin.py "$HOME/.config/omarchy/plugins/oneplus-buds.control"
omarchy plugin validate "$HOME/.config/omarchy/plugins/oneplus-buds.control"
omarchy-shell shell rescanPlugins
omarchy plugin enable oneplus-buds.control --section right
```

The exporter writes only to the new destination. Enabling uses Omarchy's supported
layout API; it does not replace your shell configuration. Run these commands inside
your existing Omarchy graphical session. Do not start another Quickshell instance.

See [publication notes](docs/publication.md) for release and marketplace status.
Installation has no dependency hook, so run the dependency check before enabling.

To stop the helper and hide the widget:

```bash
omarchy plugin disable oneplus-buds.control
```

To remove it:

```bash
omarchy plugin remove oneplus-buds.control
```

Omarchy asks for confirmation; it backs up a copied directory or removes a
Git-managed installation. This does not unpair earbuds or change their last ANC
mode. Removal affects the plugin's layout entry, not unrelated bar settings.

## Use

Pair and connect your earbuds through Omarchy's Bluetooth panel first. This plugin
does not pair devices or connect audio. Keep only one compatible device connected
when using the bar; multi-device selection currently exists only in the CLI.

Hover the earbuds icon to see available battery values. Click anywhere on the
expanded widget to open the panel. Noise control and ANC strength appear only when
supported. Selected controls reflect read-back state. A pending request is shown
until verified; an acknowledgement alone never produces a success message.

Wear the earbuds for ANC tests: devices in their case may reject changes. Main
ANC On may choose a device-dependent strength; select a specific strength if you
need one. Cold setup and explicit strengths still take several seconds. Warm main
mode changes reuse the authenticated session; recorded timings are in
[the measurement notes](docs/measurements/anc-baseline.md).
Native EQ controls live only in the opened panel. Both models show verified
factory presets; Pro 2 also shows controls generated from its returned custom-band
definition. Changes are written to the earbuds and persist independently of the
Linux audio route—no system-wide software EQ is installed or configured.
Connection startup uses BlueZ availability notifications while retaining bounded
retry fallback; both models' phase-by-phase results are in the
[connection lifecycle measurements](docs/measurements/connection-lifecycle.md).

## CLI and diagnostic reports

The included executable needs no package installation. **Disable the plugin before
running CLI queries or diagnostics**: both use the device's single RFCOMM control
channel. Re-enable afterward to resume monitoring.

```bash
omarchy plugin disable oneplus-buds.control
./oneplus-buds devices
./oneplus-buds status
./oneplus-buds anc status
./oneplus-buds eq status
./oneplus-buds eq list
./oneplus-buds eq set balanced
./oneplus-buds diagnostics --report
omarchy plugin enable oneplus-buds.control --section right
```

Use `./oneplus-buds --help` for all commands. Explicit selection puts
`--device ADDRESS` before the command. `devices` prints Bluetooth addresses for
selection; do not paste it into public issues. `diagnostics --report` omits Bluetooth
addresses and unrelated devices. Review the report before sharing and redact any
personal text in a custom device name. Do not post raw packet captures or pairing
material. See [CLI details](docs/backend-cli.md).

## Troubleshooting

- **Disconnected icon:** connect earbuds in the Bluetooth panel, check the daemon,
  and ensure only one compatible device is connected. Recovery backs off to 30 s.
- **Missing dbus binding:** run the preflight with system Python and install
  `python-dbus`; pip-only environments are not sufficient.
- **Busy control channel:** disable this plugin before CLI/hardware tools. Also
  close other earbud-control applications; do not restart Bluetooth unnecessarily.
- **ANC change fails:** take both earbuds out of the case, wear them and retry.
  The UI keeps failure visible rather than assuming a change succeeded.
- **Case battery absent:** some responses do not include it; the UI hides missing
  fields. Charging/presence semantics still need deliberate edge-case testing.
- **A physical gesture is not reflected immediately:** notification payload mapping
  is incomplete. Reopening the popup alone does not query fresh hardware state.
  For a fresh check, disable the plugin, query with the CLI, then re-enable it.
- **Widget fails to load:** validate the installed folder and inspect shell logs for
  plugin-specific errors. During development, a unique exported source path may be
  needed because the long-running shell caches QML URLs. See the [integration notes](docs/omarchy-integration.md).

## Development

The backend separates BlueZ discovery, RFCOMM transport, OPO framing, profiles,
features, typed APIs, serialized session ownership and the frontend bridge. QML
owns presentation and one child-process helper; protocol code stays in Python.
See [architecture](docs/backend-api.md), [bridge](docs/frontend-bridge.md),
[protocol](docs/protocols/OPOv1.md) and [contributing](CONTRIBUTING.md).

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
python3 tests/run_qml_hover.py
omarchy plugin validate .
```

Node runs the JavaScript model checks when available. Qt 6 `qmltestrunner` is needed
for the offscreen UI check, which stubs shell services and never contacts hardware.
The Python package metadata is for backend-only distribution; the Omarchy plugin
uses the full repository/export, not a wheel. Building a wheel separately requires
setuptools >=77; that is not a plugin runtime dependency.

## License

MIT; see [LICENSE](LICENSE) and [research provenance](docs/research/open-source.md).
