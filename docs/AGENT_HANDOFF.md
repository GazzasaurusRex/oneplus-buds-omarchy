# Agent handoff

Last updated: 2026-09-02. Phase 1 basic milestone complete for Buds Pro and Buds Pro 2.

## Current status

The dependency-free Python proof of concept separates BlueZ discovery, RFCOMM transport, OPO framing/parsing, product/capability profiles, and CLI behavior. Both the original OnePlus Buds Pro and Buds Pro 2 are hardware-verified for detection, product identity, component batteries, ANC state, Off, Transparency, and ANC On. The Pro 2 is additionally verified for Deep, Medium, Light, and Smart ANC levels. Writes require a known product profile, authentication, and fresh-session query-after-write verification.

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
- Control requires HELLO, a 2-second wait, REGISTER with the observed token, and a 1.5-second wait. Unauthenticated writes were ignored or misleading.
- Authenticated writes use the Buds Pro profile bitmap, not the newer-device set enum. Off=`01`, Transparency=`02`, light ANC=`04`, deep ANC=`08`, smart ANC=`10`.
- Authenticated SET returned `0x8404:00`; Off, Transparency, and deep ANC On were each verified by a fresh read-only session. The final hardware state was ANC On.
- Buds Pro 2 advertises OPO UUID `0000079a...`, uses RFCOMM channel 15, and returns product ID `062014`. It exposes BR/EDR/SPP/HID but no BlueZ remote GATT characteristic objects or LE bearer in the tested connection.
- Existing detection, transport, 0xAA framing, product query, component battery parser, HELLO/REGISTER authentication, and SET flow work unchanged on Pro 2.
- Pro 2 ANC needs a two-byte-capable profile: main Off index 0, ANC index 1, Transparency index 2; Deep/Medium/Light/Smart indices 4/5/6/7; observed Transparency read alias index 8.
- Pro 2 Off, Transparency, ANC On, Deep, Medium, Light, and Smart all passed fresh query-after-write verification. Main ANC On preserves the previously selected level. Final hardware state is ANC On with Smart level.

## Unresolved problems

- The CLI currently has conservative multi-second delays and busy retries. Timing can be optimized only after repeated reliability testing.
- Case presence and charging bits should be tested deliberately later.
- Discovery currently shells out to `bluetoothctl`; replace with a direct BlueZ D-Bus layer when choosing the long-term backend API.
- The current CLI is a proof of concept and lacks explicit device selection when multiple compatible devices are connected.

## Next recommended task

Add anonymised integration fixtures for complete authenticated exchanges and test repeated-operation reliability. Then improve CLI ergonomics and diagnostics around the generic profile architecture. Do not begin QML or unrelated HeyMelody features yet.
