"""Content receipts for a stable package during long Mei Hua audits."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Mapping

_CACHES = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}


def capture_package_sources(package: Path) -> dict[str, str]:
    """Hash package files and resources, including indirect calculation inputs.

    This receipt covers on-disk bytes at the two comparison times. A fresh
    process and immutable snapshot are still needed to bind loaded code; native
    dependencies and external ephemeris resources need their own receipts.
    """
    package = package.resolve()
    receipt: dict[str, str] = {}
    try:
        for path in sorted(package.rglob("*")):
            relative = path.relative_to(package)
            if any(part in _CACHES for part in relative.parts):
                continue
            if path.is_symlink() and path.is_dir():
                raise ValueError(
                    "Package directory links require a materialized audit snapshot"
                )
            if (
                not path.is_file()
                or path.suffix in {".pyc", ".pyo"}
                or path.name == ".DS_Store"
            ):
                continue
            receipt[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as error:
        raise ValueError("Cannot read stable engine package source files") from error
    if not receipt:
        raise ValueError("Engine package must contain source files")
    return receipt


def verify_package_sources(package: Path, receipt: Mapping[str, str]) -> None:
    """Reject modified, removed and newly added files; never narrow the oracle."""
    current = capture_package_sources(package)
    if current != receipt:
        added = sorted(current.keys() - receipt.keys())
        removed = sorted(receipt.keys() - current.keys())
        modified = sorted(
            name
            for name in current.keys() & receipt.keys()
            if current[name] != receipt[name]
        )
        raise ValueError(
            "Engine package sources changed during audit; use a stable snapshot. "
            f"Added={added}; removed={removed}; modified={modified}"
        )
