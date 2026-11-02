"""Explicit acquisition profiles and verified per-user ephemeris discovery.

This module never downloads, creates directories or changes Swiss state.
Acquisition is an explicit fetch_ephe command; computations only discover data.
"""

from __future__ import annotations

import os
import platform
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

from fatebridge.core.astro.ephemeris_files import ephemeris_files_for_years
from fatebridge.core.astro.ephemeris_integrity import (
    load_ephemeris_manifest,
    verify_ephemeris_bytes,
)

FENGSHUI_PROFILE = "fengshui_calendar"
MAX_EPHEMERIS_PATH_BYTES = 242
# Full 20-year intervals around supported effective event years1800..2199.
FENGSHUI_FIRST_BOUNDARY_YEAR = 1784
FENGSHUI_LAST_BOUNDARY_YEAR = 2204
FENGSHUI_FILES = ephemeris_files_for_years(
    (FENGSHUI_FIRST_BOUNDARY_YEAR, FENGSHUI_LAST_BOUNDARY_YEAR)
)
HUMAN_DESIGN_PROFILE = "human_design"
# Civil births1800..2399, the110-day Design bracket, a1-hour uncertainty
# interval and timezone rollover, then the optional65-Julian-year search.
# The final year is a conservative calendar envelope, not an accuracy bound.
HUMAN_DESIGN_FIRST_YEAR = 1799
HUMAN_DESIGN_LAST_YEAR = 2465
HUMAN_DESIGN_FILES = tuple(
    name
    for planet_name in ephemeris_files_for_years(
        (HUMAN_DESIGN_FIRST_YEAR, HUMAN_DESIGN_LAST_YEAR)
    )
    for name in (
        (planet_name, planet_name.replace("sepl_", "seas_"))
        if planet_name.startswith("sepl_")
        else (planet_name,)
    )
)


def user_ephemeris_dir() -> Path:
    """Use an explicit absolute XDG cache override, then the platform cache."""
    supplied = os.environ.get("XDG_CACHE_HOME")
    if supplied and Path(supplied).is_absolute():
        root = Path(supplied)
    elif platform.system() == "Windows":
        supplied = os.environ.get("LOCALAPPDATA")
        root = (
            Path(supplied)
            if supplied and Path(supplied).is_absolute()
            else Path.home() / "AppData/Local"
        )
    elif platform.system() == "Darwin":
        root = Path.home() / "Library/Caches"
    else:
        root = Path.home() / ".cache"
    return root / "fatebridge/ephe"


def _file_status(directory: Path, names: Sequence[str]) -> Dict[str, Any]:
    """File identity only: no claim about loaded model or TT acceptance."""
    manifest = load_ephemeris_manifest()
    rows: Dict[str, Any] = {}
    for name in names:
        try:
            verify_ephemeris_bytes(name, (directory / name).read_bytes(), manifest)
            rows[name] = {"verified": True}
        except (OSError, ValueError) as exc:
            rows[name] = {"verified": False, "reason": str(exc)}
    return {
        "directory": str(directory),
        "edition": manifest["id"],
        "source_commit": manifest["source_commit"],
        "files": rows,
        "all_files_verified": all(row["verified"] for row in rows.values()),
        "scope": "file_content_identity_not_loaded_model_or_astronomical_acceptance",
    }


def fengshui_file_status(directory: Path) -> Dict[str, Any]:
    return {
        "profile": FENGSHUI_PROFILE,
        "boundary_years_inclusive": [
            FENGSHUI_FIRST_BOUNDARY_YEAR,
            FENGSHUI_LAST_BOUNDARY_YEAR,
        ],
        **_file_status(directory, FENGSHUI_FILES),
    }


def human_design_file_status(directory: Path) -> Dict[str, Any]:
    return {
        "profile": HUMAN_DESIGN_PROFILE,
        "computation_years_inclusive": [
            HUMAN_DESIGN_FIRST_YEAR,
            HUMAN_DESIGN_LAST_YEAR,
        ],
        "coverage": "natal_activations_and_optional_first_cycle_searches",
        **_file_status(directory, HUMAN_DESIGN_FILES),
    }


def verified_user_ephemeris_dir() -> Optional[str]:
    directory = user_ephemeris_dir()
    if not ephemeris_path_fits(directory) or not directory.is_dir():
        return None
    return (
        str(directory)
        if fengshui_file_status(directory)["all_files_verified"]
        else None
    )


def ephemeris_path_fits(directory: Path) -> bool:
    value = str(directory)
    return "\0" not in value and len(os.fsencode(value)) <= MAX_EPHEMERIS_PATH_BYTES
