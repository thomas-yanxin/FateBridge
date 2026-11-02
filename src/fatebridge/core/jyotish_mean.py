"""Declared Simon1994 secular means and geometric J2000 supporting positions.

This is an optional modern astronomical model for the traditional angular
formula. It is not a reconstruction or acceptance of Raman's1900 tables.
"""

from __future__ import annotations

import math
from fractions import Fraction
from typing import Any

from fatebridge.core.astro import runtime
from fatebridge.core.ephemeris_runtime import configured_ephemeris_path
from fatebridge.core.jyotish_motion import cheshta_arc
from fatebridge.core.jyotish_sources import observe_physical

MODEL = "simon1994_j2000"
MODELS = {"unadjudicated", MODEL}
FRAME = "mean_dynamical_ecliptic_equinox_J2000"
STAR_PLANETS = ("Mars", "Mercury", "Jupiter", "Venus", "Saturn")
# Admission window in TT; this is the validated application window, not the
# much longer formal validity interval of the paper's mean elements.
LOWER_TT, UPPER_TT = 2415020.5, 2470172.5  # 1900-01-01 through2050-12-31
SOURCE = {
    "id": "simon1994_mean_j2000_1730fe5b",
    "title": "Simon et al.(1994), Numerical expressions for precession formulae and mean elements for the Moon and the planets, A&A282,663-683",
    "url": "https://articles.adsabs.harvard.edu/pdf/1994A%26A...282..663S",
    "sha256": "1730fe5bb60e03d5e3a70f76b82f97dfd07bccc67a077da636a5428343e3a503",
    "sections": ["5.2.3 and5.4-5.8; printed673-676; full secular mean longitudes"],
    "scope": "Secular mean elements, not approximate true ephemerides, osculating elements or Raman1900 table values. Formal paper interval is not an empirical accuracy certificate.",
}
# Constants are degrees. All subsequent coefficients are ARCSECONDS, with
# t in JULIAN MILLENNIA. Literal primary transcription; no fitted corrections.
LONGITUDE_COEFFICIENTS = {
    "Mercury": ("252.25090552", "5381016286.88982", "-1.92789", "0.00639"),
    "Venus": ("181.97980085", "2106641364.33548", "0.59381", "-0.00627"),
    "Earth": ("100.46645683", "1295977422.83429", "-2.04411", "-0.00523"),
    "Mars": ("355.43299958", "689050774.93988", "0.94264", "-0.01043"),
    "Jupiter": (
        "34.35151874",
        "109256603.77991",
        "-30.60378",
        "0.05706",
        "0.04667",
        "0.00591",
        "-0.00034",
    ),
    "Saturn": (
        "50.07744430",
        "43996098.55732",
        "75.61614",
        "-0.16618",
        "-0.11484",
        "-0.01452",
        "0.00083",
    ),
}


def admitted(jd_tt: float) -> bool:
    return math.isfinite(jd_tt) and LOWER_TT <= jd_tt < UPPER_TT


def mean_longitudes(jd_tt: float) -> dict[str, float]:
    """Evaluate the source's means, with an explicit TT-for-TDB substitution.

    SOFA's planetary fundamental-argument notes permit that substitution.
    This function enforces the narrower validated application window.
    """
    if not admitted(jd_tt):
        raise ValueError("Simon mean profile admitted only for1900-2050 TT")
    t = (Fraction(jd_tt) - 2451545) / 365250
    result = {}
    for planet, values in LONGITUDE_COEFFICIENTS.items():
        power_sum = Fraction(0)
        for coefficient in reversed(values[1:]):
            power_sum = (power_sum + Fraction(coefficient)) * t
        result[planet] = float((Fraction(values[0]) + power_sum / 3600) % 360)
    result["Sun"] = (result["Earth"] + 180) % 360
    return result


