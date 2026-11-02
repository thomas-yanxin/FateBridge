"""The RA-divided natal meridian-house construction in Witte 1923 p.34.

Swiss X supplies the cusps. Its first cusp is an equatorial ascendant, not a
replacement for the separately calculated physical Ascendant. No progression
time key, original interpretive keyword or event forecast is inferred here.
"""

from __future__ import annotations

import math
from fractions import Fraction
from typing import Any, Dict, Mapping, Sequence

from fatebridge.core.astro import runtime
from fatebridge.core.astro.meridian_placement import placement_sample_summaries

RULESET = "witte1923_natal_meridian_house_geometry_v1"
SOURCE = {
    "id": "witte1923_meridian_house_geometry",
    "author": "Alfred Witte",
    "title": "Der progressive Meridian waehrend eines Jahres, Astrologische Rundschau XV/2, 1923, pp.34-37",
    "url": "https://www.astrax.de/pdf/26_Der%20progressive%20Meridian%20waehrend%20eines%20Jahres.pdf",
    "source_sha256": "28b14ce9a3dbe9f35293bf9d055e5a83ab02efc3095c9655abdd4225fcf530e6",
    "sections": ["p.34: 30-degree equatorial divisions; pp.35-36: natal cusp table"],
    "scope": "Natal RA-divided cusp geometry only; no complete original progression system, interpretive keywords or event claims",
}
SWISS_SOURCE = {
    "id": "swiss_meridian_houses",
    "author": "Astrodienst AG",
    "title": "Swiss Ephemeris documentation 6.2.7 and programmer manual 15",
    "url": "https://www.astro.com/swisseph/swisseph.htm",
    "sections": ["6.2.7 Meridian system; swehouse.c X and sidereal_houses_trad"],
    "scope": "Backend geometry definition; numerical agreement is not empirical prediction evidence",
}


def unavailable_meridian_houses() -> Dict[str, Any]:
    return {
        "status": "unavailable",
        "reason": "Swiss Ephemeris is required for native Meridian cusps",
        "ruleset_id": RULESET,
        "author": "FateBridge",
        "version": "1",
        "sources": [SOURCE, SWISS_SOURCE],
        "original_text_conformance": "not_assessed",
        "real_world_efficacy": "not_tested",
    }


