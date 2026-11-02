"""Apparent, date-specific positions from a frozen twenty-object catalogue.

Astronomical ICRS observations and traditional labels are separate inputs.
The native catalogue is isolated from optional operator and Guolao catalogues.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from fractions import Fraction
from pathlib import Path
from typing import Any, cast

from fatebridge.core.astro import runtime
from fatebridge.core.astro.geometry import normalize_angle
from fatebridge.core.astro.time_scales import tt_from_ut1
from fatebridge.core.ephemeris_runtime import configured_ephemeris_path
from fatebridge.core.fixed_star_paths import fixed_star_search_path

DATA = Path(__file__).parents[1] / "data/western_stars"
MODEL_ID = "fatebridge_simbad_native_apparent_stars_v1"
NATURE_SOURCE = "https://penelope.uchicago.edu/Thayer/E/Roman/Texts/Ptolemy/Tetrabiblos/1B%2A.html#9"


def catalogue() -> dict[str, Any]:
    source = cast(dict[str, Any], json.loads((DATA / "sources.json").read_text()))
    digest = hashlib.sha256((DATA / "sefstars.txt").read_bytes()).hexdigest()
    if (
        digest != source["catalogue_sha256"]
        or len(source["stars"]) != 20
        or len({r["name"] for r in source["stars"]}) != 20
        or len({r["catalogue_key"] for r in source["stars"]}) != 20
    ):
        raise ValueError(
            "Western fixed-star catalogue does not match its source receipt"
        )
    return source


def nature_rules() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads((DATA / "nature_rules.json").read_text()))


def apparent_positions(
    julian_day_tt: float, *, sidereal: bool = False
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Native geocentric apparent ecliptic coordinates at TT, in one frame."""
    if not math.isfinite(julian_day_tt):
        raise ValueError("Fixed-star TT Julian day must be finite")
    source = catalogue()
    profile: dict[str, Any] = {
        "model_id": MODEL_ID,
        "status": "unavailable",
        "catalogue_id": source["catalogue_id"],
        "catalogue_sha256": source["catalogue_sha256"],
        "catalogue_size": 20,
        "catalogue_epoch": "ICRS J2000.0",
        "julian_day_tt": julian_day_tt,
        "longitude_frame": (
            "sidereal_lahiri" if sidereal else "tropical_true_ecliptic_of_date"
        ),
        "conjunction_basis": "ecliptic_longitude_separation_only",
        "latitude_used_for_conjunction": False,
        "space_motion": "catalogue proper motion, radial velocity and parallax; no binary orbit or covariance propagation",
        "astrometry_source": "CDS SIMBAD; individual references in bundled sources.json",
        "nature_source_url": NATURE_SOURCE,
        "nature_ruleset_id": "ptolemy_robbins_1940_i9_regional_twenty_v1",
        "nature_rules_sha256": hashlib.sha256(
            (DATA / "nature_rules.json").read_bytes()
        ).hexdigest(),
        "absolute_sky_accuracy_certified": False,
    }
    if runtime.swe is None:
        profile["unavailable_reason"] = "native_engine_unavailable"
        profile["note_zh"] = (
            "恒星层未计算：缺少原生星历引擎；空列表不表示没有恒星合相。"
        )
        return {}, profile
    swe = runtime.swe
    profile["swisseph_version"] = swe.version
    positions: dict[str, dict[str, Any]] = {}
    with runtime.preserve_ephemeris_path():
        selected = configured_ephemeris_path() or ""
        with fixed_star_search_path(DATA, selected) as search_path:
            # Swiss's environment override and fixstar2 cache otherwise bypass
            # the selected catalogue. All changes hold the shared runtime lock.
            operator_path = os.environ.get("SE_EPHE_PATH")
            try:
                # Managed calls must see the same temporary catalogue search
                # path as the C library, including the operator's DE files.
                os.environ["SE_EPHE_PATH"] = search_path
                swe.close()
                swe.set_ephe_path(search_path)
                if sidereal:
                    swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)
                flag = swe.FLG_SWIEPH | (swe.FLG_SIDEREAL if sidereal else 0)
                # fixstar2 can echo SWIEPH even when its observer Earth used
                # Moshier. Probe the same selected path explicitly, retaining
                # both raw flags rather than promoting the star flag to proof.
                _, earth_flags = runtime.ephemeris_call(
                    "calc", julian_day_tt, swe.EARTH, swe.FLG_SWIEPH | swe.FLG_HELCTR
                )
                if earth_flags < 0:
                    raise ValueError("Invalid Earth state for apparent star positions")
                for row in source["stars"]:
                    coordinates, returned_name, flags = runtime.ephemeris_call(
                        "fixstar2", row["catalogue_key"], julian_day_tt, flag
                    )
                    if flags < 0 or not all(math.isfinite(v) for v in coordinates):
                        raise ValueError(
                            "Nonfinite or invalid native fixed-star position"
                        )
                    if sidereal and not flags & swe.FLG_SIDEREAL:
                        raise ValueError(
                            "Native fixed-star position did not retain Lahiri frame"
                        )
                    if returned_name.split(",")[0] != row["catalogue_key"]:
                        raise ValueError(
                            "Native fixed-star catalogue identity mismatch"
                        )
                    positions[row["name"]] = {
                        "longitude": normalize_angle(float(coordinates[0])),
                        "latitude": float(coordinates[1]),
                        "native_flags": int(flags),
                        "source_url": row["source_url"],
                        "identifier": row["identifier"],
                    }
                profile.update(
                    {
                        "status": "computed",
                        "native_flags": sorted(
                            {p["native_flags"] for p in positions.values()}
                        ),
                        "earth_flags": int(earth_flags),
                        "earth_ephemeris_model": runtime.ephemeris_model_from_retflag(
                            earth_flags
                        ),
                        "note_zh": "恒星按本次TT传播自行、视差及径向速度，并计算岁差、章动与地心视位置；合相仅比较同一黄道下的黄经，默认容许度1°，不表示球面角距或掩星。",
                    }
                )
            except swe.Error:
                positions = {}
                profile["unavailable_reason"] = "native_position_unavailable_at_epoch"
                profile["note_zh"] = (
                    "恒星层未计算：本时刻原生视位置不可用；空列表不表示没有恒星合相。"
                )
            finally:
                swe.close()
                if operator_path is not None:
                    os.environ["SE_EPHE_PATH"] = operator_path
                else:
                    os.environ.pop("SE_EPHE_PATH", None)
                swe.set_ephe_path(selected)
    return positions, profile


