# OnePlus Buds Pro 2 (test device)

Compatibility status: **Verified for the Phase 1 basic milestone** on real hardware, 2026-09-02.

## Verified locally

- BlueZ name: `OnePlus Buds Pro 2`
- Bluetooth modalias: `bluetooth:v02B0p0000d001F`
- Paired, bonded, trusted, connected, and wake-allowed
- BlueZ 5.87 reports an aggregate battery percentage
- Services include Serial Port (`00001101...`), OPO vendor service `0000079a-d102-11e1-9b23-00025b00a5a5`, HID (`00001124...`), and vendor UUID `df21fe2c-2515-4fdb-8886-f12c4d67927c`
- BlueZ exposes BR/EDR and no remote GATT characteristic objects or LE bearer for this connection
- Manufacturer data key `0x0046` is present; raw address-bearing bytes are deliberately not recorded
- RFCOMM channel 15 accepts a connection
- OPO product query returns `062014`
- Standard 0xAA framing, battery query, product query, ANC query, HELLO, REGISTER, and authenticated SET flow are shared with the original Buds Pro
- Component battery query returned left 100% and right 100%, neither charging; the case was absent from that response
- ANC Off, Transparency, main ANC On, Deep, Medium, Light, and Smart were each set and verified by a fresh query
- The main ANC On command enables ANC but preserves the last selected ANC level. It initially reported Deep, then remained Smart after Smart was selected.
- With both earbuds out of the case and in use, two consecutive Off → Transparency → ANC On → Off cycles completed successfully. Every SET returned status `00`, every transition matched an independent fresh-session query, ANC On reported the retained Smart level, and the final state was Off.
- With both earbuds charging/in the case, SET returned status `0e`: an Off no-op still read back Off, while a requested Transparency transition remained Off. The backend correctly treats SET status as diagnostic data and requires state read-back before reporting success.
- Read-only command `0x0105` returned nine ASCII version records, including kind-4 records absent on the original model. Kind-2 values for left/right/case produced `196.196.101`, exactly matching the phone/HeyMelody firmware display.
- Notification discovery advertised ten event codes: `01 02 03 04 08 0b f1 f2 f3 0a`, versus seven on the original model. Multi-subscription succeeded and triggered a state snapshot.
- After subscription, batch status `0x810d` returned six feature switches. Recognised values were wear detection=on, hearing enhancement=on, multipoint=off, high-quality audio=off, and low latency/game mode=off. Feature `0x05` remains unnamed. Presence establishes capability independently from the current on/off value.

The Bluetooth address is deliberately not recorded.

## Verified ANC profile

The Pro 2 uses a little-endian bitmap that can span two bytes.

| Function | Write index/bitmap | Observed read index | Result |
|---|---:|---:|---|
| Off | 0 / `01` | 0 or registry alternate 3 | Verified |
| ANC On (preserve level) | 1 / `02` | active level index | Verified |
| Transparency | 2 / `04` | 8 (`00 01`) observed | Verified |
| Deep | 4 / `10` | 4 | Verified |
| Medium | 5 / `20` | 5 | Verified |
| Light | 6 / `40` | 6 | Verified |
| Smart | 7 / `80` | 7 | Verified |

The differing write and reported Transparency indices are why protocol profiles must distinguish writable main-mode indices from read aliases.

## Capability comparison

The recovered HeyMelody registry declares battery, ANC levels, custom EQ, wear detection, fit testing, multipoint, spatial audio types, personalised noise, Golden Sound/hearing enhancement, high-quality audio, Zen Mode, find-device, and other features. Only detection, identity, battery, and noise control have been verified in this phase; the other declarations are not yet Linux support claims.

Compared with the original Buds Pro, the Pro 2 advertises `0000079a...` rather than `00001107...`, uses a wider ANC profile with a main ANC parent plus four levels, exposes HID, and has different secondary vendor/manufacturer data. Both tested models use RFCOMM channel 15 and the same authenticated 0xAA protocol family.

## Still to verify later

- Case battery behavior with the case deliberately opened/closed
- Capabilities outside the Phase 1 basic milestone
- Repeated-operation timing across firmware revisions and longer stress runs