def icrs_to_j2000_ecliptic(xyz: tuple[float, ...]) -> tuple[float, float, float]:
    """IAU2000 frame bias followed by the Lieske J2000 mean obliquity.

    Angular constants: ERFA/SOFA bi00/bp00. The three elementary coordinate
    rotations are evaluated directly, independently of the reference matrix.
    """
    if len(xyz) != 3 or not all(math.isfinite(v) for v in xyz):
        raise ValueError("Finite ICRS position vector with three coordinates required")
    arcsecond = math.pi / (180 * 3600)
    epsilon = 84381.448 * arcsecond
    x, y, z = xyz
    angle = -0.0146 * arcsecond
    x, y = (
        math.cos(angle) * x + math.sin(angle) * y,
        -math.sin(angle) * x + math.cos(angle) * y,
    )
    angle = -0.041775 * arcsecond * math.sin(epsilon)
    x, z = (
        math.cos(angle) * x - math.sin(angle) * z,
        math.sin(angle) * x + math.cos(angle) * z,
    )
    angle = 0.0068192 * arcsecond + epsilon
    y, z = (
        math.cos(angle) * y + math.sin(angle) * z,
        -math.sin(angle) * y + math.cos(angle) * z,
    )
    return x, y, z


def geometric_points(jd_tt: float, policy: str) -> dict[str, Any]:
    """True geometric geocentric positions in the declared common frame."""
    if policy not in {"auto", "require_data_files"}:
        raise ValueError("Unsupported geometric ephemeris policy")
    if not admitted(jd_tt):
        return {}
    swe = runtime.swe
    if swe is None:
        raise ValueError("Swiss Ephemeris required for geometric true positions")
    result = {}
    flags = (
        swe.FLG_SWIEPH
        | swe.FLG_J2000
        | swe.FLG_EQUATORIAL
        | swe.FLG_XYZ
        | swe.FLG_ICRS
        | swe.FLG_TRUEPOS
    )
    with runtime.preserve_ephemeris_path():
        swe.set_ephe_path(configured_ephemeris_path() or "")
        for planet in STAR_PLANETS:
            value, retflag = runtime.ephemeris_call(
                "calc", jd_tt, getattr(swe, planet.upper()), flags
            )
            if retflag < 0 or not all(math.isfinite(v) for v in value[:3]):
                raise ValueError(f"Could not compute{planet} geometric ICRS position")
            model = runtime.ephemeris_model_from_retflag(retflag)
            observe_physical(f"geometric_j2000_{planet}", model)
            if policy == "require_data_files" and model not in {"swieph", "jpl"}:
                raise ValueError(
                    f"{planet}运动力J2000几何位置使用{model}; require_data_files rejects fallback"
                )
            xyz = icrs_to_j2000_ecliptic(tuple(value[:3]))
            if xyz[0] == xyz[1] == 0:
                raise ValueError("Geometric position has undefined ecliptic longitude")
            result[planet] = {
                "longitude": math.degrees(math.atan2(xyz[1], xyz[0])) % 360,
                "latitude": math.degrees(
                    math.atan2(xyz[2], math.hypot(xyz[0], xyz[1]))
                ),
                "frame": FRAME,
                "ephemeris_model": model,
                "retflag": retflag,
            }
    return result


def _matches_derived(actual: Any, expected: Any) -> bool:
    """Exact same-run agreement, including nulls, branch shape and scalar types."""
    if expected is None:
        return actual is None
    if isinstance(expected, (int, float)):
        return (
            type(actual) in (int, float)
            and math.isfinite(actual)
            and actual == expected
        )
    if isinstance(expected, dict):
        return (
            isinstance(actual, dict)
            and actual.keys() == expected.keys()
            and all(_matches_derived(actual[k], v) for k, v in expected.items())
        )
    if isinstance(expected, list):
        return (
            isinstance(actual, list)
            and len(actual) == len(expected)
            and all(_matches_derived(a, b) for a, b in zip(actual, expected))
        )
    return type(actual) is type(expected) and actual == expected


