from __future__ import annotations

import json
import os
import re
import socket
from pathlib import Path
from urllib.parse import unquote, urlparse

from . import __version__
from .models import ControllerSnapshot, StatusResult
from .profiles import compatibility_for_product, profile_for_product


_MAC_ADDRESS = re.compile(r"(?i)(?:[0-9a-f]{2}:){5}[0-9a-f]{2}")
_SECRET = re.compile(
    r"(?i)\b(token|secret|password|authorization|github[_-]?token)\b\s*[:=]\s*\S+"
)
_GITHUB_TOKEN = re.compile(
    r"\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"
)
_BEARER_TOKEN = re.compile(r"(?i)\bBearer\s+\S+")


def _redact_text(value: str) -> str:
    """Redact machine/user identifiers from report-layer strings."""
    result = _MAC_ADDRESS.sub("[device]", value)
    home = str(Path.home())
    username = Path.home().name
    hostname = socket.gethostname()
    if home:
        result = result.replace(home, "[home]")
    for personal in (username, hostname):
        if personal:
            result = re.sub(re.escape(personal), "[redacted]", result, flags=re.IGNORECASE)
    result = _BEARER_TOKEN.sub("Bearer [redacted]", result)
    result = _SECRET.sub(lambda match: f"{match.group(1)}=[redacted]", result)
    result = _GITHUB_TOKEN.sub("[redacted-token]", result)
    return result


def _safe_errors(errors: tuple[str, ...]) -> list[str]:
    return [_redact_text(str(error))[:500] for error in errors[-12:]]


def _capability_summary(capabilities: set[str]) -> dict[str, bool]:
    return {
        "battery": "battery" in capabilities,
        "anc": "anc" in capabilities,
        "transparency": "transparency" in capabilities,
        "anc_levels": "anc_levels" in capabilities,
        "eq": "eq" in capabilities,
        "custom_eq": "custom_eq" in capabilities,
    }


def build_status_report(status: StatusResult) -> dict[str, object]:
    """Build the one-shot CLI report without copying user-authored device names."""
    profile = profile_for_product(status.product_id)
    capabilities = set(profile.capabilities) if profile else set()
    return {
        "report_schema": 1,
        "plugin_version": __version__,
        "backend_version": __version__,
        "device": {
            "model": status.model or "Unverified compatible device",
            "product_id": status.product_id,
            "firmware_version": status.firmware_version,
            "protocol_family": "OPOv1/0xAA",
            "transport": status.to_dict().get("transport"),
            "compatibility": compatibility_for_product(status.product_id),
        },
        "capabilities": sorted(capabilities),
        "feature_support": _capability_summary(capabilities),
        "connection": {
            "connected": status.device.connected,
            "services_resolved": status.device.services_resolved,
            "authenticated": None,
        },
        "state": {
            "battery": status.battery,
            "anc": status.anc,
            "anc_level": status.anc_level,
        },
        "recent_errors": [],
        "protocol_diagnostics": {},
        "privacy": (
            "Bluetooth addresses, device aliases, usernames, hostnames, home paths, "
            "credentials, secrets, unrelated devices, and raw packets are omitted or redacted."
        ),
    }


def build_snapshot_report(
    snapshot: ControllerSnapshot, *, recent_errors: tuple[str, ...] = ()
) -> dict[str, object]:
    status = snapshot.status
    if status is None:
        raise RuntimeError("no compatible earbud snapshot is available")
    report = build_status_report(status)
    profile = profile_for_product(status.product_id)
    capabilities = set(profile.capabilities) if profile else set()
    capabilities.update(snapshot.feature_switches)
    report["capabilities"] = sorted(capabilities)
    report["feature_support"] = _capability_summary(capabilities)
    report["connection"] = {
        "connected": status.device.connected,
        "services_resolved": status.device.services_resolved,
        "authenticated": snapshot.session_connected,
    }
    report["recent_errors"] = _safe_errors(recent_errors)
    report["protocol_diagnostics"] = {
        "advertised_event_codes": list(snapshot.advertised_event_codes),
        "notification_event_codes": list(snapshot.notification_event_codes),
        "ignored_frame_count": snapshot.ignored_frames,
        "reconnect_count": snapshot.reconnect_count,
        "snapshot_generation": snapshot.generation,
    }
    return report


def _local_path(value: str) -> Path:
    parsed = urlparse(value)
    if parsed.scheme and parsed.scheme != "file":
        raise ValueError("diagnostic reports can only be saved to a local file")
    if parsed.scheme == "file" and parsed.netloc not in ("", "localhost"):
        raise ValueError("diagnostic reports can only be saved to a local file")
    raw_path = unquote(parsed.path) if parsed.scheme == "file" else value
    path = Path(raw_path).expanduser()
    if not path.name:
        raise ValueError("choose a diagnostic report filename")
    return path


def write_report(report: dict[str, object], destination: str) -> str:
    """Write only a backend-built, sanitised report to the user's chosen path."""
    path = _local_path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    descriptor = os.open(path, flags, 0o600)
    os.fchmod(descriptor, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write("\n")
    return path.name
