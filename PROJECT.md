I want you to build a native Omarchy plugin that provides Linux control and monitoring for OnePlus wireless earbuds, with the long-term goal of supporting as many OnePlus earbud models as technically possible.

I personally have a OnePlus Buds Pro and OnePlus Buds Pro 2 available for testing. Treat those as the first two reference/test devices, but DO NOT design the software specifically around either model.

The project should be designed as a reusable OnePlus/OPPO OPO-compatible earbud backend with an Omarchy frontend.

The finished project should be suitable for publishing publicly on the Omarchy plugins site and on GitHub.

IMPORTANT DEVELOPMENT PRINCIPLE

Do not begin by making a polished UI.

First establish reliable communication with the earbuds, understand the protocol, and build a reusable backend. Only build the Omarchy interface once the underlying controls have been proven to work.

Do not fake unsupported features or assume commands succeeded.

==================================================
PROJECT GOALS

The plugin should automatically detect compatible OnePlus earbuds and expose whichever functionality that particular device supports.

Potential functionality includes:

- Device detection
- Connection/disconnection status
- Device name/model identification
- Left earbud battery
- Right earbud battery
- Charging case battery when available
- Charging state
- ANC On
- ANC Off
- Transparency mode
- ANC strength
- Adaptive/smart ANC
- EQ presets
- Custom EQ if supported
- Bass controls
- Spatial audio
- Head tracking
- Golden Sound / personalised sound profiles
- Low latency/game mode
- Wear detection
- Multipoint status/settings
- Touch/gesture configuration
- Earbud fit testing if technically accessible
- Find My Earbuds if implemented on-device
- Zen Mode Air or equivalent features where accessible
- Firmware version
- Codec information where available
- Device-specific settings
- Any other feature exposed through the OnePlus/HeyMelody protocol

Do not assume all models support all features.

The UI must be capability-driven so unsupported controls simply do not appear.

==================================================
ARCHITECTURE

Design the project with clear separation between:

1. Bluetooth transport
2. Earbud protocol
3. Device identification and capability detection
4. Feature implementations
5. Command-line/backend interface
6. Omarchy/QML frontend

The architecture should ideally resemble:

BlueZ
|
+-- BLE transport
|
+-- Bluetooth Classic/RFCOMM transport
|
v
OPO protocol layer
|
+-- device discovery
+-- handshake/authentication
+-- state querying
+-- battery
+-- ANC
+-- EQ
+-- gestures
+-- spatial features
+-- other capabilities
|
v
backend API
|
v
Omarchy plugin

Do NOT tightly couple the OPO protocol to BLE if the same protocol can operate over another transport such as RFCOMM.

Do NOT bury Bluetooth protocol code inside QML.

==================================================
MODEL SUPPORT

The goal is to support as many OnePlus earbuds as possible.

Investigate current and historical OnePlus earbuds, including but not limited to:

- OnePlus Buds
- OnePlus Buds Z
- OnePlus Buds Z2
- OnePlus Buds Pro
- OnePlus Buds Pro 2
- OnePlus Buds Pro 3
- OnePlus Buds 3
- OnePlus Buds 3 Pro
- OnePlus Buds 4
- OnePlus Nord Buds
- OnePlus Nord Buds 2
- OnePlus Nord Buds 2r
- OnePlus Nord Buds 3
- OnePlus Nord Buds 3 Pro
- OnePlus Nord Buds CE
- other OnePlus Bluetooth earbuds/headsets where technically applicable

Do not assume these all use the same protocol.

Research each device family and group devices by protocol/capability rather than creating duplicated model-specific implementations.

Where relevant, investigate closely related OPPO and Realme earbuds because OnePlus, OPPO and Realme devices may share OPO/OPOv1 protocol implementations.

However, OnePlus should remain the primary supported brand for the initial release.

==================================================
DEVICE PROFILES AND CAPABILITIES

Avoid one giant hard-coded model switch statement.

