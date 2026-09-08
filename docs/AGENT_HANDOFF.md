# Agent handoff

Last updated: 2026-09-08. Phase 1 protocol proof, backend hardening, two-model verification, typed API/session, serialized controller, service runner, frontend bridge, Omarchy deployment adapter, live lifecycle, battery/status widget, verified ANC control-surface, two-model ANC timing baseline, persistent-session ANC optimization, accepted portrait panel, and GitHub publication milestones complete.

## Current status

The no-PyPI-dependency backend now sits inside a validated, minimally installable Omarchy plugin with a live-tested battery/status widget and capability-driven ANC popup. The layers remain separated: BlueZ D-Bus discovery, RFCOMM transport, OPO parsing, profiles/capabilities, typed backend, privacy-safe session, serialized controller, resilient service runner, schema-v1 frontend bridge, NDJSON child-process host, headless QML service adapter, and native Omarchy presentation. The checkout-local launcher imports the bundled `src/` tree because Omarchy plugin installation runs no install hooks. `BudsController` remains the sole RFCOMM owner; QML receives only address-free primitive state and routes verified commands over the bridge. Both reference models retain their previously verified detection, firmware, battery, and ANC coverage.

This handoff accompanies `perf: reuse authenticated sessions for verified ANC control`. Test command `PYTHONPATH=src python -m unittest discover -s tests` passes all 79 tests on Python 3.14.7. `omarchy plugin validate .` passes on Omarchy 4.0.2-1.

## Verified discoveries

