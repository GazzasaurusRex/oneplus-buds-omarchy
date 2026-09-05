# Agent handoff

Last updated: 2026-09-05. Phase 1 basic control and backend-hardening milestones complete.

## Current status

The dependency-free Python proof of concept separates BlueZ discovery, RFCOMM transport, OPO framing/parsing, product/capability profiles, backend orchestration, and CLI presentation. Both the original OnePlus Buds Pro and Buds Pro 2 are hardware-verified for detection, product identity, component batteries, ANC state, Off, Transparency, and ANC On. The Pro 2 is additionally verified for Deep, Medium, Light, and Smart ANC levels. Writes require a known hardware-verified product profile, authentication, SET-status recording, and fresh-session query-after-write verification.

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
- Backend hardening adds bounded RFCOMM `EBUSY` connection retries, explicit `--device` selection, profile-driven `capabilities`, and a privacy-safe `diagnostics --report` command.
- The live Buds Pro 2 diagnostics report was verified to omit its Bluetooth address and unrelated devices. `devices` shows only connected compatible addresses for explicit selection.
- Sanitised representative session fixtures cover both verified products without addresses or pairing data. The expanded suite covers framing, bursts, profiles, acknowledgements, discovery/selection, diagnostics privacy, and retry behavior.
- A live hardened-backend check identified Pro 2 product `062014`, all expected profile capabilities, and batteries L/R/case=100%. Both earbuds reported charging and ANC Off. A repeated Off request returned SET status `0e` but independently verified as Off; a Transparency request also returned `0e` and independently remained Off. This proves SET status alone is insufficient and that the verifier correctly refuses to report an unconfirmed transition. Repeat the cycle with the earbuds out of the case/in use.
- With both Pro 2 earbuds out of the case and in use, two consecutive Off → Transparency → ANC On → Off cycles passed. All six actual transitions returned SET status `00` and matched fresh-session read-back; ANC On reported the retained Smart level. The device was restored to ANC Off.
- With both original Buds Pro earbuds out of the case and in use, two consecutive Off → Transparency → ANC On → Off cycles also passed. All six actual transitions returned SET status `00` and matched fresh-session read-back; ANC On reported Deep. A phone-assisted physical check resolved a momentary subjective ambiguity and confirmed all three labels behaved correctly. After reconnecting to the PC, product `060C14`, L/R=80%, not charging, and ANC Off were independently confirmed.

## Unresolved problems

- Authentication still uses conservative multi-second delays. Timing can be optimized only after repeated control-cycle evidence on both models.
- Case presence and charging bits should be tested deliberately later.
- Discovery currently shells out to `bluetoothctl`; replace with a direct BlueZ D-Bus layer when choosing the long-term backend API.
- Diagnostics do not yet query firmware or dynamically probe capabilities beyond the verified product profile.

## Next recommended task

Replace `bluetoothctl` text parsing with direct BlueZ D-Bus access while preserving dependency-free operation if practical, then investigate firmware and device-returned capability queries for a more useful compatibility report. Keep the CLI/backend interface stable and do not begin QML yet.
