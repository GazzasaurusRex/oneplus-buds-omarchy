#!/usr/bin/env python3
"""Export a reviewable plugin tree; refuse existing destinations and symlinks."""
from __future__ import annotations

import argparse
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
FILES = (
    "manifest.json", "BarWidget.qml", "BarModel.js", "BridgeModel.js", "Service.qml",
    "oneplus-buds", "oneplus-buds-bridge", "README.md", "LICENSE", "CHANGELOG.md",
    "CONTRIBUTING.md", "pyproject.toml",
)
DIRECTORIES = ("src", "docs", "scripts", "tests")


def export(destination: Path) -> None:
    destination = destination.expanduser().absolute()
    if destination.exists() or destination.is_symlink():
        raise ValueError("destination already exists; choose a new directory")
    if destination.resolve().is_relative_to(ROOT):
        raise ValueError("destination must be outside the source checkout")
    sources = [ROOT / name for name in FILES]
    for name in DIRECTORIES:
        sources.append(ROOT / name)
        sources.extend(path for path in (ROOT / name).rglob("*")
                       if "__pycache__" not in path.parts and path.suffix not in (".pyc", ".pyo"))
    for source in sources:
        if source.is_symlink():
            raise ValueError(f"symlink not allowed: {source.relative_to(ROOT)}")
        if not source.exists():
            raise ValueError(f"missing source: {source.relative_to(ROOT)}")
    destination.mkdir(parents=True, exist_ok=False)
    for source in sources:
        if source.is_file():
            target = destination / source.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    try:
        export(args.destination)
    except (OSError, ValueError) as error:
        parser.exit(1, f"export failed: {error}\n")
    print(f"Exported plugin to {args.destination}")


if __name__ == "__main__":
    main()