- Host originally inspected on Omarchy 4.0.1-1 and currently running Omarchy 4.0.2-1; BlueZ 5.87, Python 3.14.7; `bluetooth.service` is active.
- Connected reference devices are reliably discovered through BlueZ's D-Bus ObjectManager; the earlier `bluetoothctl` parser has been removed.
- Device exposes HeyMelody vendor SPP UUID `00001107-d102-11e1-9b23-00025b00a5a5`, Serial Port, and vendor UUID `66666666-6666-6666-6666-666666666666`.
- No remote GATT services/characteristics are exposed as BlueZ objects. RFCOMM channel 15 accepts a connection, so Classic RFCOMM is the verified likely control transport.
- BlueZ standard Battery1 provides an aggregate percentage.
- Research identifies product ID `060C14` as the OnePlus Buds Pro and corroborates OPO 0xAA framing, battery query `0x0106`, ANC query `0x010c`, and ANC set `0x0404`.
- Hardware read-only queries returned product ID `060C14`, per-component battery values (L=100%, R=100%, case=80%), and ANC Off. Both earbuds had the protocol charging bit set.
- Real responses arrive in bursts and may concatenate acknowledgements with unsolicited notifications; the transport drains each burst and the framer separates it by outer length.
- A user-initiated physical switch to ANC On returned bitmap `08`, proving the query parser and revealing the original Buds Pro's profile-specific ANC mapping. Earlier write attempts used an incompatible generic mapping.
- The parser now maps Buds Pro Off=`01`, Transparency=`02`, and ANC levels light=`04`, deep=`08`, smart=`10`. The physical transition verified deep ANC `08`.
- Control requires HELLO, a 2-second wait, REGISTER with the observed token, and a 1.5-second wait. Unauthenticated writes were ignored or misleading.
- Authenticated writes use the Buds Pro profile bitmap, not the newer-device set enum. Off=`01`, Transparency=`02`, light ANC=`04`, deep ANC=`08`, smart ANC=`10`.
- Authenticated SET returned `0x8404:00`; Off, Transparency, and deep ANC On were each verified by a fresh read-only session. That earlier Buds Pro test ended with ANC On; it is not the current Pro 2 state recorded below.
- Buds Pro 2 advertises OPO UUID `0000079a...`, uses RFCOMM channel 15, and returns product ID `062014`. It exposes BR/EDR/SPP/HID but no BlueZ remote GATT characteristic objects or LE bearer in the tested connection.
- Existing detection, transport, 0xAA framing, product query, component battery parser, HELLO/REGISTER authentication, and SET flow work unchanged on Pro 2.
- Pro 2 ANC needs a two-byte-capable profile: main Off index 0, ANC index 1, Transparency index 2; Deep/Medium/Light/Smart indices 4/5/6/7; observed Transparency read alias index 8.
- Pro 2 Off, Transparency, ANC On, Deep, Medium, Light, and Smart all passed fresh query-after-write verification. Generic ANC On enables the parent mode but does not reliably preserve the visible level: a later verified On command moved Deep to Smart. Explicit level commands remain deterministic.
- Backend hardening adds bounded RFCOMM `EBUSY` connection retries, explicit `--device` selection, profile-driven `capabilities`, and a privacy-safe `diagnostics --report` command.
- The live Buds Pro 2 diagnostics report was verified to omit its Bluetooth address and unrelated devices. `devices` shows only connected compatible addresses for explicit selection.
- Sanitised representative session fixtures cover both verified products without addresses or pairing data. The expanded suite covers framing, bursts, profiles, acknowledgements, discovery/selection, diagnostics privacy, and retry behavior.
- A live hardened-backend check identified Pro 2 product `062014`, all expected profile capabilities, and batteries L/R/case=100%. Both earbuds reported charging and ANC Off. A repeated Off request returned SET status `0e` but independently verified as Off; a Transparency request also returned `0e` and independently remained Off. This proves SET status alone is insufficient and that the verifier correctly refuses to report an unconfirmed transition.
- With both Pro 2 earbuds out of the case and in use, two consecutive Off → Transparency → ANC On → Off cycles passed. All six actual transitions returned SET status `00` and matched fresh-session read-back; ANC On reported the retained Smart level. The device was restored to ANC Off.
- With both original Buds Pro earbuds out of the case and in use, two consecutive Off → Transparency → ANC On → Off cycles also passed. All six actual transitions returned SET status `00` and matched fresh-session read-back; ANC On reported Deep. A phone-assisted physical check resolved a momentary subjective ambiguity and confirmed all three labels behaved correctly. After reconnecting to the PC, product `060C14`, L/R=80%, not charging, and ANC Off were independently confirmed.
- Discovery now calls BlueZ's `org.freedesktop.DBus.ObjectManager.GetManagedObjects` through the system `dbus-python` binding. It obtains Device1 and Battery1 data in one snapshot, eliminating `bluetoothctl` subprocesses and text parsing while adding no PyPI dependency on this Omarchy host.
- Live direct-D-Bus discovery and end-to-end status were verified on the original Buds Pro. The privacy-safe diagnostic report includes modalias, service-resolution state, and discovery method while still omitting the Bluetooth address and unrelated devices. `ServicesResolved` was false in one live snapshot despite cached UUIDs and working RFCOMM, so it is informational rather than a compatibility gate.
- A repeated original Buds Pro `0x0100` query returned capability payload `00bf17682604`. Its feature bits remain unmapped. The existing read-only `0x010d` batch-status request returned no frame in that unauthenticated session, so dynamic feature state remains deliberately unreported.
- Read-only remote-version command `0x0105` returned eight structured ASCII records on product `060C14`. Kind-2 values for left/right/case format as `541.541.510`, exactly matching the version the user checked on the phone. The normal status and diagnostics APIs expose both the verified firmware string and lossless records. The same generic parser is hardware-verified on Pro 2 as described below.
- Authenticated notification discovery on `060C14` advertised seven event codes (`01 02 03 04 06 08 0a`). Subscribing only to those codes returned a successful `0x8205` response and an immediate `0x0204` snapshot. The same session's `0x010d` query still returned no frame, so batch feature state remains unresolved.
- Buds Pro 2 `0x0105` returned nine records, including extra kind-4 records. Kind-2 left/right/case values format as `196.196.101`, exactly matching the phone. Firmware is now verified for both reference profiles.
- Pro 2 notification discovery advertised ten event codes (`01 02 03 04 08 0b f1 f2 f3 0a`), and its subscription response shape differs from the original model. A subsequent `0x810d` returned six feature switches. The capability API safely reports recognised support/current state for wear detection, hearing enhancement, multipoint, high-quality audio, and low latency; ID `0x05` remains unnamed.
- An unsolicited Pro 2 notification contained peer-device information. Raw notification payloads are never surfaced by the capability API or privacy-safe diagnostics; only explicitly recognised boolean feature fields are returned.
- `BudsBackend` is now the typed public boundary. It separates cheap D-Bus discovery, one-shot `StatusResult`, authenticated `CapabilityResult`, verified `ControlResult`, and long-lived `OpoSession`; legacy dict functions remain only as CLI-compatible wrappers.
- A live Pro 2 session authenticated/subscribed once, retained the ten advertised event codes, returned redacted notifications for event codes 6 and 2, counted four ignored setup frames, and leaked no raw payload. Unit fixtures prove peer-identifying text cannot escape through `EventBatch`.
- `BudsController` now serializes access, caches typed snapshots, closes/reopens the event session around one-shot refreshes and verified writes, applies safe events, bounds notification-code history, reconnects once after polling transport failure, and shuts down deterministically. It intentionally owns no thread/event loop.
- `BudsServiceRunner` now wraps the controller with a blocking, thread-agnostic run loop. It publishes connecting/connected/disconnected/reconnecting/stopped states and snapshots, retries expected connection failures with interruptible exponential delays capped at 30 seconds, resets backoff after connection, and always shuts down on cancellation or unexpected exit.
- A live Pro 2 service-runner test detected the closed-case disconnect, backed off at 1, 2, then capped 4-second intervals, recovered automatically through the same runner when the earbuds reconnected, re-authenticated/subscribed, and resumed polling. Cancellation published `stopped`, returned a disconnected snapshot, and released the RFCOMM socket.
- Live testing revealed that BlueZ selection failures include the selected Bluetooth address in their message. Service callback errors now redact that address; a regression test protects this privacy boundary.
- `BudsFrontendBridge` now serializes controller snapshots into schema-v1 JSON-compatible data containing compatibility, capability-driven ANC modes, safe state, and counters without Bluetooth addresses or raw protocol data. It rejects unknown commands and malformed parameters before hardware access, routes refresh and verified ANC writes through the shared controller, and returns structured address-redacted responses.
- The bridge accepts a dispatcher hook so service callbacks can be queued onto a future frontend event loop. It deliberately does not select D-Bus, sockets, a process model, or QML architecture yet.
- A live read-only bridge run on the Pro 2 emitted connection and snapshot events, identified the correct model, produced address-free JSON, and ended with a disconnected final snapshot after cancellation. No device setting was changed.
- Current Omarchy 4.0.2-1 packaged sources, validator, plugin commands, manifests, loader, and representative first-party service/bar widgets were inspected read-only and compared with the current official Quattro and marketplace documentation. Third-party plugins use a root schema-v1 manifest, run inside the existing shell, and may combine `service` and `bar-widget`; plugin installation performs no dependency/install hook.
- The selected deployment is a combined service/bar-widget plugin whose headless QML service owns one Python child process. NDJSON over `Quickshell.Io.Process` stdin/stdout carries the existing schema-v1 contract. A separate user daemon, global socket/D-Bus API, second Quickshell process, and one-shot polling helpers are deliberately avoided.
- `BridgeProcessHost` starts the bridge in a non-daemon worker, isolates blocking stdin in a daemon reader, serializes/flushed stdout records, rejects malformed request envelopes, hides unexpected internal errors, and treats EOF, SIGINT, and SIGTERM as cancellation. Tests prove teardown still completes while stdin is blocked.
- Root `manifest.json` now declares the non-reserved `oneplus-buds.control` plugin as a combined schema-v1 `service` and `bar-widget`. The executable `oneplus-buds-bridge` launcher resolves the checkout-local Python source without an install hook.
- `Service.qml` owns exactly one bidirectional helper, parses schema-v1 NDJSON through `BridgeModel.js`, exposes connection/snapshot/response state, routes refresh and ANC requests over stdin, suppresses raw stderr, and stops the helper on destruction. `BarWidget.qml` proves shared-service lookup but is intentionally hidden and zero-width until visual work begins.
- Scaffold tests cover manifest shape, launcher permissions/source resolution, the single-helper lifecycle contract, shared-service lookup, hidden placeholder behavior, and JavaScript parsing/state reduction. Direct launcher EOF testing emitted valid connecting/stopped/final-snapshot NDJSON and exited cleanly.
- The live Omarchy lifecycle test used the already-running shell (PID 1009) and the supported local-plugin directory plus `rescanPlugins`/`omarchy plugin enable`; no second shell or graphical-session restart was used. The plugin catalog reported enabled, its zero-size bar item was mounted in the configured right section, and exactly one checkout-local `oneplus-buds-bridge` helper ran while the connected Pro 2 was available. This verifies shell loading, helper startup, and the frontend's `serviceFor("oneplus-buds.control")` architecture. A read-only widget IPC status hook was added for repeatable state inspection; the long-running shell retained the earlier QML component in its cache during this development run, so that newly added hook was not registered until a future fresh load.
- No plugin-specific QML, Python, Bluetooth, or helper errors appeared. Omarchy itself emitted duplicate-handler warnings for its built-in agents/Bluetooth/network/audio/monitor/power panels during hot enable/disable, and recursively watched `.git` files caused redundant reload debug messages when a full clone was placed or removed. These were shell development-reloader effects, not failures from this plugin; stage/export future development installs without `.git` to keep the reload window quiet.
- Disable stopped the helper, and removal deleted the temporary plugin directory. The exact pre-test `shell.json` compares byte-for-byte equal afterward, canonical shell ping still returns `ok`, PID 1009 never changed, the Pro 2 remains connected, and no earbud setting command was sent.
- `BarModel.js` provides pure capability-driven presentation: it accepts only numeric 0–100 percentages, orders known left/right/case components, marks charging only when explicitly reported, and omits absent, invalid, or unknown fields. `BarWidget.qml` uses current Omarchy font, foreground, spacing, geometry, and tooltip APIs; disconnected states show an icon without stale battery values.
- The first live widget compile caught a missing `Quickshell.Io` import for `IpcHandler`; commit `4559fca` fixes it and adds a regression assertion. A subsequent unique-URL load required no shell restart and returned `{"service":true,"connection":"connected","snapshot":true,"label":"L 100%⚡  R 100%⚡  C 100%","error":""}`. Live geometry was visible, 195×26, and no plugin error followed the fixed load.
- The widget test did not send refresh or setting commands. Afterward the helper stopped, all temporary/backup plugin directories were moved out of the live plugin path, `shell.json` matched its pre-test copy byte-for-byte, and shell PID 1009 remained healthy.
- `BarWidget.qml` now opens a native `PopupCard` containing a `ButtonGroup` derived solely from snapshot `anc_modes`. It rejects unsupported selections, blocks overlapping requests, tracks its own request ID, displays pending/failure state, and says “Verified on earbuds” only for a matching successful response whose result has `verified === true`. The current selection comes from independently read-back `status.anc`/`anc_level`, not optimistic UI state.
- Live Pro 2 UI testing changed ANC from Off to Transparency. The popup reported verified success and the read-only widget endpoint independently returned `current_anc: transparency`, `pending: false`, with no error. The user reported that application was slow; the current path deliberately performs conservative write authentication, separate read-back verification, and monitoring-session reauthentication, so a roughly multi-second wait is expected and was not hidden or optimized without more evidence.
- After the live control test the temporary plugin was disabled and moved out of the live plugin path, its helper stopped, `shell.json` matched the pre-test copy byte-for-byte, shell PID 1009 remained healthy, and the connected Pro 2 was left in the user-selected Transparency mode.
- Live Pro 2 controller tests passed start → subscribe → poll → shutdown and start → verified ANC write → resubscribe → shutdown. The latter began at ANC On/Deep and generic `on` read back On/Smart, disproving the earlier claim that main On always preserves the visible level; explicit levels remain deterministic. That earlier controller test ended at On/Smart; the current state is recorded below.

