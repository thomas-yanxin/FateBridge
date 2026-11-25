"""Discover installed ephemeris files and check their acquisition profiles."""

from __future__ import annotations

import os
import platform
from collections.abc import Sequence
from pathlib import Path

from typing_extensions import NotRequired, TypedDict

from fatebridge.core.astro.ephemeris_files import ephemeris_files_for_years
from fatebridge.core.astro.ephemeris_integrity import (
    load_ephemeris_manifest,
    verify_ephemeris_bytes,
)
from fatebridge.core.ephemeris_paths import (
    SWISS_PATH_BUFFER_BYTES,
    ephemeris_search_directories,
    ephemeris_search_path_fits,
)

FENGSHUI_PROFILE = "fengshui_calendar"
# note (coverage): Include full ephemeris intervals around event years 1800–2199.
FENGSHUI_FIRST_BOUNDARY_YEAR = 1784
FENGSHUI_LAST_BOUNDARY_YEAR = 2204
FENGSHUI_FILES = ephemeris_files_for_years(
    (FENGSHUI_FIRST_BOUNDARY_YEAR, FENGSHUI_LAST_BOUNDARY_YEAR)
)
HUMAN_DESIGN_PROFILE = "human_design"
# note (coverage): Allow 110 days for Design, one hour of uncertainty and 65 Julian years for cycle searches.
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


class EphemerisFileStatus(TypedDict):
    verified: bool
    reason: NotRequired[str]


class EphemerisDirectoryStatus(TypedDict):
    directory: str
    edition: str
    source_commit: str
    files: dict[str, EphemerisFileStatus]
    all_files_verified: bool
    scope: str


class FengshuiEphemerisStatus(EphemerisDirectoryStatus):
    profile: str
    boundary_years_inclusive: list[int]


class HumanDesignEphemerisStatus(EphemerisDirectoryStatus):
    profile: str
    computation_years_inclusive: list[int]
    coverage: str


def _file_status(directory: Path, names: Sequence[str]) -> EphemerisDirectoryStatus:
    """File identity only: no claim about loaded model or TT acceptance."""
    manifest = load_ephemeris_manifest()
    files: dict[str, EphemerisFileStatus] = {}
    for name in names:
        try:
            verify_ephemeris_bytes(name, (directory / name).read_bytes(), manifest)
            files[name] = {"verified": True}
        except (OSError, ValueError) as exc:
            files[name] = {"verified": False, "reason": str(exc)}
    return {
        "directory": str(directory),
        "edition": manifest["id"],
        "source_commit": manifest["source_commit"],
        "files": files,
        "all_files_verified": all(file["verified"] for file in files.values()),
        "scope": "file_content_identity_not_loaded_model_or_astronomical_acceptance",
    }


def fengshui_file_status(directory: Path) -> FengshuiEphemerisStatus:
    return {
        "profile": FENGSHUI_PROFILE,
        "boundary_years_inclusive": [
            FENGSHUI_FIRST_BOUNDARY_YEAR,
            FENGSHUI_LAST_BOUNDARY_YEAR,
        ],
        **_file_status(directory, FENGSHUI_FILES),
    }


def human_design_file_status(directory: Path) -> HumanDesignEphemerisStatus:
    return {
        "profile": HUMAN_DESIGN_PROFILE,
        "computation_years_inclusive": [
            HUMAN_DESIGN_FIRST_YEAR,
            HUMAN_DESIGN_LAST_YEAR,
        ],
        "coverage": "natal_activations_and_optional_first_cycle_searches",
        **_file_status(directory, HUMAN_DESIGN_FILES),
    }


def verified_user_ephemeris_dir() -> str | None:
    directory = user_ephemeris_dir()
    if not ephemeris_path_fits(directory) or not directory.is_dir():
        return None
    else:
        pass
    return (
        str(directory)
        if fengshui_file_status(directory)["all_files_verified"]
        else None
    )


def has_project_ephemeris_files(directory: Path) -> bool:
    """A discoverable checkout directory has a usable path and .se1 files."""
    return (
        ephemeris_path_fits(directory)
        and directory.is_dir()
        and any(candidate.is_file() for candidate in directory.glob("*.se1"))
    )


def ephemeris_path_fits(directory: Path, *, filename: str | None = None) -> bool:
    """Check whether Swiss can search this literal directory and open its file."""
    value = str(directory)
    return (
        ephemeris_search_path_fits(value)
        and ephemeris_search_directories(value) == (directory,)
        and (
            filename is None
            or len(os.fsencode(directory / filename)) < SWISS_PATH_BUFFER_BYTES
        )
    )
