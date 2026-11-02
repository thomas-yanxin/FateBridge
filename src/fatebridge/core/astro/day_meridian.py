"""The explicit ecliptic day-meridian equation in Witte's April 1924 article.

This is not a transcription of his 1923 house-table procedure or the complete
Hamburg progression system. Their printed difference follows the earlier cusp
construction in the worked example; it is not a universal correction.
Only coordinates are calculated; the articles' event claims are not adopted.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from fractions import Fraction
from typing import Any, Dict, Mapping, Sequence

from fatebridge.core.astro import runtime
from fatebridge.core.astro.day_meridian_inputs import (
    day_meridian_input_coherence,
    finite_number,
)
from fatebridge.core.astro.reference_angles import (
    UNRESOLVED_REFERENCE_BASES,
    reference_angle_basis,
)
from fatebridge.core.astro.solar_ephemeris import SolarEphemerisBatch
from fatebridge.core.astro.time_scales import ephemeris_time

RULESET = "witte1924_ecliptic_day_meridian_v1"
MERIDIAN_KEYS = (
    "natal_upper_meridian_longitude",
    "natal_lower_meridian_longitude",
    "solar_arc_midheaven_longitude",
    "upper_meridian_longitude",
    "lower_meridian_longitude",
)
SOURCE = {
    "id": "witte_1924_differentiation",
    "author": "Alfred Witte",
    "title": "Die Differenzierung der Radixsonne und die des unteren Geburtsmeridians, Astrologische Rundschau XVI/1, April 1924, pp.13-16",
    "url": "https://www.astrax.de/pdf/34_35_Die%20Differenzierung%20der%20Radixsonne%20und%20die%20des%20unteren%20Geburtsme.pdf",
    "source_sha256": "f1047ce86aca9eac341693b91bb957c3cffacd1897369ca0bf2dc2020190bde4",
    "sections": ["p.15: explicit lower-meridian equation and printed arithmetic"],
    "scope": "Selected ecliptic equation only; no gravitational theory, event interpretation, infallibility claim or full-book acceptance",
}
SOURCE_1923 = {
    "id": "witte_1923_progressive_meridian",
    "author": "Alfred Witte",
    "title": "Der progressive Meridian waehrend eines Jahres, Astrologische Rundschau XV/2, 1923, pp.34-37",
    "url": "https://www.astrax.de/pdf/26_Der%20progressive%20Meridian%20waehrend%20eines%20Jahres.pdf",
    "source_sha256": "28b14ce9a3dbe9f35293bf9d055e5a83ab02efc3095c9655abdd4225fcf530e6",
    "sections": ["pp.35-36: printed solar phases, natal house cusps and arithmetic"],
    "scope": "Historical construction comparison only; the 1923 date-to-coordinate method is not applied to this chart",
}


def source_method_comparison() -> Dict[str, Any]:
    """Distinguish two printed constructions without changing current coordinates."""
    return {
        "status": "printed_arithmetic_difference_explained",
        "selected_construction": "witte1924_ecliptic_sum",
        "compared_construction": "witte1923_printed_phase_and_natal_cusp",
        "compared_source_id": SOURCE_1923["id"],
        "computed_for_current_chart": False,
        "scope": "Historical printed example only; these comparison coordinates are not calculated for the current chart",
        "explanation": "In the printed example, 1923 adds Sun Aries 20deg50 minus phase Aries 4deg35 to natal VIII Scorpio 10deg19, yielding IC Scorpio 26deg34. The 1924 sum yields IC Scorpio 23deg30; its equivalent VIII reference is natal IC Cancer 7deg15 plus 120deg, Scorpio 7deg15. The 184 arcminute difference is exactly the printed cusp offset.",
        "historical_example_difference_arcminutes": 184,
        "separate_printed_sensitive_point_residual_arcminutes": 4,
        "difference_is_universal_correction": False,
        "original_variants_fully_reconciled": False,
        "original_progression_time_key_accepted": False,
    }


def _display(angle: Fraction) -> float:
    return min(float(angle % 360), math.nextafter(360.0, 0.0))


def _signed(first: float, second: float) -> Fraction:
    return (Fraction(first) - Fraction(second) + 180) % 360 - 180


def day_meridian_coordinates(
    natal_upper_meridian: float,
    natal_tropical_sun: float,
    solar_arc: float,
    target_tropical_sun: float,
) -> Dict[str, float]:
    """IC(day) = IC(natal) + solar arc - Sun(natal) + Sun(target).

    The meridians use the natal display frame. Both Suns must be tropical;
    their difference also applies when that natal display is sidereal.
    Fractions preserve the boundary side of the supplied finite doubles.
    """
    inputs = (
        natal_upper_meridian,
        natal_tropical_sun,
        solar_arc,
        target_tropical_sun,
    )
    mc, sun, arc, target = map(finite_number, inputs)
    ic = (mc + 180) % 360
    lower = (ic + arc - sun + target) % 360
    return {
        "natal_upper_meridian_longitude": _display(mc),
        "natal_lower_meridian_longitude": _display(ic),
        "natal_tropical_sun": _display(sun),
        "target_tropical_sun": _display(target),
        "solar_arc_degrees": _display(arc),
        "solar_arc_midheaven_longitude": _display(mc + arc),
        "transit_sun_displacement_degrees": _display(target - sun),
        "upper_meridian_longitude": _display(lower + 180),
        "lower_meridian_longitude": _display(lower),
    }


def target_sun_state(
    moment: datetime, *, _batch: SolarEphemerisBatch | None = None
) -> Dict[str, Any]:
    """Actual target Sun; an equal TT epoch reuses the batch observation."""
    if _batch is None:
        with SolarEphemerisBatch() as batch:
            result = target_sun_state(moment, _batch=batch)
        result["sun_ephemeris_source"] = batch.result
        return result
    if moment.utcoffset() is None:
        raise ValueError("Target Sun requires a timezone-aware instant")
    moment = moment.astimezone(timezone.utc)
    scales = ephemeris_time(moment)
    swe = runtime.swe
    if swe is None or scales.jd_tt is None:
        raise ValueError("Swiss Ephemeris is required for the target Sun")
    observation = _batch.sun(scales.jd_tt)
    return {
        "analysis_utc": moment.isoformat(),
        "target_julian_day_tt": scales.jd_tt,
        "target_time_scale_method": scales.method,
        "future_leap_seconds_assumed_unchanged": scales.future_leap_seconds_assumed_unchanged,
        "target_sun_ephemeris_model": observation["model"],
        "target_tropical_sun": observation["longitude"],
        "target_sun_observation_index": observation["index"],
    }


def sampled_day_meridian_spans(
    coordinates: Mapping[str, float], samples: Sequence[Mapping[str, Any]]
) -> Dict[str, Any]:
    """Pure finite arithmetic; do not bridge unavailable/filtered sample gaps."""
    computed = [s for s in samples if s.get("status", "computed") == "computed"]
    spans = {}
    for key in ("upper_meridian_longitude", "lower_meridian_longitude"):
        offsets = [_signed(s[key], coordinates[key]) for s in computed]
        jumps = [
            abs(_signed(b[key], a[key]))
            for a, b in zip(samples, samples[1:])
            if a.get("status", "computed") == b.get("status", "computed") == "computed"
        ]
        if offsets:
            spans[key] = {
                "minimum_offset_from_nominal_degrees": float(min(offsets)),
                "maximum_offset_from_nominal_degrees": float(max(offsets)),
                "maximum_adjacent_sample_jump_degrees": float(max(jumps, default=0)),
            }
    return spans


def _qualified_coordinates(
    coordinates: Mapping[str, Any], definition: Mapping[str, Any] | None
) -> Dict[str, Any]:
    result = dict(coordinates)
    basis = reference_angle_basis(definition, "Midheaven")
    if basis is not None:
        resolved = basis not in UNRESOLVED_REFERENCE_BASES
        result.update(
            reference_angle_basis={"Midheaven": basis},
            physical_reference_geometry_resolved=resolved,
        )
        if not resolved:
            result["backend_convention"] = {key: result[key] for key in MERIDIAN_KEYS}
            for key in MERIDIAN_KEYS:
                result[key] = None
    return result


def build_day_meridian(
    *,
    natal_upper_meridian: float,
    solar_profile: Mapping[str, Any],
    target: Mapping[str, Any],
    uncertainty: Mapping[str, Any],
    samples: Sequence[Mapping[str, Any]],
    native_profile: Mapping[str, Any],
    native_factors: Sequence[Mapping[str, Any]],
    nominal_effective_utc: str,
    supported_key_years: tuple[float, float],
) -> Dict[str, Any]:
    coherence = day_meridian_input_coherence(
        natal_upper_meridian=natal_upper_meridian,
        solar_profile=solar_profile,
        target=target,
        uncertainty=uncertainty,
        samples=samples,
        native_profile=native_profile,
        native_factors=native_factors,
        nominal_effective_utc=nominal_effective_utc,
        supported_key_years=supported_key_years,
        calculate=day_meridian_coordinates,
    )
    coordinates = day_meridian_coordinates(
        natal_upper_meridian,
        solar_profile["natal_tropical_sun"],
        solar_profile["solar_arc_degrees"],
        target["target_tropical_sun"],
    )
    nominal_definition = native_profile.get("angle_definition")
    qualified = _qualified_coordinates(coordinates, nominal_definition)
    nominal_resolved = qualified.get("physical_reference_geometry_resolved", True)
    sensitivity: Dict[str, Any] = {
        "status": uncertainty["status"],
        "uncertainty_minutes": uncertainty["uncertainty_minutes"],
        "continuous_interval_proven": False,
        "sample_frequency_is_probability": False,
        "scope": "Upper/lower symbolic day-meridian coordinates only, not contact-set or interpretation stability",
        **{
            key: uncertainty[key]
            for key in (
                "recorded_interval_start_utc",
                "recorded_interval_end_utc",
                "maximum_recorded_sample_gap_seconds",
                "represented_radius_seconds",
                "clock_policy",
                "input_clock_basis",
                "recorded_interval_start_clock",
                "recorded_interval_end_clock",
                "requested_clock_radius_seconds",
            )
            if key in uncertainty
        },
    }
    if uncertainty["status"] == "sampled":
        computed = [s for s in samples if s.get("status", "computed") == "computed"]
        unavailable = len(samples) - len(computed)
        spans = sampled_day_meridian_spans(coordinates, samples)
        delivered = []
        unknown = []
        resolved_samples = []
        for i, sample in enumerate(samples):
            if sample.get("status", "computed") != "computed":
                delivered.append(dict(sample))
                resolved_samples.append(sample)
                continue
            row = _qualified_coordinates(sample, sample.get("angle_definition"))
            delivered.append(row)
            if not row.get("physical_reference_geometry_resolved", True):
                unknown.append(i)
                resolved_samples.append({"status": "unavailable"})
            else:
                resolved_samples.append(sample)
        if unknown:
            actual = (
                sampled_day_meridian_spans(coordinates, resolved_samples)
                if nominal_resolved
                else {}
            )
            spans = {
                key: {
                    **actual.get(
                        key,
                        {
                            "minimum_offset_from_nominal_degrees": None,
                            "maximum_offset_from_nominal_degrees": None,
                            "maximum_adjacent_sample_jump_degrees": None,
                        },
                    ),
                    "status": (
                        "partial_reference_geometry"
                        if nominal_resolved
                        else "underdetermined_midheaven"
                    ),
                    "backend_convention_span": value,
                    "unresolved_sample_count": len(unknown),
                }
                for key, value in spans.items()
            }
        sensitivity.update(
            **(
                {
                    "status": "partial",
                    "computed_sample_count": len(computed),
                    "unavailable_sample_count": unavailable,
                    "factor_spans_scope": "computed_samples_only; unavailable gaps are not bridged",
                    "sample_scope_policy": "Preserve the full birth-time interval and explicit unavailable solar-arc samples",
                }
                if unavailable
                else {}
            ),
            sample_count=len(samples),
            factor_spans=spans,
            samples=delivered,
        )
        if unknown:
            sensitivity.update(
                status="partial",
                resolved_reference_sample_count=len(computed) - len(unknown),
                unresolved_reference_sample_count=len(unknown),
                unresolved_reference_sample_indices=unknown,
                factor_spans_scope="Resolved reference samples only; unavailable and unresolved sample gaps are not bridged; a nominal unknown prevents resolved offsets",
            )
    return {
        "status": "computed" if nominal_resolved else "partial",
        "ruleset_id": RULESET,
        "author": "FateBridge",
        "version": "3",
        "input_coherence": coherence,
        "profile": {
            **qualified,
            **target,
            **({"angle_definition": nominal_definition} if nominal_definition else {}),
            "source_formula": "IC.day = IC.natal + solar_arc - Sun.natal.tropical + Sun.target.tropical; MC.day = IC.day + 180; modulo360",
            "year_key_policy": solar_profile["key_policy"],
            "display_frame": "Natal chart frame held fixed; both Sun inputs tropical",
            "meridians_are_observations": False,
        },
        "birth_time_sensitivity": sensitivity,
        "sources": [SOURCE, SOURCE_1923],
        "source_comparison": source_method_comparison(),
        "rule_trace": [
            {
                "rule_id": RULESET,
                "source_id": SOURCE["id"],
                "source_sections": ["p.15"],
                "formula": "IC.day = IC.natal + solar_arc - Sun.natal + Sun.target (ecliptic longitudes)",
                "scope": "Explicit 1924 ecliptic equation; the 1923 phase/cusp construction is not applied",
            }
        ],
        "limitations": [
            "Symbolic day meridians are neither the physical target MC/IC nor the plain solar-arc MC/IC",
            "The 365.25-day symbolic key is the implementation's declared solar-arc convention, not a reproduction of all original progression-time tables",
            "The printed 1923/1924 difference of 3deg04min is explained by their distinct phase/cusp and equal-ecliptic constructions in this example; it is not a universal correction or full-method reconciliation",
            "A separate 1923 printed calculation gives Virgo16deg49 while the compared sensitive point is Virgo16deg45; that 4 arcminute residual is retained",
            "Only this formula is applied; no original event interpretation or empirically validated forecast is inferred",
            "Birth-time spans cover samples only; geographic, timezone-rule and ephemeris uncertainty are not propagated",
        ],
        "original_text_conformance": "not_assessed",
        "real_world_efficacy": "not_tested",
    }
