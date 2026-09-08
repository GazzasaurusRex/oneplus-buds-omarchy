# Compatibility

Compatibility describes evidence, not a promise that every firmware works.

| Product | Product ID | Status | Evidence |
|---|---|---|---|
| OnePlus Buds Pro | `060C14` | Verified | [Device record](oneplus-buds-pro.md) |
| OnePlus Buds Pro 2 | `062014` | Verified | [Device record](oneplus-buds-pro-2.md) |
| Other OnePlus products | Unknown | Experimental if discovered | No maintainer verification |

There are no community-tested models recorded yet. “Verified” means tested on the
two reference devices and their recorded firmware. “Community-tested” will mean
reported by another user with reproducible evidence. “Experimental” means
recognised protocol/service evidence without verified device support.

Current discovery requires a connected BlueZ device whose name contains
`oneplus` and whose UUIDs contain one of the two known OPO services. Renamed devices
may not match. Similar OPPO/Realme hardware is a research target, not automatic
support today. BLE-only products and other protocol families are not supported.

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

Both reference models have hardware-verified native factory EQ selection for
Balanced, Deep Sea Bass, Pure Vocals, and Bright & Crisp. Buds Pro 2 additionally
returns and supports safe updates of two device-declared six-band custom entries
(62/250/1000/4000/8000/16000 Hz, -6..+6 dB, 1 dB protocol resolution). Original
Buds Pro returns an empty custom catalogue and is correctly preset-only. EQ writes
remain unavailable to unknown/experimental products.

Pro 2 capability discovery can report recognised boolean feature switches, but
wear detection, multipoint, low latency and related switches have no implemented
write controls. Spatial audio, gestures, finding earbuds and phone-side sound
features are not implemented. Unknown feature IDs and notification schemas remain
unnamed. Physical earbud changes are not guaranteed to update the UI immediately.

Read the [contribution guide](../../CONTRIBUTING.md) before reporting a new model.

Device switching uses the generic controller lifecycle: automatic selection is
rerun after transport loss, old device state is cleared, and the next compatible
device is queried and authenticated with its own product profile. Explicit
`--device` selection stays pinned. See [lifecycle details](../backend-api.md#switching-physical-devices).