def native_meridian_houses(
    *,
    julian_day_ut1: float,
    julian_day_tt: float,
    latitude: float,
    longitude: float,
    sidereal: bool,
    physical_angles: Sequence[float],
) -> Dict[str, Any]:
    """Use X cusps in their native house-angle frame, retaining both TT epochs.

    houses_ex derives its obliquity epoch with deltat_ex(UT1, house_flags).
    Repeating exactly that choice keeps the replay inputs in the same frame;
    substituting the shared TT or a mean ayanamsha can be inconsistent.
    """
    swe = runtime.swe
    if swe is None:
        raise ValueError("Native meridian houses require Swiss Ephemeris")
    if len(physical_angles) < 3 or not all(
        math.isfinite(value)
        for value in (
            julian_day_ut1,
            julian_day_tt,
            latitude,
            longitude,
            *physical_angles[:3],
        )
    ):
        raise ValueError("Meridian houses require finite angle inputs")
    flags = swe.FLG_SIDEREAL if sidereal else 0
    with runtime.preserve_ephemeris_path():
        if sidereal:
            swe.set_sid_mode(swe.SIDM_LAHIRI, 0.0, 0.0)
        cusps, angles = runtime.ephemeris_call(
            "houses_ex", julian_day_ut1, latitude, longitude, b"X", flags
        )
        angle_tt = julian_day_ut1 + float(
            runtime.ephemeris_call("deltat_ex", julian_day_ut1, flags)
        )
        ecliptic, retflag = runtime.ephemeris_call("calc", angle_tt, swe.ECL_NUT, 0)
        if retflag < 0 or not math.isfinite(ecliptic[0]) or not 0 <= ecliptic[0] < 90:
            raise ValueError("Native meridian houses have no valid obliquity")
        offset = 0.0
        if sidereal:
            ayanflag, offset = runtime.ephemeris_call(
                "get_ayanamsa_ex", angle_tt, flags
            )
            if ayanflag < 0 or not math.isfinite(offset):
                raise ValueError("Native meridian houses have no valid Lahiri offset")
    if (
        len(cusps) != 12
        or len(angles) < 3
        or not all(math.isfinite(value) for value in (*cusps, angles[2]))
    ):
        raise ValueError("Native meridian houses require twelve finite cusps")
    rows = [
        {
            "house": index,
            "longitude": float(cusp) % 360,
            "tropical_longitude": (float(cusp) + offset) % 360,
            "right_ascension": (float(angles[2]) + (index - 10) * 30) % 360,
        }
        for index, cusp in enumerate(cusps, 1)
    ]
    return {
        "status": "computed",
        "ruleset_id": RULESET,
        "author": "FateBridge",
        "version": "1",
        "profile": {
            "house_code": "X",
            "swisseph_version": str(swe.version),
            "house_flags": int(flags),
            "obliquity_return_flags": int(retflag),
            "geographic_latitude": latitude,
            "geographic_longitude": longitude,
            "construction": "Twelve equal 30-degree right-ascension divisions starting at the upper meridian; ecliptic intersections are generally unequal in longitude",
            "zodiac": "sidereal_lahiri" if sidereal else "tropical",
            "right_ascension_frame": "true equator/equinox of native house-angle model; unchanged by zodiac display",
            "julian_day_ut1": julian_day_ut1,
            "shared_julian_day_tt": julian_day_tt,
            "native_angle_julian_day_tt": angle_tt,
            "native_angle_minus_shared_tt_seconds": (angle_tt - julian_day_tt) * 86400,
            "angle_time_policy": "houses_ex uses UT1+deltat_ex(UT1, house_flags); obliquity and apparent Lahiri offset replayed at that exact native epoch",
            "armc": float(angles[2]) % 360,
            "true_obliquity": float(ecliptic[0]),
            "ayanamsha_apparent": float(offset),
            "first_cusp_definition": "equatorial_ascendant",
            "tenth_cusp_definition": "upper_meridian_ecliptic_intersection",
            "physical_ascendant": float(physical_angles[0]) % 360,
            "retained_ascendant_definition_reference": "Existing E-backend reference; read base_chart.chart_profile.angle_definition for geographic-pole or ill-conditioned horizon qualifications; meridian cusps do not require a resolved Ascendant",
            "physical_midheaven": float(physical_angles[1]) % 360,
            "first_cusp_replaces_physical_ascendant": False,
            "base_chart_houses_replaced": False,
            "geographic_pole_meridian_convention": abs(latitude) == 90,
        },
        "cusps": rows,
        "birth_time_sensitivity": {
            "status": "not_assessed",
            "uncertainty_minutes": None,
            "continuous_interval_proven": False,
            "sample_frequency_is_probability": False,
            "sample_reference": "midpoint_analysis.time_sensitivity.samples",
        },
        "sources": [SOURCE, SWISS_SOURCE],
        "rule_trace": [
            {
                "rule_id": RULESET,
                "source_id": SOURCE["id"],
                "source_sections": ["p.34"],
                "formula": "RA(cusp h)=ARMC+(h-10)*30deg modulo360; intersect each RA meridian with the ecliptic",
                "scope": "natal cusps only; actual Ascendant and existing midpoint factors retained",
            }
        ],
        "limitations": [
            "This is the selected 1923 natal cusp construction, not all Hamburg house systems or a complete progression time key",
            "No planet-house placement, interpretation keywords or empirically validated event forecast is supplied by this cusp layer",
            "Angles depend on the supplied geographic meridian; at exact geographic poles this is a convention, not a physical rising event",
            "Sampled birth-time ranges do not establish continuous stability, measured Earth orientation, input accuracy or event probabilities",
        ],
        "original_text_conformance": "not_assessed",
        "real_world_efficacy": "not_tested",
    }


def attach_meridian_sensitivity(
    meridian: Dict[str, Any], sensitivity: Mapping[str, Any]
) -> None:
    """Summarize all supplied cusp samples; retain same-run raw sample references."""
    result = {
        "status": sensitivity["status"],
        "uncertainty_minutes": sensitivity["uncertainty_minutes"],
        "continuous_interval_proven": False,
        "sample_frequency_is_probability": False,
        "sample_reference": "midpoint_analysis.time_sensitivity.samples",
    }
    if sensitivity["status"] == "sampled":
        samples = sensitivity["samples"]
        if not samples or len(samples) != sensitivity["sample_count"]:
            raise ValueError("Every confirmed birth-time sample needs meridian cusps")
        spans = []
        for index, cusp in enumerate(meridian["cusps"]):
            nominal = Fraction(cusp["longitude"])
            values = [Fraction(s["meridian_house_cusps"][index]) for s in samples]
            offsets = [(value - nominal + 180) % 360 - 180 for value in values]
            jumps = [abs((b - a + 180) % 360 - 180) for a, b in zip(values, values[1:])]
            spans.append(
                {
                    "house": index + 1,
                    "minimum_offset_from_nominal_degrees": float(min(offsets)),
                    "maximum_offset_from_nominal_degrees": float(max(offsets)),
                    "maximum_adjacent_sample_jump_degrees": float(
                        max(jumps, default=0)
                    ),
                }
            )
        result.update(
            sample_count=len(samples),
            maximum_recorded_sample_gap_seconds=sensitivity[
                "maximum_recorded_sample_gap_seconds"
            ],
            cusp_spans=spans,
        )
    meridian["birth_time_sensitivity"] = result
    if sensitivity["status"] == "sampled":
        result["factor_placement_summary"] = placement_sample_summaries(
            meridian, sensitivity
        )
