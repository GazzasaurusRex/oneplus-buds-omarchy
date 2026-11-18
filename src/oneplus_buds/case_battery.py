"""Keep the last usable case level; a zero means unavailable in the phone app."""
from __future__ import annotations

import hashlib
import json
import os
from contextlib import suppress
from pathlib import Path
from tempfile import NamedTemporaryFile

from .models import StatusResult


def default_cache_directory() -> Path:
    return Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "oneplus-buds" / "case-battery"


class CaseBatteryCache:
    def __init__(self, directory: Path | None = None) -> None:
        self.directory = directory
        self._levels: dict[str, int] = {}

    def merge(self, status: StatusResult,
              battery: dict[str, dict[str, int | bool]] | None
              ) -> dict[str, dict[str, int | bool]]:
        # Both product and physical identity matter, including two pairs of
        # the same model. Do not put Bluetooth addresses in cache filenames.
        key = hashlib.sha256(f"{status.product_id}:{status.device.address.upper()}".encode()).hexdigest()
        result = dict(battery or {})
        sample = result.pop("case", {})
        level = sample.get("percentage")
        if type(level) is int and 1 <= level <= 100:
            if self._levels.get(key) != level:
                self._levels[key] = level
                self._save(key, level)
            result["case"] = dict(sample)
        else:
            previous = self._levels.get(key)
            if previous is None and self.directory is not None:
                try:
                    stored = json.loads((self.directory / f"{key}.json").read_text())
                    previous = stored.get("percentage") if isinstance(stored, dict) else None
                except (OSError, ValueError):
                    previous = None
            if type(previous) is int and 1 <= previous <= 100:
                self._levels[key] = previous
                # A remembered charging flag would misleadingly keep blinking
                # after the case was disconnected from its power supply.
                result["case"] = {"percentage": previous, "charging": False,
                                  "last_known": True}
        return result

    def _save(self, key: str, level: int) -> None:
        if self.directory is None:
            return
        temporary: Path | None = None
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            with NamedTemporaryFile(mode="w", dir=self.directory, delete=False) as output:
                temporary = Path(output.name)
                json.dump({"percentage": level}, output)
            temporary.replace(self.directory / f"{key}.json")
        except OSError:
            # Disk/cache failures must never interrupt Bluetooth control.
            pass
        finally:
            if temporary is not None:
                with suppress(OSError):
                    temporary.unlink(missing_ok=True)
