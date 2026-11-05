"""Explicit Sun selection, with a named complete Moshier analytical revision."""

from __future__ import annotations

import os
from typing import Any, Dict, Tuple

from fatebridge.core.analytic_solar import MODEL_ID, profile

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


def analytic_selected(year: int, native_model: str) -> bool:
    mode = solar_model_policy()
    if mode != "analytic":
        return False
    inside = VALIDATED_SOFTWARE_YEARS[0] <= year <= VALIDATED_SOFTWARE_YEARS[1]
    if mode == "analytic" and not inside:
        raise ValueError("Explicit analytic solar mode currently covers1800..2200")
    return inside


def de440_selected(year: int) -> bool:
    from .jpl_ephemeris import configured_jpl_file

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
    from .de440_solar import EXTENDED_MODEL_ID
    from .de440_solar import MODEL_ID as DE440_MODEL_ID

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
    if solar_model_policy() == "vsop2013":
        return VSOP2013_SOFTWARE_YEARS
    if not VALIDATED_SOFTWARE_YEARS[0] <= year <= VALIDATED_SOFTWARE_YEARS[
        1
    ] and de440_selected(year):
        return DE440_SOFTWARE_YEARS
    return VALIDATED_SOFTWARE_YEARS


def solar_model_cache_key(*, year: int | None = None) -> Tuple[Any, ...]:
    # The hash identifies loaded coefficients, as the clock cache identifies
    # its loaded tables. It is not an atomic filesystem-read certificate.
    mode = solar_model_policy()
    if mode in {"native", "swiss"}:
        if (
            mode == "swiss"
            and year is not None
            and not VALIDATED_SOFTWARE_YEARS[0] <= year <= VALIDATED_SOFTWARE_YEARS[1]
        ):
            raise ValueError("Explicit Swiss solar mode currently covers1800..2200")
        if mode == "swiss":
            return mode, "native_swiss_runtime"
        from .moshier_solar import MODEL_ID as COMPLETE_MOSHIER_MODEL
        from .moshier_solar import model_details as complete_moshier_details

        details = complete_moshier_details()
        return (
            mode,
            "native_swiss_runtime",
            COMPLETE_MOSHIER_MODEL,
            details["coefficient_sha256"],
            details["frame_coefficient_sha256"],
        )
    if mode == "auto":
        from .jpl_ephemeris import configured_jpl_file

        if configured_jpl_file() is not None:
            return mode, "native_strict_jpl"
    if year is not None and mode in {"auto", "de440"} and not de440_selected(year):
        # Only the requested model's source is a dependency of this year.
        # Explicit de440 has already rejected an out-of-range year above.
        from .moshier_solar import MODEL_ID as COMPLETE_MOSHIER_MODEL
        from .moshier_solar import model_details as complete_moshier_details

        details = complete_moshier_details()
        return (
            mode,
            "native_outside_packaged_years",
            COMPLETE_MOSHIER_MODEL,
            details["coefficient_sha256"],
            details["frame_coefficient_sha256"],
        )
    if mode == "vsop2013":
        if (
            year is not None
            and not VSOP2013_SOFTWARE_YEARS[0] <= year <= VSOP2013_SOFTWARE_YEARS[1]
        ):
            raise ValueError("Explicit VSOP2013 solar mode currently covers1700..2300")
        from .vsop2013_solar import MODEL_ID as VSOP2013_MODEL_ID
        from .vsop2013_solar import cache_key as vsop2013_cache_key

        return mode, VSOP2013_MODEL_ID, vsop2013_cache_key()
    if mode == "aa1996":
        if (
            year is not None
            and not VALIDATED_SOFTWARE_YEARS[0] <= year <= VALIDATED_SOFTWARE_YEARS[1]
        ):
            raise ValueError("Explicit AA1996 solar mode currently covers1800..2200")
        from .aa1996_solar import MODEL_ID as AA1996_MODEL_ID
        from .aa1996_solar import cache_key as aa1996_cache_key

        return mode, AA1996_MODEL_ID, aa1996_cache_key()
    if mode == "spk":
        from .spk_solar import MODEL_ID as SPK_MODEL_ID
        from .spk_solar import cache_key

        return mode, SPK_MODEL_ID, cache_key()
    if mode in {"auto", "de440"}:
        from .de440_solar import cache_key as de440_cache_key

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
    return mode, MODEL_ID, str(profile()["loaded_sha256"])


