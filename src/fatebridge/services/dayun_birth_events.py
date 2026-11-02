"""Probe nominal calendar-carry events under the existing dayun policy."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Mapping, Optional, Tuple

from fatebridge.core.calendar import BaZiCalendar
from fatebridge.core.timing import TimingAnalysis
from fatebridge.services.birth_time_events import NatalEventProbe
from fatebridge.services.dayun_analysis_events import collect_dayun_analysis_events
from fatebridge.services.dayun_boundary_clock_events import (
    collect_dayun_boundary_clock_events,
)
from fatebridge.services.dayun_future_events import collect_future_dayun_gap_events
from fatebridge.utils.civil_clock import utc_instant
from fatebridge.utils.solar_time import NormalizedBirthTime, rebase_birth_clock

MONTH_CARRY = timedelta(hours=6)  # 30 nominal days / 120 offset seconds per second.


@dataclass(frozen=True)
class DayunBirthEventAssessment:
    payload: Dict[str, Any]
    probes: Tuple[NatalEventProbe, ...]


def collect_dayun_birth_event_probes(
    template: NormalizedBirthTime,
    start: datetime,
    end: datetime,
    gender: Optional[str],
    *,
    natal_events: Mapping[str, Any],
    analysis_moment: Optional[datetime] = None,
    known_clocks: Optional[Mapping[datetime, NormalizedBirthTime]] = None,
) -> DayunBirthEventAssessment:
    """Supplement observed states, without claiming continuous extrema.

    One nominal month is 30 days, while its civil-calendar realization has
    variable length. Derive every carry from the selected actual Jie, never
    from a chart-specific rule or a source-case lookup.
    """
    low, high = utc_instant(start), utc_instant(end)
    if high < low or high - low > timedelta(minutes=240):
        raise ValueError("大运出生事件需要顺序明确且不超过240分钟的实际范围")
    clocks = dict(known_clocks or {})

    def clock_at(at: datetime) -> NormalizedBirthTime:
        if at not in clocks:
            clocks[at] = rebase_birth_clock(template, at)
        return clocks[at]

    cuts = {low, high}
    events: list[Dict[str, Any]] = []
    # Dayun uses the raw civil birth date even when natal pillars use an
    # apparent clock. Partition its date and offset changes independently.
    previous = clock_at(low).input_datetime
    birth_zone = previous.tzinfo
    at = low.replace(microsecond=0) + timedelta(seconds=1)
    while at <= high:
        current = at.astimezone(birth_zone)
        if (current.date(), current.utcoffset()) != (
            previous.date(),
            previous.utcoffset(),
        ):
            cuts.add(at)
            events.append(
                {
                    "kind": "dayun_civil_clock",
                    "name": "大运原始民用日期或偏移变更",
                    "lower_utc": at.isoformat(),
                    "upper_utc": at.isoformat(),
                    "at_utc": at.isoformat(),
                    "bracket_width_seconds": 0.0,
                    "source": {
                        "timezone": template.timezone,
                        "precision_scope": "loaded_civil_clock_integer_utc_second",
                    },
                }
            )
        previous = current
        at += timedelta(seconds=1)
    for event in natal_events.get("events", []):
        if event["kind"] == "jie":
            at = utc_instant(datetime.fromisoformat(event["at_utc"]))
            if low <= at <= high:
                cuts.add(at)
    ordered = sorted(cuts)
    intervals = list(zip(ordered, ordered[1:])) or [(low, high)]
    seen = set()
    for left, right in intervals:
        representative = left + (right - left) / 2
        details = TimingAnalysis.calculate_dayun_start_details(
            clock_at(representative).input_datetime, gender, template.timezone
        )
        reference = details["reference_term"]
        root = utc_instant(datetime.fromisoformat(reference["datetime_with_offset"]))
        forward = details["forward_direction"]
        distances = (
            (root - right, root - left) if forward else (left - root, right - root)
        )
        first = max(0, distances[0] // MONTH_CARRY)
        last = distances[1] // MONTH_CARRY
        if last - first > 2:
            raise ValueError("名义月进位跨度异常，不能静默裁剪")
        for index in range(first, last + 1):
            at = root + (-1 if forward else 1) * index * MONTH_CARRY
            if not low <= at <= high or not left <= at <= right:
                continue
            key = (at, root, forward)
            if key in seen:
                continue
            seen.add(key)
            cuts.add(at)
            if low <= at + timedelta(microseconds=1) <= high:
                cuts.add(at + timedelta(microseconds=1))
            events.append(
                {
                    "kind": "dayun_nominal_month_carry",
                    "name": f"{index}个名义月进位",
                    "lower_utc": at.isoformat(),
                    "upper_utc": at.isoformat(),
                    "at_utc": at.isoformat(),
                    "bracket_width_seconds": 0.0,
                    "source": {
                        "policy": "three_days_one_year_calendar_v1",
                        "direction": "顺行" if forward else "逆行",
                        "reference_jie": reference["name"],
                        "reference_at_utc": root.isoformat(),
                        "reference_provider": details["reference_term_resolution"],
                        "precision_scope": "computed_calendar_carry_not_physical_error_bound",
                    },
                }
            )
    future_cuts = cuts | {datetime.fromisoformat(e["at_utc"]) for e in events}
    analysis_events, analysis_unresolved = collect_dayun_analysis_events(
        template, gender, analysis_moment, future_cuts, clock_at
    )
    events.extend(analysis_events)
    # Future-clock inverses require initial-wall affine cells. Splitting them
    # at an unrelated projected-year/analysis inverse can strand its floor
    # and ceil on opposite sides of a redundant cut.
    future_events, unresolved_cells, future_scan = collect_future_dayun_gap_events(
        template, gender, analysis_moment, future_cuts, clock_at
    )
    events.extend(future_events)
    unresolved_cells.extend(analysis_unresolved)
    boundary_events, boundary_unresolved, boundary_scan = (
        collect_dayun_boundary_clock_events(template, gender, future_cuts, clock_at)
    )
    events.extend(boundary_events)
    unresolved_cells.extend(boundary_unresolved)
    events.sort(key=lambda e: (e["at_utc"], e["kind"]))
    instants = set()
    for event in events:
        for boundary in {event["lower_utc"], event["upper_utc"]}:
            at = datetime.fromisoformat(boundary)
            for displacement in [-1000, -1, 0, 1, 1000]:
                probe = at + timedelta(microseconds=displacement)
                if low <= probe <= high:
                    instants.add(probe)
    probes = []
    records = []
    for instant in sorted(instants):
        normalized = clock_at(instant)
        pillars = BaZiCalendar.get_four_pillars(
            normalized.corrected_datetime,
            timezone_name=template.timezone,
            civil_datetime=normalized.input_datetime,
        )
        probes.append(NatalEventProbe(normalized, pillars))
        records.append(
            {
                "instant_utc": instant.isoformat(),
                "civil_datetime": normalized.input_datetime.isoformat(),
                "corrected_clock_datetime": normalized.corrected_datetime.isoformat(),
                "pillars": {k: "".join(v) for k, v in pillars.items()},
            }
        )
    return DayunBirthEventAssessment(
        payload={
            "method_id": "dayun_all_boundary_gap_and_analysis_probes_v4",
            "status": (
                "partial_unresolved_cells" if unresolved_cells else "calculated_probes"
            ),
            "range_basis": "elapsed_utc_minutes_about_nominal_reference",
            "clock_basis": "civil_actual_instant_for_dayun_corrected_clock_for_natal",
            "nominal_month_carry_seconds": int(MONTH_CARRY.total_seconds()),
            "guard_probe_offsets_microseconds": [-1000, -1, 0, 1, 1000],
            "events": events,
            "probes": records,
            "probe_count": len(probes),
            "future_clock_scan": future_scan,
            "boundary_clock_scan": boundary_scan,
            "unresolved_cells": unresolved_cells,
            "unresolved_layers": [
                "all_continuous_current_dayun_state_changes",
                "continuous_future_clock_and_boundary_extrema_not_certified",
                "continuous_boundary_extrema_and_near_carry_floating_root_order",
                "birth_record_error_model_and_physical_time_accuracy",
            ],
            "continuous_completeness_certified": False,
            "physical_precision_certified": False,
            "interpretation_scope": "补充民用出生日期、名义月进位、分析时刻、十年闰日裁剪、分析日附近回拨及全部配置十年边界墙钟范围的跳时结束逆像探针；跳时范围扫描也适用于显式年龄，三日一年与公历加法政策不变。探针包络不是连续极值，微秒是派生数值位置，不是出生记录或物理精度。",
        },
        probes=tuple(probes),
    )