Create a capability/profile system.

A device should be able to expose information such as:

model
protocol
transport
firmware
supportsBattery
supportsCaseBattery
supportsANC
supportsTransparency
supportsANCLevels
supportsAdaptiveANC
supportsEQ
supportsCustomEQ
supportsSpatialAudio
supportsHeadTracking
supportsGoldenSound
supportsWearDetection
supportsGestures
supportsMultipoint
supportsLowLatency
supportsFindEarbuds

Prefer actual capability detection from the device whenever possible.

Use model profiles only where protocol differences genuinely require them.

Support three compatibility states:

1. Verified
   Functionality has been tested on real hardware.

2. Compatible / community-tested
   Reported working by other users.

3. Experimental
   Device exposes a recognised protocol but has not been fully tested.

Initially:

- OnePlus Buds Pro = verified after testing
- OnePlus Buds Pro 2 = verified after testing

Do not mark any other model verified without evidence.

==================================================
PHASE 1 — SYSTEM AND PROTOCOL RESEARCH

Before implementing the final application:

1. Inspect the Linux Bluetooth environment on this Omarchy system.
2. Identify my connected OnePlus earbuds through BlueZ.
3. Enumerate available Bluetooth services.
4. Determine whether each device communicates through BLE GATT, RFCOMM, another Bluetooth mechanism, or a combination.
5. Research existing open-source reverse-engineering projects involving:
   - OnePlus earbuds
   - OPPO earbuds
   - Realme earbuds
   - HeyMelody
   - OPO
   - OPOv1
6. Study existing implementations rather than reinventing known protocol behaviour.
7. Check licences before reusing code.
8. Document everything useful that is discovered.

Create protocol documentation as you work.

Suggested structure:

docs/
protocols/
OPOv1.md
other-protocols.md

devices/
oneplus-buds-pro.md
oneplus-buds-pro-2.md
compatibility.md

Record:

- Service UUIDs
- Characteristic UUIDs
- RFCOMM channels/services
- Authentication/handshake sequences
- Packet structure
- Checksums
- Message types
- Commands
- Responses
- Notifications
- Feature IDs
- Model differences

==================================================
PHASE 2 — BUILD A GENERIC BACKEND FIRST

Create a standalone backend/CLI before creating the Omarchy plugin.

Use normal Linux Bluetooth interfaces such as BlueZ through D-Bus/GATT/RFCOMM.

Do not use GUI automation.

Do not require root unless absolutely necessary.

Create a command such as:

oneplus-buds

Example commands:

oneplus-buds scan

oneplus-buds devices

oneplus-buds status

oneplus-buds info

oneplus-buds capabilities

oneplus-buds battery

oneplus-buds anc status

oneplus-buds anc on

oneplus-buds anc off

oneplus-buds anc transparency

oneplus-buds eq list

oneplus-buds eq set <preset>

oneplus-buds diagnostics

The CLI should automatically detect the currently connected supported device where practical.

It should also support explicitly selecting a device if multiple compatible earbuds are known.

==================================================
PHASE 3 — BASIC FUNCTIONALITY

Using my OnePlus Buds Pro and OnePlus Buds Pro 2, first prove that the backend can reliably:

1. Detect the earbuds.
2. Identify their model.
3. Detect whether they are connected.
4. Establish any required OPO/OPOv1 handshake.
5. Read battery information.
6. Determine current ANC/noise-control state.
7. Switch between:
   - ANC
   - ANC Off
   - Transparency

Do not move on to complicated features until this works reliably.

Query the resulting state after sending a setting whenever possible rather than simply assuming the command worked.

==================================================
PHASE 4 — COMPARE BUDS PRO AND BUDS PRO 2

Once basic control works, compare both of my test devices.

Record:

- Bluetooth services
- protocol version
- packet differences
- supported commands
- feature differences
- response differences
- firmware behaviour

Use these differences to improve the generic capability system rather than adding hacks directly into the UI.