def solar_model_environment_receipt(
    *, resolve_source: bool = True, observed_de440_models: list[str] | None = None
) -> Dict[str, Any]:
    # A successful text-only lookup must not start an unused file-backed Sun
    # calculation merely to describe its configuration. Consuming calculations
    # have already validated the mode and still request the strict source.
    if not resolve_source:
        configured = os.environ.get(ENVIRONMENT_NAME, "auto").strip().lower()
        if (
            configured in {"auto", "de440", "spk", "aa1996", "vsop2013"}
            or configured not in MODES
        ):
            return {
                "mode": configured if configured in MODES else "invalid",
                "source_resolution": "not_observed_in_business_output",
                "scope": "Configuration only; no independent solar source was resolved for this receipt. Actual consumed models are reported separately in provenance.",
            }
    if observed_de440_models is not None:
        from .de440_solar import EXTENDED_MODEL_ID
        from .de440_solar import MODEL_ID as DE440_MODEL_ID
        from .de440_solar import source_receipt as de440_source_receipt

        mode = solar_model_policy()
        models = sorted(set(observed_de440_models))
        if (
            mode not in {"auto", "de440"}
            or not models
            or any(m not in {DE440_MODEL_ID, EXTENDED_MODEL_ID} for m in models)
        ):
            raise ValueError(
                "Observed year-grid models must be named packaged DE440 profiles"
            )
        receipts = [de440_source_receipt(m) for m in models]
        common = dict(
            mode=mode,
            auto_software_years=list(DE440_SOFTWARE_YEARS),
            strict_native_jpl_overrides_auto=True,
            scope="Observed packaged year-grid sources only; derived projection profiles retain their own per-boundary identities. Range declarations do not certify civil UTC or physical accuracy.",
        )
        if len(receipts) == 1:
            return {**common, **receipts[0]}
        return {
            **common,
            "source_resolution": "observed_multiple_packaged_profiles",
            "observed_model_ids": models,
            "sources": receipts,
        }
    key = solar_model_cache_key()
    if key[0] == "swiss":
        return {
            "mode": "swiss",
            "source_selection": "required_swiss_files",
            "source_resolution": "configuration_only",
            "software_input_years": list(VALIDATED_SOFTWARE_YEARS),
            "analytical_fallback_allowed": False,
            "scope": "Actual crossings must use SWIEPH and retain observed planet/Moon file contexts. This selection does not certify physical accuracy or atomic file reads.",
        }
    if key[0] == "native":
        return {
            "mode": "native",
            "source_selection": "native_swiss_or_complete_moshier",
            "source_resolution": "configuration_only",
            "analytic_source_resolved": False,
            "scope": "Configured native selection only. Available Swiss/JPL data keep their native model; analytical fallback uses the named complete Moshier revision with its own orbit/frame receipt and no borrowed Sun flags. This configuration receipt does not prove which source a business calculation consumed or certify accuracy.",
        }
    if key[1] == "native_strict_jpl":
        return {
            "mode": "auto",
            "source_selection": "strict_native_jpl",
            "packaged_source_resolved": False,
            "scope": "Strict native JPL overrides the packaged default. Actual availability and consumption are validated by the native calculation and reported in its boundaries.",
        }
    if key[1] == "fatebridge_de440_solar_v1":
        from .de440_solar import source_receipt as de440_source_receipt

        return {
            "mode": key[0],
            **de440_source_receipt(),
            "auto_software_years": list(DE440_SOFTWARE_YEARS),
            "strict_native_jpl_overrides_auto": True,
            "scope": "Packaged default candidate; actual model use is reported by each consumed boundary. Strict native JPL overrides auto and years outside the declared software range use native policy.",
        }
    if key[0] == "spk":
        from .spk_solar import source_receipt

        return {
            "mode": "spk",
            **source_receipt(),
            "scope": "Explicit solar SPK policy; actual consumed boundaries report their own source identity",
        }
    if key[0] == "vsop2013":
        from .vsop2013_solar import source_receipt as vsop2013_source_receipt

        return {
            "mode": "vsop2013",
            **vsop2013_source_receipt(),
            "scope": "Explicit named VSOP2013/full-Moshier-Moon solar library; actual consumed boundaries retain binary/profile identity. TT qualification is not civil UTC or whole-domain certification.",
        }
    if key[0] == "aa1996":
        from .aa1996_solar import source_receipt as aa1996_source_receipt

        return {
            "mode": "aa1996",
            **aa1996_source_receipt(),
            "scope": "Explicit AA1996/full-Moshier-Moon native solar library; actual consumed boundaries retain loaded binary/profile identity",
        }
    return {
        "mode": key[0],
        "model_id": key[1],
        "loaded_coefficient_sha256": key[2],
        "auto_software_years": list(DE440_SOFTWARE_YEARS),
        "scope": "Configured policy; actual model use is reported by each result, not inferred from this configuration",
    }
