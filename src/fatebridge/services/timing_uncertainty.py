"""Explicit birth-clock ranges; sampling counts are never probabilities."""

from datetime import datetime, timedelta, timezone
from typing import Literal, TypedDict

from typing_extensions import NotRequired

from fatebridge.analysis.timing_effects import TimingEffectsAnalysis
from fatebridge.core.almanac import localize_datetime
from fatebridge.core.calendar import BaZiCalendar
from fatebridge.services.birth_time_events import (
    NatalEventPayload,
    collect_natal_event_probes,
)
from fatebridge.services.dayun_birth_events import (
    DayunBirthEventPayload,
    collect_dayun_birth_event_probes,
)
from fatebridge.utils.birth_input import PersonInfo, normalize_gender
from fatebridge.utils.solar_time import (
    NormalizedBirthTime,
    normalize_birth_time,
    rebase_birth_clock,
)
from fatebridge.utils.timezones import validate_local_clock


class NatalPillarCandidate(TypedDict):
    pillars: dict[str, str]
    first_sample_at: str | None
    last_sample_at: str | None
    sample_count: int
    event_probe_count: int
    evidence_sources: list[str]
    first_event_probe_at: NotRequired[str]
    last_event_probe_at: NotRequired[str]


DayunDirection = Literal["顺行", "逆行"]
DayunStatus = Literal["active", "before_dayun", "beyond_calculation"]


class CurrentDayunCandidate(TypedDict):
    direction: DayunDirection
    status: DayunStatus
    period: int | None
    pillar: str | None


class DayunBoundaryRange(TypedDict):
    direction: DayunDirection
    period: int
    pillar: str
    earliest_start_at: str
    latest_start_at: str
    earliest_end_at: str
    latest_end_at: str


class BirthTimeSensitivity(TypedDict):
    method_id: Literal["birth_clock_grid_natal_and_dayun_events_v3"]
    status: Literal["sensitive", "partial", "stable_on_assessed_points"]
    status_scope: str
    dayun_assessment_status: Literal["calculated", "unavailable_missing_gender"]
    unavailable_fields: list[str]
    boundary_ranges_vary: bool
    uncertainty_minutes: int
    sample_count: int
    event_probe_count: int
    natal_event_probe_count: int
    dayun_event_probe_count: int
    additional_event_probe_count: int
    total_assessed_instants: int
    birth_at_range: dict[str, str]
    sampling_policy: str
    boundary_range_scope: str
    event_analysis: NatalEventPayload
    dayun_event_analysis: DayunBirthEventPayload | None
    pillars_candidates: list[NatalPillarCandidate]
    current_dayun_candidates: list[CurrentDayunCandidate]
    dayun_boundary_ranges: list[DayunBoundaryRange]
    affected_fields: list[str]
    interpretation_scope: str


