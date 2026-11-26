"""Build Heluo results from calculated pillars and source evidence."""

from __future__ import annotations

from typing import Any

from fatebridge.core.heluo.chart import calculate as _heluo_calculate
from fatebridge.core.heluo.chart import da_yun as _heluo_da_yun
from fatebridge.core.heluo.judgment import (
    DEFAULT_MONTH_ASSIGNMENT,
    MonthAssignmentMethod,
    attach_jiehou_evidence,
    attach_solar_context,
    bind_seasonal_context,
    bind_solar_context,
    heluo_evidence,
    jiehou_evidence,
)
from fatebridge.core.heluo.judgment import judge as _heluo_judge
from fatebridge.core.heluo.judgment import solar_term as _heluo_solar_term
from fatebridge.core.heluo.timing import (
    HeluoYearContextError,
    attach_clock_evidence,
    build_heluo_timing,
)
from fatebridge.core.local_techniques.chart import (
    _build_metaphysics_analysis_context,
    _build_metaphysics_seed,
    _normalize_date_text,
)
from fatebridge.core.numerology.numerology_inputs import (
    attach_birth_clock,
    attach_pillar_links,
    normalize_numerology_utc_offset,
    numerology_birth_clock,
    numerology_seed_time,
    parse_birth_clock,
    resolve_numerology_longitude,
    resolve_numerology_timezone,
    verified_computed_pillars,
)
from fatebridge.utils.birth_input import normalize_gender
from fatebridge.utils.coordinates import parse_geo_coordinate
from fatebridge.utils.errors import NumerologySourceError
from fatebridge.utils.formatting import create_pillar_dict


def build_heluo_result(
    *,
    date: str,
    time: str,
    timezone: str | None = None,
    birth_utc_offset: str | None = None,
    latitude: float | str | None = None,
    longitude: float | str | None = None,
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
    parsed_latitude = parse_geo_coordinate(latitude, axis="latitude")
    parsed_longitude, longitude_source = resolve_numerology_longitude(
        longitude, use_true_solar_time
    )
    birth_date = _normalize_date_text(date)
    birth_clock = parse_birth_clock(time)
    timezone_name = resolve_numerology_timezone(timezone)
    input_normalized = {
        "date": birth_date,
        "time": birth_clock.normalized_clock,
        "timezone": timezone_name,
        "latitude": parsed_latitude,
        "longitude": parsed_longitude,
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
        lat=parsed_latitude,
        lon=parsed_longitude,
        gps_lat=None,
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
    dayun_raw = _heluo_da_yun(chart["xian"], chart["hou"], chart["cycleYear"])
    dayun = {
        "all": [{k: v for k, v in p.items() if k != "lines"} for p in dayun_raw["all"]]
    }
    try:
        timing = build_heluo_timing(
            chart,
            four_pillars["year"],
            analysis_year=analysis_year,
            month_index=month_index,
            day_index=day_index,
            timezone=seed.timezone,
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
    judgment["seasonal_numbers"]["seasonal_windows"] = [
        w for w in judgment["seasonal_numbers"]["seasonal_windows"] if w.get("active")
    ]
    analysis_context = _build_metaphysics_analysis_context(seed)
    analysis_context["longitude"] = parsed_longitude
    clock = numerology_birth_clock(
        seed,
        parsed_longitude,
        longitude_source,
        birth_utc_offset=confirmed_offset,
        input_clock=birth_clock,
    )
    evidence = heluo_evidence(chart, judgment, st, four_pillars)
    attach_solar_context(evidence, st)
    attach_birth_clock(evidence, clock)
    attach_pillar_links(evidence, pillar_links)
    jiehou = jiehou_evidence(st)
    attach_jiehou_evidence(evidence, jiehou)
    # Slim solar boundary_context dependencies after cross-validation
    st["boundary_context"]["dependencies"] = [
        {
            "role": dep["role"],
            "instant_utc": dep["instant_utc"],
            "record": {
                k: dep["record"][k]
                for k in (
                    "name",
                    "datetime_with_offset",
                    "timezone",
                    "resolution_provider",
                )
                if k in dep["record"]
            },
        }
        for dep in st["boundary_context"]["dependencies"]
    ]

    return {
        "analysis_type": "河洛理数",
        "input_normalized": input_normalized,
        "analysis_context": analysis_context,
        "four_pillars": create_pillar_dict(seed.pillars),
        "chart": chart,
        "dayun": dayun,
        "heluo_timing": timing,
        "jiehou_evidence": jiehou,
        "judge": judgment,
        "solar_term": st,
        "numerology_evidence": evidence,
        "summary": (
            f"已生成河洛理数输出。先天卦：{chart['xian']['name']}，"
            f"后天卦：{chart['hou']['name']}。综合葉否尚未完成原典验收。"
        ),
    }
