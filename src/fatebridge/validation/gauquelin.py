"""Literal CFEPP input audit and an independent fixed-body semiarc model.

This module evaluates calculation fidelity, not occupational prediction. It never
repairs a source clock from its published sector, imputes a time, or drops a row.
"""

from __future__ import annotations

import hashlib
import math
import re
from datetime import datetime, timedelta
from typing import Any

FINAL3_SHA256 = "2d5eb1df33057497a293b7f50aac8855af0e5107e77e736412bedd3b67067cbf"
FINAL3_ROWS = 1120
METHOD_POLICY_VERSION = "swiss_gauquelin_method_policy_v1"
METHOD_POLICY_SOURCE = "https://github.com/aloistr/swisseph/blob/v2.10.03/swecl.c"
FIELDS = (
    "sport",
    "source",
    "level",
    "name",
    "local_date",
    "regime",
    "local_time",
    "place",
    "postal_code",
    "longitude_west",
    "latitude",
    "universal_date",
    "universal_time",
    "mars12",
)
LIMITS = (0, 19, 24, 29, 59, 70, 72, 80, 106, 122, 131, 139, 152, 158, 160)


def method_profile(method: int) -> dict[str, Any]:
    """Describe the native method with the audit's explicit non-topocentric flag.

    This describes the pinned Swiss algorithm, not a historical author's model.
    Methods2..5 pass only ephemeris bits to rise_trans, whose ordinary rise/set
    paths set TOPOCTR internally. Absence of a requested TOPOCTR bit therefore
    does not make those methods geocentric. Their input height affects observer
    parallax even when refraction is disabled; it is not a measured birth height.
    """
    if type(method) is not int or method not in range(6):
        raise ValueError("gauquelin_method_must_be_integer0_to5")
    instantaneous = method in (0, 1)
    refracted = method in (3, 5)
    return {
        "policy_version": METHOD_POLICY_VERSION,
        "source": METHOD_POLICY_SOURCE,
        "method": method,
        "calculation_basis": (
            "instantaneous_placidus_position"
            if instantaneous
            else "moving_body_rise_set"
        ),
        "requested_topocentric_flag": False,
        "observer_origin": "geocentric" if instantaneous else "topocentric",
        "observer_origin_basis": (
            "explicit_coordinate_flag"
            if instantaneous
            else "native_rise_set_forces_topocentric"
        ),
        "geopos_height_use": ("not_used" if instantaneous else "observer_parallax"),
        "ecliptic_latitude": "zeroed" if method == 1 else "retained",
        "horizon": "refracted" if refracted else "geometric",
        "disk_reference": (
            "position_point"
            if instantaneous
            else "center" if method in (2, 3) else "upper_limb"
        ),
        "atmosphere_inputs_used": refracted,
        "pressure_zero_policy": (
            "native_estimate_from_observer_height" if refracted else "not_used"
        ),
        "polar_policy": (
            "native_otto_ludwig_extension"
            if instantaneous
            else "error_without_bracketing_rise_and_set"
        ),
        "historical_cfepp_method_identified": False,
    }


def source_datetime(day: str, clock: str) -> tuple[datetime, bool]:
    """A historical calendar value, deliberately not labelled modern UTC."""
    if not re.fullmatch(r"\d{4} \d{2} \d{2}", day):
        raise ValueError("invalid_date_format")
    if not re.fullmatch(r"\d{2} \d{2}", clock):
        raise ValueError("missing_or_invalid_time")
    year, month, date = map(int, day.split())
    hour, minute = map(int, clock.split())
    if hour == 24 and minute == 0:
        return datetime(year, month, date) + timedelta(days=1), True
    return datetime(year, month, date, hour, minute), False


