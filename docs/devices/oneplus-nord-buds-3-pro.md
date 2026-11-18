# OnePlus Nord Buds 3 Pro (community test device)

Compatibility status: **Community Tested** by a contributor, not maintainer
Verified. One owner unit was measured locally between 2026-10-27 and
2026-10-31; this record was produced from those measurements, not by copying
another model's profile. No new hardware tests were run for this contribution,
and no other model or firmware was tested.

Scope of this record: ANC modes/strengths (including Auto), the three factory
EQ presets, custom-EQ curve editing and profile management, touch assignments
and the shared hold cycle, the audited feature switches, BassWave level,
find-my-earbuds and case-battery caching. Each write class has its own
operation permission backed by the owner measurements below; one permission
never enables another. Device rename (a BlueZ alias write) and the raw
diagnostic query are deliberately **not** part of this contribution.

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
  when the device reports it and remembers the last usable level per device
  (see [Case battery](#case-battery-cache)).

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

The CLI's one-shot path applies the same confirmation rules: the latest
selected-mode notification confirms Auto when the fresh state query reports
the concrete intensity, and only the sequence-correlated query reply counts
as device state. Without confirmation the write stays unverified.

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

The native EQ catalogue query (`0x0122`) answers `00 00` on a fresh unit: the
device publishes no preset names or band definitions of its own. Custom
entries are created through `0x0418` (see below); the device holds exactly
three custom slots (IDs 7, 8, 9) and refused ID 10. Factory preset selection
and custom-EQ writes are authorized (`eq_preset`, `custom_eq`); management
(create/rename/delete) is gated separately by `custom_manage_verified`, which
only this model has.


## Custom EQ management (measured 2026-10-31)

`0x0418` carries an action byte: **1 create, 2 update (curve or name),
3 delete**. The app builds `[action, min, max, eq_id, name_length, name,
band_count, (frequency, gain)…]` (`HeadsetCoreService.M0`). On the owner's
unit, create stored a new profile in the next free slot (7–9), rename stored
the new name with the unchanged curve, and delete removed it again; each was
confirmed by a fresh `0x0122` catalogue read. The band layout and gain limits
always come from the device. A custom write also selects that profile on this
firmware, so create/rename restore the previously active profile afterwards.
Selecting an existing custom entry writes its unchanged curve back (the plain
`0x0406` is ignored for custom IDs on this model). Names are bounded to
non-empty, control-character-free, ≤255 UTF-8 bytes.
See [EQ profile measurement](../measurements/2026-10-31-nord-eq-profiles.json)
and [EQ curve measurement](../measurements/2026-10-31-nord-eq-curve.json).

## Touch controls and hold cycle (measured 2026-10-28)

The authenticated query `0x0108` returns `[status, count, (device_type,
button, action, function)…]`; the unit reports ten entries (five per side).
A single assignment is written with `0x0401 [01, device_type, 01, action,
function]` and verified with a fresh `0x0108`, never the ACK alone. 36
gesture/function round-trips were confirmed. Wire actions 1/2/3/6 are
configurable; action 4 is the fixed noise-control hold. The shared hold cycle
is read/written through `0x010c`/`0x0404` with the `02 01` selector and needs
at least two distinct modes (Off `01`, ANC `02`, Transparency `04`); masks
`03/05/06/07` were confirmed. See
[touch measurement](../measurements/2026-10-28-nord-touch.json) and
[hold-cycle measurement](../measurements/2026-10-28-nord-hold-cycle.json).

## Feature switches and BassWave (audited 2026-10-31)

A generic `0x010d` reply does not establish support. The audit (Wireless
Earphones 17.6.6 whitelist `064414`, app gates/labels and a read-only
`0x0100` capability query) confirms six writable switches: Personalised
noise cancellation (`0c`), BassWave (`1d`), Auto play/pause (`04`), Camera
control (`0d`), Dual connection (`11`) and Hi-Res mode (`18`). The carried
measurements record both-way ACK `00` + fresh-read trials for `04`, `0d`,
`11` and `18`; connection-changing `11`/`18` recover to the same
address/product and read back without replaying the write. The `0c` and
`1d` writes and the BassWave level write (`0x0124` read / `0x041b` write,
`[min, max, value]`, signed −10..+10 on this unit) were owner-verified with
ACK `00` and a fresh read on the same unit; their individual trial logs stay
in the contributor's fork and are not carried here. Hidden/unconfirmed:
`06` game mode, `09` vocal enhancement, `21` Enhanced PEL audio, `0b` Golden
Sound, `1b` headset spatial audio. See
[feature audit](../measurements/2026-10-31-nord-feature-audit.json),
[Auto play/pause](../measurements/2026-10-31-nord-auto-play-pause.json) and
[remaining features](../measurements/2026-10-31-nord-remaining-features.json).

## Find my earbuds (measured 2026-10-31)

`0x0400 [01]` rings, `[00]` stops; `0x8400` status `00` acknowledges. Start
and stop were confirmed live (buds in the open case, outside the ears); no
acoustic recording was made. The backend tracks stopped/ringing/unknown per
physical pair, attempts one automatic stop after 50 s, and never replays an
uncertain start. Queued commands carry a device token so recovery cannot
redirect them to another pair. See
[find measurement](../measurements/2026-10-31-nord-find-earbuds.json).

## Case battery cache

The device reports the case level when the buds sit in the open case. The
plugin remembers the last usable level (1..100) per product and physical
device under `$XDG_CACHE_HOME/oneplus-buds/case-battery/` (hashed filenames,
atomic replacement, no Bluetooth addresses). Missing/zero/invalid samples
keep the last known level, shown as `C 50%*` with a "last known" tooltip and
no stale charging flag. A fresh reading replaces the cache and restores the
live charging bit. See
[case-battery measurement](../measurements/2026-10-31-nord-case-battery.json).

## Limitations

- One contributor unit, recorded firmware `155.155.101`. Other firmware may
  behave differently; nothing here verifies another model or the family.
- No acoustic measurements: audible switching latency, sound effect of the
  presets and Auto's acoustic behaviour were not recorded.
- The historical measurements predate this integration; it re-uses them and
  adds offline regression tests only. No new hardware write tests or audio
  playback were performed for it.
- Switch IDs `0x06` and `0x0b` stay unnamed: the capability audit
  (`0x8100: 00 ff 27 52 ee c7 14`) and the app model table show no model
  support for the separate game-mode switch, and `0x0b` is Golden Sound on
  this model, not the shared hearing-enhancement name.
- Device rename (BlueZ alias write) and the raw diagnostic query are not
  included; they remain available in the contributor's fork on request.
