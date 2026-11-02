"""Named Canping luck schedules; no implicit first-period or year-wide fallback.

Volume six specifies replacing the birth hour with the active luck branch.
Volume seven separately appends the month-pillar Zi Ping schedule, explicitly
distinguishing it from Heluo's six/nine-year hexagram periods. This module names
that choice and the modern calendar conventions instead of merging the systems.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Optional, cast

from dateutil.relativedelta import relativedelta
from dateutil.tz import resolve_imaginary

from fatebridge.core.almanac import (
    get_bazi_month_boundaries,
    get_bazi_year,
)
from fatebridge.core.canping import _verses, _year_ganzhi, compute_number
from fatebridge.core.canping_solar import boundary_context, projection_boundary
from fatebridge.core.jpl_ephemeris import configured_jpl_file
from fatebridge.core.solar_model_policy import solar_model_policy
from fatebridge.core.timing import TimingAnalysis
from fatebridge.utils.civil_clock import parse_iso_datetime
from fatebridge.utils.errors import EphemerisSourceError
from fatebridge.utils.timezones import parse_timezone_name

APPENDIX = "bazi_appendix_v1"
CONTINUOUS = "bazi_continuous_v1"
LEGACY = "legacy_minggong_v1"
SOURCE_URL = (
    "https://www.digital.archives.go.jp/DAS/contents/pdf/lossy/03050271000050/0001.pdf"
)
SOURCE_SHA256 = "199c7c1100a86857bc6973da4f0cfb27be473fdd5ede7b0241fc8cdb101877ea"


def _utc(moment: datetime) -> datetime:
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError("配运和查询必须使用带时区的时刻。")
    return moment.astimezone(timezone.utc)


def appendix_age(birth: datetime, reference: datetime) -> dict[str, Any]:
    """Literal three-day grouping: remainder one discarded, remainder two lent.

    The source does not resolve within-day fractions. Civil calendar date
    counting is an explicit convention of this named profile, not elapsed-day
    precision or a silent adoption of the continuous modern alternative.
    """
    _utc(birth)
    _utc(reference)
    days = abs((reference.astimezone(birth.tzinfo).date() - birth.date()).days)
    return {
        "civil_days_to_reference": days,
        "whole_years": (days + 1) // 3,
        "discarded_days": 1 if days % 3 == 1 else 0,
        "borrowed_days": 1 if days % 3 == 2 else 0,
        "policy": "civil_date_difference; remainder_1_discarded_remainder_2_borrowed",
    }


def _boundary(wall: datetime, zone: str) -> datetime:
    return cast(
        datetime,
        resolve_imaginary(wall.replace(tzinfo=parse_timezone_name(zone), fold=0)),
    )


def luck_timeline(
    birth: datetime, gender: str, month_pillar: tuple[str, str], zone: str, method: str
) -> dict[str, Any]:
    if method not in {APPENDIX, CONTINUOUS}:
        raise ValueError("日期配运方法必须为bazi_appendix_v1或bazi_continuous_v1。")
    _utc(birth)
    if gender not in {"男", "女"}:
        raise ValueError("参评配运方向需要明确gender为男或女，不能默认性别。")
    birth = birth.astimezone(parse_timezone_name(zone))
    if method == CONTINUOUS:
        timeline = TimingAnalysis.calculate_dayun_timeline(
            birth, gender, month_pillar, zone, periods=12
        )
        timeline["profile_id"] = method
        return timeline
    details = TimingAnalysis.calculate_dayun_start_details(birth, gender, zone)
    previous, following, _, _ = get_bazi_month_boundaries(birth, zone)
    reference = (following if details["forward_direction"] else previous).moment
    offset = appendix_age(birth, reference)
    details = {
        **{
            k: details[k]
            for k in (
                "forward_direction",
                "year_stem",
                "reference_term",
                "reference_term_resolution",
                "elapsed_seconds",
            )
        },
        "reference_at": reference.isoformat(),
        "start_age_years": offset["whole_years"],
        "within_day_fraction_used": False,
    }
    start_wall = birth.replace(tzinfo=None) + relativedelta(years=offset["whole_years"])
    periods = TimingAnalysis.calculate_dayun_sequence(
        *month_pillar,
        gender,
        details["year_stem"],
        periods=12,
        start_age=offset["whole_years"],
    )
    initial = _boundary(start_wall, zone)
    # Zero whole years means birth itself. Reattaching fold=0 to a confirmed
    # second occurrence would move the initial boundary before actual birth.
    # Later anniversaries still use this profile's named fold/gap convention.
    preserve_birth = offset["whole_years"] == 0 and _utc(initial) != _utc(birth)
    if preserve_birth:
        initial = birth
    for index, row in enumerate(periods):
        row["start_at"] = (
            initial
            if index == 0
            else _boundary(start_wall + relativedelta(years=10 * index), zone)
        ).isoformat()
        row["end_at"] = _boundary(
            start_wall + relativedelta(years=10 * (index + 1)), zone
        ).isoformat()
    return {
        "profile_id": method,
        "method_id": "ziping_month_pillar_three_day_rounding_v1",
        "birth_at": birth.isoformat(),
        "timezone": zone,
        "start_at": periods[0]["start_at"],
        "start_details": details,
        "calendar_offset": offset,
        "calendar_policy": offset["policy"]
        + "; integer_years_added_to_birth_civil_clock",
        "reference_policy": "next_jie_strict_for_forward_previous_jie_inclusive_for_reverse",
        "boundary_policy": "start_inclusive_end_exclusive",
        "dst_policy": (
            "fold_0_gap_forward_initial_birth_preserved"
            if preserve_birth
            else "fold_0_gap_forward"
        ),
        "periods": periods,
    }


def _active_segment(
    start: datetime, end: datetime, period: Optional[dict], element: str, taisui: str
) -> dict[str, Any]:
    row: dict[str, Any] = {"start_at": start.isoformat(), "end_at": end.isoformat()}
    if period is None:
        return {**row, "status": "not_started"}
    numbers = compute_number(taisui, period["branch"], element)
    return {
        **row,
        "status": "active",
        "dayun_index": period["index"],
        "dayunBranch": period["branch"],
        "dayun_pillar": period["pillar"],
        **numbers,
        "verses": _verses(element, numbers, "luck"),
    }


def annual_series(
    birth: datetime, zone: str, periods: list[dict], element: str, horizon: int = 120
) -> dict[str, Any]:
    """Lichun year intervals split at every actual luck boundary, clipped at birth."""
    if type(horizon) is not int or not 1 <= horizon <= 120:
        raise ValueError("年序范围须为1至120；不是寿命估计。")
    birth_year = get_bazi_year(birth, zone)
    environment = solar_model_policy(), configured_jpl_file()
    receipts = [
        projection_boundary(
            year,
            zone,
            origin_civil_year=birth.astimezone(parse_timezone_name(zone)).year,
            origin_bazi_year=birth_year,
            horizon=horizon,
        )
        for year in range(birth_year, birth_year + horizon + 1)
    ]
    if environment != (solar_model_policy(), configured_jpl_file()):
        raise EphemerisSourceError("solar_configuration_changed")
    boundaries = {
        r["year"]: parse_iso_datetime(r["record"]["datetime_with_offset"])
        for r in receipts
    }
    resolved = [
        (parse_iso_datetime(p["start_at"]), parse_iso_datetime(p["end_at"]), p)
        for p in periods
    ]
    rows = []
    for year in range(birth_year, birth_year + horizon):
        start = max((birth, boundaries[year]), key=_utc)
        end = boundaries[year + 1]
        cuts = {_utc(start): start, _utc(end): end}
        for a, b, _ in resolved:
            if _utc(start) < _utc(a) < _utc(end):
                cuts[_utc(a)] = a
            if _utc(start) < _utc(b) < _utc(end):
                cuts[_utc(b)] = b
        ordered = [cuts[key] for key in sorted(cuts)]
        ganzhi = _year_ganzhi(year)
        segments = []
        for a, b in zip(ordered, ordered[1:]):
            period = next(
                (p for lo, hi, p in resolved if _utc(lo) <= _utc(a) < _utc(hi)), None
            )
            if period is None and _utc(a) >= _utc(resolved[0][0]):
                raise ValueError("配运时间轴未覆盖请求年序；不能沿用最后一运。")
            segments.append(_active_segment(a, b, period, element, ganzhi[1]))
        row = {
            "age": year - birth_year + 1,
            "year": year,
            "ganzhi": ganzhi,
            "taisuiBranch": ganzhi[1],
            "start_at": start.isoformat(),
            "end_at": end.isoformat(),
            "status": "split" if len(segments) > 1 else segments[0]["status"],
            "segments": segments,
        }
        if len(segments) == 1:
            row.update(
                {
                    k: deepcopy(v)
                    for k, v in segments[0].items()
                    if k not in {"start_at", "end_at", "status"}
                }
            )
        rows.append(row)
    return {
        "element": element,
        "rows": rows,
        "year_boundary": "lichun",
        "birth_pillar_year": birth_year,
        "age_policy": "sexagenary_year_ordinal; not_elapsed_age_or_lunar_new_year_age",
        "year_boundaries": receipts,
        "solar_context": boundary_context(birth, zone, birth_year, horizon, receipts),
    }


def build_canping_timing(
    *,
    birth: datetime,
    zone: str,
    gender: str,
    month_pillar: tuple[str, str],
    calculation: dict,
    method: str = APPENDIX,
    analysis_datetime: Optional[str] = None,
) -> tuple[dict, list[dict], dict]:
    timeline = luck_timeline(birth, gender, month_pillar, zone, method)
    element = calculation["element"]
    periods = []
    for i, p in enumerate(timeline["periods"]):
        numbers = compute_number(calculation["dayPalaceBranch"], p["branch"], element)
        periods.append(
            {
                "index": i,
                "branch": p["branch"],
                "pillar": p["pillar"],
                "start_at": p["start_at"],
                "end_at": p["end_at"],
                "start_age": p["age_range"]["start"],
                "end_age": p["age_range"]["end"],
                **numbers,
                "verses": _verses(element, numbers, "luck"),
            }
        )
    series = annual_series(birth, zone, periods, element)
    selected = None
    if analysis_datetime is not None:
        query = parse_iso_datetime(analysis_datetime.replace("Z", "+00:00"))
        _utc(query)
        query = query.astimezone(parse_timezone_name(zone))
        if _utc(query) < _utc(birth):
            raise ValueError("查询时刻不能早于出生时刻。")
        match = next(
            (
                (row, segment)
                for row in series["rows"]
                for segment in row["segments"]
                if _utc(parse_iso_datetime(segment["start_at"]))
                <= _utc(query)
                < _utc(parse_iso_datetime(segment["end_at"]))
            ),
            None,
        )
        if match is None:
            raise ValueError("查询时刻超出本次年序范围；不外推。")
        row, segment = match
        selected = deepcopy(segment)
        index = row["year"] - series["birth_pillar_year"]
        selected.update(
            {
                "at": query.isoformat(),
                "year": row["year"],
                "ganzhi": row["ganzhi"],
                "year_start_boundary": deepcopy(series["year_boundaries"][index]),
                "year_end_boundary": deepcopy(series["year_boundaries"][index + 1]),
            }
        )
    details = {k: deepcopy(v) for k, v in timeline.items() if k != "periods"}
    details.update(
        {
            "ruleset_id": "canping_ziping_appendix_bridge_v1",
            "ruleset_version": "1.0.0",
            "source_title": "河洛理數 史應選校訂 卷六及卷七附子平起運法",
            "source_url": SOURCE_URL,
            "source_pdf_sha256": SOURCE_SHA256,
            "source_pdf_pages": [50, 105, 106],
            "source_status": "named_appendix_schedule; volume_six_does_not_uniquely_identify_schedule",
            "calendar_scope": "Modern Jie instants, civil-date rounding or continuous extension, Lichun year boundary and civil date addition are explicitly named conventions.",
            "heluo_period_distinction": "not_heluo_six_or_nine_year_hexagram_periods",
            "selected": selected,
            "solar_year_context": deepcopy(series["solar_context"]),
        }
    )
    return details, periods, series
