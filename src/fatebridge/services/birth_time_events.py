"""Supplement the elapsed-minute uncertainty grid with natal event probes."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal, Mapping, TypedDict

from typing_extensions import NotRequired

from fatebridge.core.almanac import (
    BAZI_MONTH_START_TERMS,
    get_adjacent_solar_terms,
    require_calculated_solar_term,
)
from fatebridge.core.calendar import BaZiCalendar
from fatebridge.utils.civil_clock import utc_instant
from fatebridge.utils.civil_time import CivilPointRecord, ZonedCalendar, utc_calendar
from fatebridge.utils.clock_events import birth_civil_clock_cuts
from fatebridge.utils.solar_time import NormalizedBirthTime, rebase_birth_clock
from fatebridge.utils.timezones import parse_timezone_name

MICROSECOND = timedelta(microseconds=1)
SOLAR_BRACKET = timedelta(milliseconds=1)


class BirthEventRecord(TypedDict):
    kind: str
    name: str
    lower_utc: str
    upper_utc: str
    at_utc: str
    bracket_width_seconds: float
    source: dict[str, str]
    civil_point: NotRequired[CivilPointRecord]
    reference_point: NotRequired[CivilPointRecord]
    bracket_basis: NotRequired[str]


class UnresolvedBirthEvent(TypedDict):
    lower_utc: NotRequired[str]
    upper_utc: NotRequired[str]
    reason: str
    event_indices: NotRequired[list[int]]
    decade_boundary_index: NotRequired[int]


class BirthEventProbeRecord(TypedDict):
    instant_utc: str
    civil_datetime: str
    corrected_clock_datetime: str
    pillars: dict[str, str]


class NatalEventRegion(TypedDict):
    start_utc: str
    end_utc: str
    end_inclusive: bool
    probe_index: int


class NatalEventPayload(TypedDict):
    method_id: Literal["natal_event_boundary_probes_v1"]
    status: Literal["partial_unresolved_event_order", "calculated_probes"]
    clock_mode: str | None
    range_basis: str
    raw_clock_scan_step_seconds: int | None
    apparent_root_bracket_max_seconds: float
    monotonic_at_minute_anchors: bool | None
    coverage_scope: str
    events: list[BirthEventRecord]
    regions: list[NatalEventRegion]
    probes: list[BirthEventProbeRecord]
    probe_count: int
    endpoint_probe_indices: list[int]
    unresolved_event_orders: list[UnresolvedBirthEvent]
    unresolved_layers: list[str]
    continuous_completeness_certified: Literal[False]
    physical_precision_certified: Literal[False]
    interpretation_scope: str


@dataclass(frozen=True, kw_only=True)
class NatalEventProbe:
    normalized: NormalizedBirthTime
    pillars: dict[str, tuple[str, str]]


@dataclass(frozen=True, kw_only=True)
class NatalEventAssessment:
    payload: NatalEventPayload
    probes: tuple[NatalEventProbe, ...]


def collect_natal_event_probes(
    template: NormalizedBirthTime,
    start: datetime,
    end: datetime,
    *,
    known_clocks: Mapping[datetime, NormalizedBirthTime] | None = None,
) -> NatalEventAssessment:
    """Probe raw civil and solar-clock boundaries within the supplied UTC range."""
    low, high = utc_instant(start), utc_instant(end)
    if high < low or high - low > timedelta(minutes=240):
        raise ValueError("出生事件核对需要顺序明确且不超过240分钟的实际时刻范围")
    zone = parse_timezone_name(template.timezone)
    low_day = utc_calendar(low).julian_day_exact()
    high_day = utc_calendar(high).julian_day_exact()
    clocks: dict[datetime, NormalizedBirthTime] = dict(known_clocks or {})
    events: list[BirthEventRecord] = []
    unresolved: list[UnresolvedBirthEvent] = []
    cuts = {low, high}

    def clock_at(at: datetime) -> NormalizedBirthTime:
        if at not in clocks:
            clocks[at] = rebase_birth_clock(template, at)
        return clocks[at]

    def add_event(
        kind: str,
        name: str,
        left: datetime,
        right: datetime,
        source: dict[str, str],
        *,
        civil_point: CivilPointRecord | None = None,
    ) -> None:
        if right < low or left > high:
            return
        left, right = max(left, low), min(right, high)
        event: BirthEventRecord = {
            "kind": kind,
            "name": name,
            "lower_utc": left.isoformat(),
            "upper_utc": right.isoformat(),
            "at_utc": right.isoformat(),
            "bracket_width_seconds": (right - left).total_seconds(),
            "source": source,
        }
        if civil_point is not None:
            event["civil_point"] = civil_point
            event["bracket_basis"] = "nominal_gregorian_microsecond_enclosure_v1"
        if event not in events:
            events.append(event)
            cuts.update((left, right))

    clock_cuts, scan_step = birth_civil_clock_cuts(
        zone, low, high, boundary="offset" if template.applied else "shichen"
    )
    clock_policy = (
        "fixed_offset_civil_clock"
        if isinstance(zone, timezone)
        else "iana_integer_second_clock"
    )
    for at, civil in clock_cuts:
        add_event(
            "civil_clock",
            civil.isoformat(),
            at,
            at,
            {"policy": clock_policy, "timezone": template.timezone},
        )

    previous_term, following = get_adjacent_solar_terms(low, template.timezone)
    terms = [previous_term] if previous_term.point.day == low_day else []
    for _ in range(64):
        point = following.point
        if point.day > high_day:
            break
        terms.append(following)
        _, upper = point.nominal_calendar_bracket()
        cursor = ZonedCalendar(upper, timezone.utc).require_datetime()
        _, next_term = get_adjacent_solar_terms(cursor, template.timezone)
        if next_term.point.day <= point.day:
            raise ValueError("节令事件迭代没有前进，不能给出完整候选")
        following = next_term
    else:
        raise ValueError("出生范围内节令事件超出核对预算，不能静默裁剪")
    for term in terms:
        if term.name in BAZI_MONTH_START_TERMS:
            require_calculated_solar_term(term)
            if not low_day <= term.point.day <= high_day:
                continue
            lower, upper = term.point.nominal_calendar_bracket()
            add_event(
                "jie",
                term.name,
                ZonedCalendar(lower, timezone.utc).require_datetime(),
                ZonedCalendar(upper, timezone.utc).require_datetime(),
                {
                    "provider": term.resolution_provider,
                    "model": term.ephemeris_model,
                    "precision_scope": "computed_point_not_physical_error_bound",
                },
                civil_point=term.point.to_record(),
            )

    monotonic_anchors: bool | None = None
    if template.applied and high > low:
        monotonic_anchors = True
        anchors = [low]
        at = low + timedelta(minutes=1)
        while at < high:
            anchors.append(at)
            at += timedelta(minutes=1)
        anchors.append(high)
        for a, b in zip(anchors, anchors[1:]):
            first = clock_at(a).corrected_datetime.replace(tzinfo=None)
            last = clock_at(b).corrected_datetime.replace(tzinfo=None)
            if last <= first:
                monotonic_anchors = False
                unresolved.append(
                    {
                        "event_indices": [],
                        "lower_utc": a.isoformat(),
                        "upper_utc": b.isoformat(),
                        "reason": "corrected_clock_not_increasing_at_minute_anchors",
                    }
                )
                continue
            target = first.replace(minute=0, second=0, microsecond=0)
            if target < first:
                target += timedelta(hours=1)
            targets = 0
            while target <= last:
                if target.hour == 0 or target.hour % 2 == 1:
                    targets += 1
                    if targets > 32:
                        raise ValueError("校正钟面跨度异常，不能静默裁剪事件")
                    left, right = a, b
                    if first == target:
                        right = left
                    elif last == target:
                        left = right
                    else:
                        for _ in range(64):
                            if right - left <= SOLAR_BRACKET:
                                break
                            middle = left + (right - left) / 2
                            if middle in (left, right):
                                break
                            value = clock_at(middle).corrected_datetime.replace(
                                tzinfo=None
                            )
                            if value < target:
                                left = middle
                            else:
                                right = middle
                        else:
                            raise ValueError("太阳钟事件括区间未收敛，不能给出已解边界")
                    add_event(
                        "solar_clock",
                        target.isoformat(),
                        left,
                        right,
                        {
                            "policy": template.solar_time_strategy or "unknown",
                            "method": template.equation_of_time_method or "unknown",
                            "precision_scope": "conditional_computational_bracket",
                        },
                    )
                target += timedelta(hours=1)

    events.sort(
        key=lambda event: (event["lower_utc"], event["upper_utc"], event["kind"])
    )
    for index, event in enumerate(events):
        if event["kind"] != "solar_clock" or event["lower_utc"] == event["upper_utc"]:
            continue
        for other_index, other in enumerate(events):
            if (
                other["kind"] == "jie"
                and event["lower_utc"] <= other["upper_utc"]
                and other["lower_utc"] <= event["upper_utc"]
            ):
                unresolved.append(
                    {
                        "event_indices": [index, other_index],
                        "lower_utc": event["lower_utc"],
                        "upper_utc": event["upper_utc"],
                        "reason": "apparent_clock_bracket_overlaps_calculated_jie",
                    }
                )

    instants = set(cuts)
    for cut in cuts:
        for neighbor in (cut - MICROSECOND, cut + MICROSECOND):
            if low <= neighbor <= high:
                instants.add(neighbor)
    intervals = list(zip(sorted(cuts), sorted(cuts)[1:]))
    if not intervals:
        intervals = [(low, high)]
    midpoints = [left + (right - left) / 2 for left, right in intervals]
    instants.update(midpoints)
    ordered_instants = sorted(instants)
    probes: list[NatalEventProbe] = []
    records: list[BirthEventProbeRecord] = []
    for instant in ordered_instants:
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
                "pillars": {key: "".join(value) for key, value in pillars.items()},
            }
        )
    positions = {instant: index for index, instant in enumerate(ordered_instants)}
    # note (clock): The separate end probe retains any state outside the last half-open region.
    regions: list[NatalEventRegion] = [
        {
            "start_utc": left.isoformat(),
            "end_utc": right.isoformat(),
            "end_inclusive": left == right,
            "probe_index": positions[midpoint],
        }
        for (left, right), midpoint in zip(intervals, midpoints)
    ]
    return NatalEventAssessment(
        payload={
            "method_id": "natal_event_boundary_probes_v1",
            "status": (
                "partial_unresolved_event_order" if unresolved else "calculated_probes"
            ),
            "clock_mode": (
                template.solar_time_strategy if template.applied else "raw_civil"
            ),
            "range_basis": "elapsed_utc_minutes_about_nominal_reference",
            "raw_clock_scan_step_seconds": scan_step,
            "apparent_root_bracket_max_seconds": SOLAR_BRACKET.total_seconds(),
            "monotonic_at_minute_anchors": monotonic_anchors,
            "coverage_scope": (
                "calculated_jie_and_raw_clock_events"
                if not template.applied
                else "calculated_jie_and_bracketed_corrected_clock_events"
            ),
            "events": events,
            "regions": regions,
            "probes": records,
            "probe_count": len(probes),
            "endpoint_probe_indices": [positions[low], positions[high]],
            "unresolved_event_orders": unresolved,
            "unresolved_layers": [
                "birth_record_error_model_and_physical_time_accuracy",
                "continuous_dayun_state_changes_and_boundary_extrema",
            ]
            + (
                ["apparent_clock_behavior_inside_numerical_brackets"]
                if template.applied
                else []
            ),
            "continuous_completeness_certified": False,
            "physical_precision_certified": False,
            "interpretation_scope": "派生事件探针补充分钟网格；括区间宽度不是物理精度，有限探针或求根收敛未证明全部连续候选、交运状态与极值。不得将探针频次解释为概率或把派生微秒写回出生档案。",
        },
        probes=tuple(probes),
    )
