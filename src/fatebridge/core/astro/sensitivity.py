"""Recalculate specialty charts over an explicitly supplied birth-time interval.

This is a finite UTC grid, not an interval proof or a probability distribution.
The recorded clock is varied before the existing optional solar-clock mapping.
Every sample preserves its recorded and effective UTC instants for replay.
"""

from __future__ import annotations

import math
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from typing import Any, Dict, List, Optional

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
from fatebridge.core.astro.solar_rebase import (
    rebase_solar_datetime,
    solar_rebase_adjustment,
)
from fatebridge.core.astro.source_pattern import (
    source_pattern_sample,
    source_pattern_summary,
)
from fatebridge.utils.errors import EphemerisSourceError

RULESET = "fatebridge.specialty_birth_time_sensitivity.v1"


def _offsets(radius: float) -> List[timedelta]:
    if not math.isfinite(radius) or not 0 <= radius <= 120:
        raise ValueError("birth_time_uncertainty_minutes must be finite and in [0,120]")
    delta = timedelta(minutes=radius)
    microseconds = (delta.days * 86400 + delta.seconds) * 1000000 + delta.microseconds
    # Include both endpoints and the nominal instant, also for fractional radii.
    ticks = set(range(-microseconds, microseconds + 1, 30000000))
    ticks.update((-microseconds, 0, microseconds))
    return [timedelta(microseconds=tick) for tick in sorted(ticks)]


def _sample_birth(birth: AstroBirthInfo, offset: timedelta) -> AstroBirthInfo:
    recorded = birth.recorded_datetime or birth.local_datetime
    instant = recorded.astimezone(timezone.utc) + offset
    local = instant.astimezone(recorded.tzinfo)
    effective = local
    correction = 0.0
    solar = None
    solar_time_reference = None
    if birth.applied_true_solar:
        # An aware instant disambiguates folds; do not relocalize a wall clock.
        adjustment, solar_time_reference = solar_rebase_adjustment(
            local, birth.timezone, birth.longitude
        )
        correction = adjustment["total_correction_minutes"]
        solar = rebase_solar_datetime(local, correction)
        effective = solar
    return replace(
        birth,
        recorded_datetime=local,
        local_datetime=effective,
        utc_datetime=effective.astimezone(timezone.utc),
        solar_datetime=solar,
        solar_correction_minutes=correction,
        solar_time_reference=solar_time_reference,
    )


def _clock_offsets(
    birth: AstroBirthInfo, offsets: List[timedelta]
) -> tuple[List[timedelta], Dict[str, Any]]:
    if birth.clock_conversion is None:
        return offsets, {}
    from fatebridge.core.astro.birth_clock import resolve_solar_birth_clock

    conversion = birth.clock_conversion
    wall = datetime.fromisoformat(conversion["input_wall_datetime"])
    radius = offsets[-1]
    start_wall, end_wall = wall - radius, wall + radius
    start, _ = resolve_solar_birth_clock(
        start_wall, birth.longitude, conversion["input_clock_basis"]
    )
    end, _ = resolve_solar_birth_clock(
        end_wall, birth.longitude, conversion["input_clock_basis"]
    )
    nominal = birth.require_utc_datetime.astimezone(timezone.utc)
    lower = start - nominal
    upper = end - nominal
    if lower > timedelta() or upper < timedelta():
        raise ValueError(
            "Solar clock interval must contain its nominal physical instant"
        )

    def microseconds(delta: timedelta) -> int:
        return (delta.days * 86400 + delta.seconds) * 1_000_000 + delta.microseconds

    low, high = microseconds(lower), microseconds(upper)
    ticks = set(range(low, high + 1, 30_000_000))
    ticks.update((low, 0, high))
    return [timedelta(microseconds=tick) for tick in sorted(ticks)], {
        "input_clock_basis": conversion["input_clock_basis"],
        "recorded_interval_start_clock": start_wall.isoformat(),
        "recorded_interval_end_clock": end_wall.isoformat(),
        "requested_clock_radius_seconds": radius.total_seconds(),
    }


def _delta(first: float, second: float) -> float:
    return float((Fraction(first) - Fraction(second) + 180) % 360 - 180)