## Current hardware and repository state

- Connected test hardware at session end: OnePlus Buds Pro 2, product `062014`, firmware `196.196.101`, used for optimized-path verification.
- Last verified ANC state: Off on Pro 2 after optimized-path verification. Original Pro was also left Off after its optimized cycles. Both completed runs exited 0 and released their controller/session.
- Implementation in this milestone: persistent-session main ANC controls, response-correlated verification with bounded settling, nonblocking service polling, atomic bridge response/snapshot capture, phase timing and hardware measurement records.
- Automated status: 79 tests passing for timing instrumentation, control optimization, and harness. Previously verified compilation, `git diff --check`, both JavaScript model suites, direct launcher EOF testing, and `omarchy plugin validate .` pass.
- Existing `omarchy-shell` PID 1009 remains running. The temporary development plugin is disabled and removed, its helper/RFCOMM owner is stopped, and shell configuration is restored exactly.

## Unresolved problems

- Cold session setup, standalone CLI, explicit ANC levels, and disconnected recovery retain conservative authentication waits. Healthy main-mode changes now reuse authentication/subscriptions. Warm measurements do not prove shorter cold-start waits safe.
- Case presence and charging bits should be tested deliberately later.
- Dynamic `0x8100` bit semantics, original Buds Pro `0x810d` silence, Pro 2 feature ID `0x05`, and additional notification payloads remain unresolved. Do not infer names for unknown fields.
- Public packaging declares and checks the platform `dbus-python` binding; it is already installed on the tested Omarchy system but is not a Python-package dependency.
- `0x0204` notification schemas are not mapped yet. The event API exposes only their numeric code until each payload is validated.
- The device exposes one RFCOMM control channel. `BudsServiceRunner` uses `BudsController` as its sole serialized session owner rather than opening concurrent sessions directly.
- Bridge callbacks are synchronous by default; a frontend adapter must supply the dispatcher hook to marshal them onto its event loop rather than doing UI work in the polling thread.
- Omarchy caches QML components by source URL in this long-running development session. Use a unique temporary source directory when a same-path hot reload retains an older component; do not restart the user's shell solely to invalidate development cache.
- Marketplace metadata and submission remain external follow-up; the repository, README, LICENSE, dependency/install documentation and validation are complete.

