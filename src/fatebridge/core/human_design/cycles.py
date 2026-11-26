"""First-cycle contacts (Saturn return, Uranus opposition, Chiron return) in continuous TT."""

from __future__ import annotations

import math
import re
from datetime import date, datetime, timedelta, timezone
from fractions import Fraction
from typing import Any, Callable

from fatebridge.core.astro import runtime
from fatebridge.core.astro.time_scales import ephemeris_time
from fatebridge.core.human_design.mechanics import position_flag_model
from fatebridge.core.human_design.time import (
    ConfirmedLeapSecond,
    epoch_context_at_tt,
    resolve_birth_clock,
)
from fatebridge.utils.civil_time import datetime_fromisoformat_preserving_offset
from fatebridge.utils.errors import EphemerisSourceError
from fatebridge.utils.timezones import parse_timezone_name

HORIZON_DAYS = 65 * 365.25
STEP_DAYS = 2.0
ROOT_SECONDS = 0.0002
RESIDUAL_DEGREES = 1e-7
BODIES: dict[str, tuple[int, float]] = {
    "Saturn": (6, 360.0),
    "Uranus": (7, 180.0),
    "Chiron": (15, 360.0),
}
Row = list[float | int]
Reader = Callable[[float], Row]

LEAP_REFERENCE = re.compile(
    r"(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):60(?:\.(\d{1,6}))?(Z|[+-]\d{2}:\d{2})"
)
REDUCED_FRACTION_PATTERN = re.compile(
    r"(?P<date>[0-9]{4}(?:-[0-9]{2}-[0-9]{2}|[0-9]{4}|-W[0-9]{2}(?:-[0-9])?|W[0-9]{2}[0-9]?))"
    r"[\s\S](?P<clock>[0-9]{2}(?::?[0-9]{2})?)[.,](?P<fraction>[0-9]{1,6})"
    r"(?P<offset>Z|[+-][0-9]{2}(?::?[0-9]{2})?(?::?[0-9]{2})?(?:[.,][0-9]{1,6})?)?"
)


def validate_reference_precision(value: str) -> None:
    if re.search(r"[.,]\d{7,}", value):
        raise ValueError("cycle_reference_datetime 的小数秒最多6位，不静默截断")


def reference_leap_second(value: str) -> ConfirmedLeapSecond | None:
    leap = LEAP_REFERENCE.fullmatch(value)
    if leap is None:
        return None
    y, m, d, h, minute, fraction, offset = leap.groups()
    anchor = datetime(
        int(y),
        int(m),
        int(d),
        int(h),
        int(minute),
        59,
        int((fraction or "").ljust(6, "0")),
        tzinfo=parse_timezone_name(offset),
    )
    return ConfirmedLeapSecond.from_utc_anchor(anchor.astimezone(timezone.utc))


def _portable_base(match: re.Match[str]) -> datetime:
    calendar = match["date"].replace("-", "")
    if "W" in calendar:
        day = date.fromisocalendar(
            int(calendar[:4]), int(calendar[5:7]), int(calendar[7:] or "1")
        )
    else:
        day = date(int(calendar[:4]), int(calendar[4:6]), int(calendar[6:]))
    clock = match["clock"].replace(":", "")
    offset = match["offset"] or ""
    if offset == "Z":
        offset = "+00:00"
    elif offset:
        whole, dot, fraction = offset[1:].replace(",", ".").partition(".")
        whole = whole.replace(":", "").ljust(6, "0")
        offset = offset[0] + ":".join((whole[:2], whole[2:4], whole[4:]))
        if dot:
            offset += "." + fraction.ljust(6, "0")
    return datetime_fromisoformat_preserving_offset(
        f"{day.isoformat()}T{clock[:2]}:{clock[2:] or '00'}:00{offset}"
    )


def reference_datetime(value: str) -> datetime:
    validate_reference_precision(value)
    match = REDUCED_FRACTION_PATTERN.fullmatch(value)
    try:
        parsed = datetime_fromisoformat_preserving_offset(value.replace("Z", "+00:00"))
    except ValueError:
        if match is None:
            raise
        parsed = _portable_base(match)
    if match is None:
        return parsed
    digits = match["fraction"]
    unit_seconds = 3600 if len(match["clock"]) == 2 else 60
    micros = int(digits) * unit_seconds * (10 ** (6 - len(digits)))
    return parsed.replace(microsecond=0) + timedelta(microseconds=micros)


