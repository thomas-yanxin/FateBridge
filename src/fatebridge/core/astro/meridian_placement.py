"""RA-based placement in the natal meridian circles described by Witte1924.

The complete ecliptic direction is projected in the declared native house
obliquity frame. A longitude-only control is diagnostic, never a replacement
for the actual latitude. Celestial-pole directions retain an unknown RA.
"""

from __future__ import annotations

import math
import sys
from fractions import Fraction
from typing import Any, Dict, Mapping, Sequence

RULESET = "witte1924_meridian_ra_placement_v1"
POLE_NORM_THRESHOLD = 64 * sys.float_info.epsilon
SOURCE = {
    "id": "witte1924_meridian_houses",
    "author": "Alfred Witte",
    "title": "Die Haeuser des Geburtsmeridians, Astrologische Blaetter6, May1924, pp55-60",
    "url": "https://www.astrax.de/pdf/38_Die%20Haeuser%20des%20Geburtsmeridians_1924_AstrBlaetter_55-60.pdf",
    "source_sha256": "eaa50014a2ded967292e352dd8cde0faf3c13ce9ddf280868c681b0f8411095b",
    "sections": [
        "p.56: equatorial divisions",
        "p.58: RA relation",
        "p.59: cusp comparison",
    ],
    "scope": "Named natal equatorial house geometry only; no source claims about harm, lifespan, keywords or event efficacy adopted",
}


def _finite(value: float) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, (float, int))
        or not math.isfinite(value)
    ):
        raise ValueError("Meridian coordinates require finite numbers")


def _turn(value: Fraction) -> float:
    return min(float(value % 360), math.nextafter(360.0, 0.0))