def time_sensitivity(
    birth: AstroBirthInfo,
    *,
    sidereal: bool,
    uncertainty_minutes: Optional[float],
    include_hypothetical: bool = True,
) -> Dict[str, Any]:
    """Factual factor samples; never infer a birth time from observed outcomes."""
    common = {
        "ruleset_id": RULESET,
        "author": "FateBridge",
        "uncertainty_minutes": uncertainty_minutes,
        "scope": "sampled factors and the declared source pattern / equal13 decisions only; not all midpoint contact sets",
        "continuous_interval_proven": False,
        "sample_frequency_is_probability": False,
    }
    if uncertainty_minutes is None:
        return {
            **common,
            "status": "not_assessed",
            "reason": "No user-confirmed interval; missing uncertainty is not zero",
        }
    offsets = _offsets(uncertainty_minutes)
    if runtime.swe is None:
        return {
            **common,
            "status": "unavailable",
            "reason": "Swiss Ephemeris is required for sensitivity recalculation",
        }
    offsets, clock_interval = _clock_offsets(birth, offsets)
    samples: List[Dict[str, Any]] = []
    models = set()
    element_source = None
    physical_cohort = PhysicalSourceCohort()
    try:
        for offset in offsets:
            sample = _sample_birth(birth, offset)
            native = _native_factors(
                sample,
                sidereal,
                include_hypothetical=include_hypothetical,
                include_meridian_houses=include_hypothetical,
            )
            if element_source is None:
                element_source = native["hypothetical_element_source"]
            elif native["hypothetical_element_source"] != element_source:
                raise EphemerisSourceError("fictitious_changed_across")
            models.update(native["ephemeris_models"])
            physical_source_index = physical_cohort.add(
                native["physical_ephemeris_source"]
            )
            samples.append(
                {
                    "offset_seconds": offset.total_seconds(),
                    "physical_source_index": physical_source_index,
                    **(
                        {"reference_angle_model": native["reference_angle_model"]}
                        if "reference_angle_model" in native
                        else {}
                    ),
                    "recorded_utc": sample.recorded_datetime.astimezone(  # type: ignore[union-attr]
                        timezone.utc
                    ).isoformat(),
                    "effective_utc": sample.require_utc_datetime.isoformat(),
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
                    **(
                        {
                            "meridian_house_cusps": [
                                row["longitude"]
                                for row in native["meridian_houses"]["cusps"]
                            ],
                            "meridian_armc": native["meridian_houses"]["profile"][
                                "armc"
                            ],
                            "meridian_obliquity": native["meridian_houses"]["profile"][
                                "true_obliquity"
                            ],
                            "meridian_angle_julian_day_tt": native["meridian_houses"][
                                "profile"
                            ]["native_angle_julian_day_tt"],
                            "meridian_ayanamsha": native["meridian_houses"]["profile"][
                                "ayanamsha_apparent"
                            ],
                            "meridian_factor_positions": native["meridian_houses"][
                                "factor_placement"
                            ]["factors"],
                        }
                        if include_hypothetical
                        else {}
                    ),
                }
            )
    except EphemerisSourceError:
        raise
    except (OverflowError, ValueError) as error:
        raise ValueError(
            f"Cannot recalculate the declared birth-time interval: {error}"
        ) from error
    nominal = next(s for s in samples if s["offset_seconds"] == 0)["factor_longitudes"]
    spans: Dict[str, Dict[str, Any]] = {}
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
    return {
        **common,
        **clock_interval,
        "status": "sampled",
        "sample_count": len(samples),
        "maximum_recorded_sample_gap_seconds": max(
            (
                b["offset_seconds"] - a["offset_seconds"]
                for a, b in zip(samples, samples[1:])
            ),
            default=0.0,
        ),
        "represented_radius_seconds": max(
            abs(offset.total_seconds()) for offset in offsets
        ),
        "datetime_resolution": "microsecond; represented radius is reported separately",
        "recorded_interval_start_utc": samples[0]["recorded_utc"],
        "recorded_interval_end_utc": samples[-1]["recorded_utc"],
        "clock_policy": (
            "Declared local solar clock interval endpoints converted separately to the shared physical UTC axis; samples cover that mapped interval with UTC gaps <=30 seconds"
            if clock_interval
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
    payload: Dict[str, Any],
    birth: AstroBirthInfo,
    *,
    kind: str,
    uncertainty_minutes: Optional[float],
) -> None:
    """Annotate nominal interpretation/partition facts with actual recalculations."""
    base = payload["base_chart"] if kind == "germany" else payload
    sensitivity = time_sensitivity(
        birth,
        sidereal=base["chart_profile"]["zodiac"] == "sidereal",
        uncertainty_minutes=uncertainty_minutes,
        include_hypothetical=kind == "germany",
    )
    if kind == "germany":
        layer = payload["midpoint_analysis"]
        layer["time_sensitivity"] = sensitivity
        if "meridian_houses" in layer:
            attach_meridian_sensitivity(layer["meridian_houses"], sensitivity)
        if sensitivity["status"] != "sampled":
            layer["comparative_geometry"] = build_comparative_geometry(
                layer, sensitivity
            )
            return
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
            return
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