## Next recommended task

Local publication preparation is complete: README, MIT license, changelog,
contribution/compatibility guides, issue templates, dependency preflight, CLI
launcher, safe exporter, metadata and marketplace submission draft are present.
The clean export passes 82 tests, Qt interaction checks and plugin validation.

The repository URL is https://github.com/GazzasaurusRex/oneplus-buds-omarchy.git.
The remote initially contained one MIT-license commit; its history is preserved.
The user requested the original project MIT license, Copyright (c) 2026 Gaz and
contributors, which replaced the initial GitHub copy. The reviewed snapshot is
now published on `main` at commit `ea5314b`; a fresh shallow clone passed
manifest, license, CLI and dependency-preflight checks. README, manifest
and Python metadata use the selected URL. Local source and history checks found
only placeholder Bluetooth addresses. The working tree is clean and the local
`master` branch tracks the configured `origin/main`. Marketplace submission
remains a separate explicit action; no release tag has been created.

If control latency is revisited, use the recorded phase data first. Cold-start
handshake waits and mapping validated notification semantics are separate future
investigations; do not shorten authentication or trust unknown notifications based
on these warm-session results.

## Completed optimization — 2026-09-06

- Main On/Off/Transparency on a running controller now reuse the authenticated
  RFCOMM session and subscriptions by default. Explicit levels and one-shot calls
  retain the proven legacy path. `reuse_session=False` permits baseline comparison.
