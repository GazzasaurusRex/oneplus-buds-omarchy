# OnePlus Buds Pro 4 (experimental)

Read-only baseline, 2026-11-24. Product `067814`, firmware
`116.116.100` (left/right/case). BlueZ resolved services and reported 100%.
OPO over RFCOMM channel 15 reported both buds at 100% and charging, and the
case at 100% and not charging. This is a single snapshot.

BlueZ listed Audio Sink, AVRCP controller and target, Handsfree, PnP Information,
GAP, GATT, and these vendor services:

- `0000079a-d102-11e1-9b23-00025b00a5a5` (shared OPO service)
- `0000079f-d102-11e1-9b24-00025b00a5a5`
- `81c2e72a-0591-443e-a1ff-05f988593351`
- `9b26d8c0-a8ed-440b-95b0-c4714a518bcc`
- `df21fe2c-2515-4fdb-8886-f12c4d67927c` (also reported by Buds 4)
- `f8d1fbe4-7966-4334-8024-ff96c9330e15`

Authenticated queries returned ANC bitmap index 3, current EQ ID 7, and an
empty EQ catalogue. Index 3 means Off in the three comparison profiles, but
the Pro 4 app setting has yet to be checked. Pro 2 maps EQ ID 7 to Hans Zimmer
Soundscape Tuning, while Nord uses it as the base for custom slots. Buds 4
maps factory IDs 0–2 and exposes six-band custom entries. These mappings do
not establish the Pro 4 labels or layout. An empty catalogue does not rule
out custom EQ. No control writes were performed.

Worn baseline confirmed against the phone app: Adaptive ANC read back as
bitmap index 13, and Dynaudio Featured read back as EQ ID 7. These are the
original settings to restore during testing. The earlier index 3 remains
unmapped for Pro 4.

First ANC trial: Transparency selected in the phone app read back as index
8 in a fresh session. The wearer heard little difference in a quiet room.
The app's Adaptive setting was Standard, described as balancing cancellation
and transparency. After Adaptive was reselected in the app, fresh readback
confirmed Adaptive and EQ ID 7 (Dynaudio Featured). The protocol readback
did not expose the Adaptive strength setting.

First EQ trial: Balanced selected in the phone app read back as factory
ID 0 in a fresh session. The wearer heard a noticeable difference from
Dynaudio Featured. After restoration in the phone app, independent readbacks
confirmed Dynaudio Featured (ID 7) and Adaptive ANC.

The phone app lists Balanced, Bold, Serenade, Bass, and Dynaudio Featured.
Bold, Serenade, and Bass read back as IDs 1, 2, and 3, respectively, with a
noticeable audible difference reported for each. After the full factory
preset sweep, fresh readbacks confirmed Adaptive and Dynaudio Featured (ID 7).
The app's custom EQ editor shows ten
bands at 31, 62, 125, 250, 500,
1000, 2000, 4000, 8000, and 16000 Hz. This differs from the six-band Buds 4
catalogue. Although empty during discovery, the catalogue during the Bold
trial returned an inactive entry named Custom1 (ID 4), with those same ten
bands, all at 0 dB, and limits of −6 to +6 dB. The total slot count and
custom write behavior remain unverified.

Opening the custom editor in the phone app selected Custom1. A fresh query
confirmed active EQ ID 4 and all ten baseline gains at 0 dB.
The phone-app trial raised only 1 kHz to +3 dB. Fresh readback confirmed
the change and the other nine gains stayed at 0 dB. The wearer heard a
difference. After restoring 1 kHz in the app, fresh readback confirmed all
ten gains at 0 dB with Custom1 still active. A subsequent fresh EQ readback
confirmed Dynaudio Featured (ID 7) active and Custom1 still flat. Two
standalone ANC queries at that point did not decode a mode. The phone app
still showed Adaptive with Standard selected. A follow-up authenticated
probe stopped before the ANC query because product identification did not
return the expected ID in that session.
On retry, three independent sessions using a response-matched product query
followed by an authenticated ANC query all identified product 067814 and
reported index 13 (Adaptive). Standard remains an app-confirmed setting.

Phone ANC capture baseline: Linux independently read Adaptive. Reconfirm
Standard in the app immediately before capture. For two rounds, select
Transparency then Adaptive in the official app and pause after each tap for
a fresh Linux readback. Record each app command and matching response by
direction, opcode, sequence where present, and relevant payload or status.
Keep notifications separate from acknowledgements. Expected read indices
are 8 and 13. After round two, check Standard again in the app. Retain raw
phone logs locally outside the repository. No Linux writes in this stage.

