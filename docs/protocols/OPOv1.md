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

For the OnePlus Buds Pro profile only, researched ANC values are Off=`01`, noise cancellation=`02`, Transparency=`04`. These will not be enabled for writing until the device returns product ID `060C14` and read-back behavior is verified.

The connection initialization flow must also negotiate and subscribe to the device's notification event IDs before control writes. A write attempted without this step was ignored and ANC remained Off.

## Handshake variants

Recent BLE and Buds Pro 3 implementations send a HELLO packet (`0x0001`) followed by REGISTER (`0x0085`) with a fixed four-byte token. An RFCOMM implementation and device registry covering the original Buds Pro instead use the `0x0100` capability query and report that normal state queries require no registration sequence. The proof of concept therefore starts with the older, less invasive query flow. Hardware responses must decide whether an additional handshake is required.

## Sources and licence posture

- Leaf-lsgtky/OppoPods: RFCOMM implementation plus a recovered HeyMelody device registry. At inspected commit `ad1bb42`, no licence file was present; research only, no code copied.
- AasheeshLikePanner/cracked-oneplus-buds: BLE OPOv1 research and Swift demonstration. At inspected commit `6320765`, no licence file was present; research only.
- nic0manz/oneplus_buds3_pro_python: RFCOMM/channel-15 example for Buds Pro 3. At inspected commit `faec7e5`, no licence file was present; research only and not assumed compatible with Buds Pro.
- BlueZ RFCOMM documentation: Linux socket transport reference (LGPL documentation/source project).