def reference_epoch(value: str) -> tuple[str, float]:
    validate_reference_precision(value)
    leap = reference_leap_second(value)
    if leap is not None:
        return leap.utc_label, leap.tt.as_float()
    moment = reference_datetime(value)
    if moment.utcoffset() is None:
        raise ValueError("cycle_reference_datetime 必须带明确时区或UTC偏移")
    moment = moment.astimezone(timezone.utc)
    if not 1800 <= moment.year <= 2600:
        raise ValueError("cycle_reference_datetime 的UTC年份须在1800至2600之间")
    tt = ephemeris_time(moment).jd_tt
    if tt is None:
        raise ValueError("cycle_reference_datetime 无可用TT")
    return moment.isoformat(), tt


def validate_cycle_reference(
    *,
    birth_year: int,
    birth_month: int,
    birth_day: int,
    birth_hour: int,
    birth_minute: int,
    birth_timezone: str,
    cycle_reference_datetime: str,
    birth_second: int = 0,
) -> None:
    """Validate cycle reference instant is not before birth in continuous TT (in-process)."""
    clock = resolve_birth_clock(
        birth_year=birth_year,
        birth_month=birth_month,
        birth_day=birth_day,
        birth_hour=birth_hour,
        birth_minute=birth_minute,
        birth_second=birth_second,
        birth_timezone=birth_timezone,
    )
    _, reference_tt = reference_epoch(cycle_reference_datetime)
    birth_tt = (
        clock.jd_tt if clock.leap_second else ephemeris_time(clock.utc_anchor).jd_tt
    )
    if birth_tt is None or reference_tt < birth_tt - 1e-12:
        raise ValueError("周期评估时刻不能早于出生瞬间")


def _increment(longitude: float, previous: float) -> Fraction:
    return (Fraction(longitude) - Fraction(previous) + 180) % 360 - 180


def _derive_body_contacts(
    body: str, birth_tt: float, read: Reader, *, require_swiss_files: bool = False
) -> dict[str, Any]:
    _, target = BODIES[body]
    target_exact = Fraction(target)
    contacts: list[dict[str, Any]] = []
    end = birth_tt + HORIZON_DAYS
    model: str | None = None
    first: Row | None = None

    def at(t: float) -> Row:
        nonlocal model
        row = read(t)
        actual = position_flag_model(int(row[3]))
        if require_swiss_files and actual != "swieph":
            raise EphemerisSourceError("required_swiss_backend_unavailable")
        if model is None:
            model = actual
        return row

    def crossing(left: Row, lp: Fraction, right: Row, rp: Fraction) -> dict[str, Any]:
        lo, hi, lv, hv = left, right, lp - target_exact, rp - target_exact
        for _ in range(128):
            if lv == 0:
                hi, hv = lo, lv
                break
            if hv == 0:
                lo, lv = hi, hv
                break
            if math.nextafter(float(lo[0]), math.inf) >= hi[0]:
                break
            t = float(lo[0] + (hi[0] - lo[0]) / 2)
            if t in (lo[0], hi[0]):
                break
            mid = at(t)
            mv = lv + _increment(float(mid[1]), float(lo[1]))
            if (mv > 0) == (lv > 0):
                lo, lv = mid, mv
            else:
                hi, hv = mid, mv
        solved, residual = min(
            ((lo, lv), (hi, hv)), key=lambda item: (abs(item[1]), item[0][0])
        )
        epoch = epoch_context_at_tt(
            float(solved[0]), method="human_design_first_cycle_contact_TT"
        )
        return {
            "jd_tt": float(solved[0]),
            "utc_label": epoch["utc_label"],
            "longitude": solved[1],
            "longitude_speed": solved[2],
            "motion": (
                "direct"
                if solved[2] > 0
                else ("retrograde" if solved[2] < 0 else "stationary")
            ),
            "residual_degrees": float(residual),
        }

    try:
        first = at(birth_tt)
        left, phase = first, Fraction(0)
        steps = math.ceil(HORIZON_DAYS / STEP_DAYS)
        for k in range(1, steps + 1):
            t = min(birth_tt + k * STEP_DAYS, end)
            right = at(t)
            right_phase = phase + _increment(float(right[1]), float(left[1]))
            if (
                min(phase, right_phase) <= target_exact <= max(phase, right_phase)
                and phase != right_phase
            ):
                contacts.append(crossing(left, phase, right, right_phase))
            left, phase = right, right_phase
        status = "sampled_search_completed"
        failure = None
    except Exception as exc:
        status = "unavailable" if first is None else "partial"
        failure = {"reason": str(exc)}

    return {
        "body": body,
        "target_arc_degrees": target,
        "birth_jd_tt": birth_tt,
        "natal_longitude": first[1] if first is not None else None,
        "native_return_flag_model": model,
        "status": status,
        "failure": failure,
        "contacts": contacts,
    }