- Round 1, first tap: the app selected Transparency and a fresh Linux query
  decoded Transparency (index 8). Phone command and response correlation
  awaits the local capture.
- Round 1, second tap: the app selected Adaptive and a fresh Linux query
  decoded Adaptive (index 13). Phone command and response correlation
  awaits the local capture.
- Round 2, first tap: the app selected Transparency and a fresh Linux query
  decoded Transparency (index 8). Phone command and response correlation
  awaits the local capture.
- Round 2, second tap: the app selected Adaptive and a fresh Linux query
  decoded Adaptive (index 13). Final Standard selection awaits confirmation
  in the app. Phone command and response correlation awaits the local capture.

The phone capture was dropped from the test plan. Both phone-app rounds
independently confirmed restoration to Adaptive before the Linux trial.
After identifying product 067814 and reading Adaptive (index 13), Linux
sent one SET ANC command (0x0404, sequence 0x42, payload `01 01 04`),
using the Pro 2 and Buds 4 Transparency mapping. The matching response
(0x8404, sequence 0x42) carried status `00`. A separate authenticated
session read Transparency (index 8, payload `00 01 01 00 01`).
The wearer confirmed the switch and restored Adaptive in the phone app.
A fresh Linux query decoded Adaptive (index 13), and the wearer confirmed
Standard in the phone app after restoration.

Adaptive strength comparison (fresh authenticated query at each step):

- Starting Standard: response `0x810c`, payload `00 01 01 00 20`,
  Adaptive index 13, no decoded level.
- Less noise: response `0x810c`, payload `00 01 01 00 10`, bitmap index
  12. Only the final payload byte changed. The current profile has no
  mapping for index 12, so the decoder returned no ANC state.
- More noise: response `0x810c`, payload `00 01 01 00 40`, bitmap index
  14. Only the final payload byte changed. The current profile has no
  mapping for index 14, so the decoder returned no ANC state.
- Restored Standard: response `0x810c`, payload `00 01 01 00 20`,
  Adaptive index 13, no decoded level. The payload matched the baseline.

The query distinguishes all three settings through the final bitmap byte.
The response opcode and preceding four payload bytes were identical.

Linux Adaptive / Standard candidate trial: both SET commands used opcode
`0x0404`, sequence `0x42`, and received matching `0x8404` status `00`.
Transparency payload `01 01 04` read back as `00 01 01 00 01`.
From that verified state, Standard candidate payload `01 01 00 20` read
back as `00 01 01 00 20` in a separate authenticated session. The wearer
confirmed Adaptive / Standard in the official app.

Linux then tested the other Adaptive settings one at a time. Each
`0x0404` write used sequence `0x42`, received a matching `0x8404`
status `00`, and was verified in a separate authenticated session:

| Step | SET payload | Fresh `0x810c` response payload |
|---|---|---|
| Less noise | `01 01 00 10` | `00 01 01 00 10` |
| Restore Standard | `01 01 00 20` | `00 01 01 00 20` |
| More noise | `01 01 00 40` | `00 01 01 00 40` |
| Restore Standard | `01 01 00 20` | `00 01 01 00 20` |

Panel writes remained disabled throughout these trials.

Live Omarchy panel trial: enabled only Transparency and the three Adaptive
settings. Starting on Standard, the panel's Transparency write returned
status 00 and verified Transparency. The next panel write returned status
00 and verified Adaptive / Standard. Selecting Less noise next returned
status 00 and verified Adaptive / Less noise. More noise also returned
status 00 and verified Adaptive / More noise. The final Standard selection
returned status 00 and verified Standard. After a deliberate Bluetooth
disconnect and reconnect, the panel opened a fresh session and again
reported Adaptive / Standard without another write. Other Pro 4 ANC modes
remain disabled pending separate write tests.

## Hardware validation order

1. In the phone app, record the original ANC mode and strength, active EQ
   preset, available preset names, and any existing custom curve. With both
   earbuds worn, switch one ANC mode at a time in the app. Check the audible
   change and query from a fresh Linux session after each switch. Restore the
   original mode and strength and repeat the readback.
2. With a familiar track at fixed volume, select factory presets one at a
   time in the app. Record labels, fresh EQ IDs and audible differences.
   Restore the original selection and verify it. Inspect the custom editor
   for frequencies and gain limits before considering any custom edit.
3. Only after correlating app settings with readback, test Linux writes
   separately. Require fresh readback, physical confirmation and restoration
   for each operation before granting its profile write permission.
