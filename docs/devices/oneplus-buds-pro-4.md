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

## Off and fixed Noise cancellation trials

Starting baseline: a fresh authenticated Linux query returned Adaptive /
Standard, index 13, response `0x810c`, payload `00 01 01 00 20`.
The panel was temporarily disabled to release its RFCOMM session.

The official app selected Off and the wearer noticed a change. A fresh
Linux reply (`0x810c`) carried `00 01 01 08 00`, bitmap index 3.
The Pro 2 and Buds 4 use write index 0 for Off, making `01 01 01` the
candidate SET payload. Read index 3 is a separate observation.

Linux Off trial: after confirming Standard (`00 01 01 00 20`), sent one
`0x0404` SET, sequence `0x42`, payload `01 01 01`. The matching
`0x8404` response carried status `00`. A fresh session returned
`00 01 01 08 00` (Off, index 3). The wearer confirmed it sounded correct
and restored Adaptive in the phone app. Fresh Linux readback returned
`00 01 01 00 20` (Standard, index 13).

The official app lists High, Moderate, Low, and Auto under Noise
cancellation. With High selected, a fresh Linux reply (`0x810c`) carried
`00 01 01 10 00`, bitmap index 4. The Pro 2 and Buds 4 have a distinct
explicit High write (index 4, payload `01 01 10`), which is the candidate
for this trial. Their generic Noise cancellation write uses index 1 and
does not specify a strength. The Pro 4 read index is independent evidence.

Linux High trial: the fresh baseline was Standard (`00 01 01 00 20`).
One `0x0404` SET (sequence `0x42`, payload `01 01 10`) got matching
`0x8404` status `00`. A separate session read `00 01 01 10 00`
(Noise cancellation / High, index 4). The wearer confirmed it sounded
correct and restored Adaptive in the app. Fresh readback confirmed Standard
at index 13 (`00 01 01 00 20`). Only Off and explicit High were added to
the panel for these two trials.

Live panel trial: selecting Off returned status `00` and verified Off
by readback. The panel showed Off selected. Selecting Adaptive / Standard
next returned status `00` and verified Standard before the High trial.
Selecting High returned status `00` and verified Noise cancellation /
High (`on` / `deep`). The final Standard selection returned status `00`
and verified Adaptive / Standard. A deliberate Bluetooth disconnect and
reconnect opened a fresh panel session, which read and displayed Adaptive /
Standard without another write. Generic Noise cancellation, Moderate,
Low, and Auto remain disabled pending separate tests.

## Remaining Noise cancellation strengths

Starting Adaptive / Standard read back as index 13, payload
`00 01 01 00 20`. Phone-selected Moderate returned response `0x810c`,
payload `00 01 01 20 00`, bitmap read index 5. The Pro 2 and Buds 4
explicit Moderate write uses index 5, yielding candidate payload
`01 01 20`. The read and candidate write mappings are independent.

From verified Standard (`00 01 01 00 20`), one Linux Moderate SET
(`0x0404`, sequence `0x42`, payload `01 01 20`) received matching
`0x8404` status `00`. A fresh session returned `00 01 01 20 00`
(Moderate, index 5). The wearer confirmed the sound and restored Adaptive
in the app. Fresh readback confirmed Standard (index 13, payload
`00 01 01 00 20`) before Moderate was enabled in the local profile.

Phone-selected Low returned `0x810c` payload `00 01 01 40 00`, read
index 6. The explicit Pro 2 and Buds 4 Low write independently supplies
candidate write index 6, payload `01 01 40`.

From verified Standard, one Linux Low SET (`0x0404`, sequence `0x42`,
payload `01 01 40`) received matching `0x8404` status `00`. A fresh
session returned `00 01 01 40 00` (Low, index 6). The wearer confirmed
the sound and restored Adaptive in the app. Fresh readback confirmed
Standard at index 13, payload `00 01 01 00 20`, before Low was enabled.

Phone-selected Noise cancellation / Auto returned `0x810c` payload
`00 01 01 80 00`, read index 7. The Nord's explicit Auto and the
Pro 2 and Buds 4 Smart writes use write index 7, yielding candidate
payload `01 01 80`. This is distinct from the Adaptive settings at
indices 12–14.

