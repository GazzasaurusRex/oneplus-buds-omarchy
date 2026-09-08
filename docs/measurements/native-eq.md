# Native EQ hardware verification

Date: 2026-09-08. Transport: OPOv1 over RFCOMM channel 15. All identifiers are
product IDs; Bluetooth addresses and raw peer data are omitted.

Each run read and retained current/detailed EQ state before SET, transmitted SET
exactly once, required a sequence-correlated fresh current query, and re-read the
detailed catalogue. The values below are command-through-verification timings from
the initial implementation; the current instrumentation additionally reports the
mandatory preservation read as `preserve_read` and includes it in `session_total`.

| Product | Operation | Fresh queries | Time | Audible confirmation |
|---|---|---:|---:|---|
| `062014` | Balanced | 1 | 244 ms | Yes |
| `062014` | Deep Sea Bass | 1 | 244 ms | Yes |
| `062014` | Pure Vocals | 1 | 216 ms | Yes |
| `062014` | Bright & Crisp | 1 | 194 ms | Yes |
| `062014` | Custom1 alternating ±6 dB | 1 | 235 ms | Yes |
| `060C14` | Deep Sea Bass | 1 | 123 ms | Yes |
| `060C14` | Pure Vocals | 1 | 117 ms | Yes |
| `060C14` | Bright & Crisp | 1 | 103 ms | Yes |

Pro 2 returned custom IDs 4 and 5, each with 62/250/1000/4000/8000/16000 Hz,
-6..+6 dB limits and signed integer gains. ID 5 started flat, was temporarily set
to `+6,-6,+6,-6,+6,-6`, and every band was read back. It was then restored to
all zero (146 ms), ID 4 was reselected, and a separate session confirmed ID 4
`+3,+1,0,0,0,0` selected with ID 5 flat. The user confirmed ID 4 initially
matched HeyMelody.

Original Buds Pro returned no custom entries. After its three non-default audible
tests it was restored to its initial Balanced state; a separate session confirmed
ID 0 and an empty custom catalogue. ANC was not written during EQ testing.

Both products therefore demonstrate state across RFCOMM control-session reconnects.
The test did not isolate a complete earbud power-off/reboot cycle, so stronger
nonvolatile-persistence claims are intentionally deferred.
