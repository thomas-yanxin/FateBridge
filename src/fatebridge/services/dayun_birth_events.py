"""Probe nominal calendar-carry events under the existing dayun policy."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from typing import Literal, Mapping, TypedDict

from fatebridge.core.calendar import BaZiCalendar
from fatebridge.core.timing import TimingAnalysis
from fatebridge.services.birth_time_events import (
    BirthEventProbeRecord,
    BirthEventRecord,
    NatalEventPayload,
    NatalEventProbe,
    UnresolvedBirthEvent,
)
from fatebridge.services.dayun_analysis_events import collect_dayun_analysis_events
from fatebridge.services.dayun_boundary_clock_events import (
    BoundaryClockScan,
    collect_dayun_boundary_clock_events,
)
from fatebridge.services.dayun_future_events import (
    FutureClockScan,
    collect_future_dayun_gap_events,
)
from fatebridge.services.dayun_wall_cells import build_dayun_wall_cells
from fatebridge.utils.civil_clock import utc_instant
from fatebridge.utils.civil_time import CivilPoint, ZonedCalendar, utc_calendar
from fatebridge.utils.clock_events import birth_civil_clock_cuts
from fatebridge.utils.solar_time import NormalizedBirthTime, rebase_birth_clock
from fatebridge.utils.timezones import parse_timezone_name

MONTH_CARRY = timedelta(hours=6)  # 30 nominal days / 120 offset seconds per second.


class DayunBirthEventPayload(TypedDict):
    method_id: Literal["dayun_all_boundary_gap_and_analysis_probes_v4"]
    status: Literal["partial_unresolved_cells", "calculated_probes"]
    range_basis: str
    clock_basis: str
    nominal_month_carry_seconds: int
    guard_probe_offsets_microseconds: list[int]
    events: list[BirthEventRecord]
    probes: list[BirthEventProbeRecord]
    probe_count: int
    future_clock_scan: FutureClockScan
    boundary_clock_scan: BoundaryClockScan
    unresolved_cells: list[UnresolvedBirthEvent]
    unresolved_layers: list[str]
    continuous_completeness_certified: Literal[False]
    physical_precision_certified: Literal[False]
    interpretation_scope: str


@dataclass(frozen=True, kw_only=True)
class DayunBirthEventAssessment:
    payload: DayunBirthEventPayload
    probes: tuple[NatalEventProbe, ...]


def collect_dayun_birth_event_probes(
    template: NormalizedBirthTime,
    start: datetime,
    end: datetime,
    gender: str | None,
    *,
    natal_events: NatalEventPayload,
    analysis_moment: datetime | None = None,
    known_clocks: Mapping[datetime, NormalizedBirthTime] | None = None,
) -> DayunBirthEventAssessment:
    """Probe the selected Jie carry points and the inverse images of Dayun boundaries."""
    low, high = utc_instant(start), utc_instant(end)
    if high < low or high - low > timedelta(minutes=240):
        raise ValueError("大运出生事件需要顺序明确且不超过240分钟的实际范围")
    clocks = dict(known_clocks or {})
    low_day = utc_calendar(low).julian_day_exact()
    high_day = utc_calendar(high).julian_day_exact()

    def clock_at(at: datetime) -> NormalizedBirthTime:
        if at not in clocks:
            clocks[at] = rebase_birth_clock(template, at)
        return clocks[at]

    cuts = {low}
    jie_guards = set()
    events: list[BirthEventRecord] = []
    # note (dayun): Partition raw civil changes separately from the corrected natal clock.
    birth_zone = parse_timezone_name(template.timezone)
    clock_cuts, _ = birth_civil_clock_cuts(birth_zone, low, high, boundary="date")
    clock_scope = (
        "fixed_offset_civil_clock_microsecond"
        if isinstance(birth_zone, timezone)
        else "loaded_civil_clock_integer_utc_second"
    )
    for at, _ in clock_cuts:
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
                    "precision_scope": clock_scope,
                },
            }
        )
    for event in natal_events.get("events", []):
        if event["kind"] == "jie":
            for boundary in {event["lower_utc"], event["upper_utc"]}:
                at = utc_instant(datetime.fromisoformat(boundary))
                if low <= at <= high:
                    cuts.add(at)
                    jie_guards.add(at)
    ordered = sorted(cuts | {high})
    intervals = list(zip(ordered, ordered[1:])) or [(low, high)]
    seen = set()
    for left, right in intervals:
        representative = left + (right - left) / 2
        resolution = TimingAnalysis.resolve_dayun_start(
            clock_at(representative).input_datetime, gender, template.timezone
        )
        reference = resolution.target_term
        root = reference.point
        forward = resolution.forward_direction
        left_day = utc_calendar(left).julian_day_exact()
        right_day = utc_calendar(right).julian_day_exact()
        distances = (
            (root.day - right_day, root.day - left_day)
            if forward
            else (left_day - root.day, right_day - root.day)
        )
        first = max(0, distances[0] // Fraction(1, 4))
        last = distances[1] // Fraction(1, 4)
        if last - first > 2:
            raise ValueError("名义月进位跨度异常，不能静默裁剪")
        for index in range(first, last + 1):
            point = CivilPoint(root.day + (-1 if forward else 1) * Fraction(index, 4))
            if not (
                low_day <= point.day <= high_day and left_day <= point.day <= right_day
            ):
                continue
            key = (point.day, root.day, forward)
            if key in seen:
                continue
            seen.add(key)
            lower, upper = point.nominal_calendar_bracket()
            left_label = ZonedCalendar(lower, timezone.utc).require_datetime()
            right_label = ZonedCalendar(upper, timezone.utc).require_datetime()
            cuts.update((left_label, right_label))
            if low <= right_label + timedelta(microseconds=1) <= high:
                cuts.add(right_label + timedelta(microseconds=1))
            events.append(
                {
                    "kind": "dayun_nominal_month_carry",
                    "name": f"{index}个名义月进位",
                    "lower_utc": left_label.isoformat(),
                    "upper_utc": right_label.isoformat(),
                    "at_utc": right_label.isoformat(),
                    "bracket_width_seconds": (right_label - left_label).total_seconds(),
                    "civil_point": point.to_record(),
                    "reference_point": root.to_record(),
                    "bracket_basis": "nominal_gregorian_microsecond_enclosure_v1",
                    "source": {
                        "policy": "three_days_one_year_calendar_v1",
                        "direction": "顺行" if forward else "逆行",
                        "reference_jie": reference.name,
                        "reference_at_utc": utc_instant(reference.moment).isoformat(),
                        "reference_provider": reference.resolution_provider,
                        "precision_scope": "computed_calendar_carry_not_physical_error_bound",
                    },
                }
            )
    future_cuts = cuts | {datetime.fromisoformat(e["at_utc"]) for e in events}
    cells = build_dayun_wall_cells(
        template.timezone, gender, future_cuts, high, clock_at
    )
    # note (dayun): Share the original cells so unrelated probes cannot split inverse brackets.
    future_events, unresolved_cells, future_scan, future_gaps = (
        collect_future_dayun_gap_events(template, analysis_moment, cells)
    )
    analysis_events, analysis_unresolved = collect_dayun_analysis_events(
        template, gender, analysis_moment, cells, clock_at, future_gaps
    )
    events.extend(analysis_events)
    events.extend(future_events)
    unresolved_cells.extend(analysis_unresolved)
    boundary_events, boundary_unresolved, boundary_scan = (
        collect_dayun_boundary_clock_events(template, cells)
    )
    events.extend(boundary_events)
    unresolved_cells.extend(boundary_unresolved)
    events.sort(key=lambda e: (e["at_utc"], e["kind"]))
    instants = set()
    # note (dayun): Keep non-grid Jie guards when the first wall label selects a different reference.
    guard_centers = jie_guards | {
        datetime.fromisoformat(boundary)
        for event in events
        for boundary in (event["lower_utc"], event["upper_utc"])
    }
    for at in guard_centers:
        for displacement in [-1000, -1, 0, 1, 1000]:
            probe = at + timedelta(microseconds=displacement)
            if low <= probe <= high:
                instants.add(probe)
    probes = []
    records: list[BirthEventProbeRecord] = []
    for instant in sorted(instants):
        normalized = clock_at(instant)
        pillars = BaZiCalendar.get_four_pillars(
            normalized.corrected_datetime,
            timezone_name=template.timezone,
            civil_datetime=normalized.input_datetime,
        )
        probes.append(NatalEventProbe(normalized=normalized, pillars=pillars))
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