From verified Standard, one Linux Auto SET (`0x0404`, sequence `0x42`,
payload `01 01 80`) received matching `0x8404` status `00`. A fresh
session returned `00 01 01 80 00` (Noise cancellation / Auto, index 7).
The wearer confirmed the sound and restored Adaptive in the app. Fresh
readback confirmed Standard at index 13, payload `00 01 01 00 20`, before
Auto was enabled under Noise cancellation. Pro 4 Auto uses query readback
and remains separate from Adaptive and from the Nord notification fallback.

## Linux EQ write trials

Baseline: Dynaudio Featured (ID 7) selected. Custom1 (ID 4) was inactive
with all ten gains at 0 dB (31, 62, 125, 250, 500, 1000, 2000, 4000,
8000, and 16000 Hz), limits −6 to +6 dB, and a 1 dB step.

- Factory SET EQ (`0x0406`): selected Balanced (ID 0), then restored
  Dynaudio Featured (ID 7). Both writes returned status 00. Separate
  Bluetooth sessions confirmed both selections and the unchanged curve.
- Custom SET EQ detail (`0x0418`): raised only 1 kHz to +1 dB. The write
  returned status 00 and selected Custom1. A separate session confirmed
  the full curve. Restoring the original gains and then Dynaudio Featured
  both returned status 00. A final separate session confirmed all ten
  gains at 0 dB and Dynaudio Featured active.

Initially only Balanced and Dynaudio Featured were enabled for factory
writes. In subsequent standalone Linux trials, Bold (ID 1), Serenade
(ID 2), and Bass (ID 3) each returned status 00 and were verified in an
independent Bluetooth session. Each trial restored Dynaudio Featured
(ID 7), also acknowledged and verified in a fresh session. Custom1
matched the baseline after every selection and restoration. All five
factory presets are now write-enabled. Curve writes are limited to
Custom1, and slot management remains disabled.

Live panel EQ trial: Balanced (ID 0) was selected from Dynaudio Featured.
The panel write returned status 00 and verified Balanced by readback.
Selecting Dynaudio Featured next returned status 00 and verified ID 7.
The panel's curve readback still showed all ten Custom1 bands at 0 dB.
Editing Custom1 in the panel returned status 00 and verified active ID 4.
The full readback showed 1 kHz at +1 dB and all nine other bands at 0 dB.
After restoring 1 kHz in the panel and selecting Dynaudio Featured, the
final panel readback confirmed ID 7 active and all ten Custom1 gains at
their original 0 dB. The final preset write returned status 00.

Follow-up panel trial: selecting Bold (ID 1) returned status 00 and
verified Bold by readback. Selecting Serenade (ID 2) also returned
status 00 and verified Serenade by readback. Selecting Bass (ID 3)
returned status 00 and verified Bass by readback.
The final Dynaudio Featured selection returned status 00. Panel readback
confirmed ID 7 active and all ten Custom1 gains still at 0 dB.

## Custom profile creation investigation

Before creation, live Linux catalogue for product 067814 showed Dynaudio
Featured (ID 7) active and only Custom1 (ID 4), inactive. Its bands at
31, 62, 125, 250, 500, 1000, 2000, 4000, 8000, and 16000 Hz were all
0 dB, with limits −6 to +6 dB and a 1 dB step.

The official app added Temp in slot 5 and made it active. A fresh Linux
session confirmed both slots. Temp matched Custom1's ten frequencies and
gain limits, with every band at 0 dB. Custom1 was unchanged. Slot 5 is
the only additional slot observed so far.

After removing Temp in the app, a fresh read confirmed the exact baseline.
The existing Linux create path then created LinuxTemp in slot 5 with status
00. An independent session verified the new flat curve, untouched Custom1,
and Dynaudio Featured still active. Separate Linux rename to LinuxRenamed
and delete each returned status 00. Fresh reads verified the name change
without curve changes, then removal and exact baseline restoration.
Panel creation, rename, and delete are limited to slot 5. Editing remains
limited to Custom1, which is protected from rename and delete.

The panel Add profile trial created PanelTemp in slot 5 with status 00.
Panel readback confirmed both flat curves and Dynaudio Featured active.
Panel deletion of PanelTemp returned status 00 and verified slot 5 absent.
A separate authenticated Linux session then confirmed Dynaudio Featured
(ID 7) active and only Custom1 (ID 4) remaining, with its original ten
frequencies, 0 dB gains and −6 to +6 dB limits. The panel was re-enabled
in its original position after the independent read.

