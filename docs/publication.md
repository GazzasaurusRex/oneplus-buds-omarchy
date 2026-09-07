# Publication preparation

Checked against the current [publishing guide](https://plugins.omarchy.org/publish.html),
[development guide](https://plugins.omarchy.org/develop.html), and
[submission form source](https://github.com/omacom/omarchy-plugin-marketplace/blob/main/.github/ISSUE_TEMPLATE/submit-plugin.yml)
on 2026-09-07. The installed Omarchy 4.0.2-1 `plugin add`, `remove` and `validate`
commands were inspected too.

## Prepared locally

The root manifest declares `oneplus-buds.control`, version `0.0.1`, with service
and bar-widget entry points. README, MIT license, changelog, contribution guidance,
compatibility matrix and issue templates are present. Runtime dependencies and
known limitations are documented. The plugin runs from bundled source without
install hooks. A read-only dependency preflight and a clean exporter are included.

The version remains an unreleased development snapshot; this task does not tag a
release, upload a repository or submit a listing. The user selected `https://github.com/scoobysti29-design/oneplus-buds-omarchy.git`. Its initial
commit is preserved in history. At the user's request, the current LICENSE uses
the project's original MIT notice, Copyright (c) 2026 Gaz and contributors.

## Reviewable submission draft

| Field | Proposed value |
|---|---|
| Repository URL | https://github.com/scoobysti29-design/oneplus-buds-omarchy |
| Category | Hardware |
| Tags | Bar, Media, Quickshell |
| Plugin name | OnePlus Buds Control |
| ID | `oneplus-buds.control` |
| Version | `0.0.1` (pre-release) |
| License | MIT |

Maintainer notes:

> Native Omarchy service/bar widget for OnePlus earbuds, with a Python backend
> using BlueZ D-Bus and Bluetooth Classic RFCOMM. Buds Pro and Buds Pro 2 basic
> battery, firmware and noise controls are hardware-verified. Requires system
> Python 3.11+, python-dbus and BlueZ. No PyPI runtime dependencies or install
> hooks. One helper follows plugin lifecycle inside the existing shell; no second
> Quickshell instance. Only advertised verified controls are exposed. Installation
> and removal use Omarchy commands. The project is independent of OnePlus/OPPO.

Submission is through the [marketplace issue form](https://github.com/omacom/omarchy-plugin-marketplace/issues/new?template=submit-plugin.yml).
The form requires a public repository, one category and one to three listed tags.
Its declarations about ownership, permissions and installation behavior must be
reviewed by the submitting owner. Marketplace approval is not a security review.
An optional preview should show only the panel/widget, with no personal desktop
content. Existing temporary desktop captures are not committed preview assets.

## Remaining external steps

1. Review the published source/history at the user-selected repository. README
   and metadata contain its actual URL, and the initial license history is retained.
2. Re-run validation for the actual release commit; choose whether to publish
   0.0.1 as a pre-release or continue toward the 0.1 target. Keep manifest,
   pyproject and Python `__version__` consistent.
3. Submit the draft listing only after the repository is public and reviewed.

For a public Git URL, the current install flow is:

```bash
omarchy plugin add https://github.com/scoobysti29-design/oneplus-buds-omarchy.git
python3 "$HOME/.config/omarchy/plugins/oneplus-buds.control/scripts/check_dependencies.py"
omarchy plugin enable oneplus-buds.control --section right
```

Decline immediate enable if offered until the preflight passes. Omarchy performs the clone,
validation and enable flow; it does not install Python dependencies. Users should
run the documented preflight before enabling. Updates for Git-managed installs
use `omarchy plugin update oneplus-buds.control`; copied exports must be replaced
only after preserving any local modifications.

## Local verification scope

Use a fresh export for packaging checks so hidden repository files, caches and
virtual environments cannot influence imports:

```bash
python3 scripts/export_plugin.py /tmp/oneplus-publication-review
omarchy plugin validate /tmp/oneplus-publication-review
/tmp/oneplus-publication-review/oneplus-buds --help
python3 /tmp/oneplus-publication-review/scripts/check_dependencies.py
```

The exporter refuses an existing destination and source symlinks, preserves
executable modes and excludes caches/Git internals. This validates a source plugin
export, not a Python wheel. Wheel builds require setuptools >=77 and have not
been tested on this host, where setuptools is absent. Wheels are not the Omarchy
installation path. Prior live lifecycle, two-model ANC and accepted portrait UI
results remain in the handoff; packaging work should not repeat hardware cycles.

Validation result (2026-09-07): the clean source export passed Omarchy validation,
CLI help, dependency preflight, all 82 Python tests (including JavaScript checks),
and the Qt hover suite. The missing-dbus preflight path exited 1 as expected under
`python3 -S`. Documentation link checks and whitespace checks passed. No hardware
or desktop configuration was changed during packaging validation.
