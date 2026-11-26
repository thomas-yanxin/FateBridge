"""Continuous TT birth clock, 88-degree solar arc solver, and natal chart assembly."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from typing import Any, Literal, TypedDict

from fatebridge.core.astro import runtime
from fatebridge.core.astro.physical_epoch import utc_from_tt as physical_utc_from_tt
from fatebridge.core.astro.time_scales import ephemeris_time, ut1_from_tt
from fatebridge.core.astro.tt_epoch import TTInstant
from fatebridge.core.astro.utc_policy import leap_table
from fatebridge.core.human_design.depth import cross_identifier
from fatebridge.core.human_design.mechanics import (
    VALID_PROFILES,
    _rational_activation,
    activation_longitude_fraction,
    bodygraph,
    definition_bridging,
    position_flag_model,
    positions_at_tt,
    variables_from_activations,
)
from fatebridge.core.jpl_ephemeris import configured_jpl_file
from fatebridge.utils.errors import EphemerisSourceError
from fatebridge.utils.timezones import parse_timezone_name, validate_local_clock

UtcLabelStatus = Literal[
    "inserted_UTC_leap_second",
    "unique_civil_label",
    "unrepresentable_historical_fractional_UTC_adjustment",
]


@dataclass(frozen=True)
class BirthClock:
    local_anchor: datetime
    utc_anchor: datetime
    local_label: str
    utc_label: str
    leap_second: bool
    jd_tt: float | None
    evidence: dict[str, Any] | None


@dataclass(frozen=True)
class ConfirmedLeapSecond:
    """A confirmed UTC second 60, with second 59 as its datetime carrier."""

    utc_anchor: datetime
    offset_before: int
    offset_after: int

    @classmethod
    def from_utc_anchor(cls, utc: datetime) -> ConfirmedLeapSecond:
        if (utc.hour, utc.minute, utc.second) != (23, 59, 59):
            raise ValueError("当地60秒未对应UTC闰秒分钟，不能归并到下一秒")
        effective_date = (utc.date() + timedelta(days=1)).isoformat()
        entries = leap_table()["entries"]
        for previous, following in zip(entries, entries[1:]):
            before = previous["tai_minus_utc_seconds"]
            after = following["tai_minus_utc_seconds"]
            if following["effective_date"] == effective_date and after - before == 1:
                return cls(utc, before, after)
        raise ValueError("冻结IERS记录未确认该UTC闰秒，不推测未来插秒")

    @property
    def effective(self) -> datetime:
        return self.utc_anchor + timedelta(seconds=1)

    @property
    def tt(self) -> TTInstant:
        return TTInstant.from_utc(
            self.effective, tai_minus_utc_seconds=self.offset_before
        )

    @property
    def utc_label(self) -> str:
        utc = self.utc_anchor
        return utc.isoformat()[:17] + f"60.{utc.microsecond:06d}+00:00"


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


def resolve_birth_clock(
    *,
    birth_year: int,
    birth_month: int,
    birth_day: int,
    birth_hour: int,
    birth_minute: int,
    birth_second: int = 0,
    birth_timezone: str,
) -> BirthClock:
    if type(birth_second) is not int or not 0 <= birth_second <= 60:
        raise ValueError("出生秒须为0至60的整数；60仅用于已公布UTC闰秒")
    local = datetime(
        birth_year,
        birth_month,
        birth_day,
        birth_hour,
        birth_minute,
        59 if birth_second == 60 else birth_second,
        tzinfo=parse_timezone_name(birth_timezone, issue_path="birth_timezone"),
    )
    validate_local_clock(local)
    utc = local.astimezone(timezone.utc)
    if birth_second != 60:
        return BirthClock(
            local, utc, local.isoformat(), utc.isoformat(), False, None, None
        )
    leap = ConfirmedLeapSecond.from_utc_anchor(utc)
    tt = leap.tt.as_float()
    local_label = local.isoformat()[:17] + "60" + local.isoformat()[19:]
    evidence = {
        "method_id": "human_design_confirmed_birth_leap_second_v1",
        "local_label": local_label,
        "utc_label": leap.utc_label,
        "jd_tt": tt,
        "tai_minus_utc_during_leap_seconds": leap.offset_before,
        "tai_minus_utc_after_leap_seconds": leap.offset_after,
    }
    return BirthClock(local, utc, local_label, leap.utc_label, True, tt, evidence)


def utc_from_tt(jd_tt: float) -> tuple[str | None, datetime | None, bool]:
    return physical_utc_from_tt(jd_tt)


def _epoch_time_context(
    jd_tt: float,
    utc_label: str | None,
    utc_datetime: datetime | None,
    is_leap_second: bool,
    method: str,
) -> EpochTime:
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


def epoch_context_at_tt(jd_tt: float, *, method: str) -> EpochContext:
    utc_label, utc_datetime, is_leap_second = utc_from_tt(jd_tt)
    return {
        "utc_label": utc_label,
        "datetime": utc_datetime,
        "time": _epoch_time_context(
            jd_tt, utc_label, utc_datetime, is_leap_second, method
        ),
    }


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
    flag = (
        runtime.swe.FLG_MOSEPH if backend == "moshier" else runtime.swe.FLG_SWIEPH
    ) | runtime.swe.FLG_SPEED
    coordinates, return_flags = runtime.ephemeris_call(
        "calc", jd_tt, runtime.swe.SUN, flag
    )
    model = position_flag_model(return_flags)
    longitude_degrees = float(coordinates[0])
    if not math.isfinite(longitude_degrees):
        raise RuntimeError("Swiss Ephemeris 太阳位置或实际后端标记无效")
    if require_swiss_files and model != "swieph":
        raise RuntimeError("设计时刻求解要求 Swiss Ephemeris 数据文件")
    if backend == "moshier" and model != "moshier":
        raise RuntimeError("设计时刻参考后端未实际采用 Moshier")
    return longitude_degrees % 360.0


def _solar_residual(birth_sun: float, design_sun: float) -> Fraction:
    return (Fraction(birth_sun) - Fraction(design_sun)) % 360 - 88


def solve_design_epoch_tt(
    birth_jd_tt: float, *, require_swiss_files: bool = False, backend: str = "swieph"
) -> dict[str, Any]:
    """Fast bracketed bisection in continuous TT down to adjacent binary64 floats."""
    if not math.isfinite(birth_jd_tt):
        raise ValueError("出生 TT 必须为有限数值")
    birth_jd_tt = float(birth_jd_tt)
    birth_sun = sun_at_tt(birth_jd_tt, require_swiss_files, backend=backend)
    lo, hi = birth_jd_tt - 110.0, birth_jd_tt - 70.0
    r_lo = _solar_residual(
        birth_sun, sun_at_tt(lo, require_swiss_files, backend=backend)
    )
    r_hi = _solar_residual(
        birth_sun, sun_at_tt(hi, require_swiss_files, backend=backend)
    )
    if not (r_lo > 0 > r_hi):
        raise RuntimeError("设计时刻的太阳黄经未能括定 88 度根")
    iterations = 0
    while math.nextafter(lo, math.inf) < hi:
        mid = lo + (hi - lo) / 2
        if mid in (lo, hi):
            break
        r_mid = _solar_residual(
            birth_sun, sun_at_tt(mid, require_swiss_files, backend=backend)
        )
        iterations += 1
        if r_mid == 0:
            lo = hi = mid
            r_lo = r_hi = r_mid
            break
        if r_mid > 0:
            lo, r_lo = mid, r_mid
        else:
            hi, r_hi = mid, r_mid
    solved, residual = (lo, r_lo) if abs(r_lo) <= abs(r_hi) else (hi, r_hi)
    if abs(float(residual)) > 1e-7:
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
            "design_jd_tt": solved,
            "birth_jd_tt": birth_jd_tt,
            "residual_degrees": float(residual),
            "bracket_width_seconds": (hi - lo) * 86400.0,
            "days_before_birth": birth_jd_tt - solved,
            "iterations": iterations,
            "method": "bracketed_bisection_in_continuous_TT",
            "utc_is_leap_second": leap_second,
            "utc_label_status": context["utc_label_status"],
        },
    }


def solve_design_epoch(
    birth: datetime, *, require_swiss_files: bool = False
) -> dict[str, Any]:
    if birth.utcoffset() is None:
        raise ValueError("出生瞬间必须带时区")
    birth = birth.astimezone(timezone.utc)
    time = ephemeris_time(birth)
    if time.jd_tt is None:
        raise RuntimeError("人类图需要可用的 TT 星历时刻")
    solved = solve_design_epoch_tt(time.jd_tt, require_swiss_files=require_swiss_files)
    moment = solved["datetime"]
    solved["solver"]["civil_elapsed_days"] = (
        None if moment is None else (birth - moment).total_seconds() / 86400.0
    )
    return solved


def _assemble_chart(
    birth_utc: str | None,
    solved: dict[str, Any],
    personality_positions: dict[str, Any],
    personality_time: dict[str, Any] | EpochTime,
    node_mode: str,
    require_swiss_files: bool,
    backend: str = "swieph",
) -> dict[str, Any]:
    design_positions = positions_at_tt(
        solved["time"]["jd_tt"],
        node_mode,
        require_swiss_files=require_swiss_files,
        backend=backend,
    )
    sides = {
        side: [
            {
                "body": body,
                **state,
                **_rational_activation(activation_longitude_fraction(state)),
            }
            for body, state in pos_map.items()
        ]
        for side, pos_map in (
            ("personality", personality_positions),
            ("design", design_positions),
        )
    }
    graph = bodygraph(
        (p["gate"] for p in sides["personality"]),
        (p["gate"] for p in sides["design"]),
    )
    suns = {
        side: next(a for a in items if a["body"] == "Sun")
        for side, items in sides.items()
    }
    profile = f"{suns['personality']['line']}/{suns['design']['line']}"
    if profile not in VALID_PROFILES:
        raise RuntimeError("太阳弧与人生角色不一致，拒绝输出无效 Profile")
    angle = (
        "juxtaposition"
        if profile == "4/1"
        else ("right" if suns["personality"]["line"] <= 4 else "left")
    )
    cross_gates = [
        next(a["gate"] for a in sides[side] if a["body"] == body)
        for side, body in (
            ("personality", "Sun"),
            ("personality", "Earth"),
            ("design", "Sun"),
            ("design", "Earth"),
        )
    ]
    return {
        "birth_utc": birth_utc,
        "design_utc": solved["utc_label"],
        "design_solver": solved["solver"],
        "time_scales": {"personality": personality_time, "design": solved["time"]},
        "activations": sides,
        "variables": variables_from_activations(sides),
        "bodygraph": graph,
        "definition_bridging": definition_bridging(graph),
        "profile": profile,
        "incarnation_cross": {
            "gates": cross_gates,
            "order": [
                "personality_sun",
                "personality_earth",
                "design_sun",
                "design_earth",
            ],
            "angle": angle,
            **cross_identifier(cross_gates[0], angle),
        },
    }


def chart_at(
    birth: datetime,
    node_mode: str = "true",
    *,
    require_swiss_files: bool = False,
) -> dict[str, Any]:
    if birth.utcoffset() is None:
        raise ValueError("出生瞬间必须带时区")
    birth = birth.astimezone(timezone.utc)
    time = ephemeris_time(birth)
    if time.jd_tt is None:
        raise RuntimeError("人类图需要可用的 TT 星历时刻")
    solved = solve_design_epoch(birth, require_swiss_files=require_swiss_files)
    p_pos = positions_at_tt(
        time.jd_tt, node_mode, require_swiss_files=require_swiss_files
    )
    p_time = {
        "jd_tt": time.jd_tt,
        "jd_ut1": time.jd_ut1,
        "method": time.method,
        "future_leap_seconds_assumed_unchanged": time.future_leap_seconds_assumed_unchanged,
        "utc_is_leap_second": False,
        "utc_label_status": "unique_civil_label",
    }
    return _assemble_chart(
        birth.isoformat(), solved, p_pos, p_time, node_mode, require_swiss_files
    )


def chart_at_tt(
    birth_jd_tt: float,
    node_mode: str = "true",
    *,
    require_swiss_files: bool = False,
    backend: str = "swieph",
) -> dict[str, Any]:
    if not math.isfinite(birth_jd_tt):
        raise ValueError("出生 TT 必须为有限数值")
    context = epoch_context_at_tt(birth_jd_tt, method="continuous_TT_interval_sample")
    solved = solve_design_epoch_tt(
        birth_jd_tt, require_swiss_files=require_swiss_files, backend=backend
    )
    p_pos = positions_at_tt(
        birth_jd_tt, node_mode, require_swiss_files=require_swiss_files, backend=backend
    )
    return _assemble_chart(
        context["utc_label"],
        solved,
        p_pos,
        context["time"],
        node_mode,
        require_swiss_files,
        backend,
    )
