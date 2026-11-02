"""NATAL event probes complement an elapsed-minute uncertainty grid.

Calculated boundaries and numerical brackets are not physical error bounds.
This layer does not certify continuous dayun states, extrema or record accuracy.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Mapping, Optional, Tuple

from fatebridge.core.almanac import (
    BAZI_MONTH_START_TERMS,
    get_adjacent_solar_terms,
    require_calculated_solar_term,
)
from fatebridge.core.calendar import BaZiCalendar
from fatebridge.utils.civil_clock import utc_instant
from fatebridge.utils.solar_time import NormalizedBirthTime, rebase_birth_clock
from fatebridge.utils.timezones import parse_timezone_name

MICROSECOND = timedelta(microseconds=1)
SOLAR_BRACKET = timedelta(milliseconds=1)


@dataclass(frozen=True)
class NatalEventProbe:
    normalized: NormalizedBirthTime
    pillars: Dict[str, Tuple[str, str]]


@dataclass(frozen=True)
class NatalEventAssessment:
    payload: Dict[str, Any]
    probes: Tuple[NatalEventProbe, ...]


def collect_natal_event_probes(
    template: NormalizedBirthTime,
    start: datetime,
    end: datetime,
    *,
    known_clocks: Optional[Mapping[datetime, NormalizedBirthTime]] = None,
) -> NatalEventAssessment:
    """Retain actual event probes without promoting them to full certainty.

    Raw civil clock/date/offset changes use the IANA whole-second clock model.
    Apparent-clock roots are bracketed between minute anchors; monotonic anchor
    checks and root convergence are not an interval completeness proof.
    """
    low, high = utc_instant(start), utc_instant(end)
    if high < low or high - low > timedelta(minutes=240):
        raise ValueError("出生事件核对需要顺序明确且不超过240分钟的实际时刻范围")
    zone = parse_timezone_name(template.timezone)
    clocks: Dict[datetime, NormalizedBirthTime] = dict(known_clocks or {})
    events: List[Dict[str, Any]] = []
    unresolved: List[Dict[str, Any]] = []
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
        source: Dict[str, str],
    ) -> None:
        if right < low or left > high:
            return
        left, right = max(left, low), min(right, high)
        event = {
            "kind": kind,
            "name": name,
            "lower_utc": left.isoformat(),
            "upper_utc": right.isoformat(),
            "at_utc": right.isoformat(),
            "bracket_width_seconds": (right - left).total_seconds(),
            "source": source,
        }
        if event not in events:
            events.append(event)
            cuts.update((left, right))

    # Offset and wall-label changes occur on integer UTC seconds in the
    # supported IANA/Python civil-time model. Never step a same-zone wall clock
    # across a fold, and never infer an observation error from this resolution.
    previous = low.astimezone(zone)
    at = low.replace(microsecond=0) + timedelta(seconds=1)
    while at <= high:
        civil = at.astimezone(zone)
        if template.applied:
            changed = civil.utcoffset() != previous.utcoffset()
        else:
            changed = (civil.date(), (civil.hour + 1) // 2 % 12, civil.utcoffset()) != (
                previous.date(),
                (previous.hour + 1) // 2 % 12,
                previous.utcoffset(),
            )
        if changed:
            add_event(
                "civil_clock",
                civil.isoformat(),
                at,
                at,
                {"policy": "iana_integer_second_clock", "timezone": template.timezone},
            )
        previous = civil
        at += timedelta(seconds=1)

    previous_term, following = get_adjacent_solar_terms(low, template.timezone)
    terms = [previous_term] if utc_instant(previous_term.moment) == low else []
    for _ in range(64):
        moment = utc_instant(following.moment)
        if moment > high:
            break
        terms.append(following)
        _, next_term = get_adjacent_solar_terms(moment + MICROSECOND, template.timezone)
        if utc_instant(next_term.moment) <= moment:
            raise ValueError("节令事件迭代没有前进，不能给出完整候选")
        following = next_term
    else:
        raise ValueError("出生范围内节令事件超出核对预算，不能静默裁剪")
    for term in terms:
        if term.name in BAZI_MONTH_START_TERMS:
            require_calculated_solar_term(term)
            moment = utc_instant(term.moment)
            add_event(
                "jie",
                term.name,
                moment,
                moment,
                {
                    "provider": term.resolution_provider,
                    "model": term.ephemeris_model,
                    "precision_scope": "computed_point_not_physical_error_bound",
                },
            )

    monotonic_anchors: Optional[bool] = None
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
                and event["lower_utc"] <= other["at_utc"] <= event["upper_utc"]
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
    probes: List[NatalEventProbe] = []
    records: List[Dict[str, Any]] = []
    for instant in ordered_instants:
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
                "pillars": {key: "".join(value) for key, value in pillars.items()},
            }
        )
    positions = {instant: index for index, instant in enumerate(ordered_instants)}
    # Nondegenerate segments are half-open. A boundary exactly at the closed
    # range end can have a different state; its separate endpoint probe retains
    # that state without assigning it to the preceding segment's midpoint.
    regions = [
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
            "raw_clock_scan_step_seconds": 1,
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
