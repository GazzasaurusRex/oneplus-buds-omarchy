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
| Remote version | `0x0105` | `0x8105` | response: status, record count, ASCII triples |
| Battery | `0x0106` | `0x8106` | pairs `[component, raw]` |
| ANC query | `0x010c` | `0x810c` | request `01 01` |
| ANC set | `0x0404` | state via `0x0204`/query | `01 01 mode` |
| Current native EQ | `0x010f` | `0x810f` / `0x0504` | response: status, EQ ID |
| Native EQ catalogue | `0x0122` | `0x8122` | request `01 05` |
| Select native EQ | `0x0406` | `0x8406` | one-byte EQ ID |
| Update custom EQ | `0x0418` | `0x8418` | structured custom entry |
| Batch status / wake | `0x010d` | `0x810d` | fixed sequence `00`; parameter list |

Battery component IDs are 1=left, 2=right, 3=case. `raw & 0x7f` is percentage and bit 7 indicates charging.

The Buds Pro response observed on 2026-09-02 prefixes the pairs with a one-byte component count. Its capability response `0x8100` reports an inner payload length one byte shorter than the payload bounded by the valid outer frame length. An unsolicited `0x0204` snapshot following subscription reported an inner length three bytes larger than its outer-bounded payload. The outer length still separated concatenated frames exactly, so it is authoritative for these observed quirks.

A repeat read-only query on 2026-09-05 returned capability payload `00 bf 17 68 26 04` from the original Buds Pro. The first byte is consistent with a success status, but the remaining bytes are not yet mapped to stable feature names. The documented `0x010d` batch-status request produced no response in unauthenticated and authenticated sessions. No dynamic capabilities are inferred from either result.

### Remote version

The original Buds Pro returned `status=00`, `count=08`, followed by comma-separated ASCII triples `(component, kind, value)`:

```text
1,1,11  1,2,541  1,3,541
2,1,11  2,2,541  2,3,541
3,1,4   3,2,510
```

Component IDs 1/2/3 align with left/right/case. Joining kind-2 values in that order produces `541.541.510`, which the user independently confirmed against the phone's firmware display. The parser retains all records, rejects malformed/count-mismatched payloads, and formats firmware only when both left and right kind-2 records exist.

The Buds Pro 2 uses the same structure. It returned kind-2 values `196`, `196`, and `101`, independently confirmed as phone-displayed firmware `196.196.101`. It additionally returned kind-4 value `0` for all three components; kind 4 remains uninterpreted.

### Notification negotiation

After HELLO and REGISTER, the original Buds Pro returned `0x8200` payload `00 07 01 02 03 04 06 08 0a`. Sending `0x0205` with that exact advertised set returned `0x8205` status `00` and echoed each event code as a little status pair, followed by an immediate `0x0204` state snapshot. No unsupported event was requested. The profile's existing `0x010d` batch query still produced no response, so its feature state is not inferred.

The Buds Pro 2 advertised ten codes (`01 02 03 04 08 0b f1 f2 f3 0a`). Its subscription response used a different leading byte/shape but was followed by an immediate snapshot and working batch response, so the backend does not assume the original model's acknowledgement layout. One unsolicited pre-handshake notification contained peer-device information; raw notifications are deliberately excluded from CLI capability/diagnostic output.

The Pro 2 `0x810d` payload was `00 06 05 01 04 01 0b 01 11 00 18 00 06 00`: success, six `(feature ID, boolean)` pairs. Corroborated IDs map to wear detection `0x04`, low latency/game mode `0x06`, hearing enhancement `0x0b`, multipoint `0x11`, and high-quality audio `0x18`; `0x05` remains unknown. A returned ID demonstrates support even when its current value is false.

For product `060C14` (original OnePlus Buds Pro), queried ANC state is a model-profile bitmap: Off=`01`, Transparency=`02`, light ANC=`04`, deep ANC=`08`, and smart ANC=`10`. Deep ANC `08` was observed after a physical stem-control transition to ANC On.

Authenticated writes on product `060C14` use the same model bitmap: Off=`01`, Transparency=`02`, light ANC=`04`, deep ANC=`08`, and smart ANC=`10`. An authenticated `04` write returned success (`0x8404`, status `00`) and read back as light ANC. Community implementations for newer devices use a different set enum, so writes must remain product-gated.

Control requires the legacy HELLO frame, a two-second wait, REGISTER with the observed token, and a 1.5-second wait before SET. The hardware also stops returning ANC-query state in the same RFCOMM control session, so verification closes that socket and queries in a fresh session after channel teardown.

## Verified Buds Pro control flow

1. Connect RFCOMM channel 15.
2. Query product ID and refuse writes unless it is `060C14`.
3. Send raw HELLO `AA 07 00 00 00 01 23 00 00 12`; wait 2 seconds.
4. Send raw REGISTER `AA 0C 00 00 00 85 41 05 00 00 B5 50 A0 69`; wait 1.5 seconds.
5. Send `0x0404` with payload `01 01 bitmap`.
6. Record any `0x8404` status, then verify the requested state independently.
7. Close the control socket, allow channel teardown, open a fresh socket, and query `0x010c`.
8. Treat the operation as successful only if the queried state matches.

This sequence was verified for Off, Transparency, and deep ANC On on 2026-09-02.

`0x8404` payload byte 0 is a SET result/status. `00` was observed on successful state changes. Buds Pro 2 returned `0e` both for an already-active Off request (read-back matched) and for a Transparency request while the earbuds appeared to be charging/in their case (read-back remained Off). It therefore cannot be classified as success or rejection without context. Some sessions do not deliver this response. Its presence, absence, or value is not treated as success; the independent state query remains mandatory.

## Verified Buds Pro 2 differences

