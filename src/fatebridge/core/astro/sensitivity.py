"""Recalculate specialty charts over an explicitly supplied birth-time interval.

Recorded physical samples feed the optional solar clock mapping. Each sample
preserves its recorded and effective epochs for replay.
"""

from __future__ import annotations

from datetime import timedelta
from fractions import Fraction
from typing import Any

from fatebridge.core.astro import runtime
from fatebridge.core.astro.birth import AstroBirthInfo
from fatebridge.core.astro.comparative import build_comparative_geometry
from fatebridge.core.astro.geometry import _sector13_for_longitude
from fatebridge.core.astro.meridian_houses import attach_meridian_sensitivity
from fatebridge.core.astro.midpoints import _native_factors
from fatebridge.core.astro.physical_sources import PhysicalSourceCohort
from fatebridge.core.astro.reference_angles import (
    UNRESOLVED_REFERENCE_BASES,
    reference_angle_basis,
)
from fatebridge.core.astro.sensitivity_grid import sampling_radius
from fatebridge.core.astro.sensitivity_timing import (
    SpecialtySampleTimes,
    sample_time_receipt,
    specialty_sample_times,
)
from fatebridge.core.astro.source_pattern import (
    source_pattern_sample,
    source_pattern_summary,
)
from fatebridge.utils.errors import EphemerisSourceError

RULESET = "fatebridge.specialty_birth_time_sensitivity.v1"


def _delta(first: float, second: float) -> float:
    return float((Fraction(first) - Fraction(second) + 180) % 360 - 180)


