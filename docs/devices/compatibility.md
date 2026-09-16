# Compatibility

Compatibility describes evidence, not a promise that every firmware works.

| Product | Product ID | Status | Evidence |
|---|---|---|---|
| OnePlus Buds Pro | `060C14` | Verified | [Device record](oneplus-buds-pro.md) |
| OnePlus Buds Pro 2 | `062014` | Verified | [Device record](oneplus-buds-pro-2.md) |
| Other compatible OnePlus/OPO products | Unknown | Experimental if discovered | No maintainer verification |

There are no community-tested models recorded yet. **Verified** means maintainer
hardware testing on the two reference devices and their recorded firmware.
**Community Tested** means a device owner has supplied reproducible evidence that
the advertised functions work on that model. **Experimental** means recognised
protocol/service evidence without that device evidence. Community testing never
upgrades a model to maintainer-verified status.
Community Tested is an evidence label; write controls remain gated to
maintainer-hardware-verified profiles.

Current discovery requires a connected BlueZ device whose name contains
`oneplus` or `oppo` and whose UUIDs contain one of the two known OPO services.
Renamed devices may not match. An OPPO match is only an Experimental candidate,
not a support claim. Realme hardware remains a research target rather than an
automatic match. BLE-only products and other protocol families are not supported.

Unknown candidates may receive existing read-only queries over RFCOMM channel 15;
this does not prove they implement that transport or protocol. Unknown product IDs
are experimental and receive no ANC write controls. A failed query is not evidence
of compatibility. Multi-device CLI selection is supported; the bar requires one
compatible connected device.

## Feature scope

Both reference profiles expose component battery, case battery when returned,
firmware, ANC, transparency and ANC strengths. Pro supports Light/Deep/Smart;
Pro 2 also supports Medium. Main On does not reliably preserve the visible strength.
Case presence and charging flags need further deliberate edge-case testing.

Both reference models have hardware-verified native factory EQ selection. Buds Pro
uses Balanced, Deep Sea Bass, Pure Vocals, and Bright & Crisp. Buds Pro 2 firmware
`196.196.101` uses Balanced, Bass, Serenade, Bold, and Hans Zimmer Soundscape Tuning.
Buds Pro 2 additionally
returns and supports safe updates of two device-declared six-band custom entries
(62/250/1000/4000/8000/16000 Hz, -6..+6 dB, 1 dB protocol resolution). Original
Buds Pro returns an empty custom catalogue and is correctly preset-only. EQ writes
remain unavailable to unknown/experimental products.

Pro 2 capability discovery can report recognised boolean feature switches, but
wear detection, multipoint, low latency and related switches have no implemented
write controls. Spatial audio, gestures, finding earbuds and phone-side sound
features are not implemented. Unknown feature IDs and notification schemas remain
unnamed. Physical earbud changes are not guaranteed to update the UI immediately.

Experimental devices show their status in the panel. Select **Report
compatibility**, review the collection/privacy explanation, choose where to save
the JSON report, then optionally open a GitHub compatibility issue. The report is
created locally and is never uploaded automatically. You can also disable the
plugin and run `./oneplus-buds diagnostics --report` as a CLI fallback. Read the
[contribution guide](../../CONTRIBUTING.md) before reporting a new model.

Device switching uses the generic controller lifecycle: automatic selection is
rerun after transport loss, old device state is cleared, and the next compatible
device is queried and authenticated with its own product profile. Explicit
`--device` selection stays pinned. See [lifecycle details](../backend-api.md#switching-physical-devices).
