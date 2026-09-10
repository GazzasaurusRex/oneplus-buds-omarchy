# Omarchy integration decision

Status: deployment adapter and first read-only bar widget validated live on Omarchy 4.0.2-1, 2026-09-06.

## Current contract

The installed Omarchy Quattro shell and the current official documentation agree on these requirements:

- One long-running `omarchy-shell` Quickshell process hosts plugins. Plugin entry points are components inside that process, not new `ShellRoot` instances.
- A third-party plugin is a Git repository with `manifest.json` at its root and is installed below `~/.config/omarchy/plugins/<id>/`.
- Manifest schema version 1 requires `id`, `name`, `version`, non-empty `kinds`, and `entryPoints`. The `omarchy.*` ID namespace is reserved, entry points must be safe relative files, and symlinks are rejected.
- A plugin may declare both `service` and `bar-widget`. The shell creates the enabled service once and registers the widget with the active bar.
- Third-party code runs unsandboxed as the user. The installer clones and validates files but runs no install hook or privileged dependency setup.
- `omarchy plugin validate <folder>` is the local validation command. Publication additionally requires a public GitHub repository, README, license, and safe installation/removal.

Primary references:

- [Omarchy shell plugin contract](https://github.com/basecamp/omarchy/blob/quattro/shell/README.md)
- [Omarchy shell architecture](https://github.com/basecamp/omarchy/blob/quattro/docs/omarchy-shell.md)
- [Official custom-plugin guide](https://plugins.omarchy.org/develop.html)
- [Official publication checklist](https://plugins.omarchy.org/publish.html)

The installed `/usr/share/omarchy/shell/README.md`, plugin manifests, `shell.qml`, `PluginRegistry.qml`, and `omarchy-plugin-validate` were also inspected directly. Packaged files remain unmodified.

## Decision

Use a combined schema-v1 `service` + `bar-widget` plugin. Its headless QML service will own exactly one long-lived Python helper through `Quickshell.Io.Process` with stdin enabled:

```text
omarchy-shell (existing process)
  ├─ OnePlus service QML
  │    └─ one Python bridge-host child
  │         └─ BudsFrontendBridge
  │              └─ BudsServiceRunner
  │                   └─ BudsController (sole RFCOMM owner)
  └─ OnePlus bar widget / popup
       └─ reads service state and submits commands to the service
```

The helper and QML service exchange newline-delimited schema-v1 JSON over the child's stdin/stdout. QML uses `SplitParser` for complete output lines and `Process.write()` for command requests. The service holds frontend-safe primitive data; the bar widget never imports Python, opens Bluetooth sockets, or parses OPO packets.

This is smaller and safer than a separately installed user service:

- lifecycle follows plugin enable/disable and `omarchy-shell` startup/shutdown;
- no systemd unit, D-Bus policy, socket path, stale daemon, or second install channel;
- no root access or system-wide configuration;
- stdout is already an event stream, while stdin supplies request/response command routing;
- all operations still converge on one serialized controller.

An in-QML backend was rejected because Quickshell's generic Bluetooth API does not implement the vendor RFCOMM/OPO protocol and protocol code must remain outside QML. One-shot helper processes were rejected because they would repeatedly authenticate, contend for the single RFCOMM channel, lose notifications, and increase polling/wakeups. A standalone user daemon remains a future option only if multiple independent clients become a demonstrated requirement.

## Adapter implementation

`python -m oneplus_buds.bridge_host` implements the selected process boundary. It:

- starts the bridge/service lifecycle in one non-daemon worker;
- reads NDJSON commands on a separate daemon reader so signals are not trapped behind blocking stdin;
- serializes concurrent stdout writes with a lock and flushes each compact JSON record;
- treats stdin EOF, `SIGINT`, and `SIGTERM` as cancellation;
- waits for the service worker and controller shutdown before exiting;
- rejects malformed envelopes before command routing;
- converts unexpected command failures to a generic error without exposing internal details.

The request envelope permits only `request_id`, `command`, and `parameters`. Responses and asynchronous events share stdout and are distinguished by their `type` field. Schema details remain in [frontend-bridge.md](frontend-bridge.md).

Automated lifecycle tests use fake bridges and no Bluetooth hardware. They cover normal request routing, malformed input, internal failures, compact one-record-per-line output, EOF shutdown, and cancellation while input remains blocked.

## Minimal plugin scaffold

The repository root is now directly installable as an Omarchy plugin checkout:

- `manifest.json` declares `oneplus-buds.control` as a combined `service` and `bar-widget`, defaulting to the right section.
- `oneplus-buds-bridge` is an executable checkout-local launcher that imports the bundled `src/` tree. This avoids relying on an install hook or prior Python-package installation.
- `Service.qml` starts exactly one bidirectional helper after the shell injects the manifest source directory. It parses schema-v1 lines through `BridgeModel.js`, exposes primitive connection/snapshot/response state, sends refresh and ANC requests over stdin, suppresses raw stderr, and stops the helper when unloaded.
- `BarWidget.qml` resolves the shared service through `bar.shell.serviceFor("oneplus-buds.control")` but remains invisible and zero-width. It exists only to prove the combined plugin shape before visual work begins.

`omarchy plugin validate .` passes. The Python suite covers the manifest, executable launcher, one-helper constraint, shared-service lookup, hidden placeholder, and JavaScript parser/reducer. Direct launcher EOF testing emits valid lifecycle NDJSON and exits cleanly.

The running-shell test is still pending: canonical IPC reported `omarchy-shell is not running` in the development session. No second Quickshell instance was started. In a graphical session, temporarily enable the plugin and verify helper startup, service lookup, logs, and clean disable/removal before replacing the hidden widget with visual UI.

## Read-only status widget

`BarWidget.qml` now uses the shared service snapshot to present connection and only valid battery components actually returned by the backend. `BarModel.js` validates percentages, orders left/right/case fields, marks charging only when explicitly true, and omits absent, invalid, and unknown fields. The bar uses Omarchy's current font, foreground, spacing, geometry, and tooltip primitives and exposes a read-only IPC status record for lifecycle checks.

A fresh live load on the connected Buds Pro 2 reported `connected`, a populated address-free snapshot, and `L 100%⚡  R 100%⚡  C 100%`. Omarchy reported the widget visible at height 26 and width 195. No earbud setting command was sent. A missing `Quickshell.Io` import was found by the first live compile, fixed, regression-tested, and verified on a new component URL without restarting the graphical shell.

## Next implementation boundary

The bar popup now provides the smallest capability-driven ANC surface. `BarModel.js` orders known modes but includes any future mode explicitly advertised by `anc_modes`; the widget rejects unsupported selections, prevents overlapping requests, correlates the response by request ID, and reports success only when the bridge returns `result.verified === true`. Pending and failed states remain visible in the popup.

A live Pro 2 click from Off to Transparency completed through QML → shared service → bridge → serialized controller → authenticated write → independent query-after-write verification. The popup reported “Verified on earbuds,” and read-only IPC independently returned `current_anc: transparency`, `pending: false`, and no error. The user observed that applying the change felt slow. This matches the deliberately conservative write authentication, verification connection, and monitoring-session reauthentication path; it was not shortened without repeated timing evidence on both reference models.

## Compact hover presentation

The ANC latency milestone is complete; see the
[recorded measurements](measurements/anc-baseline.md). Do not repeat those cycles
for presentation work.

The bar now rests at icon width and reveals only available batteries on hover.
Its implicit width animates for 180 ms with OutCubic easing, matching the installed
ActiveWindow widget convention; clipped content cannot paint over neighbours.
Pointer exit starts a 300 ms collapse delay, re-entry cancels it, and an open popup
holds the width stable. The entire width is a single click target. The panel shows
battery/connection information even when no ANC modes are supported. Vertical bars
keep the icon compact and provide battery information in the panel and tooltip.

`python tests/run_qml_hover.py` exercises the actual widget with Qt mouse events,
width animations and timers using fake shell services and popup/IPC primitives.
It covers idle/expanded widths, expanded-area clicking, popup hold, delayed collapse,
re-entry, partial/absent batteries and disconnection. It does not start Quickshell
or contact earbuds. Qt 6 qmltestrunner is required only for this development test.

Live validation passed in the existing Omarchy shell on 2026-09-07: idle width
23.1875 px expanded to 120.5 px for L/R=100%, with clean neighbour geometry and
collapse after pointer exit. The user confirmed clicking the expanded battery area
opens the panel as expected. No ANC setting was changed. No plugin-specific runtime
errors appeared. Cleanup stopped the helper, removed the temporary plugin, restored
shell configuration byte-for-byte, and preserved shell PID 1025.

The panel now uses a portrait layout (320 logical px wide) with native full-width
Buttons grouped into Noise control and ANC strength. A vertical scroll viewport
and PopupCard height cap keep controls reachable on smaller screens; text wraps.
Main noise cancellation remains visibly selected when an explicit strength is
active. Keyboard focus reveals offscreen buttons. Live geometry reports 320×425;
the user accepted the live layout as easy to read and navigate. Temporary-install
cleanup passed, with exact configuration restoration, helper shutdown and no shell
restart. Publication documentation and dependency/export checks are now complete; see
[publication preparation](publication.md). Public repository selection, remote
installation verification and marketplace submission remain outstanding.