def parse_line(line: bytes, number: int) -> dict[str, Any]:
    """Retain invalid records and raw fields. IDs refer to source line order."""
    result: dict[str, Any] = {
        "case_id": f"CF-{number}",
        "cohort": "published_1066" if number <= 1066 else "supplementary_54",
        "source_line_sha256": hashlib.sha256(line).hexdigest(),
        "issues": [],
    }
    if len(line) != 160:
        result["issues"].append("invalid_fixed_width")
        return result
    raw = {
        key: line[a:b].decode("latin-1").strip()
        for key, a, b in zip(FIELDS, LIMITS, LIMITS[1:])
    }
    result["raw"] = raw
    for prefix in ("local", "universal"):
        try:
            date, rolled = source_datetime(raw[f"{prefix}_date"], raw[f"{prefix}_time"])
            result[prefix] = date
            result[f"{prefix}_24_hour_rollover"] = rolled
        except ValueError as exc:
            result["issues"].append(f"{prefix}:{exc}")
    for name, bound in (("longitude_west", 180), ("latitude", 90)):
        try:
            if not re.fullmatch(r"[+-]\d{2,3}\.\d{2}", raw[name]):
                raise ValueError("missing_or_invalid_coordinate")
            value = float(raw[name])
            if abs(value) > bound:
                raise ValueError("coordinate_out_of_range")
            result[name] = value
        except ValueError as exc:
            result["issues"].append(f"{name}:{exc}")
    if "longitude_west" in result:
        result["longitude_east"] = -result["longitude_west"]
    if raw["regime"] not in {"f", "o", "a"}:
        result["issues"].append("unknown_time_regime")
    if not re.fullmatch(r"(?:[1-9]|1[0-2])", raw["mars12"]):
        result["issues"].append("missing_or_invalid_source_sector")
    else:
        result["mars12"] = int(raw["mars12"])
    return result


def decode_final3(data: bytes) -> list[dict[str, Any]]:
    """Only the pinned complete source is eligible for this historical replay."""
    if hashlib.sha256(data).hexdigest() != FINAL3_SHA256:
        raise ValueError("final3_source_hash_mismatch")
    lines = data.splitlines()
    if len(lines) != FINAL3_ROWS:
        raise ValueError("final3_source_row_count_mismatch")
    return [parse_line(line, i) for i, line in enumerate(lines, 1)]


def clock_coherence(row: dict[str, Any]) -> dict[str, Any]:
    """Partial resolution check; never a complete historical zone resolver."""
    if row["issues"]:
        return {"status": "not_checked_invalid_input"}
    local, universal = row["local"], row["universal"]
    observed = (local - universal).total_seconds()
    common = {"observed_offset_seconds": observed, "regime": row["raw"]["regime"]}
    if row["raw"]["regime"] != "f":
        return {**common, "status": "not_checked_regime"}
    if local < datetime(1891, 3, 14):
        expected = row["longitude_east"] * 240
        model = "local_mean_solar_time"
    elif datetime(1891, 3, 16) <= local < datetime(1911, 3, 9):
        expected = 561.0
        model = "paris_mean_time"
    else:
        return {**common, "status": "not_checked_date"}
    residual = observed - expected
    return {
        **common,
        "model": model,
        "expected_offset_seconds": expected,
        "residual_seconds": residual,
        "resolution_tolerance_seconds": 60,
        "status": (
            "coherent_at_source_resolution" if abs(residual) <= 60 else "unreconciled"
        ),
    }


def _angle(value: float, bound: float | None = None) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
    ):
        raise ValueError("finite_numeric_angle_required")
    if bound is not None and abs(value) > bound:
        raise ValueError("angle_out_of_range")
    return float(value)


def sector12(sector36: float) -> int:
    value = _angle(sector36)
    if not 1 <= value < 37:
        raise ValueError("sector36_out_of_range")
    return 1 + math.floor((value - 1) / 3)


def semiarc_sector(
    armc: float, latitude: float, ra: float, declination: float
) -> dict[str, Any]:
    """Frozen equatorial point, geometric horizon, clockwise 36 equal-time bins.

    Earth-rotation hour angle increases from rise to upper transit to set. No
    longitude-only zodiac segmentation, refraction, motion, or polar extension.
    """
    armc, ra = _angle(armc), _angle(ra)
    latitude, declination = _angle(latitude, 90), _angle(declination, 90)
    if abs(latitude) == 90 or abs(declination) == 90:
        return {"status": "underdetermined_pole", "sector36": None}
    cosine = -math.tan(math.radians(latitude)) * math.tan(math.radians(declination))
    if abs(cosine) >= 1:
        return {"status": "no_two_horizon_crossings", "sector36": None}
    semiarc = math.degrees(math.acos(cosine))
    hour_angle = (armc - ra + 180) % 360 - 180
    if -semiarc <= hour_angle <= semiarc:
        position = 1 + 9 * (hour_angle + semiarc) / semiarc
    else:
        unwrapped = hour_angle if hour_angle > semiarc else hour_angle + 360
        position = 19 + 9 * (unwrapped - semiarc) / (180 - semiarc)
    # An exact next-rise endpoint belongs to sector1; no near-cusp bias.
    if position == 37:
        position = 1.0
    return {
        "status": "computed",
        "sector36": position,
        "sector12": sector12(position),
        "hour_angle_degrees": hour_angle,
        "diurnal_semiarc_degrees": semiarc,
    }