- SET is sent without a development sleep; transport waits for matching response
  command/sequence with deadlines, then separate fresh state-query transactions
  independently verify the result. No acknowledgement or cache update is proof.
- Original Pro's first fast trial correctly rejected premature Transparency
  read-back. A separate read-only session subsequently found Transparency. Bounded
  response-paced settling queries fixed this observed race without replaying SET.
- Completed original Pro run: eight verified requests, seven actual transitions,
  status `00`, On/Deep, same session and subscriptions throughout, final Off.
  Median actual-transition completion 260 ms versus 15.132 s baseline.
- Pro 2 first run completed four verified requests then stopped outside the timed
  ANC-error handler. The original harness lacked enough detail to identify why;
  do not call this a proven protocol failure or claim its cause was fixed. The
  harness now records safe failure phase/type and service lifecycle, preserves
  successful control data before monitoring assertions, and checks final monitoring.
- Completed Pro 2 rerun, unchanged control implementation: eight verified requests,
  six actual transitions, status `00`, On/Smart, same session and ten subscriptions
  throughout, final Off. Median actual-transition completion 167 ms versus 15.138 s
  baseline. All-request median is 107 ms (includes two already-Off requests).
- Neither successful run needed monitoring restoration. SET send elapsed within
  the session call was under 0.23 ms. This is not a measurement of audible change
  time; a listening observation was requested but not supplied.
- Service polling drains available frames without waiting under the controller
  lock; its 0.5 s interval is outside that lock. Reads are bounded under floods.
- Bridge uses an atomic result/snapshot pair so serialization does not wait for a
  second lock behind possible subsequent monitoring recovery. Failed fast writes
  close the uncertain session, invalidate cached ANC, and return without replay;
  normal polling/service recovery handles reconnects.
- Expected-failure timing and successful phase timing are privacy-safe. Full
  sanitized baseline, rejected/incomplete trial, and optimized records are in
  `docs/measurements/`; analysis explains units, nested totals, and scope.