def time_sensitivity(
    birth: AstroBirthInfo,
    *,
    sidereal: bool,
    uncertainty_minutes: float | None,
    include_hypothetical: bool = True,
    _times: SpecialtySampleTimes | None = None,
) -> dict[str, Any]:
    """Factual factor samples; never infer a birth time from observed outcomes."""
    common = {
        "ruleset_id": RULESET,
        "author": "FateBridge",
        "uncertainty_minutes": uncertainty_minutes,
        "scope": "sampled factors and the declared source pattern / equal13 decisions only; not all midpoint contact sets",
        "continuous_interval_proven": False,
    }
    if uncertainty_minutes is None:
        return {
            **common,
            "status": "not_assessed",
            "reason": "No user-confirmed interval; missing uncertainty is not zero",
        }
    sampling_radius(uncertainty_minutes)
    if runtime.swe is None:
        return {
            **common,
            "status": "unavailable",
            "reason": "Swiss Ephemeris is required for sensitivity recalculation",
        }
    times = (
        _times
        if _times is not None
        else specialty_sample_times(birth, uncertainty_minutes)
    )
    physical_grid = times.physical_grid
    offsets = times.label_offsets
    samples: list[dict[str, Any]] = []
    models = set()
    element_source = None
    physical_cohort = PhysicalSourceCohort()
    try:
        for offset, sample in zip(offsets, times.samples):
            native = _native_factors(
                birth,
                sidereal,
                include_hypothetical=include_hypothetical,
                include_meridian_houses=include_hypothetical,
                epoch=sample.effective,
            )
            if element_source is None:
                element_source = native["hypothetical_element_source"]
            elif native["hypothetical_element_source"] != element_source:
                raise EphemerisSourceError("fictitious_changed_across")
            models.update(native["ephemeris_models"])
            physical_source_index = physical_cohort.add(
                native["physical_ephemeris_source"]
            )
            meridian_fields = {}
            if include_hypothetical:
                meridian = native["meridian_houses"]
                profile = meridian["profile"]
                meridian_fields = {
                    "meridian_house_cusps": [
                        row["longitude"] for row in meridian["cusps"]
                    ],
                    "meridian_armc": profile["armc"],
                    "meridian_obliquity": profile["true_obliquity"],
                    "meridian_source_ecliptic_longitude_origin": profile[
                        "source_ecliptic_longitude_origin"
                    ],
                    "meridian_angle_julian_day_tt": profile[
                        "native_angle_julian_day_tt"
                    ],
                    "meridian_ayanamsha": profile["ayanamsha_apparent"],
                    "meridian_factor_positions": meridian["factor_placement"][
                        "factors"
                    ],
                }
            samples.append(
                {
                    "offset_seconds": (
                        offset.total_seconds() if offset is not None else None
                    ),
                    **(
                        {"physical_timing": sample_time_receipt(sample)}
                        if physical_grid
                        else {}
                    ),
                    "physical_source_index": physical_source_index,
                    **(
                        {"reference_angle_model": native["reference_angle_model"]}
                        if "reference_angle_model" in native
                        else {}
                    ),
                    "recorded_utc": sample.recorded.epoch.utc_label,
                    "effective_utc": sample.effective.utc_label,
                    "julian_day_tt": native["julian_day_tt"],
                    "julian_day_ut1": native["julian_day_ut1"],
                    "time_scale_method": native["time_scale_method"],
                    "future_leap_seconds_assumed_unchanged": native[
                        "future_leap_seconds_assumed_unchanged"
                    ],
                    **(
                        {"angle_definition": native["angle_definition"]}
                        if "angle_definition" in native
                        else {}
                    ),
                    "factor_longitudes": {
                        factor["id"]: factor["longitude"]
                        for factor in native["factors"]
                    },
                    **meridian_fields,
                }
            )
    except EphemerisSourceError:
        raise
    except (OverflowError, ValueError) as error:
        raise ValueError(
            f"Cannot recalculate the declared birth-time interval: {error}"
        ) from error
    nominal = samples[times.nominal_index]["factor_longitudes"]
    spans: dict[str, dict[str, Any]] = {}
    for name, angle in nominal.items():
        values = [s["factor_longitudes"][name] for s in samples]
        residuals = [_delta(v, angle) for v in values]
        spans[name] = {
            "minimum_offset_from_nominal_degrees": min(residuals),
            "maximum_offset_from_nominal_degrees": max(residuals),
            "maximum_adjacent_sample_jump_degrees": max(
                (abs(_delta(a, b)) for a, b in zip(values, values[1:])), default=0.0
            ),
        }
    for factor in ("Ascendant", "Midheaven"):
        unresolved = sum(
            reference_angle_basis(s.get("angle_definition"), factor)
            in UNRESOLVED_REFERENCE_BASES
            for s in samples
        )
        if unresolved:
            convention = spans[factor]
            spans[factor] = {
                "status": f"underdetermined_{factor.lower()}",
                "minimum_offset_from_nominal_degrees": None,
                "maximum_offset_from_nominal_degrees": None,
                "maximum_adjacent_sample_jump_degrees": None,
                "backend_convention_span": convention,
                "unresolved_sample_count": unresolved,
            }
    label_offsets = [offset for offset in offsets if offset is not None]
    complete_label_grid = len(label_offsets) == len(offsets)
    return {
        **common,
        **times.clock_interval,
        **({"recorded_physical_grid": physical_grid} if physical_grid else {}),
        "status": "sampled",
        "sample_count": len(samples),
        "maximum_recorded_sample_gap_seconds": (
            max(
                (b - a for a, b in zip(label_offsets, label_offsets[1:])),
                default=timedelta(),
            ).total_seconds()
            if complete_label_grid
            else None
        ),
        "represented_radius_seconds": (
            max(abs(offset.total_seconds()) for offset in label_offsets)
            if complete_label_grid
            else None
        ),
        "datetime_resolution": "microsecond; represented radius is reported separately",
        "recorded_interval_start_utc": samples[0]["recorded_utc"],
        "recorded_interval_end_utc": samples[-1]["recorded_utc"],
        "clock_policy": (
            "Retain solved recorded TT/UT1; bound consecutive recorded physical gaps to 30 SI seconds; label quantities reported only where defined"
            if physical_grid
            else "UTC elapsed offsets of recorded instant; optional solar correction recalculated at every sample using the original model"
        ),
        "zodiac": "sidereal_lahiri" if sidereal else "tropical",
        "ephemeris_models": sorted(models),
        "ephemeris_model_scope": "physical_bodies",
        "physical_ephemeris_sources": physical_cohort.sources,
        "physical_ephemeris_models_consistent": True,
        "factor_scope": (
            "hamburg_native" if include_hypothetical else "physical_reference"
        ),
        "factor_count": len(nominal),
        "hypothetical_element_source": element_source,
        "factor_spans": spans,
        "samples": samples,
        "limitations": [
            "Samples do not prove behavior between grid points; narrow changes can be missed",
            "Coordinate, timezone-rule and ephemeris uncertainty are not propagated",
            "No rectification, confidence probability or real-world outcome inference",
        ],
    }


