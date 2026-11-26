"""Explicit Sun selection, with a bundled DE441 fallback."""

from __future__ import annotations

import os
from typing import Any

from fatebridge.core.aa1996_solar import MODEL_ID as AA1996_MODEL_ID
from fatebridge.core.aa1996_solar import cache_key as aa1996_cache_key
from fatebridge.core.aa1996_solar import source_receipt as aa1996_source_receipt
from fatebridge.core.analytic_solar import MODEL_ID
from fatebridge.core.de440_solar import EXTENDED_MODEL_ID
from fatebridge.core.de440_solar import MODEL_ID as DE440_MODEL_ID
from fatebridge.core.de440_solar import cache_key as de440_cache_key
from fatebridge.core.de440_solar import source_receipt as de440_source_receipt
from fatebridge.core.de441_solar import CACHE_IDENTITY
from fatebridge.core.ephemeris_runtime import has_swiss_data_files
from fatebridge.core.jpl_ephemeris import configured_jpl_file
from fatebridge.core.spk_solar import MODEL_ID as SPK_MODEL_ID
from fatebridge.core.spk_solar import cache_key as spk_cache_key
from fatebridge.core.spk_solar import source_receipt as spk_source_receipt
from fatebridge.core.vsop2013_solar import MODEL_ID as VSOP2013_MODEL_ID
from fatebridge.core.vsop2013_solar import cache_key as vsop2013_cache_key
from fatebridge.core.vsop2013_solar import source_receipt as vsop2013_source_receipt

ENVIRONMENT_NAME = "FATEBRIDGE_SOLAR_TERM_MODEL"
MODES = frozenset(
    {"auto", "native", "swiss", "analytic", "spk", "de440", "aa1996", "vsop2013"}
)
VALIDATED_SOFTWARE_YEARS = (1800, 2200)
DE440_SOFTWARE_YEARS = (1700, 2300)
VSOP2013_SOFTWARE_YEARS = (1700, 2300)


def solar_model_policy() -> str:
    mode = os.environ.get(ENVIRONMENT_NAME, "auto").strip().lower()
    if mode not in MODES:
        raise ValueError(
            f"{ENVIRONMENT_NAME} must be auto, native, swiss, analytic, spk, de440, aa1996, or vsop2013"
        )
    return mode


def de440_selected(year: int) -> bool:
    mode = solar_model_policy()
    inside = DE440_SOFTWARE_YEARS[0] <= year <= DE440_SOFTWARE_YEARS[1]
    if mode == "de440" and not inside:
        raise ValueError(
            "Explicit packaged DE440 solar mode currently covers1700..2300"
        )
    return inside and (
        mode == "de440" or (mode == "auto" and configured_jpl_file() is None)
    )


def de440_profile_for_year(year: int | None = None) -> str:
    """Select a year-grid profile without resolving any coefficient bytes."""
    if (
        year is None
        or VALIDATED_SOFTWARE_YEARS[0] <= year <= VALIDATED_SOFTWARE_YEARS[1]
    ):
        return DE440_MODEL_ID
    if DE440_SOFTWARE_YEARS[0] <= year <= DE440_SOFTWARE_YEARS[1]:
        return EXTENDED_MODEL_ID
    raise ValueError("Packaged DE440 year-grid selection covers1700..2300")


def solar_context_input_years(year: int) -> tuple[int, int]:
    """Neighbor reuse follows the qualification of the selected input profile.

    This is a per-context scope, not the union of all public model ranges.
    Existing input profiles retain their established neighboring-year behavior.
    """
    mode = solar_model_policy()
    if mode == "vsop2013":
        return VSOP2013_SOFTWARE_YEARS
    if mode == "native":
        return (1, 9999)
    if not VALIDATED_SOFTWARE_YEARS[0] <= year <= VALIDATED_SOFTWARE_YEARS[
        1
    ] and de440_selected(year):
        return DE440_SOFTWARE_YEARS
    if mode == "auto" and not (
        VALIDATED_SOFTWARE_YEARS[0] <= year <= VALIDATED_SOFTWARE_YEARS[1]
    ):
        return (1, 9999)
    return VALIDATED_SOFTWARE_YEARS


def solar_model_cache_key(*, year: int | None = None) -> tuple[Any, ...]:
    # Keys bind immutable packaged source identities or configured native data.
    # The selected calculation verifies the bytes it uses.
    mode = solar_model_policy()
    if (
        mode == "analytic"
        and year is not None
        and not VALIDATED_SOFTWARE_YEARS[0] <= year <= VALIDATED_SOFTWARE_YEARS[1]
    ):
        raise ValueError("Explicit analytic solar mode currently covers1800..2200")
    if mode in {"native", "swiss"}:
        if (
            mode == "swiss"
            and year is not None
            and not VALIDATED_SOFTWARE_YEARS[0] <= year <= VALIDATED_SOFTWARE_YEARS[1]
        ):
            raise ValueError("Explicit Swiss solar mode currently covers1800..2200")
        if mode == "swiss":
            return mode, "native_swiss_runtime"
        if configured_jpl_file() is not None:
            return mode, "native_strict_jpl"
        return mode, "native_swiss_runtime", *CACHE_IDENTITY
    if mode == "auto" and configured_jpl_file() is not None:
        return mode, "native_strict_jpl"
    if (
        mode == "auto"
        and has_swiss_data_files()
        and (
            year is None
            or VALIDATED_SOFTWARE_YEARS[0] <= year <= VALIDATED_SOFTWARE_YEARS[1]
        )
    ):
        return mode, "native_swiss_runtime"
    if year is not None and mode in {"auto", "de440"} and not de440_selected(year):
        # Use the native source policy outside the packaged year grid.
        # Explicit de440 has already rejected an out-of-range year above.
        return mode, "native_outside_packaged_years", *CACHE_IDENTITY
    if mode == "vsop2013":
        if (
            year is not None
            and not VSOP2013_SOFTWARE_YEARS[0] <= year <= VSOP2013_SOFTWARE_YEARS[1]
        ):
            raise ValueError("Explicit VSOP2013 solar mode currently covers1700..2300")
        return mode, VSOP2013_MODEL_ID, vsop2013_cache_key()
    if mode == "aa1996":
        if (
            year is not None
            and not VALIDATED_SOFTWARE_YEARS[0] <= year <= VALIDATED_SOFTWARE_YEARS[1]
        ):
            raise ValueError("Explicit AA1996 solar mode currently covers1800..2200")
        return mode, AA1996_MODEL_ID, aa1996_cache_key()
    if mode == "spk":
        return mode, SPK_MODEL_ID, spk_cache_key()
    if mode in {"auto", "de440"}:
        selected = de440_profile_for_year(year)
        return (
            mode,
            selected,
            (
                de440_cache_key()
                if year is None or selected == de440_profile_for_year()
                else de440_cache_key(selected)
            ),
        )
    return mode, MODEL_ID


def solar_model_environment_receipt(
    *, resolve_source: bool = True, observed_de440_models: list[str] | None = None
) -> dict[str, Any]:
    """Minimal solar model mode summary without prose walls."""
    mode = solar_model_policy()
    receipt: dict[str, Any] = {"mode": mode}
    if observed_de440_models:
        receipt["observed_model_ids"] = sorted(set(observed_de440_models))
    return receipt
