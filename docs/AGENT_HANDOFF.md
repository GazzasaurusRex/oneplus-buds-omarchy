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
- A user-initiated physical switch to ANC On returned bitmap `08`, proving the query parser and revealing the original Buds Pro's profile-specific ANC mapping. Earlier write attempts used an incompatible generic mapping.
- The parser now maps Buds Pro Off=`01`, Transparency=`02`, and ANC levels light=`04`, deep=`08`, smart=`10`. The physical transition verified deep ANC `08`.
- Corrected Off writes with fixed sequence `F0` produced no response and did not change a fresh query from Transparency. After control sessions, RFCOMM channel 15 remained `EBUSY` for over 20 seconds; ordinary query sessions released sooner.

## Unresolved problems

- Reconnect the earbuds cleanly, then determine whether writes fail because of session initialization/order, another client holding the vendor endpoint, or a missing Buds Pro-specific prerequisite.
- Case presence and charging bits behaved consistently across live state changes, but should be tested deliberately later.
- Enable ANC writes only after product ID `060C14` is returned and each mode can be queried back.
- Current CLI shells out to `bluetoothctl`; a future backend should use D-Bus directly when dependency/API choices are settled.

## Next recommended task

After a clean reconnect, query the starting state and attempt one Off write while capturing the RFCOMM exchange. Do not test the other modes until Off is acknowledged or confirmed by fresh read-back.