- 79 tests pass, including correlated/fragmented responses, deadline bounds,
  missing acknowledgements, settling mismatch, no replay, session retention,
  concurrent commands, shutdown ownership, nonblocking polls, bridge delivery,
  and harness privacy/final-monitoring failure. Plugin validation passes.
- No QML or desktop configuration was changed. User's pre-existing PROJECT.md
  hover-expansion requirements are preserved as documentation, not implemented.
- Final default-bridge Pro 2 check verified already-active Off in 59.448 ms,
  retained the same session through a ten-second monitoring hold, had no service
  errors, and exited 0. Compilation and `git diff --check` also pass.

## Compact hover widget — 2026-09-07

- Idle bar presentation is now icon-only. Available batteries expand horizontally
  on hover with the installed shell's 180 ms OutCubic width-animation convention.
  The host receives the animated implicit width, and text is clipped within it.
- Leaving starts a 300 ms single-shot collapse timer; re-entry cancels it.
  An open popup holds expansion stable until closed and the pointer has left.
- One MouseArea covers the entire animated width. Clicking opens the panel even
  for devices without ANC, with battery/connection information and hidden absent
  ANC controls. Vertical bars retain the compact icon and expose data in the panel.
- Read-only IPC now includes expanded, width, and popup_open fields.
- Validation: six frontend scaffold/model tests pass; QML parsing, plugin validation,
  and diff whitespace checks pass. `python tests/run_qml_hover.py` passes with real
  Qt mouse events, animation and timers, covering expanded-area clicks, popup hold,
  delayed collapse, re-entry, one known battery, empty batteries, and disconnection.
  Its shell/IPC/popup primitives are stubs; this is not a live Omarchy rendering test.
- No Bluetooth command, desktop configuration change, plugin install, or shell restart
  was performed. Prior hardware results remain the evidence; current hardware state
  was not re-queried. The next task is the live visual check above.

## Live hover check complete — 2026-09-07

- Temporary export (without `.git`) was installed at
  `~/.config/omarchy/plugins/oneplus-hover-20260907-a` and enabled in the existing
  shell, PID 1025. No shell restart occurred. One Python bridge helper was present.
- Live status connected, L/R=100%, no case value, ANC Off, no backend error.
  Idle width 23.1875 px; hover width 120.5 px; height 26 px.
- Live geometry and regional screenshot verified readable expansion and no overlap
  with neighbouring icons. The right section grows leftward; the agents widget
  stays at x=1110 while earbuds expand from x≈1087 to x≈990.
- Pointer exit returned expanded=false and width=23.1875.
- The user confirmed the expanded battery area opens the panel as expected.
  The panel was already closed at the subsequent IPC/screenshot inspection;
  popup visual acceptance is the user's observation, not an assistant screenshot.
- No plugin-specific runtime warnings/errors. Built-in duplicate IPC-handler
  warnings appeared during hot enable, as in prior development loads.
- Cleanup passed: temporary plugin disabled and moved out of the live plugin path,
  helper stopped, shell configuration restored byte-for-byte, original shell PID
  1025 unchanged and ping healthy. Temporary evidence/backups remain under
  `/tmp/oneplus-live-hover/`. No ANC request was sent; last live state was Off.
- The user wants changes to the panel after this test; details are pending.

## Portrait panel redesign — 2026-09-07

- User reported that the horizontal ANC options extended off-screen and requested
  a readable vertical rectangular panel consistent with Omarchy.
- Replaced the single ButtonGroup row with native full-width Buttons, grouped into
  Noise control and ANC strength. Unknown advertised modes remain in Other modes;
  absent groups are hidden. Main ANC On is labelled Noise cancellation and stays
  selected when an explicit ANC strength is active.
- Panel width is 320 logical px, height follows content with a 380 px content
  minimum and PopupCard screen-height cap. A clipped vertical Flickable with
  scrollbar handles overflow. Header/battery/status messages wrap. Buttons retain
  native themed selected/hover/focus states; Tab, Up/Down, Enter/Space and Escape
  are supported, and focusing a button reveals it in the scroll viewport.
- Capability guards, pending-request exclusion and independently verified response
  handling remain in place. No backend setting logic changed.
- Six frontend scaffold/model checks, Qt hover interaction tests, QML parsing,
  plugin validation and whitespace checks pass. Grouping tests cover unknown
  modes and empty capabilities.
