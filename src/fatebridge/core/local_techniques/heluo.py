"""Build Heluo results from calculated pillars and source evidence."""

from __future__ import annotations

from decimal import Decimal
from fractions import Fraction
from typing import Any

from fatebridge.core.heluo.heluo import calculate as _heluo_calculate
from fatebridge.core.heluo.heluo import da_yun as _heluo_da_yun
from fatebridge.core.heluo.heluo import judge as _heluo_judge
from fatebridge.core.heluo.heluo_clock import (
    attach_clock_evidence,
    source_clock_snapshot,
)
from fatebridge.core.heluo.heluo_jiehou import (
    attach_jiehou_evidence,
    jiehou_evidence,
    jiehou_snapshot,
)
from fatebridge.core.heluo.heluo_months import (
    DEFAULT_MONTH_ASSIGNMENT,
    MonthAssignmentMethod,
)
from fatebridge.core.heluo.heluo_snapshot import (
    build_snapshot_text as _heluo_snapshot_text,
)
from fatebridge.core.heluo.heluo_solar_context import (
    attach_solar_context,
    bind_seasonal_context,
    bind_solar_context,
    solar_context_snapshot,
)
from fatebridge.core.heluo.heluo_solar_context import solar_term as _heluo_solar_term
from fatebridge.core.heluo.heluo_timing import (
    HeluoYearContextError,
    build_heluo_timing,
    selected_timing_snapshot,
)
from fatebridge.core.local_techniques.chart import (
    _build_metaphysics_analysis_context,
    _build_metaphysics_seed,
    _normalize_date_text,
)
from fatebridge.core.numerology.numerology_clock_policy import parse_birth_clock
from fatebridge.core.numerology.numerology_evidence import heluo_evidence
from fatebridge.core.numerology.numerology_inputs import (
    attach_birth_clock,
    birth_clock_snapshot,
    normalize_numerology_utc_offset,
    numerology_birth_clock,
    numerology_seed_time,
    resolve_numerology_longitude,
    resolve_numerology_timezone,
)
from fatebridge.core.numerology.numerology_pillars import (
    attach_pillar_links,
    pillar_link_snapshot,
    verified_computed_pillars,
)
from fatebridge.utils.birth_input import normalize_gender
from fatebridge.utils.errors import NumerologySourceError
from fatebridge.utils.formatting import create_pillar_dict