Last-profile test: with the owner's expendable Custom1 backed by a flat
baseline read, an isolated Linux delete of slot 4 returned status 00.
A fresh session found an empty catalogue and Dynaudio Featured (ID 7)
still active. The standard Linux create path then stopped before sending
a write because no existing curve supplied a layout. The panel also
hides its custom EQ section when the catalogue is empty. This reproduces
the Linux recovery problem. Firmware creation from an empty catalogue
had not yet been tested at that point.
The official app recovered the empty catalogue by creating Custom1 in
slot 4. Fresh Linux readback confirmed the original flat ten-band layout
and gain limits. The recreated Custom1 was active at verification.

Linux recovery follow-up: restored Dynaudio Featured, then deleted the
expendable Custom1 in an isolated trial. A separate session confirmed the
empty catalogue. A Pro 4-only local layout template supplied the ten
frequencies and gain limits to the existing create path for slot 4.
Creation returned status 00. Another session confirmed the exact original
Custom1 entry and Dynaudio Featured active. The template is not exposed in
the catalogue. The panel keeps Add profile visible on an empty catalogue
for profiles with a tested template. No Nord template was inferred.

## Wear detection investigation

Starting Linux read (2026-11-25), firmware previously recorded as
`116.116.100`: an authenticated feature-status reply (`0x810d`) reported
candidate switch `0x04` as true. Other true IDs were `0x05, 0x06, 0x11,
0x13`; false IDs were `0x0b, 0x18, 0x27, 0x28`. The app's starting
setting was On, labeled In-ear detection. After the wearer disabled it in
the app, a fresh Linux reply reported `0x04=false`. All other reported
switches matched the baseline. Turning it back on in the app returned
`0x04=true` with the rest unchanged.

Linux then sent one feature SET (`0x0403`, payload `04 00`) from the
confirmed On state. The matching `0x8403` acknowledgement was `00`.
An independent session read `0x04=false`; every other switch still
matched the baseline. Playback continued on removal with detection Off.
With detection On, removal paused playback. The app detected reinsertion,
but playback did not automatically resume in this trial. A fresh Linux
read verified original On restored, with all other switches unchanged.
Only In-ear detection is enabled for feature writes in the local panel.
The panel Off trial returned status `00` and verified `0x04=false`.
The panel On write also returned status `00` and verified `0x04=true`.
A separate authenticated Linux session confirmed the original On setting
and all other reported switches matched the baseline. The widget was
re-enabled in its original bar position after the independent read.

## Touch controls investigation

Fresh authenticated baseline for product `067814` (2026-11-25). The
`0x8108` response reported these function IDs by (button, action):

| Button | Action | Left | Right |
|---:|---:|---:|---:|
| 1 | 1 | 34 | 1 |
| 1 | 2 | 6 | 6 |
| 1 | 3 | 35 | 5 |
| 1 | 4 | 8 | 8 |
| 1 | 5 | 7 | 7 |
| 1 | 6 | 18 | 18 |
| 6 | 1 | 29 | 29 |
| 6 | 2 | 28 | 28 |
| 6 | 3 | 0 | 0 |

Both double presses report function 6, the existing Next track mapping.
Other IDs are recorded as observations and do not authorize any writes.

The official app changed Left double press to Previous track. A fresh
Linux read showed only (left, button 1, action 2) changed, from function
6 to 5. Right double press remained 6 and the other 16 entries matched.

The wearer restored Next track in the app. A fresh Linux read matched
all 18 baseline entries. A single Linux touch SET with payload
`01 01 01 02 05` was acknowledged. A separate authenticated session
confirmed Left double press at function 5 and the other 17 entries
unchanged. The wearer confirmed the gesture selected the previous track.
Linux restored Next track with payload `01 01 01 02 06` and acknowledgement
`00`; an independent read matched all 18 original entries. Only Left
double press, with Previous track and Next track, is enabled for panel
writes. The right side, other actions, and shared ANC hold cycle still
require separate validation.
The panel Previous track trial returned status `00` and verified the
Left double-press assignment at function 5. The panel readback matched
the other 17 baseline entries. Restoring Next track in the panel also
returned status `00`. Both the panel readback and a separate Linux
session matched all 18 original entries.

Right double-press app trial: selecting Previous track changed only
(right, button 1, action 2), from 6 to 5. All other 17 entries matched
the baseline. A fresh read after app restoration matched all 18 baseline
entries. Linux then sent one SET `0x0401`, payload `01 02 01 02 05`,
and received acknowledgement `00`. An independent session confirmed
Right double press at function 5 and the other 17 entries unchanged.
The wearer confirmed that the gesture selected the previous track.
Linux restored Next track using `01 02 01 02 06` with status `00`, and
a fresh session matched all 18 baseline entries. The right-side double
press is enabled for the same two choices. The panel Previous track write
returned status `00`; readback verified function 5 and confirmed the
other 17 entries were unchanged. Restoring Next track in the panel returned
status `00`. Panel readback and a separate Bluetooth session both matched
all 18 original assignments.

