"""O(1) process-generation cache identity for the solar solver."""

from __future__ import annotations

from types import ModuleType
from typing import Any

from fatebridge.core import solar_model_policy
from fatebridge.core.astro import historical_utc, utc_policy
from fatebridge.core.ephemeris_runtime import (
    configured_ephemeris_path,
    ephemeris_generation,
    has_swiss_data_files,
)
from fatebridge.core.jpl_ephemeris import configured_jpl_file


def loaded_clock_profile_key() -> tuple[int, int, int, int]:
    """O(1) identity of the loaded clock and leap-second tables."""
    return (
        id(utc_policy.leap_table()),
        id(utc_policy.utc_definition_source()),
        id(historical_utc.utc1960_table()),
        id(historical_utc.historical_utc_table()),
    )


def solar_term_cache_context(
    module: ModuleType | None, *, year: int | None = None, native_only: bool = False
) -> tuple[Any, ...]:
    """Lightweight O(1) cache key without filesystem glob/stat or json.dumps."""
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
    return (
        id(module),
        str(getattr(module, "version", "unknown")),
        configured_ephemeris_path(),
        ephemeris_generation(),
        has_swiss_data_files() if module is not None else False,
        jpl_file,
        loaded_clock_profile_key(),
        "solar_roots_v4",
        solar_model,
    )
