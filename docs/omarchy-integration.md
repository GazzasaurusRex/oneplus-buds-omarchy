# Omarchy integration decision

Status: deployment adapter selected and lifecycle-tested on Omarchy 4.0.2-1, 2026-09-06. No QML interface has been built yet.

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

## Next implementation boundary

The next milestone should scaffold the minimal combined plugin manifest and headless `Service.qml` adapter, plus model-level QML/JavaScript tests where practical. It should prove helper startup, line parsing, command writes, service sharing, plugin validation, and clean unload before implementing the visual bar widget or control panel.
