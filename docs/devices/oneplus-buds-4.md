# OnePlus Buds 4 (community-tested device)

Compatibility status: **Community Tested** on a contributor's hardware, 2026-10-17.
This is not maintainer hardware verification. The original read-only report is
[issue #1](https://github.com/GazzasaurusRex/oneplus-buds-omarchy/issues/1).
Protocol investigation, HCI capture and hardware write/read-back verification were
contributed by Joel Tony (GitHub: [@jay-tau](https://github.com/jay-tau)).

ANC, factory EQ and custom EQ writes are authorized as three independent operation
classes from that evidence. The Community Tested label remains unchanged; no other
current or future write class inherits those permissions.

## Observed locally

- BlueZ name: `OnePlus Buds 4`
- Services include the OPO vendor service `0000079a-d102-11e1-9b23-00025b00a5a5`
  (shared with the Buds Pro 2) and vendor UUID `df21fe2c-2515-4fdb-8886-f12c4d67927c`
- RFCOMM channel 15 accepts a connection
- OPO product query returns `065414`
- Kind-2 version records for left/right/case produced `138.138.105`, exactly
  matching HeyMelody 117.6.6
- Component battery matched HeyMelody (case 30%, left 60%, right 60%). The case
  was absent from the response while the earbuds were worn.
- Notification discovery advertised nine event codes: `01 02 03 04 08 0b f1 f2 f3`
  (the Pro 2 also advertises `0a`)
- Batch status `0x810d` returned seven feature switches. `0x04` matched
  HeyMelody's Auto play/pause (on), `0x06` its Game mode (off) and `0x11`
  multipoint (on, with two hosts connected). HeyMelody showed Hi-Res mode on
  while `0x18` read off, so the shared `high_quality_audio` name is unconfirmed
  for this model. `0x05`, `0x0b` and `0x1b` were not matched to app settings.
  The profile leaves `0x0b` and `0x18` unnamed.
- HeyMelody refuses noise-control changes unless the earbuds are worn

The Bluetooth address is deliberately not recorded.

## ANC profile

HeyMelody's SET payloads were captured with an Android HCI snoop log while each
mode was selected in the app and confirmed on screen. They match the Pro 2
write indices, plus Adaptive. Each mode was then written from Linux and read
back with a fresh query.

| Function | HeyMelody label | Write index/bitmap | Observed read index | Result |
|---|---|---:|---:|---|
| Off | Off | 0 / `01` | 3 | Read back |
| ANC On | Noise cancellation | 1 / `02` | active level index | Read back |
| Transparency | Transparency | 2 / `04` | 8 (`00 01`) | Read back |
| Deep | High | 4 / `10` | 4 | Read back |
| Medium | Moderate | 5 / `20` | 5 | Read back |
| Light | Low | 6 / `40` | 6 | Read back |
| Smart | Auto | 7 / `80` | 7 | Read back |
| Adaptive | Adaptive | 11 / `00 08` | 11 (`00 08`) | Read back |

Adaptive is a parent mode without a strength. The Pro 2 read alias 0 for Off
was not observed on this model, so it is not mapped.

## Native EQ

HeyMelody selects factory presets with `0x0406` and these IDs: 0 Balanced,
1 Serenade and 2 Bass. Serenade and Bass are swapped relative to the Pro 2.
The `0x0122` catalogue returns only custom entries: here three user-created
entries (IDs 4–6) with six bands at 62/250/1000/4000/8000/16000 Hz and
-6..+6 dB limits. Selecting a custom entry in HeyMelody re-sends its full
definition with `0x0418`, in the same encoding the backend uses for custom
updates. Selecting one with `0x0406` and its ID was also accepted and read back.

## Linux hardware test

Earbuds worn, firmware `138.138.105`, BlueZ 5.87:

- One-shot backend path: Off, On, Deep, Medium, Light, Smart, Transparency,
  Adaptive and Off; EQ Balanced, Serenade and Bass. Every SET returned `00` and
  every fresh query matched the request.
- Controller path (persistent session; strengths use its one-shot fallback):
  Transparency, On, Adaptive, Light, Smart and Off; EQ Balanced, Serenade,
  Bass, a custom entry by ID, and a custom update that rewrote an entry with
  its existing gains. Every SET returned `00` and all were read back.
  Main-mode changes took 0.13–0.31 s in this single run.
- Custom gain change: the one-shot path raised one band of a custom entry by
  1 dB and an independent catalogue query read it back; the persistent session
  then restored the original gain, also read back.
- Afterwards ANC was set to Off and the original EQ selection was restored. The
  parsed custom entries (names, limits and band gains) matched the starting
  catalogue.
- One earlier attempt aborted before any write with `payload length mismatch`
  on a frame received while identifying the device. Six later sessions did not
  reproduce it.

Audible effects were not separately recorded.

## Still to verify later

- Meaning of feature switches `0x05`, `0x0b`, `0x18` and `0x1b` on this model
- Case battery and charging behaviour with the case opened and closed
- BassWave, OnePlus 3D Audio, Golden Sound and Hi-Res mode are not implemented
