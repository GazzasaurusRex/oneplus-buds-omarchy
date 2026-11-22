#!/usr/bin/env python3
"""Quietly report a safe, fast-forward-only plugin update without installing it."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys


PLUGIN_ID = "oneplus-buds.control"
UPDATE_COMMAND = f"omarchy plugin update {PLUGIN_ID}"
GIT_TIMEOUT_SECONDS = 20


def hidden(*, eligible: bool = False) -> dict[str, object]:
    return {
        "eligible": eligible,
        "available": False,
        "view_url": "",
        "manual_command": UPDATE_COMMAND,
        "commits_behind": 0,
    }


def _git(checkout: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment.update({
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_SSH_COMMAND": "ssh -oBatchMode=yes",
    })
    return subprocess.run(
        ("git", "-C", str(checkout), *args),
        check=check,
        capture_output=True,
        text=True,
        timeout=GIT_TIMEOUT_SECONDS,
        env=environment,
    )


def _github_repository(remote: str) -> str | None:
    value = remote.strip()
    patterns = (
        r"https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?$",
        r"git@github\.com:([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?$",
        r"ssh://git@github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?$",
    )
    for pattern in patterns:
        match = re.fullmatch(pattern, value)
        if match:
            return f"https://github.com/{match.group(1)}/{match.group(2)}"
    return None


def check_checkout(checkout: Path, *, home: Path | None = None) -> dict[str, object]:
    """Fetch origin/HEAD and report only a clean canonical checkout that can ff."""
    home = (home or Path.home()).expanduser().resolve()
    expected = home / ".config" / "omarchy" / "plugins" / PLUGIN_ID
    checkout = checkout.expanduser()

    # Exported review trees, symlinked sources, Git worktrees and ordinary
    # development clones must never phone home or advertise an install update.
    if (checkout.is_symlink() or checkout.resolve() != expected.resolve()
            or not (checkout / ".git").is_dir()):
        return hidden()

    try:
        if _git(checkout, "rev-parse", "--is-inside-work-tree").stdout.strip() != "true":
            return hidden()
        if _git(checkout, "status", "--porcelain").stdout:
            return hidden(eligible=True)

        # Read the configured URL rather than `remote get-url`, which can apply
        # url.*.insteadOf rewriting and stop the comparison link representing
        # the origin that is actually recorded in this installed checkout.
        remote = _git(checkout, "config", "--get", "remote.origin.url").stdout.strip()
        _git(checkout, "fetch", "--quiet", "origin", "HEAD")
        head = _git(checkout, "rev-parse", "HEAD").stdout.strip()
        fetched = _git(checkout, "rev-parse", "FETCH_HEAD").stdout.strip()
        if head == fetched:
            return hidden(eligible=True)

        ancestor = _git(
            checkout, "merge-base", "--is-ancestor", head, fetched, check=False
        )
        if ancestor.returncode != 0:
            return hidden(eligible=True)

        behind = int(_git(checkout, "rev-list", "--count", f"{head}..{fetched}").stdout)
        repository = _github_repository(remote)
        return {
            "eligible": True,
            "available": True,
            "view_url": (
                f"{repository}/compare/{head}...{fetched}" if repository else ""
            ),
            "manual_command": UPDATE_COMMAND,
            "commits_behind": max(1, behind),
        }
    except (OSError, ValueError, subprocess.SubprocessError):
        return hidden(eligible=True)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: check_plugin_update.py CHECKOUT")
    print(json.dumps(check_checkout(Path(sys.argv[1])), separators=(",", ":")))


if __name__ == "__main__":
    main()
