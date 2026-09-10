# Publication preparation

Checked against the current [publishing guide](https://plugins.omarchy.org/publish.html),
[development guide](https://plugins.omarchy.org/develop.html),
[submission guide](https://github.com/omacom/omarchy-plugin-marketplace/blob/main/SUBMISSION.md),
and [verification policy](https://github.com/omacom/omarchy-plugin-marketplace/blob/main/VERIFICATION.md)
on 2026-09-10. The installed Omarchy 4.0.3-1 validator was exercised too.

## Prepared locally

The root manifest declares `oneplus-buds.control`, version `0.1.0`, with service
and bar-widget entry points. README, MIT license, changelog, contribution guidance,
compatibility matrix and issue templates are present. Runtime dependencies and
known limitations are documented. The plugin runs from bundled source without
install hooks. A read-only dependency preflight and a clean exporter are included.

The version remains an unreleased release candidate; preparing it does not create
a tag, GitHub release, or marketplace listing. The repository is
`https://github.com/GazzasaurusRex/oneplus-buds-omarchy.git`. Its initial
commit is preserved in history. At the user's request, the current LICENSE uses
the project's original MIT notice, Copyright (c) 2026 Gaz and contributors.

## Reviewable submission draft

| Field | Proposed value |
|---|---|
| Repository URL | https://github.com/GazzasaurusRex/oneplus-buds-omarchy |
| Category | Hardware |
| Tags | `bar`, `media`, `quickshell` |
| Plugin name | OnePlus Buds Control |
| ID | `oneplus-buds.control` |
| Version | `0.1.0` (release candidate; not tagged) |
| License | MIT |

Maintainer notes:

> Native Omarchy service/bar widget for OnePlus earbuds, with a Python backend
> using BlueZ D-Bus and Bluetooth Classic RFCOMM. Buds Pro and Buds Pro 2 battery,
> firmware, noise controls, and model-appropriate native EQ are hardware-verified. Requires system
> Python 3.11+, python-dbus and BlueZ. No PyPI runtime dependencies or install
> hooks. One helper follows plugin lifecycle inside the existing shell; no second
> Quickshell instance. Only advertised verified controls are exposed. Installation
> and removal use Omarchy commands. The project is independent of OnePlus/OPPO.

Submission is through the [marketplace issue form](https://github.com/omacom/omarchy-plugin-marketplace/issues/new?template=submit-plugin.yml)
or the documented CLI issue format. It requires a public repository, one category,
and one to three controlled lowercase tags. Validation and the automated security
baseline bind to the exact submitted commit; publication requires the marketplace
maintainer's later `approved-and-verified` decision. The submitting owner must
review the ownership, permissions, installation, and security-disclaimer checklist.
Marketplace validation and approval are not a security review.
The root `preview.png` is a user-supplied 563×1080 live panel capture. It was
reviewed for visible personal information and unrelated application content before
being committed for marketplace use.

## Remaining external steps

1. Review and commit the `0.1.0` release-candidate changes, then push that exact
   commit to the public repository. Keep manifest, pyproject and Python
   `__version__` consistent.
2. Decide whether to create the annotated `v0.1.0` tag and GitHub release from
   that commit. Tagging and release publication require explicit authorization.
3. Submit the marketplace draft only after the owner reviews and confirms every
   checklist statement and explicitly approves creation of the external issue.

For a public Git URL, the current install flow is:

```bash
omarchy plugin add https://github.com/GazzasaurusRex/oneplus-buds-omarchy.git
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

Validation result (2026-09-10): the checkout and a clean source export passed
Omarchy 4.0.3-1 validation, CLI help, dependency preflight, all 110
Python/JavaScript tests, and all 4 Qt offscreen interaction tests. Whitespace
checks passed. No hardware or desktop configuration was changed during packaging
validation.
