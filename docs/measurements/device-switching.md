# Physical device switching — 2026-09-08

The unchanged live plugin reproduced the report: original Buds Pro was the only
BlueZ-connected device, while the plugin retained Pro 2 ANC modes and reported
selected-device-unavailable. The installed controller matched the checkout.

After deploying the generic lifecycle fix, the following observations came from
the actual widget's read-only IPC state, with helper PID **4404** unchanged:

| Stage | Product | Firmware | Left/right battery | ANC | Medium control | Session |
|---|---|---|---|---|---|---|
| Initial original Pro | 060C14 | 541.541.510 | 90% / 90% | Off | Absent | Connected |
| Switch to Pro 2 | 062014 | 196.196.101 | 100% / 100% | Off | Present | Connected |
| Both cases closed, repeated retries | None | None | None | None | Absent | Disconnected |
| Switch back to original Pro | 060C14 | 541.541.510 | 90% / 90% | Off | Absent | Connected |

BlueZ independently confirmed only the expected device connected at both switch
endpoints. The empty gap removed identity, battery label, ANC selection and all
ANC modes. Successful session publication follows authentication/subscription;
no restart or setting write was required between switches. No matching runtime
errors appeared in the inspected user journal. These checks establish backend
and actual UI-bound state; no screenshot or subjective visual check is claimed.

The installation was reloaded once to deploy the fix before this sequence.
Both subsequent switches used that same running helper and shell.
