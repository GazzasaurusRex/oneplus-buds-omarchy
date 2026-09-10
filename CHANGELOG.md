# Changelog

## Unreleased — 0.1.0 release candidate

- Hardware-verified OnePlus Buds Pro and Buds Pro 2 identity, battery, firmware,
  ANC On/Off/Transparency and supported strengths.
- Generic transport-independent OPO framing, RFCOMM transport, device profiles,
  typed backend, privacy-safe diagnostics and serialized session ownership.
- Persistent authenticated sessions for verified main-mode changes; recorded
  warm transition medians of 260 ms on Pro and 167 ms on Pro 2. Audible response
  time was not measured; explicit strengths retain conservative setup.
- Combined Omarchy service/bar plugin with one backend helper and reconnect logic.
- Compact idle icon, battery hover expansion and delayed collapse.
- Portrait panel with themed full-width controls, grouped ANC modes/strengths,
  wrapping text and vertical scrolling; accepted in live user review.
- Native earbud EQ with model-specific verified presets, fresh read-back, Pro 2
  device-defined six-band custom curves, and capability-driven panel controls.
- Live EQ-panel acceptance on both reference models, including device switching,
  HeyMelody-originated state reload, and closed-case power-cycle persistence.
- Fixed Pro 2 custom-slot selection being reset by routine snapshot replacement;
  current HeyMelody names and protocol ID 7 are hardware-mapped on firmware
  `196.196.101`.
- Publication documentation, MIT license, dependency preflight, checkout-local
  CLI launcher and clean plugin exporter.

No public release or marketplace listing has been made.
