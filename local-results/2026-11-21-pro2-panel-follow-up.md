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

- Focused backend after the touch-control follow-up: 67 passed.
- Full backend regression suite: 281 passed.
- Qt offscreen interactions: 36 passed, 0 failed.
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

The normal user plugin was restored after the earlier test. Its rollback copy is
still retained while this exact follow-up worktree is loaded temporarily. The
saved work remains local and has not been pushed.

## Touch-control follow-up

The Pro 2 phone app offered Single tap as None or Play/Pause. Triple tap offered
None, Previous, Next Track, Voice Assistant, or Game mode. Voice Assistant and
Game mode were intentionally left unaudited and are not enabled in the panel.
Double-tap Previous/Next remained covered by the earlier verified trial.

| Control | Original | Trial | Physical observation | Fresh readback | Restored |
|---|---|---|---|---|---|
| Left single-tap | Play/Pause | None | Did not pause or resume playback | None, function `0` | Play/Pause, function `1`; behaviour confirmed |
| Right single-tap | Play/Pause | None | Did not pause or resume playback | None, function `0` | Play/Pause, function `1`; behaviour confirmed |
| Left triple-tap | Previous | None | Did not change playback or track | None, function `0` | Previous, function `5`; behaviour confirmed |
| Right triple-tap | Previous | Next | Advanced to the next track | Next, function `6` | Previous, function `5`; behaviour confirmed |

The final fresh readback showed both sides restored to Single Play/Pause,
Double Next, and Triple Previous. Pro 2 per-earbud Long hold is hidden because
its reported function `18` is not a phone-app editable row; the separately
verified shared Touch & hold ANC cycle remains available. Nord Long hold
permissions and controls are unchanged.
