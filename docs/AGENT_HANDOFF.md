# Agent handoff

Last updated: 2026-09-02, Phase 1 in progress.

## Current status

The repository began empty except for `PROJECT.md`. A dependency-free Python proof of concept now separates BlueZ discovery, RFCOMM transport, OPO framing/parsing, and CLI behavior. Unit fixtures cover framing, fragmented streams, product ID, battery, and ANC parsing. ANC writes are hard-gated on product ID `060C14` and require query-after-write verification.

## Verified discoveries

- Host: Omarchy 4.0.1-1, BlueZ 5.87, Python 3.14.7; `bluetooth.service` is active.
- A connected OnePlus Buds Pro is reliably visible through `bluetoothctl`.
- Device exposes HeyMelody vendor SPP UUID `00001107-d102-11e1-9b23-00025b00a5a5`, Serial Port, and vendor UUID `66666666-6666-6666-6666-666666666666`.
- No remote GATT services/characteristics are exposed as BlueZ objects. RFCOMM channel 15 accepts a connection, so Classic RFCOMM is the verified likely control transport.
- BlueZ standard Battery1 provides an aggregate percentage.
- Research identifies product ID `060C14` as the OnePlus Buds Pro and corroborates OPO 0xAA framing, battery query `0x0106`, ANC query `0x010c`, and ANC set `0x0404`.
- Hardware read-only queries returned product ID `060C14`, per-component battery values (L=100%, R=100%, case=80%), and ANC Off. Both earbuds had the protocol charging bit set.
- Real responses arrive in bursts and may concatenate acknowledgements with unsolicited notifications; the transport drains each burst and the framer separates it by outer length.
- ANC On writes were sent only after product ID gating. Attempts without subscription, with negotiated subscription, and after the fixed-sequence batch wake query were ignored; a fresh connection still reported Off. No other mode write was attempted.

## Unresolved problems

- Determine why Buds Pro accepts queries but ignores `0x0404` ANC writes. Current hypotheses: an unobserved authentication/session prerequisite, another model-specific command encoding, or a physical-state prerequisite.
- Capture a known hardware-initiated ANC transition: ask the user to change mode on the earbuds, then run `anc status`. This validates the query parser before further writes.
- Case presence and charging bits behaved consistently across live state changes, but should be tested deliberately later.
- Enable ANC writes only after product ID `060C14` is returned and each mode can be queried back.
- Current CLI shells out to `bluetoothctl`; a future backend should use D-Bus directly when dependency/API choices are settled.

## Next recommended task

Have the user switch from ANC Off to ANC On using the earbud stem controls, then immediately run `PYTHONPATH=src python -m oneplus_buds.cli anc status`. If that reports On, capture the raw response and investigate HeyMelody/Buds Pro write initialization or command differences before sending more controls.
