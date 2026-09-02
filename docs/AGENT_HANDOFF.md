# Agent handoff

Last updated: 2026-09-02. First Phase 1 practical milestone complete.

## Current status

The dependency-free Python proof of concept separates BlueZ discovery, RFCOMM transport, OPO framing/parsing, and CLI behavior. It reliably detects and identifies the connected original OnePlus Buds Pro, reads component batteries, queries ANC, and switches among Off, Transparency, and deep ANC On. ANC writes are hard-gated on product ID `060C14`, authenticated, and require fresh-session query-after-write verification.

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

## Unresolved problems

- The CLI currently has conservative multi-second delays and busy retries. Timing can be optimized only after repeated reliability testing.
- `anc status` reports On without exposing light/deep/smart detail; preserve that detail in a future structured state model.
- Case presence and charging bits should be tested deliberately later.
- Discovery currently shells out to `bluetoothctl`; replace with a direct BlueZ D-Bus layer when choosing the long-term backend API.
- Enable ANC writes only after product ID `060C14` is returned and each mode can be queried back.
- Current CLI shells out to `bluetoothctl`; a future backend should use D-Bus directly when dependency/API choices are settled.

## Next recommended task

Add integration-test logging/fixtures for the verified authenticated exchange without recording the device address. Then improve CLI ergonomics and repeated-operation reliability while remaining within the Buds Pro Phase 1 scope; do not begin QML or Buds Pro 2 work yet.