def calculate_cycle_context(
    chart: dict[str, Any],
    reference: str | None,
    *,
    require_swiss_files: bool,
) -> dict[str, Any]:
    if runtime.swe is None:
        raise RuntimeError("人类图周期需要 Swiss Ephemeris")
    birth_tt = chart["time_scales"]["personality"]["jd_tt"]
    ref_label, ref_tt = (
        reference_epoch(reference) if reference is not None else (None, None)
    )
    if ref_tt is not None and ref_tt < birth_tt - 1e-12:
        raise ValueError("周期评估时刻不能早于出生瞬间")

    bodies_out: list[dict[str, Any]] = []
    for body, (body_id, _) in BODIES.items():
        cache: dict[float, Row] = {}

        def read(t: float, _id: int = body_id, _cache: dict[float, Row] = cache) -> Row:
            if t not in _cache:
                coords, flags = runtime.ephemeris_call(
                    "calc", t, _id, runtime.swe.FLG_SWIEPH | runtime.swe.FLG_SPEED
                )
                _cache[t] = [t, float(coords[0]), float(coords[3]), int(flags)]
            return _cache[t]

        row = _derive_body_contacts(
            body, birth_tt, read, require_swiss_files=require_swiss_files
        )
        if ref_tt is not None and row["contacts"]:
            if ref_tt < row["contacts"][0]["jd_tt"]:
                row["reference_relation"] = "before_first_observed_contact"
            elif ref_tt > row["contacts"][-1]["jd_tt"]:
                row["reference_relation"] = "after_last_observed_contact"
            else:
                row["reference_relation"] = "between_observed_contacts"
        else:
            row["reference_relation"] = None
        bodies_out.append(row)

    return {
        "method_id": "human_design_first_cycle_contacts_v2",
        "status": (
            "computed_finite_search"
            if all(r["status"] == "sampled_search_completed" for r in bodies_out)
            else "partial"
        ),
        "reference_utc": ref_label,
        "reference_jd_tt": ref_tt,
        "birth_jd_tt": birth_tt,
        "bodies": bodies_out,
    }


def cycle_summary(context: dict[str, Any], profile: str) -> dict[str, Any]:
    if context.get("status") == "not_requested":
        return {
            "status": "not_requested",
            "reference_utc": None,
            "bodies": [],
            "sixth_line": {
                "applicable": "6" in profile.split("/"),
                "phase_status": "not_assessed",
                "current_phase": None,
            },
        }
    return {
        "status": context["status"],
        "reference_utc": context["reference_utc"],
        "bodies": [
            {
                "body": row["body"],
                "status": row["status"],
                "contact_count": len(row["contacts"]),
                "reference_relation": row.get("reference_relation"),
                "contacts": row["contacts"],
            }
            for row in context["bodies"]
        ],
        "sixth_line": {
            "applicable": "6" in profile.split("/"),
            "phase_status": (
                "unassigned_source_contact_conventions_unresolved"
                if "6" in profile.split("/")
                else "not_applicable_no_sixth_profile_line"
            ),
            "current_phase": None,
        },
    }