- Temporary live export: `~/.config/omarchy/plugins/oneplus-panel-20260907-a`.
  Backup/export/install/cleanup scripts: `/tmp/oneplus-live-panel/`.
  Live IPC reports panel 320×425, connected, L/R=100%, ANC Off and no error.
  No plugin-specific runtime warnings; existing built-in duplicate IPC warnings
  recur on hot enable.
- User accepted the live layout: “the layout looks good now. its all easy to read
  and navigate.” Visual acceptance is the user's observation.
- Cleanup passed: temporary plugin disabled and moved out of the live plugin path,
  helper stopped, shell configuration restored byte-for-byte, original shell PID
  unchanged and ping healthy. Source changes remain in the checkout; no permanent
  plugin installation was performed. No ANC request was sent during these tests.

## Publication preparation complete — 2026-09-07

- Added README, LICENSE (MIT default proposed to user), CHANGELOG, CONTRIBUTING,
  compatibility matrix, GitHub bug/compatibility templates and publication draft.
  Current official publishing/development guides and submission form were checked;
  draft category Hardware and tags Bar/Media/Quickshell match the form.
- Corrected research-license wording: OppoPods README declares GPL-3.0 despite
  absence of a standalone license file at the recorded revision. Its source was
  not copied. Runtime Omarchy/dbus-python dependencies are not vendored.
- Added executable checkout-local `oneplus-buds` CLI launcher, read-only
  `scripts/check_dependencies.py` and `scripts/export_plugin.py`. Export refuses
  existing destinations/source symlinks and excludes caches/Git internals.
- Manifest and pyproject declare MIT, with README/license Python metadata.
  Version remains unreleased 0.0.1 across all three version locations.
- Clean export `/tmp/oneplus-publication-review` validated with Omarchy, CLI help,
  dependency preflight, all 82 Python tests (including JS subprocess checks), and
  Qt offscreen hover tests (3 QtTest results). Dependency failure was exercised
  with `python3 -S`, correctly reporting missing dbus and exiting 1. Relative links
  in new public docs resolve; `git diff --check` passes.
- No Bluetooth tests, live UI reloads, settings changes or desktop installs were
  repeated. The accepted UI implementation remains part of the working tree.
- The GitHub remote is now configured and the reviewed snapshot is published.
  No release tag was created. Publication notes contain the repository URL and
  marketplace submission draft.
- Python wheel building is not the plugin install path and was not tested:
  setuptools is absent on this host. The plugin export needs no build dependency.
  Remaining external work is release decision and marketplace submission after
  authorization.

## GitHub publication complete — 2026-09-08

- Pushed the reviewed history to the selected GitHub repository. `main` points to
  `a7622c5`; the original initialization commit and project history are retained.
- The published `LICENSE` is the requested project MIT notice, Copyright (c) 2026
  Gaz and contributors.
- Fresh shallow clone validation passed `omarchy plugin validate`, CLI `--help`,
  and dependency preflight. No hardware or desktop configuration was changed.
- No release tag was created. Marketplace submission remains a separate external
  publication action.

## Generic physical-device switching fix — 2026-09-08

- Reproduced before editing: BlueZ showed only original Buds Pro connected while
  the unchanged installed plugin remained disconnected with Pro 2 controls and
  a selected-device-unavailable error. A controlled controller reproduction also
  demonstrated that `start()` promoted automatic selection into a permanent
  address pin. Existing 82 tests passed despite the bug.
- Diagnosis: shutdown retained device/profile-derived status and feature/event
  caches; retry discovery ran with A's address; immediate session recovery reused
  A's cached status without BlueZ selection. Retry shutdown did not publish a
  cleared snapshot, leaving stale identity/capabilities in the frontend.
- Fix separates explicit selection from active identity. Recovery closes the
  old session, clears all device data, reruns selection and status queries, then
  creates/authenticates/subscribes a fresh session using the selected product's
  profile. Failed setup clears partial state. The runner publishes empty state
  during backoff. Explicit selection remains pinned; ambiguous automatic
  selection retains the existing error. Error redaction survives identity reset.
- Automated: 86 Python tests pass, including both orders through the real runner,
  bridge and JS reducer; independent batteries/firmware/ANC/capabilities; fresh
  authentication; cleared A-only feature/event/counter state; immediate switch;
  repeated empty retries; explicit pinning; failed authentication cleanup.
  Qt interaction tests pass (3 results); plugin validation and diff checks pass.
