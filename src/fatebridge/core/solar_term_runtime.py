"""Private cache identity for the solar solver's loaded clock and orbit data."""

from __future__ import annotations

import json
from types import ModuleType
from typing import Any

from fatebridge.core import solar_model_policy
from fatebridge.core.astro import historical_utc, utc_policy
from fatebridge.core.ephemeris_paths import ephemeris_search_directories
from fatebridge.core.ephemeris_runtime import effective_ephemeris_search_path
from fatebridge.core.jpl_ephemeris import configured_jpl_file


def loaded_clock_profile_key() -> str:
    """Snapshot the loaded coefficients and metadata used by clock calculations."""
    return json.dumps(
        (
            utc_policy.leap_table(),
            utc_policy.utc_definition_source(),
            historical_utc.utc1960_table(),
            historical_utc.historical_utc_table(),
        ),
        sort_keys=True,
        separators=(",", ":"),
    )


def solar_term_cache_context(
    module: ModuleType | None, *, year: int | None = None, native_only: bool = False
) -> tuple[Any, ...]:
    # Validate strict mode even when a prior default year is already cached.
    jpl_file = configured_jpl_file()
    mode = "native" if native_only else solar_model_policy.solar_model_policy()
    if jpl_file is not None and mode in {
        "swiss",
        "analytic",
        "spk",
        "de440",
        "aa1996",
        "vsop2013",
    }:
        label = {"swiss": "Swiss", "vsop2013": "VSOP2013", "aa1996": "AA1996"}.get(
            mode, "analytic/SPK/DE440"
        )
        raise ValueError(
            f"Explicit {label} solar mode conflicts with strict JPL selection"
        )
    # An explicit native reobservation must not load an unrelated configured
    # analytic/SPK source merely to fingerprint its native data candidates.
    solar_model = (
        "native_observation_only"
        if native_only
        else (
            solar_model_policy.solar_model_cache_key(year=year)
            if year is not None
            else solar_model_policy.solar_model_cache_key()
        )
    )
    if jpl_file is not None and module is None:
        raise ModuleNotFoundError(
            "Swiss Ephemeris is required for explicitly selected JPL mode"
        )
    clock_profile = loaded_clock_profile_key()
    selected = effective_ephemeris_search_path()
    search_path = selected or "."
    entries = []
    depths: dict[str, int] = {}
    for index, directory in enumerate(ephemeris_search_directories(search_path)):
        path = directory.absolute()
        files: list[
            tuple[str, int, int, int, int, int]
            | tuple[str, str, int | None]
            | tuple[str, int | None]
        ] = []
        try:
            candidates = {
                p for pattern in ("sepl*.se1", "semo*.se1") for p in path.glob(pattern)
            }
            candidates.update(
                path / name
                for name in ("swe_deltat.txt", "sedeltat.txt", "seleapsec.txt")
            )
            if jpl_file is not None:
                candidates.add(path / jpl_file)
            for candidate in sorted(candidates):
                name = candidate.name
                if name not in depths:
                    depths[name] = len(
                        ephemeris_search_directories(search_path, filename=name)
                    )
                if index >= depths[name]:
                    continue
                try:
                    stat = candidate.stat()
                    files.append(
                        (
                            candidate.name,
                            stat.st_dev,
                            stat.st_ino,
                            stat.st_size,
                            stat.st_mtime_ns,
                            stat.st_ctime_ns,
                        )
                    )
                except FileNotFoundError:
                    continue
                except OSError as error:
                    files.append((candidate.name, "unreadable", error.errno))
        except OSError as error:
            files.append(("directory_unreadable", error.errno))
        entries.append((str(path), tuple(files)))
    return (
        id(module),
        str(getattr(module, "version", "unknown")),
        selected,
        tuple(entries),
        jpl_file,
        clock_profile,
        "all_numerical_solar_roots_explicit_tt_points_v3",
        solar_model,
    )