Product `062014` uses the same RFCOMM channel, 0xAA packet format, queries, authentication frames, token, and SET command. Its advertised OPO service is `0000079a...` instead of `00001107...`.

Its ANC bitmap can span two bytes and needs a product profile with separate write indices and read aliases:

- Main writes: Off index 0, ANC On index 1, Transparency index 2.
- Levels: Deep index 4, Medium index 5, Light index 6, Smart index 7.
- Observed Transparency report: index 8 (`00 01` little-endian bitmap).
- Registry read aliases: Off may also report index 3; Transparency may report index 8.

Main ANC On enables the parent mode but does not reliably preserve the currently reported level: one sequence retained Smart, while a later command starting from Deep returned Smart. The backend therefore verifies only parent mode for `on`; explicit Deep/Medium/Light/Smart commands verify both mode and level. All three main modes and all four levels were verified on hardware with query-after-write. This confirms that framing is generic but ANC interpretation belongs in the device capability/profile layer.

## Native EQ (verified 2026-09-08)

Current EQ uses empty query `0x010f`; successful `0x810f` is `[00, eq_id]`.
Notification `0x0504` carries the ID without a status byte. Factory/custom entry
selection uses `0x0406 [eq_id]`, acknowledged by `0x8406 [status]`. The backend
sends SET once and requires a fresh correlated current query plus a fresh detailed
catalogue read; acknowledgement alone is never success.

Detailed query `0x0122 01 05` returns `0x8122`:

```text
status count
repeat count times:
  selected min_gain_i8 max_gain_i8 eq_id name_length name_utf8 band_count
  repeat band_count times: frequency_hz_u16le gain_i8
```

Detailed update `0x0418` action 2 omits `selected` but otherwise carries the same
entry definition. Community sources also identify create=1 and delete=3; they are
not exposed. The backend updates only a custom ID, layout, name and limits returned
by that connected device and rejects wrong band counts, non-integer gains,
out-of-range gains, malformed UTF-8, duplicate/zero frequencies, truncation and
trailing data before a packet can be sent.

Both products expose factory IDs 0 Balanced, 1 Deep Sea Bass, 2 Pure Vocals and
3 Bright & Crisp. Every preset was selected, freshly read back, and audibly
confirmed on both reference devices. Warm authenticated command/read-back time was
approximately 97–123 ms on Buds Pro and 194–244 ms on Buds Pro 2 in the recorded
runs (excluding the required pre-write preservation read). See the
[hardware verification record](../measurements/native-eq.md).

Buds Pro 2 firmware `196.196.101` returned custom IDs 4 and 5 with six bands at
62, 250, 1000, 4000, 8000 and 16000 Hz, limits -6..+6 dB, and signed whole-byte
gains (1 dB protocol resolution). The original selected ID 4 values
`+3,+1,0,0,0,0` matched HeyMelody. A reversible ID 5 update to
`+6,-6,+6,-6,+6,-6` was freshly read back and audibly confirmed, then restored
to all zero; ID 4 was reselected and both curves were verified in a separate
session. Buds Pro firmware `541.541.510` returned zero custom entries, so its
profile correctly exposes preset-only EQ.

State survived independent RFCOMM session teardown/reconnect on both models. Full
earbud power-off/reboot persistence has not been isolated from normal app/device
behavior and remains an explicit follow-up. A Pro 2 registry mentions firmware-
gated ID 7 Clear Vocals, but it is not exposed because the device does not provide
a factory catalogue and that ID was not hardware-tested.

## Handshake variants

Recent BLE and Buds Pro 3 implementations send a HELLO packet (`0x0001`) followed by REGISTER (`0x0085`) with a fixed four-byte token. An RFCOMM implementation and device registry covering the original Buds Pro instead use the `0x0100` capability query and report that normal state queries require no registration sequence. The proof of concept therefore starts with the older, less invasive query flow. Hardware responses must decide whether an additional handshake is required.

## Sources and licence posture

- Leaf-lsgtky/OppoPods: RFCOMM implementation plus a recovered HeyMelody device registry. At inspected commit `ad1bb42`, no licence file was present; research only, no code copied.
- Zhaoyi-ya/OppoPodsManager: EQ command and variable-band parser corroboration at
  `f272e9e` (GPL-3.0); research only, no code copied.
- 1812z/OppoPods: independent EQ command corroboration at `0d9e8a6`; no standalone
  licence file found, research only.
- AasheeshLikePanner/cracked-oneplus-buds: BLE OPOv1 research and Swift demonstration. At inspected commit `6320765`, no licence file was present; research only.
- nic0manz/oneplus_buds3_pro_python: RFCOMM/channel-15 example for Buds Pro 3. At inspected commit `faec7e5`, no licence file was present; research only and not assumed compatible with Buds Pro.
- BlueZ RFCOMM documentation: Linux socket transport reference (LGPL documentation/source project).


## Verified persistent-session control (2026-09-06)

Both reference products accept main On/Off/Transparency writes over the existing
authenticated RFCOMM monitoring connection while subscriptions remain active.
SET `0x0404` responses `0x8404` and fresh ANC `0x010c` responses `0x810c` echo the
request sequence in the tested exchanges. The implementation matches command and
sequence, retaining unrelated notifications for safe session processing.

SET acknowledgement is not application completion: original Pro immediately
returned its previous mode after a Transparency acknowledgement, but a later fresh
read-only session reported Transparency. Bounded repeated fresh queries resolve
this settling race without repeating the SET. Original Pro verified actual changes
in about 260 ms; Pro 2's completed run needed one query per request. The independent
verification is now a separate query transaction on the same channel, not a new
socket. Cold authentication delays remain unchanged. Full evidence, including
rejected/incomplete runs, is in [latency measurements](../measurements/anc-baseline.md).