==================================================
PHASE 5 — FEATURE DISCOVERY

Investigate additional functionality available through HeyMelody/OnePlus.

For each feature:

1. Determine whether the feature executes inside the earbuds or inside the Android phone.
2. Determine whether it can realistically be reproduced on Linux.
3. Identify the protocol command/state query.
4. Implement it in the backend.
5. Test it.
6. Query state after changing it when possible.
7. Only expose it to the frontend once it is demonstrated to function.

Maintain clear distinctions between:

SUPPORTED
EXPERIMENTAL
NOT POSSIBLE / PHONE-SIDE

Do not create placebo controls.

==================================================
PHASE 6 — UNKNOWN DEVICE SUPPORT

The software should attempt to recognise compatible devices that are not yet in the device database.

If an unknown OnePlus/OPPO-compatible device exposes a recognised OPO protocol:

- Detect it.
- Identify whatever information is available.
- Expose only safely detected functionality.
- Mark the device Experimental.
- Never send potentially dangerous or poorly understood commands simply because another model supports them.

Provide a compatibility report.

Example:

OnePlus Nord Buds XYZ

Model: OnePlus Nord Buds XYZ
Protocol: OPOv1
Transport: BLE
Firmware: unknown

Battery: supported
ANC: supported
Transparency: supported
ANC levels: unknown
EQ: unknown
Spatial audio: unknown
Gestures: unknown

Compatibility status: Experimental

==================================================
PHASE 7 — DIAGNOSTICS / COMMUNITY REPORTING

Because this will be a public plugin, provide a diagnostic command that users can use when reporting compatibility.

For example:

oneplus-buds diagnostics --report

The output should include useful NON-SENSITIVE information such as:

- reported device model
- protocol
- transport
- firmware
- supported service UUIDs
- detected capabilities
- backend/plugin version
- feature test results

Do NOT expose Bluetooth pairing keys, private credentials, unrelated Bluetooth devices, personal information, or sensitive system data.

Make the report easy to paste into a GitHub issue.

==================================================
PHASE 8 — OMARCHY PLUGIN

Only after the backend works reliably, create the Omarchy frontend.

Read the current Omarchy plugin documentation and inspect current first-party Omarchy plugins before deciding the architecture.

Use Omarchy's expected manifest.json and QML/Quickshell structure.

Do not start an unnecessary separate Quickshell instance.

Integrate into Omarchy correctly.

Create a compact bar widget.

When no compatible earbuds are connected, it may either hide itself or display an appropriate disconnected state depending on what is consistent with Omarchy conventions.

When earbuds are connected, display:

- headphone/earbud icon
- useful battery information
- connection state

Clicking the widget should open a control panel.

Example conceptual layout:

OnePlus Buds Pro 2

L 86%    R 82%    Case 64%

Noise Control
[ ANC ] [ Off ] [ Transparency ]

ANC
[ Mild ] [ Smart ] [ Max ]

EQ
Balanced        >

Spatial Audio
Off             >

Wear Detection               On

Multipoint                    On

Device Information            >

The exact controls should change depending on detected capabilities.

Do not show disabled fake controls for features the device doesn't have. Prefer hiding unsupported functionality.

==================================================
OMARCHY UI REQUIREMENTS

The plugin should:

- Follow the current Omarchy theme automatically.
- Look consistent with first-party Omarchy plugins.
- Respond correctly when the Omarchy theme changes.
- Use appropriate spacing and typography.
- Support mouse interaction.
- Support keyboard navigation where appropriate.
- Have useful tooltips.
- Update when earbud state changes.
- Gracefully handle device disconnection.
- Gracefully handle Bluetooth being disabled.
- Avoid excessive polling.
- Prefer Bluetooth notifications/events where possible.
- Not cause unnecessary wakeups or battery usage.

==================================================
PUBLIC PROJECT QUALITY

Treat this as software intended for other people, not a throwaway script.

Organise the project cleanly.

