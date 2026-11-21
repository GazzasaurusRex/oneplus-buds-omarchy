# Buds Pro 2 Omarchy panel follow-up

- Date: 2026-11-21
- Saved branch: `pro2-tested-6146ac2-2026-11-18`
- Saved commit: `767ab6c9dbebefddf47e05950670ec5dd8870a30`
- PR #6 base: `6146ac23c4d5fef848b222d1c3097747852081f3`
- Device: OnePlus Buds Pro 2, product `062014`
- Firmware: `196.196.101`
- Privacy: no Bluetooth address or raw packets recorded

## Local panel correction

The saved follow-up commit contained the tested write permissions and protocol
fixes, but the Pro 2 profile omitted the `feature_switches`, `touch_controls`,
and `hold_cycle` capability flags needed to expose those verified operations in
the panel. Those three flags and matching regression updates were added only in
the local worktree. No Hi-Res or Find My Earbuds permission was added.

## Checks

- Focused backend: 40 passed.
- Full backend regression suite: 274 passed.
- Qt offscreen interactions: 34 passed, 0 failed.
- `omarchy plugin validate .`: passed.
- `git diff --check`: passed.
- The tested export was loaded from a unique plugin path because the long-lived
  shell cached the original QML URL. The stale helper was confirmed by process
  path before restarting only the Omarchy shell.

## Live reversible tests

| Control | Original | Trial | Physical observation | Fresh readback | Restored |
|---|---|---|---|---|---|
| Wear detection | On | Off | Removing one earbud did not pause playback | Off, verified | On; removal paused playback |
| Left double-tap | Next | Previous | Left double-tap selected previous track | Left Previous; right remained Next; verified | Left Next; advanced track |
| Right double-tap | Next | Previous | Right double-tap selected previous track | Right Previous; left remained Next; verified | Right Next; advanced track |
| ANC hold cycle | ANC + Transparency | ANC + Off | Hold cycled only ANC/Off | ANC + Off, verified | ANC + Transparency; physical cycle confirmed |
| BassWave | Enabled, +2 | -5 | Bass audibly decreased | -5, verified; engine remained enabled | +2; original bass returned |
| Multipoint | On; PC and phone connected | Off | PC stayed connected; phone disconnected | Off, verified | On; PC and phone connected |

## Post-reconnect state

After a deliberate PC disconnect/reconnect, the panel reported:

- connection: connected
- wear detection: on
- multipoint: on
- left double-tap: Next track
- right double-tap: Next track
- ANC hold cycle: ANC + Transparency
- BassWave: enabled, level `+2`
- Hi-Res protocol value: off/read-only; no write permission
- Find My Earbuds: no Pro 2 capability or write permission

The normal user plugin was restored after the test. Results and code/test
corrections are committed only on the local follow-up branch and were not pushed.