def conjunction_hits(
    points: dict[str, float],
    positions: dict[str, dict[str, Any]],
    labels: dict[str, dict[str, Any]],
    *,
    orb: float = 1.0,
) -> list[dict[str, Any]]:
    """Classify before rounding; the next float outside a limit is outside."""
    if not math.isfinite(orb) or not 0 <= orb <= 180:
        raise ValueError("Fixed-star orb must be finite and between 0 and 180 degrees")
    # Reduce the supplied doubles exactly before testing the limit. Near the
    # 0/360 wrap, two float subtractions can round an outside value onto 1°.
    for value in points.values():
        normalize_angle(value)  # finite validation
    point_angles = {name: Fraction(value) % 360 for name, value in points.items()}
    attributions = nature_rules()["stars"]
    hits = []
    for name, star in positions.items():
        attribution = attributions[name]
        if {p["planet"] for p in attribution["components"]} != set(
            labels[name]["nature"]
        ):
            raise ValueError(
                "Traditional star labels disagree with the named source attribution"
            )
        longitude = normalize_angle(star["longitude"])
        star_angle = Fraction(star["longitude"]) % 360
        for point, point_angle in point_angles.items():
            distance = (star_angle - point_angle) % 360
            separation = min(distance, 360 - distance)
            if separation <= Fraction(orb):
                hits.append(
                    {
                        "star": name,
                        "cn": labels[name]["cn"],
                        "point": point,
                        "orb": float(separation),
                        "star_longitude": longitude,
                        "star_latitude": star["latitude"],
                        "nature": labels[name]["nature"],
                        "nature_components": attribution["components"],
                        "nature_source_region": attribution["region"],
                        "nature_source_url": NATURE_SOURCE,
                        "astrometry_source_url": star["source_url"],
                        "catalogue_identifier": star["identifier"],
                    }
                )
    hits.sort(key=lambda row: (row["orb"], row["star"], row["point"]))
    return hits


def build_layer(
    points: dict[str, float],
    julian_day_ut1: float,
    labels: dict[str, dict[str, Any]],
    *,
    julian_day_tt: float | None = None,
    sidereal: bool = False,
    orb: float = 1.0,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not math.isfinite(julian_day_ut1):
        raise ValueError("Fixed-star UT1 Julian day must be finite")
    # Validate arguments even when the physical layer will be unavailable.
    conjunction_hits(points, {}, labels, orb=orb)
    if julian_day_tt is None and runtime.swe is not None:
        julian_day_tt = tt_from_ut1(julian_day_ut1)
    if julian_day_tt is None:
        profile = {
            "model_id": MODEL_ID,
            "status": "unavailable",
            "unavailable_reason": "tt_unavailable",
            "orb_limit": orb,
            "note_zh": "恒星层未计算：缺少TT时间基准；空列表不表示没有恒星合相。",
        }
        return [], profile
    positions, profile = apparent_positions(julian_day_tt, sidereal=sidereal)
    profile["orb_limit"] = orb
    return conjunction_hits(points, positions, labels, orb=orb), profile