- Live verification used one fixed helper PID 4404 throughout both directions:
  original Pro (`060C14`, firmware `541.541.510`, L/R 90%, ANC Off) → Pro 2
  (`062014`, firmware `196.196.101`, L/R 100%, ANC Off) → original Pro with
  its original readings. Session-connected was true after each recovery; Medium
  appeared only for Pro 2. BlueZ independently confirmed each final device.
- Between Pro 2 and Pro, repeated live retries showed null identity/firmware/
  battery, empty battery label/ANC controls/selection, and session disconnected.
  Evidence is read-only widget IPC state used by the actual UI, not screenshot
  or subjective visual acceptance. No ANC setting command was sent.
- No shell restart occurred and no matching plugin runtime errors appeared in
  the inspected journal. The fixed live plugin remains enabled at
  `~/.config/omarchy/plugins/oneplus-switch-fixed`; original installation is
  preserved at `/tmp/oneplus-switch-original`. The final connected device is
  original Buds Pro, ANC Off. Address-free transition samples are in
  `/tmp/oneplus-switch-evidence.jsonl`; durable verification summary is in
  `docs/measurements/device-switching.md`.

## Connection lifecycle optimization — 2026-09-08

- Instrumented the unchanged lifecycle before adjusting timing. Backend JSONL
  uses monotonic and Unix nanoseconds for phase/cross-process correlation; a
  separate GLib observer timestamps BlueZ Device1 signals and actual QML state.
  Traces contain no addresses, object paths, raw frames, tokens or error text.
- Eight baseline hardware runs cover cold service startup, arrival at an empty
  running service, same-device reconnect and cross-model switch on both reference
  models. Usable UI took 8.655–38.073 seconds. Backend setup consistently took
  8.525–9.014 seconds; timer backoff added 7.909–29.074 seconds on arrivals.
- Diagnosis: disconnected recovery had no BlueZ event wake-up; startup opened a
  status socket and then a monitoring socket, consistently causing a one-second
  EBUSY retry; fixed query drains delayed product/state; firmware preceded
  essential state; subscription setup delayed UI usability. Runtime SDP was not
  involved because verified RFCOMM channel 15 was already used directly.
- The process host now watches BlueZ availability signals on a private D-Bus/
  GLib loop. Generation-counted hints interrupt a pending retry once while fresh
  ObjectManager discovery remains authoritative. Normal failures retain capped
  exponential backoff, cancellation behavior and the timer-only fallback. BlueZ
  daemon restarts clear hint state. No connection or active-device state is cached.
- Startup now keeps one RFCOMM socket through fresh product/profile resolution,
  conservative HELLO/REGISTER authentication and response-correlated battery/ANC
  reads. It publishes usable state before subscription and firmware, which then
  populate on the same serialized session. Subscription failure still invokes
  normal teardown/recovery. The established 2-second HELLO and 1.5-second REGISTER
  waits remain unchanged because this milestone did not establish shorter safe
  values.
- Eight optimized hardware runs cover the same matrix. Usable UI took
  4.476–4.869 seconds: Pro 2 cold 4.869, arrival 4.481, reconnect 4.504, switch
  4.485; original Pro cold 4.630, arrival 4.597, reconnect 4.561, switch 4.476.
  BlueZ-to-discovery delay was 0.365–2.910 ms for non-cold scenarios. Both switch
  directions cleared the intermediate UI and loaded the destination profile,
  battery, ANC, capabilities and firmware. No successful optimized startup used
  EBUSY recovery or retry backoff, and no matching runtime errors were found.
- Automated suite is 97 tests, adding one-socket/fresh-profile behavior on both
  fixtures, essential-before-optional ordering, socket cleanup, correlated
  deferred firmware, lost-wakeup prevention, wake de-duplication, cancellation,
  fallback backoff and BlueZ restart/late-UUID cases. Existing generic switching,
  bridge, control and privacy tests remain green. Qt tests and plugin validation
  also pass.
- Full method, phase audit and before/after table are in
  `docs/measurements/connection-lifecycle.md`; raw and summarized address-free
  artifacts are adjacent as `2026-09-08-connection-{baseline,optimized}*`.
  The live optimized plugin is enabled at
  `~/.config/omarchy/plugins/oneplus-connect-optimized`; current hardware is Pro 2
  connected with ANC Off. Baseline and prior installs remain preserved under
  `/tmp`. No ANC command was sent during connection measurements.