Right triple-press app trial: selecting Next track changed only (right,
button 1, action 3) from function 5 to 6. The other 17 entries matched the
baseline. The app offers additional gesture choices; only separately
tested assignments are candidates for the panel.
The phone-app restore matched all 18 baseline entries. One Linux SET
(`0x0401`, payload `01 02 01 03 06`) received status `00`. A separate
session confirmed function 6 and the other 17 entries unchanged.
The wearer confirmed that the gesture advanced the track. Linux restored
Previous track with payload `01 02 01 03 05` and status `00`. A fresh
session matched all 18 baseline entries. Right triple press is enabled
for Previous track and Next track in the local panel. The panel Next track
write returned status `00`. Readback verified function 6 and all other
17 entries matched the baseline. Restoring Previous track in the panel
returned status `00`. Panel readback and a fresh independent Linux
session each matched all 18 original assignments.

Left triple-press app trial: the wearer identified the original function
35 as Gemini. Selecting Next track changed (left, button 1, action 3)
from 35 to 6. Left single press also changed from 34 to 1. The other
16 entries matched the baseline. No Linux write was attempted.
After restoring Gemini, the app showed a combined single-press option
“Play / pause / stop Gemini” and the alternative “None”. A fresh Linux
read matched all 18 baseline entries, including left single press 34
and left triple press 35. Treat those assignments as coupled and leave
their panel writes disabled pending separate validation.

Right single-press app trial: the options were “Play / pause / stop
Gemini” and “None”. Selecting None changed only (right, button 1, action
1) from function 1 to 0. The other 17 entries matched the baseline.
After the app re-enabled Right single press, Linux reported right single
press 34 and right triple press 35, instead of the original 1 and 5.
The other 16 entries matched. The baseline check stopped the trial
before any Linux write. Restore the right triple-press assignment in
the app and both values return to baseline: 1 for right single press
and 5 for right triple press. A fresh query matched all 18 entries.
From that exact baseline, one Linux SET (`0x0401`, payload
`01 02 01 01 00`) returned status `00`. A separate session verified
right single press 0 and the other 17 assignments unchanged.
The wearer confirmed playback continued on Right single press. Linux
restored function 1 with payload `01 02 01 01 01` and status `00`.
An independent session matched all 18 baseline entries, including
Right triple press at function 5. Right single press is enabled for
None and Play / pause only. The panel None write returned status `00`
and verified function 0. All other 17 assignments matched the baseline.
Restoring Play / pause in the panel returned status `00`. Panel and
independent Linux reads both matched all 18 original assignments.

Shared ANC hold-cycle baseline: authenticated query `0x010c` with
payload `02 01` returned `0x810c` payload `00 02 01 06 00`.
Active ANC was Adaptive / Standard (`00 01 01 00 20`). The hold-cycle
reply has an extra byte compared with the existing Nord parser. Phone-app
labels include Noise cancellation, Adaptive, Transparency, and Off. The
earbud-specific app screen showed Noise cancellation + Transparency.
After the wearer changed both sides to Noise cancellation + Off, a fresh
reply was `00 02 01 03 00`. All 18 gesture entries and active Adaptive /
Standard matched baseline. Whether the cycle is shared remains unverified.
After the reported left-only return to Transparency, a fresh query still
returned `00 02 01 03 00`. The 18 gesture entries and active ANC matched
baseline. The wearer checked both app screens: left showed Noise
control with Noise cancellation + Transparency, and right showed Noise
control with Noise cancellation + Off. The reply matched the right
selection in this split state. The app supports per-earbud cycles;
the query's addressing and any write scope are still unverified.
Restoring the right side to Transparency returned the original
`00 02 01 06 00`. Re-establishing the split with both earbuds out
(left Cancellation + Transparency, right Cancellation + Off)
again returned `00 02 01 03 00`, the baseline for the isolation trial.
With the right bud in the closed case and the left out, a fresh session
still returned `00 02 01 03 00` and all 18 gesture entries. Active ANC
reported Transparency (`00 01 01 00 01`) during this trial. Casing the
right bud did not expose the left cycle through this query. No cycle
write was sent.
After taking the right bud out and restoring its original cycle in the
official app, a fresh session returned the baseline hold reply
`00 02 01 06 00`, active Adaptive / Standard (`00 01 01 00 20`), and all
18 original gesture assignments. The panel was re-enabled. Pro 4 hold
cycle writes remain disabled pending a side-addressing test.