def enrich_specialty_sensitivity(
    payload: dict[str, Any],
    birth: AstroBirthInfo,
    *,
    kind: str,
    uncertainty_minutes: float | None,
) -> SpecialtySampleTimes | None:
    """Annotate native samples and return their typed clock axes for directions."""
    base = payload["base_chart"] if kind == "germany" else payload
    times = (
        specialty_sample_times(birth, uncertainty_minutes)
        if uncertainty_minutes is not None and runtime.swe is not None
        else None
    )
    sensitivity = time_sensitivity(
        birth,
        sidereal=base["chart_profile"]["zodiac"] == "sidereal",
        uncertainty_minutes=uncertainty_minutes,
        include_hypothetical=kind == "germany",
        _times=times,
    )
    if kind == "germany":
        layer = payload["midpoint_analysis"]
        layer["time_sensitivity"] = sensitivity
        if "meridian_houses" in layer:
            attach_meridian_sensitivity(layer["meridian_houses"], sensitivity)
        if sensitivity["status"] != "sampled":
            return None
        if (
            sensitivity["hypothetical_element_source"]
            != layer["profile"]["hypothetical_element_source"]
        ):
            raise EphemerisSourceError("fictitious_nominal_mismatch")
        nominal_cohort = PhysicalSourceCohort()
        nominal_cohort.add(layer["profile"]["physical_ephemeris_source"])
        for source in sensitivity["physical_ephemeris_sources"]:
            nominal_cohort.add(source)
        layer["comparative_geometry"] = build_comparative_geometry(layer, sensitivity)
        assessments = [
            source_pattern_sample(
                sample["factor_longitudes"], sample.get("angle_definition")
            )
            for sample in sensitivity["samples"]
        ]
        summary = source_pattern_summary(assessments)
        state = summary["sampled_status"]
        sensitivity["source_pattern"] = {
            "source_id": "udo_rudolph_1996_abc_excerpt",
            "basis_expression": "Mars+Jupiter-Zeus=Midheaven",
            "maximum_direct_orb_degrees": 2.0,
            **summary,
        }
        # Preserve the nominal reading; explicitly carry its conditional status.
        for reading in layer.get("interpretations", []):
            reading["birth_time_sampled_status"] = state
        for dial in layer.get("dials", {}).values():
            for row in dial["four_factor_contacts"]:
                if "source_interpretation" in row:
                    row["source_interpretation"]["birth_time_sampled_status"] = state
    else:
        payload["time_sensitivity"] = sensitivity
        if sensitivity["status"] != "sampled":
            return None
        # Native sample coherence alone does not cover the already computed
        # nominal equal13 positions. Different models are not pure clock effects.
        nominal_cohort = PhysicalSourceCohort()
        try:
            nominal_cohort.add(payload["chart_profile"]["physical_ephemeris_source"])
            for source in sensitivity["physical_ephemeris_sources"]:
                nominal_cohort.add(source)
        except EphemerisSourceError as error:
            raise EphemerisSourceError("nominal_source_mismatch") from error
        sectors = []
        for planet in payload["planets"]:
            name = planet["id"]
            observed = [
                (
                    _sector13_for_longitude(
                        s["factor_longitudes"][name],
                        s["factor_longitudes"]["Ascendant"],
                    )
                    if s.get("angle_definition", {}).get("geometric_ascendant_resolved")
                    is not False
                    else None
                )
                for s in sensitivity["samples"]
            ]
            computed = [value for value in observed if value is not None]
            unknown = len(observed) - len(computed)
            sectors.append(
                {
                    "id": name,
                    "nominal_sector": planet["sector13"],
                    "observed_sectors": sorted(set(computed)),
                    "sampled_status": (
                        "underdetermined"
                        if unknown
                        else (
                            "same_in_samples"
                            if len(set(computed)) == 1
                            else "varies_across_samples"
                        )
                    ),
                    **(
                        {
                            "computed_sample_count": len(computed),
                            "unresolved_sample_count": unknown,
                        }
                        if unknown
                        else {}
                    ),
                    "sector_by_sample": observed,
                }
            )
            planet["sector13_evidence"][
                "birth_time_uncertainty"
            ] = "sampled; see time_sensitivity; not a continuous interval proof"
        sensitivity["sector_assignments"] = sectors
    return times
