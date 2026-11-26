"""Named Canping luck schedules; no implicit first-period or year-wide fallback.

Volume six specifies replacing the birth hour with the active luck branch.
Volume seven separately appends the month-pillar Zi Ping schedule, explicitly
distinguishing it from Heluo's six/nine-year hexagram periods. This module names
that choice and the modern calendar conventions instead of merging the systems.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from fractions import Fraction
from typing import Any, Optional

from dateutil.relativedelta import relativedelta

from fatebridge.core.almanac import get_bazi_year, localize_datetime
from fatebridge.core.jpl_ephemeris import configured_jpl_file
from fatebridge.core.numerology.canping import _verses, _year_ganzhi, compute_number
from fatebridge.core.numerology.canping_solar import (
    ResolvedProjectionBoundary,
    boundary_context,
    resolve_projection_boundary,
)
from fatebridge.core.solar_model_policy import solar_model_policy
from fatebridge.core.timing import TimingAnalysis
from fatebridge.utils.civil_time import (
    CivilPoint,
    UTCCalendar,
    ZonedCalendar,
    parse_civil_iso_clock,
    utc_calendar,
)
from fatebridge.utils.errors import EphemerisSourceError, ParameterError
from fatebridge.utils.timezones import parse_timezone_name

APPENDIX = "bazi_appendix_v1"
CONTINUOUS = "bazi_continuous_v1"
LEGACY = "legacy_minggong_v1"
SOURCE_URL = (
    "https://www.digital.archives.go.jp/DAS/contents/pdf/lossy/03050271000050/0001.pdf"
)
SOURCE_SHA256 = "199c7c1100a86857bc6973da4f0cfb27be473fdd5ede7b0241fc8cdb101877ea"
COMPARISON_POLICY = "retained_nominal_civil_point_v1"


@dataclass(frozen=True)
class ResolvedCanpingInterval:
    """A numerical interval and its separate, explicitly retained labels."""

    start: CivilPoint
    end: CivilPoint
    start_label: ZonedCalendar
    end_label: ZonedCalendar
    year: int
    facts: dict[str, object]
    year_start_boundary: ResolvedProjectionBoundary
    year_end_boundary: ResolvedProjectionBoundary

    def to_record(self) -> dict[str, object]:
        return {
            "start_at": self.start_label.isoformat(),
            "end_at": self.end_label.isoformat(),
            "start_point": self.start.to_record(),
            "end_point": self.end.to_record(),
            "comparison_policy": COMPARISON_POLICY,
            **deepcopy(self.facts),
        }


@dataclass(frozen=True)
class ResolvedAnnualSeries:
    record: dict[str, object]
    intervals: tuple[ResolvedCanpingInterval, ...]


def _utc(moment: datetime) -> UTCCalendar:
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError("配运和查询必须使用带时区的时刻。")
    return utc_calendar(moment)


def appendix_age(
    birth: datetime, reference: datetime | ZonedCalendar
) -> dict[str, Any]:
    """Literal three-day grouping: remainder one discarded, remainder two lent.

    The source does not resolve within-day fractions. Civil calendar date
    counting is an explicit convention of this named profile, not elapsed-day
    precision or a silent adoption of the continuous modern alternative.
    """
    birth_clock = ZonedCalendar.from_datetime(birth)
    reference_clock = (
        reference
        if isinstance(reference, ZonedCalendar)
        else ZonedCalendar.from_datetime(reference)
    )
    days = abs(
        ZonedCalendar(reference_clock.utc, birth_clock.zone).local_ordinal
        - birth.toordinal()
    )
    return {
        "civil_days_to_reference": days,
        "whole_years": (days + 1) // 3,
        "discarded_days": 1 if days % 3 == 1 else 0,
        "borrowed_days": 1 if days % 3 == 2 else 0,
        "policy": "civil_date_difference; remainder_1_discarded_remainder_2_borrowed",
    }


def luck_timeline(
    birth: datetime, gender: str, month_pillar: tuple[str, str], zone: str, method: str
) -> dict[str, Any]:
    if method not in {APPENDIX, CONTINUOUS}:
        raise ValueError("日期配运方法必须为bazi_appendix_v1或bazi_continuous_v1。")
    _utc(birth)
    if gender not in {"男", "女"}:
        raise ValueError("参评配运方向需要明确gender为男或女，不能默认性别。")
    birth = localize_datetime(birth, zone)
    if method == CONTINUOUS:
        timeline = TimingAnalysis.calculate_dayun_timeline(
            birth, gender, month_pillar, zone, periods=12
        )
        timeline["profile_id"] = method
        return timeline
    resolution = TimingAnalysis.resolve_dayun_start(birth, gender, zone)
    term = resolution.target_term
    if not term.has_defined_local_clock:
        raise ParameterError(
            f"参评附法需要{term.name}的当地日期，时区规则未定义该时点的当地钟时。",
            [
                {
                    "path": "request.dayun_method",
                    "code": "undefined_canping_reference_date",
                }
            ],
        )
    start_details = resolution.to_details()
    reference = term.calendar
    offset = appendix_age(birth, reference)
    details = {
        **{
            k: start_details[k]
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
    boundary, preserve_birth = TimingAnalysis._resolve_dayun_calendar_boundary(
        birth, start_wall, 0, zone
    )
    for index, row in enumerate(periods, start=1):
        row["start_at"] = boundary.isoformat()
        boundary, _ = TimingAnalysis._resolve_dayun_calendar_boundary(
            birth, start_wall, 10 * index, zone
        )
        row["end_at"] = boundary.isoformat()
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
    period: Optional[dict], element: str, taisui: str
) -> dict[str, object]:
    if period is None:
        return {"status": "not_started"}
    numbers = compute_number(taisui, period["branch"], element)
    return {
        "status": "active",
        "dayun_index": period["index"],
        "dayunBranch": period["branch"],
        "dayun_pillar": period["pillar"],
        **numbers,
        "verses": _verses(element, numbers, "luck"),
    }


def resolve_annual_series(
    birth: datetime, zone: str, periods: list[dict], element: str, horizon: int = 120
) -> ResolvedAnnualSeries:
    """Retain Lichun/period points through clipping, splitting and selection."""
    if type(horizon) is not int or not 1 <= horizon <= 120:
        raise ValueError("年序范围须为1至120；不是寿命估计。")
    birth_year = get_bazi_year(birth, zone)
    birth_label = ZonedCalendar.from_datetime(birth)
    birth_point = CivilPoint(birth_label.utc.julian_day_exact())
    origin_year = ZonedCalendar(birth_label.utc, parse_timezone_name(zone)).local_parts[
        0
    ]
    environment = solar_model_policy(), configured_jpl_file()
    boundaries = [
        resolve_projection_boundary(
            year,
            zone,
            origin_civil_year=origin_year,
            origin_bazi_year=birth_year,
            horizon=horizon,
        )
        for year in range(birth_year, birth_year + horizon + 1)
    ]
    if environment != (solar_model_policy(), configured_jpl_file()):
        raise EphemerisSourceError("solar_configuration_changed")
    # Dayun boundaries are defined by the named civil birthday mapping. Its
    # labels own these points; solar boundaries above retain their solved point.
    resolved = []
    for period_row in periods:
        start_clock = ZonedCalendar.from_isoformat(period_row["start_at"])
        end_clock = ZonedCalendar.from_isoformat(period_row["end_at"])
        resolved.append(
            (
                CivilPoint(start_clock.utc.julian_day_exact()),
                start_clock,
                CivilPoint(end_clock.utc.julian_day_exact()),
                end_clock,
                period_row,
            )
        )
    rows = []
    intervals = []
    for index, year in enumerate(range(birth_year, birth_year + horizon)):
        previous, following = boundaries[index : index + 2]
        if birth_point.day >= previous.term.point.day:
            start, start_label = birth_point, birth_label
        else:
            start, start_label = previous.term.point, previous.term.calendar
        end, end_label = following.term.point, following.term.calendar
        cuts: dict[Fraction, tuple[CivilPoint, ZonedCalendar]] = {
            start.day: (start, start_label),
            end.day: (end, end_label),
        }
        for a, a_label, b, b_label, _ in resolved:
            if start.day < a.day < end.day:
                cuts[a.day] = (a, a_label)
            if start.day < b.day < end.day:
                cuts[b.day] = (b, b_label)
        ordered = [cuts[key] for key in sorted(cuts)]
        ganzhi = _year_ganzhi(year)
        segments = []
        for (a, a_label), (b, b_label) in zip(ordered, ordered[1:]):
            period = next(
                (p for lo, _, hi, _, p in resolved if lo.day <= a.day < hi.day),
                None,
            )
            if period is None and a.day >= resolved[0][0].day:
                raise ValueError("配运时间轴未覆盖请求年序；不能沿用最后一运。")
            interval = ResolvedCanpingInterval(
                a,
                b,
                a_label,
                b_label,
                year,
                _active_segment(period, element, ganzhi[1]),
                previous,
                following,
            )
            intervals.append(interval)
            segments.append(interval.to_record())
        row = {
            "age": year - birth_year + 1,
            "year": year,
            "ganzhi": ganzhi,
            "taisuiBranch": ganzhi[1],
            "start_at": start_label.isoformat(),
            "end_at": end_label.isoformat(),
            "start_point": start.to_record(),
            "end_point": end.to_record(),
            "comparison_policy": COMPARISON_POLICY,
            "status": "split" if len(segments) > 1 else segments[0]["status"],
            "segments": segments,
        }
        if len(segments) == 1:
            row.update(
                {
                    k: deepcopy(v)
                    for k, v in segments[0].items()
                    if k
                    not in {
                        "start_at",
                        "end_at",
                        "start_point",
                        "end_point",
                        "comparison_policy",
                        "status",
                    }
                }
            )
        rows.append(row)
    receipts = [boundary.to_record() for boundary in boundaries]
    record: dict[str, object] = {
        "element": element,
        "rows": rows,
        "year_boundary": "lichun",
        "birth_pillar_year": birth_year,
        "comparison_policy": COMPARISON_POLICY,
        "age_policy": "sexagenary_year_ordinal; not_elapsed_age_or_lunar_new_year_age",
        "year_boundaries": receipts,
        "solar_context": boundary_context(birth, zone, birth_year, horizon, receipts),
    }
    return ResolvedAnnualSeries(record, tuple(intervals))


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
        start_label = ZonedCalendar.from_isoformat(p["start_at"])
        end_label = ZonedCalendar.from_isoformat(p["end_at"])
        periods.append(
            {
                "index": i,
                "branch": p["branch"],
                "pillar": p["pillar"],
                "start_at": p["start_at"],
                "end_at": p["end_at"],
                "start_point": CivilPoint(
                    start_label.utc.julian_day_exact()
                ).to_record(),
                "end_point": CivilPoint(end_label.utc.julian_day_exact()).to_record(),
                "comparison_policy": COMPARISON_POLICY,
                "start_age": p["age_range"]["start"],
                "end_age": p["age_range"]["end"],
                **numbers,
                "verses": _verses(element, numbers, "luck"),
            }
        )
    resolved_series = resolve_annual_series(birth, zone, periods, element)
    series = resolved_series.record
    selected = None
    if analysis_datetime is not None:
        query = parse_civil_iso_clock(analysis_datetime.replace("Z", "+00:00"))
        if not isinstance(query, UTCCalendar):
            raise ValueError("analysis_datetime须为带时区的ISO时刻。")
        query_clock = ZonedCalendar(query, parse_timezone_name(zone))
        query_day = query_clock.utc.julian_day_exact()
        if query_day < utc_calendar(birth).julian_day_exact():
            raise ValueError("查询时刻不能早于出生时刻。")
        match = next(
            (
                interval
                for interval in resolved_series.intervals
                if interval.start.day <= query_day < interval.end.day
            ),
            None,
        )
        if match is None:
            raise ValueError("查询时刻超出本次年序范围；不外推。")
        selected = match.to_record()
        selected.update(
            {
                "at": query_clock.isoformat(),
                "year": match.year,
                "ganzhi": _year_ganzhi(match.year),
                "year_start_boundary": match.year_start_boundary.to_record(),
                "year_end_boundary": match.year_end_boundary.to_record(),
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
            "comparison_policy": COMPARISON_POLICY,
            "solar_year_context": deepcopy(series["solar_context"]),
        }
    )
    return details, periods, series