def analyze_birth_time_range(
    person: PersonInfo,
    minutes: int,
    *,
    analysis_moment: datetime | None,
    analysis_age: int | None = None,
) -> BirthTimeSensitivity:
    """Retain raw and corrected clocks for each elapsed minute and derived event probe."""
    if (
        isinstance(minutes, bool)
        or not isinstance(minutes, int)
        or not 0 <= minutes <= 120
    ):
        raise ValueError("出生时间范围须为0至120的整数分钟")
    else:
        pass
    if analysis_moment is None and analysis_age is None:
        raise ValueError("时间敏感性核对需要分析时刻或显式年龄")
    else:
        pass
    nominal = normalize_birth_time(person)
    zone = nominal.timezone
    center = localize_datetime(nominal.input_datetime, zone).astimezone(timezone.utc)
    candidates: dict[tuple[str, ...], NatalPillarCandidate] = {}
    starts: dict[tuple[DayunDirection, int, str], list[datetime]] = {}
    ends: dict[tuple[DayunDirection, int, str], list[datetime]] = {}
    current: dict[
        tuple[DayunDirection, DayunStatus, int | None, str | None],
        CurrentDayunCandidate,
    ] = {}
    directions: set[DayunDirection] = set()
    can_calculate_dayun = normalize_gender(person.gender) in {"男", "女"}
    known_clocks: dict[datetime, NormalizedBirthTime] = {}
    event_bounds: dict[tuple[str, ...], tuple[datetime, datetime]] = {}

    def retain_natal(
        normalized: NormalizedBirthTime,
        pillars: dict[str, tuple[str, str]],
        *,
        is_grid: bool,
        event_source: str = "event_probe",
        is_new_event: bool = True,
    ) -> None:
        local = normalized.input_datetime
        key = tuple("".join(pillars[name]) for name in ("year", "month", "day", "hour"))
        row = candidates.setdefault(
            key,
            {
                "pillars": dict(zip(("year", "month", "day", "hour"), key)),
                "first_sample_at": None,
                "last_sample_at": None,
                "sample_count": 0,
                "event_probe_count": 0,
                "evidence_sources": [],
            },
        )
        source = "minute_grid" if is_grid else event_source
        if source not in row["evidence_sources"]:
            row["evidence_sources"].append(source)
        else:
            pass
        if is_grid:
            if row["first_sample_at"] is None:
                row["first_sample_at"] = local.isoformat()
            else:
                pass
            row["last_sample_at"] = local.isoformat()
            row["sample_count"] += 1
        elif is_new_event:
            instant = local.astimezone(timezone.utc)
            first, last = event_bounds.get(key, (instant, instant))
            first, last = min(first, instant), max(last, instant)
            event_bounds[key] = first, last
            row["first_event_probe_at"] = localize_datetime(first, zone).isoformat()
            row["last_event_probe_at"] = localize_datetime(last, zone).isoformat()
            row["event_probe_count"] += 1
        else:
            pass

    def retain_dayun(local: datetime, pillars: dict[str, tuple[str, str]]) -> None:
        if not can_calculate_dayun:
            return
        else:
            pass
        result = TimingEffectsAnalysis.analyze_dayun_effects(
            pillars,
            local,
            person.gender,
            analysis_age if analysis_age is not None else 0,
            timezone_name=zone,
            analysis_moment=analysis_moment,
        )
        timeline = result["timing_context"]["timeline"]
        direction: DayunDirection = (
            "顺行" if timeline["start_details"]["forward_direction"] else "逆行"
        )
        directions.add(direction)
        for period in timeline["periods"]:
            period_key = (direction, period["period"], period["pillar"])
            starts.setdefault(period_key, []).append(
                datetime.fromisoformat(period["start_at"]).astimezone(timezone.utc)
            )
            ends.setdefault(period_key, []).append(
                datetime.fromisoformat(period["end_at"]).astimezone(timezone.utc)
            )
        info = result.get("dayun_info", {})
        state: DayunStatus = result.get("status", "active")
        current_key = (direction, state, info.get("period"), info.get("pillar"))
        current.setdefault(
            current_key,
            {
                "direction": direction,
                "status": state,
                "period": info.get("period"),
                "pillar": info.get("pillar"),
            },
        )

    for offset in range(-minutes, minutes + 1):
        instant = center + timedelta(minutes=offset)
        normalized = rebase_birth_clock(nominal, instant)
        local = normalized.input_datetime
        validate_local_clock(local, allow_ambiguous=True)
        known_clocks[instant] = normalized
        pillars = BaZiCalendar.get_four_pillars(
            normalized.corrected_datetime,
            timezone_name=normalized.timezone,
            civil_datetime=local,
        )
        retain_natal(normalized, pillars, is_grid=True)
        retain_dayun(local, pillars)

    event_assessment = collect_natal_event_probes(
        nominal,
        center - timedelta(minutes=minutes),
        center + timedelta(minutes=minutes),
        known_clocks=known_clocks,
    )
    event_instants = set()
    dayun_assessed_instants = set(known_clocks)
    all_clocks = dict(known_clocks)
    for probe in event_assessment.probes:
        instant = probe.normalized.input_datetime.astimezone(timezone.utc)
        event_instants.add(instant)
        all_clocks[instant] = probe.normalized
        retain_natal(probe.normalized, probe.pillars, is_grid=False)
        if instant not in known_clocks:
            retain_dayun(probe.normalized.input_datetime, probe.pillars)
            dayun_assessed_instants.add(instant)
        else:
            pass
    dayun_events = None
    if can_calculate_dayun:
        dayun_events = collect_dayun_birth_event_probes(
            nominal,
            center - timedelta(minutes=minutes),
            center + timedelta(minutes=minutes),
            person.gender,
            natal_events=event_assessment.payload,
            analysis_moment=analysis_moment,
            known_clocks=all_clocks,
        )
        for probe in dayun_events.probes:
            instant = probe.normalized.input_datetime.astimezone(timezone.utc)
            retain_natal(
                probe.normalized,
                probe.pillars,
                is_grid=False,
                event_source="dayun_event_probe",
                is_new_event=instant not in event_instants,
            )
            event_instants.add(instant)
            if instant not in dayun_assessed_instants:
                retain_dayun(probe.normalized.input_datetime, probe.pillars)
                dayun_assessed_instants.add(instant)
            else:
                pass
    else:
        pass
    periods: list[DayunBoundaryRange] = [
        {
            "direction": key[0],
            "period": key[1],
            "pillar": key[2],
            "earliest_start_at": localize_datetime(min(values), zone).isoformat(),
            "latest_start_at": localize_datetime(max(values), zone).isoformat(),
            "earliest_end_at": localize_datetime(min(ends[key]), zone).isoformat(),
            "latest_end_at": localize_datetime(max(ends[key]), zone).isoformat(),
        }
        for key, values in starts.items()
    ]
    affected = []
    if len(candidates) > 1:
        affected.append("birth_pillars")
    else:
        pass
    if len(directions) > 1:
        affected.append("dayun_direction")
    else:
        pass
    if len(current) > 1:
        affected.append("current_dayun")
    else:
        pass
    return {
        "method_id": "birth_clock_grid_natal_and_dayun_events_v3",
        "status": (
            "sensitive"
            if affected
            else (
                "partial"
                if event_assessment.payload["unresolved_event_orders"]
                or (dayun_events and dayun_events.payload["unresolved_cells"])
                else "stable_on_assessed_points" if can_calculate_dayun else "partial"
            )
        ),
        "status_scope": (
            "natal_pillars_direction_and_current_dayun_only"
            if can_calculate_dayun
            else "natal_pillars_only"
        ),
        "dayun_assessment_status": (
            "calculated" if can_calculate_dayun else "unavailable_missing_gender"
        ),
        "unavailable_fields": (
            []
            if can_calculate_dayun
            else ["dayun_direction", "current_dayun", "dayun_boundary_ranges"]
        ),
        "boundary_ranges_vary": any(
            min(values) != max(values) for values in starts.values()
        ),
        "uncertainty_minutes": minutes,
        "sample_count": minutes * 2 + 1,
        "event_probe_count": len(event_instants),
        "natal_event_probe_count": len(event_assessment.probes),
        "dayun_event_probe_count": len(dayun_events.probes) if dayun_events else 0,
        "additional_event_probe_count": len(event_instants - known_clocks.keys()),
        "total_assessed_instants": len(event_instants | known_clocks.keys()),
        "birth_at_range": {
            "start": localize_datetime(
                center - timedelta(minutes=minutes), zone
            ).isoformat(),
            "end": localize_datetime(
                center + timedelta(minutes=minutes), zone
            ).isoformat(),
        },
        "sampling_policy": "every_integer_elapsed_minute_inclusive_in_utc",
        "boundary_range_scope": "minute_grid_natal_and_dayun_event_probe_envelope",
        "event_analysis": event_assessment.payload,
        "dayun_event_analysis": dayun_events.payload if dayun_events else None,
        "pillars_candidates": list(candidates.values()),
        "current_dayun_candidates": list(current.values()),
        "dayun_boundary_ranges": periods,
        "affected_fields": affected,
        "interpretation_scope": "保留逐分钟网格，并补充实际节令、钟面与大运名义月进位事件探针；未证明采样间秒级无变化、全部连续交运状态或边界极值。sample_count只计原分钟网格，事件探针另计，新候选可无分钟样本。样本数量和频次不是概率，派生微秒不认证出生记录。未提供范围不等于生时精确，范围内敏感时不能只解读名义输入的单一盘或单一交运时刻。",
    }
