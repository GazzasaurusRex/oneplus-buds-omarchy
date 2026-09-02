# OPO/OPOv1 research notes

Status: early Phase 1 research, 2026-09-02. Values below are either observed on the test device or independently corroborated by multiple implementations. No command is considered safe for another model merely because it is listed here.

## Transport and identification

The connected OnePlus Buds Pro exposes Bluetooth Classic Serial Port Profile and vendor service `00001107-d102-11e1-9b23-00025b00a5a5`. BlueZ resolves the device but creates no remote GATT service or characteristic objects. A connect-only test to RFCOMM channel 15 succeeded. This establishes RFCOMM/SPP as the likely control transport for this device.

Related devices can expose `0000079a-d102-11e1-9b23-00025b00a5a5` over RFCOMM or as a BLE service, with `0100079a-...` write and `0200079a-...` notify characteristics. Transport must therefore remain separate from framing.

## Frame format

Multi-byte fields are little-endian:

`AA total_length 00 00 command_lo command_hi sequence payload_len_lo payload_len_hi payload...`

`total_length` counts bytes after itself, so the complete frame is `total_length + 2` bytes. No checksum appears in the observed/researched 0xAA framing.

## Commands relevant to the first milestone

| Meaning | Request | Response/notification | Payload |
|---|---:|---:|---|
| Capability handshake | `0x0100` | `0x8100` | empty |
| Notification capabilities | `0x0200` | `0x8200` | response: status, count, event IDs |
| Subscribe notifications | `0x0205` | `0x8205` | count followed by negotiated event IDs |
| Product ID | `0x0103` | `0x8103` | response begins status + 3-byte ID |
| Battery | `0x0106` | `0x8106` | pairs `[component, raw]` |
| ANC query | `0x010c` | `0x810c` | request `01 01` |
| ANC set | `0x0404` | state via `0x0204`/query | `01 01 mode` |
| Batch status / wake | `0x010d` | `0x810d` | fixed sequence `00`; parameter list |

Battery component IDs are 1=left, 2=right, 3=case. `raw & 0x7f` is percentage and bit 7 indicates charging.

The Buds Pro response observed on 2026-09-02 prefixes the pairs with a one-byte component count. Its capability response `0x8100` reports an inner payload length one byte shorter than the payload bounded by the valid outer frame length. An unsolicited `0x0204` snapshot following subscription reported an inner length three bytes larger than its outer-bounded payload. The outer length still separated concatenated frames exactly, so it is authoritative for these observed quirks.

For product `060C14` (original OnePlus Buds Pro), queried ANC state is a model-profile bitmap: Off=`01`, Transparency=`02`, light ANC=`04`, deep ANC=`08`, and smart ANC=`10`. Deep ANC `08` was observed after a physical stem-control transition to ANC On.

Authenticated writes on product `060C14` use the same model bitmap: Off=`01`, Transparency=`02`, light ANC=`04`, deep ANC=`08`, and smart ANC=`10`. An authenticated `04` write returned success (`0x8404`, status `00`) and read back as light ANC. Community implementations for newer devices use a different set enum, so writes must remain product-gated.

Control requires the legacy HELLO frame, a two-second wait, REGISTER with the observed token, and a 1.5-second wait before SET. The hardware also stops returning ANC-query state in the same RFCOMM control session, so verification closes that socket and queries in a fresh session after channel teardown.

## Verified Buds Pro control flow

1. Connect RFCOMM channel 15.
2. Query product ID and refuse writes unless it is `060C14`.
3. Send raw HELLO `AA 07 00 00 00 01 23 00 00 12`; wait 2 seconds.
4. Send raw REGISTER `AA 0C 00 00 00 85 41 05 00 00 B5 50 A0 69`; wait 1.5 seconds.
5. Send `0x0404` with payload `01 01 bitmap`.
6. Require successful `0x8404` status `00` when present.
7. Close the control socket, allow channel teardown, open a fresh socket, and query `0x010c`.
8. Treat the operation as successful only if the queried state matches.

This sequence was verified for Off, Transparency, and deep ANC On on 2026-09-02.

## Verified Buds Pro 2 differences

Product `062014` uses the same RFCOMM channel, 0xAA packet format, queries, authentication frames, token, and SET command. Its advertised OPO service is `0000079a...` instead of `00001107...`.

Its ANC bitmap can span two bytes and needs a product profile with separate write indices and read aliases:

- Main writes: Off index 0, ANC On index 1, Transparency index 2.
- Levels: Deep index 4, Medium index 5, Light index 6, Smart index 7.
- Observed Transparency report: index 8 (`00 01` little-endian bitmap).
- Registry read aliases: Off may also report index 3; Transparency may report index 8.

Main ANC On preserves the last selected level. All three main modes and all four levels were verified on hardware with query-after-write. This confirms that framing is generic but ANC interpretation belongs in the device capability/profile layer.

## Handshake variants

Recent BLE and Buds Pro 3 implementations send a HELLO packet (`0x0001`) followed by REGISTER (`0x0085`) with a fixed four-byte token. An RFCOMM implementation and device registry covering the original Buds Pro instead use the `0x0100` capability query and report that normal state queries require no registration sequence. The proof of concept therefore starts with the older, less invasive query flow. Hardware responses must decide whether an additional handshake is required.

## Sources and licence posture

- Leaf-lsgtky/OppoPods: RFCOMM implementation plus a recovered HeyMelody device registry. At inspected commit `ad1bb42`, no licence file was present; research only, no code copied.
- AasheeshLikePanner/cracked-oneplus-buds: BLE OPOv1 research and Swift demonstration. At inspected commit `6320765`, no licence file was present; research only.
- nic0manz/oneplus_buds3_pro_python: RFCOMM/channel-15 example for Buds Pro 3. At inspected commit `faec7e5`, no licence file was present; research only and not assumed compatible with Buds Pro.
- BlueZ RFCOMM documentation: Linux socket transport reference (LGPL documentation/source project).
