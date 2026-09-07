# Open-source protocol research

Research snapshot: 2026-09-05.

| Project | Relevant finding | Transport/model scope | Licence at inspected revision |
|---|---|---|---|
| Leaf-lsgtky/OppoPods | 0xAA framing, RFCOMM UUID/channel 15, product registry, battery and ANC parsers | Broad OPPO/OnePlus/Realme; registry explicitly contains Buds Pro | README declares GPL-3.0; no standalone licence file at inspected revision |
| AasheeshLikePanner/cracked-oneplus-buds | HELLO/REGISTER flow and BLE OPO service/characteristics | Nord Buds 3 Pro; BLE | No licence file found |
| nic0manz/oneplus_buds3_pro_python | Native RFCOMM and channel 15; similar 0xAA commands | Buds Pro 3 only | No licence file found |
| Wasabules/OpenPeats | Related OPPO-family reverse engineering; shows other product lines may use incompatible `0xFF` framing | SoundPEATS H3 | Repository-specific; do not treat commands as OPOv1 |

The directly relevant repositories are used only as factual research. OppoPods declares GPL-3.0 in its README; the other two had no explicit license found at the inspected revisions. This project independently implements the documented wire format and does not copy their source code.

The term “OPOv1” is used inconsistently in community projects: it can mean the 0xAA command protocol rather than one fixed Bluetooth bearer. Evidence shows the protocol may run over BLE GATT or Bluetooth Classic RFCOMM depending on model. The original OnePlus Buds Pro is an RFCOMM/SPP device.

At OppoPods commit `ad1bb4275b0ce1ce844d5d999dd92e75abc52831`, its protocol notes corroborate `0x0105` as `getRemoteVersion`, the notification flow `0x0200` → `0x8200` → `0x0205` → `0x8205`, and dynamic feature-ID lists for `0x010d`. These facts guided independent implementation and hardware probing; no source code was copied. Its README declares GPL-3.0, though the inspected tree has no standalone licence file.

Publication provenance review (2026-09-07): the project uses the installed Omarchy
QML APIs and system dbus-python at runtime; neither dependency is vendored. Protocol
research and sanitized hardware observations are documented above. No third-party
source or raster assets are bundled. The original project files are licensed MIT.
