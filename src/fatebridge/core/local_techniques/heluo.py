"""
Heluo (河洛理数) local technique.

Pure relocation from the package facade.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fatebridge.core.heluo_clock import attach_clock_evidence, source_clock_snapshot
from fatebridge.core.heluo_jiehou import (
    attach_jiehou_evidence,
    jiehou_evidence,
    jiehou_snapshot,
)
from fatebridge.core.heluo_months import DEFAULT_MONTH_ASSIGNMENT, MonthAssignmentMethod
from fatebridge.core.heluo_solar_context import (
    attach_solar_context,
    bind_seasonal_context,
    bind_solar_context,
    solar_context_snapshot,
)
from fatebridge.core.heluo_timing import (
    HeluoYearContextError,
    build_heluo_timing,
    selected_timing_snapshot,
)
from fatebridge.core.numerology_clock_policy import require_birth_clock
from fatebridge.core.numerology_evidence import heluo_evidence
from fatebridge.core.numerology_inputs import (
    attach_birth_clock,
    birth_clock_snapshot,
    normalize_numerology_utc_offset,
    numerology_birth_clock,
    numerology_seed_time,
    resolve_numerology_longitude,
    resolve_numerology_timezone,
)
from fatebridge.core.numerology_pillars import (
    attach_pillar_links,
    pillar_link_snapshot,
    verified_computed_pillars,
)
from fatebridge.utils.birth_input import normalize_gender
from fatebridge.utils.errors import NumerologySourceError
from fatebridge.utils.formatting import create_pillar_dict

from ..heluo import build_snapshot_text as _heluo_snapshot_text
from ..heluo import calculate as _heluo_calculate
from ..heluo import da_yun as _heluo_da_yun
from ..heluo import judge as _heluo_judge
from ..heluo import solar_term as _heluo_solar_term
from .chart import (
    _build_metaphysics_analysis_context,
    _build_metaphysics_seed,
    _normalize_date_text,
)


def build_heluo_result(
    *,
    date: str,
    time: str,
    zone: Optional[str] = None,
    birth_utc_offset: Optional[str] = None,
    lat: Any = None,
    lon: Any = None,
    gps_lat: Optional[float] = None,
    gps_lon: Optional[float] = None,
    gender: Optional[str] = None,
    use_true_solar_time: bool = False,
    analysis_year: Optional[int] = None,
    month_index: Optional[int] = None,
    day_index: Optional[int] = None,
    month_assignment_method: MonthAssignmentMethod = DEFAULT_MONTH_ASSIGNMENT,
) -> Dict[str, Any]:
    """河洛理数（heluo）。

    四柱来自 FateBridge 自有历法引擎；起命/起运/命运篇/爻辞由
    ``fatebridge.core.heluo`` 完成。节气按出生绝对时刻计算；原典核验范围
    与继承实现的未决规则由 numerology_evidence 单独返回。
    """
    normalized_gender = normalize_gender(gender)
    if not isinstance(gender, str) or normalized_gender not in {"男", "女"}:
        raise ValueError("河洛相荡、寄宫和元堂需要明确gender为男或女，不能默认性别。")
    longitude, longitude_source = resolve_numerology_longitude(
        lon, gps_lon, use_true_solar_time
    )
    input_normalized = {
        "date": _normalize_date_text(date),
        "time": require_birth_clock(time),
        "zone": resolve_numerology_timezone(zone),
        "lat": lat,
        "lon": lon,
        "gpsLat": gps_lat,
        "gpsLon": gps_lon,
        "gender": normalized_gender,
        "use_true_solar_time": bool(use_true_solar_time),
        "analysis_year": analysis_year,
        "month_index": month_index,
        "day_index": day_index,
        "month_assignment_method": month_assignment_method,
    }
    confirmed_offset = normalize_numerology_utc_offset(birth_utc_offset)
    if confirmed_offset is not None:
        input_normalized["birth_utc_offset"] = confirmed_offset
    seed_time = numerology_seed_time(
        input_normalized["date"],
        input_normalized["time"],
        input_normalized["zone"],
        confirmed_offset,
    )
    seed = _build_metaphysics_seed(
        date_text=input_normalized["date"],
        time_text=seed_time,
        timezone_name=input_normalized["zone"],
        lat=lat,
        lon=longitude,
        gps_lat=gps_lat,
        gps_lon=None,
        use_true_solar_time=bool(use_true_solar_time),
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
    jg = _heluo_judge(
        chart,
        four_pillars,
        month_zhi,
        st,
        month_assignment_method=month_assignment_method,
    )
    bind_seasonal_context(st, jg["seasonal_numbers"])
    snapshot_text = _heluo_snapshot_text(chart, jg, dayun)
    timing_text = selected_timing_snapshot(timing)
    if timing_text:
        snapshot_text += "\n\n" + timing_text
    analysis_context = _build_metaphysics_analysis_context(seed)
    analysis_context["longitude"] = longitude
    clock = numerology_birth_clock(
        seed,
        longitude,
        longitude_source,
        birth_utc_offset=confirmed_offset,
        input_clock=time,
    )
    snapshot_text += "\n\n" + birth_clock_snapshot(clock)
    evidence = heluo_evidence(chart, jg, st, four_pillars)
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
        "judge": jg,
        "solar_term": st,
        "numerology_evidence": evidence,
        "snapshot_text": snapshot_text,
        "summary": (
            f"已生成河洛理数输出。先天卦：{chart['xian']['name']}，"
            f"后天卦：{chart['hou']['name']}。综合葉否尚未完成原典验收。"
        ),
    }