Suggested structure:

backend/
protocols/
devices/
plugin/
docs/
tests/

Include:

README.md
LICENSE
CHANGELOG.md
CONTRIBUTING.md

Document:

- installation
- dependencies
- supported devices
- tested devices
- experimental devices
- troubleshooting
- architecture
- how to contribute a compatibility report
- how to add support for a new model
- protocol discoveries

Clearly distinguish between:

Verified hardware
Community tested hardware
Experimental hardware

==================================================
TESTING

Create tests where meaningful.

Protocol packet encoding and decoding should have automated tests where possible.

Device-profile/capability detection should have tests.

Do not make automated tests depend on real earbuds unless explicitly running hardware integration tests.

Keep captured protocol samples or anonymised fixtures where useful for regression testing.

==================================================
SECURITY AND SYSTEM SAFETY

Do not:

- make unnecessary system-wide configuration changes
- alter PipeWire configuration unnecessarily
- alter my normal Bluetooth audio configuration unnecessarily
- disable Bluetooth security
- expose pairing credentials
- run arbitrary scripts from unknown repositories
- require permanent root access
- install large dependency stacks without justification

Before running a command with sudo or making a system-wide change, explain why it is necessary.

Prefer user-level services and configuration.

==================================================
OMARCHY PUBLICATION

Prepare the plugin so it can eventually be submitted to the Omarchy plugins repository/site.

Check the CURRENT Omarchy plugin development and publication requirements rather than assuming older documentation is still correct.

Ensure:

- manifest.json is valid
- installation is clean
- uninstall/removal is clean
- dependencies are documented
- repository structure meets current expectations
- plugin validation succeeds

Run:

omarchy plugin validate

and any relevant QML linting or validation.

Check runtime logs for errors.

==================================================
DEVELOPMENT WORKFLOW

Work iteratively.

Do not try to generate the entire application in one pass.

Preferred order:

1. Research
2. Device discovery
3. Protocol proof-of-concept
4. Buds Pro basic control
5. Buds Pro 2 basic control
6. Generic protocol abstraction
7. Capability system
8. Additional features
9. Unknown-device detection
10. Omarchy UI
11. Diagnostics
12. Documentation
13. Packaging/publication preparation

After each major milestone, briefly tell me:

- what was discovered
- what now works
- which hardware was tested
- what failed
- what remains
- what you need me to physically test

==================================================
WHEN YOU NEED ME

You may need physical interaction with the earbuds.

When necessary, ask me to do specific things such as:

- connect the Buds Pro
- connect the Buds Pro 2
- put earbuds into the charging case
- remove them from the case
- disconnect my phone
- connect my phone
- switch ANC mode using HeyMelody
- switch EQ preset
- enable/disable a setting
- play audio
- listen for a change
- perform a gesture
- verify whether a feature actually changed

Give me one clear test at a time.

Use the resulting observations to continue development.

==================================================
FIRST RELEASE TARGET

Do not attempt to replicate every HeyMelody feature before producing something usable.

Target an initial v0.1 containing:

- automatic device detection
- OnePlus Buds Pro verified
- OnePlus Buds Pro 2 verified
- generic OPO-compatible detection
- connection status
- left/right battery
- case battery where available
- ANC On
- ANC Off
- Transparency mode
- clean Omarchy bar widget
- control panel
- diagnostics/compatibility report
- proper documentation

Once v0.1 is reliable, expand feature and device support incrementally.

==================================================
START NOW

Begin with research and inspection only.

First:

1. Inspect this Omarchy system's Bluetooth/BlueZ environment.
2. Detect my currently available OnePlus earbuds.
3. Identify their services and likely protocol.
4. Research existing OPO/OPOv1/HeyMelody implementations.
5. Create an initial architecture and research notes.

Do not build the final QML interface yet.

The first practical milestone is a small command-line proof-of-concept that can detect one of my earbuds, display its battery state and successfully query/change ANC mode.