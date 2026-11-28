"""Build Canping results from calculated pillars and compact evidence."""

from __future__ import annotations

from typing import Any

from fatebridge.core.almanac import get_bazi_year
from fatebridge.core.metaphysics.seed import (
    build_local_metaphysics_seed,
    build_metaphysics_analysis_context,
)
from fatebridge.core.numerology.canping import calculate as _canping_calculate
from fatebridge.core.numerology.canping import canping_evidence
from fatebridge.core.numerology.canping import liunian_series as _canping_liunian_series
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
from fatebridge.core.numerology.timing import (
    APPENDIX,
    CONTINUOUS,
    LEGACY,
    build_canping_timing,
    build_schedule_basis,
)
from fatebridge.utils.birth_input import normalize_gender
from fatebridge.utils.civil_time import normalize_date_text
from fatebridge.utils.coordinates import parse_geo_coordinate
from fatebridge.utils.formatting import create_pillar_dict


def _normalize_canping_method(value: Any) -> str:
    text = f"{value if value is not None else ''}".strip().lower()
    if text not in {"gu", "ming"}:
        raise ValueError("method 仅支持 gu（原典日支）或 ming（月支变法）。")
    return text


def build_canping_result(
    *,
    date: str,
    time: str,
    timezone: str | None = None,
    birth_utc_offset: str | None = None,
    latitude: float | str | None = None,
    longitude: float | str | None = None,
    gender: str | None = None,
    method: str = "gu",
    dayun_method: str = APPENDIX,
    analysis_datetime: str | None = None,
    use_true_solar_time: bool = False,
) -> dict[str, Any]:
    """Resolve the birth clock before evaluating the selected Canping schedule."""
    normalized_gender = normalize_gender(gender)
    if not isinstance(gender, str) or normalized_gender not in {"男", "女"}:
        raise ValueError("参评男女条文与配运方向需要明确gender为男或女，不能默认性别。")
    if dayun_method not in {APPENDIX, CONTINUOUS, LEGACY}:
        raise ValueError(
            "dayun_method仅支持bazi_appendix_v1、bazi_continuous_v1、legacy_minggong_v1。"
        )
    if dayun_method == LEGACY and analysis_datetime is not None:
        raise ValueError(
            "legacy命宫顺排没有已核实的日期映射，不支持analysis_datetime。"
        )
    normalized_method = _normalize_canping_method(method)
    parsed_latitude = parse_geo_coordinate(latitude, axis="latitude")
    parsed_longitude, longitude_source = resolve_numerology_longitude(
        longitude, use_true_solar_time
    )
    birth_date = normalize_date_text(date)
    birth_clock = parse_birth_clock(time)
    timezone_name = resolve_numerology_timezone(timezone)
    input_normalized = {
        "date": birth_date,
        "time": birth_clock.normalized_clock,
        "timezone": timezone_name,
        "latitude": parsed_latitude,
        "longitude": parsed_longitude,
        "gender": normalized_gender,
        "method": normalized_method,
        "dayun_method": dayun_method,
        "analysis_datetime": analysis_datetime,
        "use_true_solar_time": use_true_solar_time,
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
    seed = build_local_metaphysics_seed(
        date_text=birth_date,
        time_text=seed_time,
        timezone_name=timezone_name,
        lat=parsed_latitude,
        lon=parsed_longitude,
        gps_lat=None,
        gps_lon=None,
        use_true_solar_time=use_true_solar_time,
    )
    year_stem, year_branch = seed.pillars["year"]
    year_gz = f"{year_stem}{year_branch}"
    month_branch = seed.pillars["month"][1]
    day_branch = seed.pillars["day"][1]
    hour_branch = seed.pillars["hour"][1]
    pillar_links = verified_computed_pillars(
        {k: "".join(seed.pillars[k]) for k in ("year", "month", "day", "hour")}
    )
    result = _canping_calculate(
        year_gz=year_gz,
        month_branch=month_branch,
        day_branch=day_branch,
        hour_branch=hour_branch,
        gender=normalized_gender,
        method=normalized_method,
        include_luck=dayun_method == LEGACY,
        compact_verses=True,
    )
    timing: dict[str, Any]
    if dayun_method == LEGACY:
        birth_year = get_bazi_year(seed.input_datetime, seed.timezone)
        series = _canping_liunian_series(
            year_gz=year_gz,
            month_branch=month_branch,
            day_branch=day_branch,
            hour_branch=hour_branch,
            gender=normalized_gender,
            method=normalized_method,
            birth_year=birth_year,
        )
        series.update(
            birth_pillar_year=birth_year,
            year_boundary="lichun_year_labels_only",
            age_policy="nominal_age_by_lichun_year_labels; no_actual_boundaries",
        )
        timing = {
            "profile_id": LEGACY,
            "source_status": "inherited_schedule_not_classically_verified",
            "calendar_scope": "year_labels_only; no_actual_boundaries",
            "selected": None,
        }
    else:
        timing, periods, series = build_canping_timing(
            birth=seed.input_datetime,
            zone=seed.timezone,
            gender=normalized_gender,
            month_pillar=seed.pillars["month"],
            calculation=result,
            method=dayun_method,
            analysis_datetime=analysis_datetime,
        )
        result.update(
            dayun=periods, mingGong=None, qiyunAge=None, dayunPolicy=dayun_method
        )
    result["timing"] = timing
    analysis_context = {
        **input_normalized,
        **build_metaphysics_analysis_context(seed),
        "longitude": parsed_longitude,
    }
    clock = numerology_birth_clock(
        seed,
        parsed_longitude,
        longitude_source,
        birth_utc_offset=confirmed_offset,
        input_clock=birth_clock,
    )
    basis = build_schedule_basis(dayun_method, timing, clock)
    timing["schedule_basis"] = basis
    if dayun_method == LEGACY:
        timing["first_row"] = dict(result["dayun"][0])
        timing["first_period"] = None
    evidence = canping_evidence(result)
    attach_birth_clock(evidence, clock)
    attach_pillar_links(evidence, pillar_links)
    four_pillars = create_pillar_dict(seed.pillars)

    return {
        "analysis_type": "邵子参评数 / 金锁银匙",
        "analysis_context": analysis_context,
        "four_pillars": four_pillars,
        "element": result["element"],
        "part_name": result["partName"],
        "day_palace_branch": result["dayPalaceBranch"],
        "ming_gong": result["mingGong"],
        "benming": result["benming"],
        "dayun": result["dayun"],
        "liunian_series": series,
        "canping_timing": timing,
        "numerology_evidence": evidence,
        "summary": (
            f"年纳音：{result['element']}部，"
            f"取法：{'原典日支' if normalized_method == 'gu' else '月支变法'}，"
            f"配运：{dayun_method}。"
        ),
    }