def house_from_ra(right_ascension: float, armc: float) -> Dict[str, Any]:
    """Half-open30deg sectors, using the actual input floats without cusp bias."""
    _finite(right_ascension)
    _finite(armc)
    offset = (Fraction(right_ascension) - Fraction(armc) - 90) % 360
    position = 1 + offset / 30
    house = 1 + int(offset // 30)
    return {
        "house": house,
        "house_position": min(
            float(position), math.nextafter(float(house + 1), float(house))
        ),
        "offset_from_first_cusp_degrees": _turn(offset),
        "distance_to_nearest_cusp_degrees": float(min(offset % 30, 30 - offset % 30)),
    }


def project_direction(
    longitude: float, latitude: float, obliquity: float
) -> Dict[str, Any]:
    for value in (longitude, latitude, obliquity):
        _finite(value)
    if not -90 <= latitude <= 90 or not 0 <= obliquity < 90:
        raise ValueError("Invalid ecliptic latitude or house obliquity")
    lam, beta, eps = map(math.radians, (longitude % 360, latitude, obliquity))
    x = math.cos(beta) * math.cos(lam)
    y = math.cos(beta) * math.sin(lam) * math.cos(eps) - math.sin(beta) * math.sin(eps)
    z = math.cos(beta) * math.sin(lam) * math.sin(eps) + math.sin(beta) * math.cos(eps)
    horizontal = math.hypot(x, y)
    declination = math.degrees(math.atan2(z, horizontal))
    if horizontal <= POLE_NORM_THRESHOLD:
        return {
            "status": "underdetermined_equatorial_pole",
            "right_ascension": None,
            "declination": declination,
            "equatorial_horizontal_norm": horizontal,
        }
    # Keep the signed raw angle until sector classification, so a tiny
    # negative angle is not rounded by float addition to exactly360deg.
    if obliquity == 0.0:
        # The rotation is exactly the identity. A trig round-trip can turn
        # longitude30 into29.999999999999996 and select the previous house.
        # Preserve the original angular input, including either side of zero.
        raw_ra = longitude
        declination = latitude
    else:
        raw_ra = math.degrees(math.atan2(y, x))
    return {
        "status": "computed",
        "right_ascension": _turn(Fraction(raw_ra)),
        "raw_right_ascension": raw_ra,
        "declination": declination,
        "equatorial_horizontal_norm": horizontal,
    }


def factor_position(
    *, longitude: float, latitude: float, obliquity: float, armc: float
) -> Dict[str, Any]:
    _finite(armc)
    direction = project_direction(longitude, latitude, obliquity)
    control = project_direction(longitude, 0.0, obliquity)
    zero = house_from_ra(control["raw_right_ascension"], armc)
    raw_ra = direction.pop("raw_right_ascension", None)
    result = {
        **direction,
        "right_ascension_raw_degrees": raw_ra,
        "input_tropical_longitude": longitude % 360,
        "input_ecliptic_latitude": latitude,
        "longitude_only_control_house": zero["house"],
        "longitude_only_control_house_position": zero["house_position"],
        "house": None,
        "house_position": None,
        "offset_from_first_cusp_degrees": None,
        "distance_to_nearest_cusp_degrees": None,
        "latitude_changes_house": None,
    }
    if raw_ra is not None:
        result.update(house_from_ra(raw_ra, armc))
        result["latitude_changes_house"] = result["house"] != zero["house"]
    return result


def attach_factor_placement(
    meridian: Dict[str, Any],
    factors: Sequence[Mapping[str, Any]],
    *,
    factor_ayanamsha: float,
) -> None:
    """Reuse this run's19 orbital factors and their actual native latitude."""
    profile = meridian["profile"]
    if not factors or len({factor["id"] for factor in factors}) != len(factors):
        raise RuntimeError("Meridian placement requires a nonempty distinct factor set")
    _finite(factor_ayanamsha)
    rows = []
    for factor in factors:
        rows.append(
            {
                **factor_position(
                    longitude=(factor["longitude"] + factor_ayanamsha) % 360,
                    latitude=factor["latitude"],
                    obliquity=profile["true_obliquity"],
                    armc=profile["armc"],
                ),
                "id": factor["id"],
                "kind": factor["kind"],
                "model": factor["model"],
            }
        )
    meridian["version"] = "2"
    meridian["factor_placement"] = {
        "status": (
            "computed" if all(r["status"] == "computed" for r in rows) else "partial"
        ),
        "ruleset_id": RULESET,
        "author": "FateBridge",
        "version": "1",
        "factor_count": len(rows),
        "physical_factor_count": sum(r["kind"] == "physical_body" for r in rows),
        "hypothetical_factor_count": sum(r["kind"] == "hypothetical" for r in rows),
        "node_factor_count": sum(r["kind"] == "lunar_node" for r in rows),
        "factors": rows,
        "factor_ayanamsha_apparent": factor_ayanamsha,
        "factor_julian_day_tt": profile["shared_julian_day_tt"],
        "projection_obliquity_julian_day_tt": profile["native_angle_julian_day_tt"],
        "coordinate_policy": "Same-run native ecliptic longitude/latitude; sidereal longitude restored with factor-epoch apparent offset. Projected using the disclosed native house obliquity; no factor time changed or new ephemeris query",
        "sector_policy": "House1 starts at ARMC+90deg; half-open30deg RA sectors. No cusp bias or Swiss house_pos near-cusp snapping adopted; reported floats are not physical error bounds",
        "pole_horizontal_norm_threshold": POLE_NORM_THRESHOLD,
        "reference_points_included": False,
        "scope": "Actual orbital-factor set with physical bodies, analytical mean node and any supplied mathematical hypothetical factors counted separately; reference angle points excluded; applying named geometry does not assert an original interpretation for every modern factor",
        "source_example_reconciliation": "Witte1924 p59 printed comparison remains unreconciled against the two predeclared obliquity models; no fitted correction adopted",
        "sources": [SOURCE],
        "full_original_method_accepted": False,
        "real_world_efficacy": "not_tested",
    }


def placement_sample_summaries(
    meridian: Mapping[str, Any], sensitivity: Mapping[str, Any]
) -> list[dict[str, Any]]:
    nominal = meridian.get("factor_placement")
    if not nominal or sensitivity["status"] != "sampled":
        return []
    expected = {r["id"] for r in nominal["factors"]}
    cohorts = []
    for sample in sensitivity["samples"]:
        rows = {r["id"]: r for r in sample["meridian_factor_positions"]}
        if set(rows) != expected or len(rows) != len(
            sample["meridian_factor_positions"]
        ):
            raise RuntimeError(
                "Every meridian placement sample requires the same factor set"
            )
        cohorts.append(rows)
    summaries = []
    for factor in nominal["factors"]:
        values = [c[factor["id"]] for c in cohorts]
        unknown = sum(v["status"] != "computed" for v in values)
        houses = sorted({v["house"] for v in values if v["status"] == "computed"})
        summaries.append(
            {
                "id": factor["id"],
                "nominal_house": factor["house"],
                "sampled_houses": houses,
                "unresolved_sample_count": unknown,
                "sampled_status": (
                    "underdetermined"
                    if unknown or factor["status"] != "computed"
                    else (
                        "all_sampled_same_house_as_nominal"
                        if houses == [factor["house"]]
                        else "varies_across_samples"
                    )
                ),
            }
        )
    return summaries
