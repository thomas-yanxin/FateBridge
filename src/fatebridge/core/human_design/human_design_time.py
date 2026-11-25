"""Continuous TT Design-epoch solving and explicit UTC leap-second labels."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Literal, TypedDict

from fatebridge.core.astro import runtime
from fatebridge.core.astro.physical_epoch import utc_from_tt as physical_utc_from_tt
from fatebridge.core.astro.time_scales import ephemeris_time, ut1_from_tt
from fatebridge.core.astro.utc_policy import leap_table
from fatebridge.core.human_design.human_design_natal_sources import (
    observe_native_source,
)
from fatebridge.core.human_design.human_design_provenance import position_flag_model
from fatebridge.core.human_design.human_design_solar_root import (
    SOLAR_COORDINATE_POLICY,
    SolarRoot,
    solve_solar_root,
)
from fatebridge.core.jpl_ephemeris import configured_jpl_file
from fatebridge.utils.errors import EphemerisSourceError

UtcLabelStatus = Literal[
    "inserted_UTC_leap_second",
    "unique_civil_label",
    "unrepresentable_historical_fractional_UTC_adjustment",
]


class EpochTime(TypedDict):
    jd_tt: float
    jd_ut1: float
    method: str
    future_leap_seconds_assumed_unchanged: bool
    utc_is_leap_second: bool
    utc_label_status: UtcLabelStatus


class EpochContext(TypedDict):
    utc_label: str | None
    datetime: datetime | None
    time: EpochTime


class DesignSolver(SolarRoot):
    target_solar_arc_degrees: float
    days_before_birth: float
    civil_elapsed_days: float | None
    method: str
    birth_jd_tt: float
    utc_is_leap_second: bool
    utc_label_status: UtcLabelStatus
    precision_scope: str


class SolvedDesignEpoch(EpochContext):
    solver: DesignSolver


def sun_at_tt(
    jd_tt: float, require_swiss_files: bool = False, *, backend: str = "swieph"
) -> float:
    if runtime.swe is None:
        raise RuntimeError("人类图需要 Swiss Ephemeris")
    if backend not in {"swieph", "moshier"}:
        raise ValueError("人类图星历请求后端必须为 swieph 或 moshier")
    if backend == "moshier" and require_swiss_files:
        raise ValueError("强制 Moshier 与要求 Swiss 数据文件冲突")
    if require_swiss_files and configured_jpl_file() is not None:
        raise EphemerisSourceError("jpl_swiss_file_requirement_conflict")
    coordinates, return_flags = runtime.ephemeris_call(
        "calc",
        jd_tt,
        runtime.swe.SUN,
        (runtime.swe.FLG_MOSEPH if backend == "moshier" else runtime.swe.FLG_SWIEPH)
        | runtime.swe.FLG_SPEED,
    )
    try:
        model = position_flag_model(return_flags)
    except ValueError as error:
        raise RuntimeError(
            "Swiss Ephemeris 太阳返回旗标与人类图坐标口径不一致"
        ) from error
    longitude_degrees = float(coordinates[0])
    if not math.isfinite(longitude_degrees):
        raise RuntimeError("Swiss Ephemeris 太阳位置或实际后端标记无效")
    if require_swiss_files and model != "swieph":
        raise RuntimeError("设计时刻求解要求 Swiss Ephemeris 数据文件")
    if backend == "moshier" and model != "moshier":
        raise RuntimeError("设计时刻参考后端未实际采用 Moshier")
    observe_native_source("Sun", jd_tt, return_flags, role="solar_root")
    return longitude_degrees % 360


def utc_from_tt(jd_tt: float) -> tuple[str | None, datetime | None, bool]:
    """Preserve the Human Design adapter for the shared UTC label."""
    return physical_utc_from_tt(jd_tt)


def solve_design_epoch(
    birth: datetime, *, require_swiss_files: bool = False
) -> SolvedDesignEpoch:
    """Solve 88 degrees in TT, which remains continuous across UTC leap seconds."""
    if birth.utcoffset() is None:
        raise ValueError("出生瞬间必须带时区")
    birth = birth.astimezone(timezone.utc)
    time = ephemeris_time(birth)
    if time.jd_tt is None:
        raise RuntimeError("人类图需要可用的 TT 星历时刻")
    return _solve_design_epoch_tt(time.jd_tt, birth, require_swiss_files)


def solve_design_epoch_tt(
    birth_jd_tt: float, *, require_swiss_files: bool = False, backend: str = "swieph"
) -> SolvedDesignEpoch:
    """Physical-epoch variant for interval samples, including UTC second 60."""
    if not math.isfinite(birth_jd_tt):
        raise ValueError("出生 TT 必须为有限数值")
    _, moment, _ = utc_from_tt(birth_jd_tt)
    return _solve_design_epoch_tt(birth_jd_tt, moment, require_swiss_files, backend)


def epoch_context_at_tt(jd_tt: float, *, method: str) -> EpochContext:
    """Retain continuous TT and its possibly non-datetime civil label."""
    utc_label, utc_datetime, is_leap_second = utc_from_tt(jd_tt)
    return {
        "utc_label": utc_label,
        "datetime": utc_datetime,
        "time": _epoch_time_context(
            jd_tt, utc_label, utc_datetime, is_leap_second, method
        ),
    }


def _epoch_time_context(
    jd_tt: float,
    utc_label: str | None,
    utc_datetime: datetime | None,
    is_leap_second: bool,
    method: str,
) -> EpochTime:
    # note (time scale): Invert the civil forward policy to retain its pre-1960 Delta T flag.
    jd_ut1 = ut1_from_tt(jd_tt)
    return {
        "jd_tt": jd_tt,
        "jd_ut1": float(jd_ut1),
        "method": method,
        "future_leap_seconds_assumed_unchanged": bool(
            utc_datetime
            and utc_datetime >= datetime.fromisoformat(leap_table()["expires_at"])
        ),
        "utc_is_leap_second": is_leap_second,
        "utc_label_status": (
            "inserted_UTC_leap_second"
            if is_leap_second
            else (
                "unique_civil_label"
                if utc_label is not None
                else "unrepresentable_historical_fractional_UTC_adjustment"
            )
        ),
    }


def _solve_design_epoch_tt(
    birth_jd_tt: float,
    birth: datetime | None,
    require_swiss_files: bool,
    backend: str = "swieph",
) -> SolvedDesignEpoch:
    root = solve_solar_root(
        birth_jd_tt,
        lambda jd_tt: sun_at_tt(jd_tt, require_swiss_files, backend=backend),
    )
    root["numerical_precision"]["sun_coordinate_policy"] = SOLAR_COORDINATE_POLICY
    solved = root["design_jd_tt"]
    error = root["residual_degrees"]
    if abs(error) > 1e-7:
        raise RuntimeError("设计时刻太阳弧残差超出容差")
    label, moment, leap_second = utc_from_tt(solved)
    context = _epoch_time_context(
        solved,
        label,
        moment,
        leap_second,
        "continuous_TT_root_with_frozen_UTC_leap_policy",
    )
    return {
        "datetime": moment,
        "utc_label": label,
        "time": context,
        "solver": {
            "target_solar_arc_degrees": 88.0,
            **root,
            "days_before_birth": birth_jd_tt - solved,
            "civil_elapsed_days": (
                None
                if moment is None or birth is None
                else (birth - moment).total_seconds() / 86400
            ),
            "method": "bracketed_bisection_in_continuous_TT",
            "birth_jd_tt": birth_jd_tt,
            "design_jd_tt": solved,
            "utc_is_leap_second": leap_second,
            "utc_label_status": context["utc_label_status"],
            "precision_scope": "数值根收敛；不表示出生记录达到相同精度。",
        },
    }