def verified_planet_evidence(model: dict[str, Any], planet: str) -> dict[str, Any]:
    """Verify a receipt's complete mean/operand/arc chain before interpretation.

    This re-evaluates the declared mean and angular functions. It does not
    independently observe the birth instant, recompute the geometric ephemeris,
    authenticate frame labels or certify a historical/predictive model.
    """
    try:
        if (
            planet not in STAR_PLANETS
            or model["selected"] != MODEL
            or model["status"] != "computed_declared_secular_model"
            or model["source_id"] != SOURCE["id"]
            or model["frame"] != FRAME
            or type(model["julian_day_tt"]) not in (int, float)
        ):
            raise ValueError("Unrecognized computed mean model")
        means = mean_longitudes(model["julian_day_tt"])
        if not _matches_derived(model["mean_longitudes"], means):
            raise ValueError("Mean longitudes disagree with their declared TT")
        true = model["true_position_provenance"][planet]
        longitude = true["longitude"]
        if (
            true["frame"] != FRAME
            or type(longitude) not in (int, float)
            or not math.isfinite(longitude)
            or not 0 <= longitude < 360
        ):
            raise ValueError("Invalid geometric operand or frame")
        inner = planet in {"Mercury", "Venus"}
        mean = means["Sun"] if inner else means[planet]
        apogee = means[planet] if inner else means["Sun"]
        expected = {
            "mean_longitude": mean,
            "true_longitude": longitude,
            "seeghrochcha": apogee,
            "arc": cheshta_arc(
                mean,
                longitude,
                apogee,
                mean_frame=FRAME,
                true_frame=FRAME,
                seeghrochcha_frame=FRAME,
            ),
        }
        evidence = model["planet_evidence"][planet]
        if not isinstance(evidence, dict) or not _matches_derived(evidence, expected):
            raise ValueError("Operands or angular branches disagree with calculation")
    except (KeyError, TypeError, ValueError, OverflowError) as error:
        raise ValueError(
            "Cheshta model inputs contradict the declared mean/geometry/arc chain"
        ) from error
    return evidence


def model_balas(raw: dict[str, Any]) -> dict[str, Any]:
    selected = raw.get("cheshta_model", "unadjudicated")
    context: dict[str, Any] = {
        "selected": selected,
        "julian_day_tt": raw.get("julian_day_tt"),
        "status": "mean_model_unadjudicated",
        "validated_window_tt": {"start_inclusive": LOWER_TT, "end_exclusive": UPPER_TT},
        "scope": "Modern secular mean model for the declared angular formula only; not acceptance of Raman1900 tables, complete Shadbala, or real-world predictive efficacy",
    }
    if selected == "unadjudicated":
        return {"model_context": context, "summary": dict.fromkeys(STAR_PLANETS)}
    if selected != MODEL:
        raise ValueError("Unsupported Cheshta model")
    if not admitted(raw["julian_day_tt"]):
        context["status"] = "outside_validated_model_window"
        return {"model_context": context, "summary": dict.fromkeys(STAR_PLANETS)}
    means = mean_longitudes(raw["julian_day_tt"])
    evidence = {}
    for planet in STAR_PLANETS:
        inner = planet in {"Mercury", "Venus"}
        mean, apogee = (
            (means["Sun"], means[planet]) if inner else (means[planet], means["Sun"])
        )
        true = raw["motion_true_j2000"][planet]
        arc = cheshta_arc(
            mean,
            true["longitude"],
            apogee,
            mean_frame=FRAME,
            true_frame=true["frame"],
            seeghrochcha_frame=FRAME,
        )
        evidence[planet] = {
            "mean_longitude": mean,
            "true_longitude": true["longitude"],
            "seeghrochcha": apogee,
            "arc": arc,
        }
    context.update(
        {
            "status": "computed_declared_secular_model",
            "source_id": SOURCE["id"],
            "frame": FRAME,
            "time_argument": "t=(JD_TT-2451545)/365250; TT substitutes forTDB in the slow mean arguments",
            "solar_mean": "Earth secular mean+180deg, never trueSun",
            "mean_longitudes": means,
            "true_position_provenance": raw["motion_true_j2000"],
            "planet_evidence": evidence,
            "rule_id": "jyotish.cheshta_simon1994.v1",
        }
    )
    return {
        "model_context": context,
        "summary": {p: data["arc"]["value"] for p, data in evidence.items()},
    }
