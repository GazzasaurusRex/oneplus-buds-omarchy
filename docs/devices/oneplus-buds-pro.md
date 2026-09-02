# OnePlus Buds Pro (test device)

Compatibility status: **Verified for the Phase 1 basic milestone** on real OnePlus Buds Pro hardware, 2026-09-02.

## Verified locally

- BlueZ name: `OnePlus Buds Pro`
- Bluetooth modalias: `bluetooth:v02B0p0000d001F`
- Paired, bonded, trusted, and connected
- BlueZ 5.87 reports an aggregate battery value (100% during inspection)
- Services include Serial Port (`00001101...`), HeyMelody vendor SPP (`00001107-d102-11e1-9b23-00025b00a5a5`), and vendor UUID `66666666-6666-6666-6666-666666666666`
- Both BR/EDR and LE bearers exist, but BlueZ exposes no remote GATT service/characteristic objects
- RFCOMM channel 15 accepts a connection
- OPO product query returns ID `060C14`
- Per-component battery query initially returned left 100%, right 100%, case 80% with both earbuds' charging bits set. A later query omitted the case and cleared both charging bits, consistent with live in/out-of-case state.
- ANC query returned Off initially. After the user physically enabled ANC, it returned bitmap `08`, matching the registry's deep-ANC profile index.
- Authenticated ANC writes were acknowledged and independently verified for Off=`01`, Transparency=`02`, and deep ANC On=`08`.

The Bluetooth address is deliberately not recorded.

## Corroborated profile information (not yet device-returned)

A recovered HeyMelody registry maps product ID `060C14` to OnePlus Buds Pro, `supportSpp=true`, UUID `00001107...`, and declares battery, ANC/noise modes, wear detection, multipoint, EQ, fit detection, and other features. Only battery and basic ANC are in scope now.

## Still to verify

- Determine whether shorter safe authentication/cooldown timings work across firmware versions; current conservative timings favor reliability.
- Deliberately test case-open/case-closed battery behavior later.