def build_heluo_result(
    *,
    date: str,
    time: str,
    zone: str | None = None,
    birth_utc_offset: str | None = None,
    lat: str | int | float | Decimal | Fraction | None = None,
    lon: str | int | float | Decimal | Fraction | None = None,
    gps_lat: float | None = None,
    gps_lon: float | None = None,
    gender: str | None = None,
    use_true_solar_time: bool = False,
    analysis_year: int | None = None,
    month_index: int | None = None,
    day_index: int | None = None,
    month_assignment_method: MonthAssignmentMethod = DEFAULT_MONTH_ASSIGNMENT,
) -> dict[str, Any]:
    """Resolve the birth clock and solar terms before casting the Heluo chart."""
    normalized_gender = normalize_gender(gender)
    if not isinstance(gender, str) or normalized_gender not in {"男", "女"}:
        raise ValueError("河洛相荡、寄宫和元堂需要明确gender为男或女，不能默认性别。")
    else:
        pass
    longitude, longitude_source = resolve_numerology_longitude(
        lon, gps_lon, use_true_solar_time
    )
    birth_date = _normalize_date_text(date)
    birth_clock = parse_birth_clock(time)
    timezone_name = resolve_numerology_timezone(zone)
    input_normalized = {
        "date": birth_date,
        "time": birth_clock.normalized_clock,
        "zone": timezone_name,
        "lat": lat,
        "lon": lon,
        "gpsLat": gps_lat,
        "gpsLon": gps_lon,
        "gender": normalized_gender,
        "use_true_solar_time": use_true_solar_time,
        "analysis_year": analysis_year,
        "month_index": month_index,
        "day_index": day_index,
        "month_assignment_method": month_assignment_method,
    }
    confirmed_offset = normalize_numerology_utc_offset(birth_utc_offset)
    if confirmed_offset is not None:
        input_normalized["birth_utc_offset"] = confirmed_offset
    else:
        pass
    seed_time = numerology_seed_time(
        birth_date,
        birth_clock.normalized_clock,
        timezone_name,
        confirmed_offset,
    )
    seed = _build_metaphysics_seed(
        date_text=birth_date,
        time_text=seed_time,
        timezone_name=timezone_name,
        lat=lat,
        lon=longitude,
        gps_lat=gps_lat,
        gps_lon=None,
        use_true_solar_time=use_true_solar_time,
    )
    four_pillars = {
        "year": "".join(seed.pillars["year"]),
        "month": "".join(seed.pillars["month"]),
        "day": "".join(seed.pillars["day"]),
        "hour": "".join(seed.pillars["hour"]),
    }
    month_zhi = seed.pillars["month"][1]
    pillar_links = verified_computed_pillars(four_pillars)
    hour_zhi = seed.pillars["hour"][1]
    birth_year = seed.input_datetime.year

    # 四柱的时柱可用真太阳时；太阳交节仍以原始民用时刻代表的绝对瞬间判断。
    st = _heluo_solar_term(
        seed.input_datetime.year,
        seed.input_datetime.month,
        seed.input_datetime.day,
        seed.timezone,
        birth_datetime=seed.input_datetime,
    )
    bind_solar_context(st, seed.calendar_context, seed.input_datetime)

    chart = _heluo_calculate(
        four_pillars=four_pillars,
        gender=normalized_gender,
        hour_zhi=hour_zhi,
        birth_year=birth_year,
        month_zhi=month_zhi,
        month_yang_ling=st["yang_ling"],
    )
    # Only this adapter has established the birth instant against solar terms.
    # A boolean supplied to the fixed-pillar domain function alone proves no date.
    chart["yangLingBasis"] = "solstice_instant"
    chart["yuantang_derivation"]["half_year"].update(
        basis="solstice_instant", birth_instant_utc=st["anchor_utc"]
    )
    dayun = _heluo_da_yun(chart["xian"], chart["hou"], chart["cycleYear"])
    try:
        timing = build_heluo_timing(
            chart,
            four_pillars["year"],
            analysis_year=analysis_year,
            month_index=month_index,
            day_index=day_index,
        )
    except HeluoYearContextError as exc:
        raise NumerologySourceError("runtime_heluo_year_context_conflict") from exc
    judgment = _heluo_judge(
        chart,
        four_pillars,
        month_zhi,
        st,
        month_assignment_method=month_assignment_method,
        birth_datetime=seed.input_datetime,
    )
    bind_seasonal_context(st, judgment["seasonal_numbers"])
    snapshot_text = _heluo_snapshot_text(chart, judgment, dayun)
    timing_text = selected_timing_snapshot(timing)
    if timing_text:
        snapshot_text += "\n\n" + timing_text
    else:
        pass
    analysis_context = _build_metaphysics_analysis_context(seed)
    analysis_context["longitude"] = longitude
    clock = numerology_birth_clock(
        seed,
        longitude,
        longitude_source,
        birth_utc_offset=confirmed_offset,
        input_clock=birth_clock,
    )
    snapshot_text += "\n\n" + birth_clock_snapshot(clock)
    evidence = heluo_evidence(chart, judgment, st, four_pillars)
    attach_solar_context(evidence, st)
    snapshot_text += "\n\n" + solar_context_snapshot(st["boundary_context"])
    attach_birth_clock(evidence, clock)
    attach_pillar_links(evidence, pillar_links)
    snapshot_text += "\n\n" + pillar_link_snapshot(pillar_links)
    attach_clock_evidence(evidence, timing["source_clock"], timing["year_context"])
    snapshot_text += "\n\n" + source_clock_snapshot(timing["source_clock"])
    jiehou = jiehou_evidence(st)
    attach_jiehou_evidence(evidence, jiehou)
    snapshot_text += "\n\n" + jiehou_snapshot(jiehou)

    return {
        "analysis_type": "河洛理数",
        "input_normalized": input_normalized,
        "analysis_context": analysis_context,
        "four_pillars": create_pillar_dict(seed.pillars),
        "calendar_context": seed.calendar_context,
        "chart": chart,
        "dayun": dayun,
        "heluo_timing": timing,
        "jiehou_evidence": jiehou,
        "judge": judgment,
        "solar_term": st,
        "numerology_evidence": evidence,
        "snapshot_text": snapshot_text,
        "summary": (
            f"已生成河洛理数输出。先天卦：{chart['xian']['name']}，"
            f"后天卦：{chart['hou']['name']}。综合葉否尚未完成原典验收。"
        ),
    }