### Left gesture and volume-slide follow-up

Saved a fresh `0x8108` baseline before any changes. All 18 tuples matched
the original table above, including left single press 34, left triple
press 35, and function 7 on button 1/action 5 on both sides.
App selection of None for left single press changed function 34 to 0
and left triple press 35 to 5. The wearer reported that this disables
Gemini integration in the app. All other 16 entries matched baseline.
After the app restore, a fresh authenticated query matched all 18
baseline entries, including left single 34 and left triple 35.
Repeating the separate Left triple press → Next track app trial reproduced
both changes: left triple 35 → 6 and left single 34 → 1. All 16 other
entries matched baseline.

After restoring the app baseline, one Linux SET `0x0401` with payload
`01 01 01 01 00` returned status `00`. A separate session showed only
Left single press changed to 0. Left triple press remained 35 and the
other 16 entries also matched. The phone app showed None and Gemini
respectively, and a left single press did not pause music. Linux restored
34 with `01 01 01 01 22`, status `00`; a fresh session confirmed the
full baseline before the next write.

One Linux Left triple-press SET (`01 01 01 03 06`) returned status
`00`. A separate session found only triple press changed, to 6, while
single press stayed 34. The app showed Play / pause / stop Gemini for
single and Next track for triple. The wearer confirmed that a triple
press advanced playback. Linux restored Gemini (35) with payload
`01 01 01 03 23` and status `00`. A separate session matched all 18
original entries.

The phone app offered Volume control and Switch track for the left slide.
Selecting Switch track changed only left button 1/action 5, function
7 → 10. Right slide stayed at 7 and the other 16 entries matched.
Restoring left Volume control matched all 18 baseline entries.
The right slide offered the same choices. Selecting Switch track
changed only right button 1/action 5 from 7 to 10. This confirms the
same mapping independently on both earbuds. No slide writes were sent.
Restoring right Volume control matched all 18 baseline entries in a
fresh session. The panel labels Slide read-only, hides Long hold on
both sides, and leaves Touch & hold read-only. The complete raw gesture
table is retained in panel status diagnostics. The left Gemini-related
assignments are labeled but remain read-only in the panel.

Follow-up panel build keeps the Gemini assignments visible as current
values and offers only None for left single or Next track for left
triple. Restoring Gemini is an app operation. The panel None write
returned status `00`; its readback matched all other 17 entries,
including Gemini (35) on left triple press.
The wearer reported Gemini integration stayed enabled after the panel
write, so the app could directly restore Play / pause / stop Gemini.
A separate Bluetooth session verified all 18 original entries.
The panel Left triple-press Next track write also returned status
`00`. Readback confirmed function 6, single press still 34, and all
other 16 entries unchanged. The wearer restored Gemini in the app and
confirmed the menus still appeared. Live readback matched all 18 original
assignments and both menus still advertised their verified targets.
The wearer reported neither panel change disabled Gemini integration.

Left Slide Linux trial: from the full original table, SET `0x0401`
payload `01 01 01 05 0a` returned status `00`. A separate session
confirmed only Left Slide changed to 10. The wearer confirmed the app
setting and the gesture: down advanced tracks and up went back. The
first pre-restore read already showed 7, so no write was sent at that
point. A repeat Linux write to 10 and explicit restore to 7 both
received status `00` and matched their expected full tables in fresh
sessions. The cause of the initial return to 7 was not established.

Right Slide trial: SET `0x0401`, payload `01 02 01 05 0a`,
received status `00`. Fresh readback verified Right Slide 10 and
the other 17 entries unchanged. The wearer confirmed the app setting
and track switching. Linux restored right Volume control with payload
`01 02 01 05 07` and status `00`. A separate session verified all 18
original entries. Both Slide menus now offer the two verified functions.
Touch & hold stays read-only and Long hold remains hidden.

Follow-up: per-earbud squeeze-and-hold editing. Identify side-addressed
reads and writes, then verify each side independently against the app,
fresh readback, and the physical cycle. Check that the opposite earbud
stays unchanged and restore both original cycles before enabling editing.

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
