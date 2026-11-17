# OnePlus Nord Buds 3 Pro (community test device)

Compatibility status: **Community Tested** by a contributor, not maintainer
Verified. One owner unit was measured locally between 2026-10-27 and
2026-10-31; this record was produced from those measurements, not by copying
another model's profile. No new hardware tests were run for this contribution,
and no other model or firmware was tested.

Scope of this record: ANC modes/strengths (including Auto) and the three
factory EQ presets. The contributor's fork also explored custom EQ, touch
controls, feature switches, find-my-earbuds and case-battery caching; those are
deliberately **not** part of this contribution and are not claimed here.

## Device identity (measured 2026-10-27)

- BlueZ name: `OnePlus Nord Buds 3 Pro`
- Bluetooth modalias: `bluetooth:v02B0p0000d001F`
- OPO vendor service `0000079a-d102-11e1-9b23-00025b00a5a5`, RFCOMM channel 15
- OPO product query `0x0103` returns `064414`
- Recorded firmware `155.155.101` (kind-2 component records 155/155/101).
  The version query is optional; a session that does not answer it simply
  shows no firmware string.
- Standard 0xAA framing, capability primer, HELLO/REGISTER authentication and
  the authenticated SET flow behave as documented for the other OPOv1 models.
- Component battery query returned left/right percentages plus a case entry
  (`00 03 01 64 02 64 03 32` on 2026-10-31). The panel shows the case value
  when the device reports it; there is no case-battery cache in this profile.

The Bluetooth address is deliberately not recorded.

## ANC profile (measured, all four strengths confirmed on the unit)

The device uses the same little-endian bitmap convention as the Buds Pro 2.
Every mode below was written with the authenticated `0x0404` flow, acknowledged
with status `00`, and confirmed by independent fresh device state.

| Display label | Internal key | Write index/bitmap | Observed read index |
|---|---|---:|---:|
| Off | `off` | 0 / `01` | 0 |
| Noise cancellation | `on` | 1 / `02` | active level index |
| Transparency | `transparency` | 2 / `04` | 2 |
| High | `deep` | 4 / `10` | 4 |
| Moderate | `medium` | 5 / `20` | 5 |
| Low | `light` | 6 / `40` | 6 |
| Auto | `auto` | 7 / `80` | selected-mode notification |

Two behaviours differ from the Buds Pro 2:

- The main ANC On command (`02`) does not report the parent mode. The device
  answers with the level it actually applied (`10`, `20` or `40`).
- While Auto is selected, the selected-mode query `0x010c 01 01` can return
  the concrete intensity the adaptive algorithm settled on (for example
  `00 01 01 40`), and the active-intensity query `0x010c 04 01` reports the
  same concrete level. Only the pushed selected-mode notification
  `0x0204 03 01 01 80` confirms Auto. Active-intensity notifications
  (`03 04 01 bitmap`) and query responses with a foreign sequence never
  replace the selection, and a later contradictory selected-mode push
  supersedes an earlier one. An acknowledgement alone is never success.

The CLI's one-shot path applies the same confirmation rule: a matching
selected-mode notification confirms Auto when the fresh state query reports
the concrete intensity; without it the write stays unverified.

The mapping is not a guess: the phone app's encrypted model table
(`resources/res/raw/melody_app_whitelist.json`, AES/GCM with the signing
certificate's SHA-256) lists exactly these indices for `064414`, including
Auto at index 7, and the independent measurements match it entry for entry.

### English labels (rechecked 2026-10-31)

The display labels **Low, Moderate, High, Auto** match the English resources
the app selects for `064414` in Wireless Earphones 17.6.6 (`com.oplus.melody`,
SHA256 `ed75c8f4ad06ebdb2100477b6db75c49931c2514127f390b259b6bff8c768641`).
The whitelist pairs protocol indices 6/5/4/7 with mode types 3/8/4/7;
`wa.i.b(Context,Integer)` selects these resource keys:

| Internal key | App mode type | English label |
|---|---:|---|
| `light` | 3 | Low |
| `medium` | 8 | Moderate |
| `deep` | 4 | High |
| `auto` | 7 | Auto |

The APK also contains Smart in legacy/other UI contexts and Adaptive for a
separate mode type 10; neither replaces the Nord strength label Auto in this
selector. Internal keys stay `light`/`medium`/`deep`/`auto`; only the display
labels are model-specific (`AncProfile.level_labels`). The decompiled app is
static evidence, not a phone runtime trace; the REA/JADX exports remain in the
contributor's research folder and are not shipped. HeyMelody 117.6.6 was not
supplied and has not been compared.

### Session reuse and latency (measured 2026-10-31)

All supported strengths use the one authenticated controller session. Before
that, strength writes closed the monitoring socket, rediscovered the device,
authenticated, wrote, verified on another socket and resubscribed: Low and the
restoration to Moderate took 15.52/15.30 s at the frontend. With the warm
session, controller verification took 60.7/118.3/72.9/60.2 ms for
Low/Moderate/High/Auto and the confirmed selection appeared after
149.7/302.7/152.0/151.2 ms. The IPC harness samples every 80 ms plus process
overhead, so frontend values are observed bounds, not exact render times.
The device's audible application time was not measured. The original Moderate
state was restored and confirmed after every test sequence.

Sanitized hardware records:
[ANC latency measurement](../measurements/2026-10-31-nord-anc-latency.json)
(includes the legacy-path baseline, the Auto notification/timeout behaviour
and the final worn-state verification).

One observed guard: a strength write can be refused while both buds are
unworn or in the case (the app guards the same condition). Direct
Off → Low succeeded with the buds worn, so an ANC-On prerequisite is not
required on this unit.

## Native EQ (measured)

The device accepts the factory IDs 0 to 6: a selection is acknowledged with
status `00` and confirmed by a fresh `0x010f` read; unknown IDs leave the
current selection untouched. The phone app offers exactly three of them, and
the owner confirmed the mapping by changing every preset in the app and
reading the device back:

| App label | Factory ID | Plugin name |
|---|---:|---|
| Ausgewogen (Standard) / Balanced | 3 | Balanced (Default) |
| Serenade | 4 | Serenade |
| Bass | 5 | Bass |

The same mapping appears in the app's decrypted model table for `064414`
(`equalizerMode`: protocolIndex 3/4/5 for modeType 11/14/12). The German CLI
alias `ausgewogen` resolves to ID 3.

The native EQ catalogue query (`0x0122`) answers `00 00`: the device publishes
no preset names, band definitions or custom entries of its own. This profile
therefore offers preset selection only. Custom EQ writes are **not**
authorized: `community_write_permissions` is exactly `{"anc", "eq_preset"}`.

## Limitations

- One contributor unit, recorded firmware `155.155.101`. Other firmware may
  behave differently; nothing here verifies another model or the family.
- No acoustic measurements: audible switching latency, sound effect of the
  presets and Auto's acoustic behaviour were not recorded.
- The historical measurements predate this PR; the contribution re-uses them
  and adds offline regression tests only. No hardware write tests or audio
  playback were performed for it.
- Feature switches, touch controls, find-my-earbuds, custom EQ and
  case-battery caching are out of scope and remain unavailable on this
  profile. Switch IDs `0x06` and `0x0b` stay unnamed: the capability audit
  (`0x8100: 00 ff 27 52 ee c7 14`) and the app model table show no model
  support for the separate game-mode switch, and `0x0b` is Golden Sound on
  this model, not the shared hearing-enhancement name.
