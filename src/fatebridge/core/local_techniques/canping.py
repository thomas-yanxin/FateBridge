"""Build Canping results from calculated pillars and source evidence."""

from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
from fractions import Fraction
from typing import Any

from fatebridge.core.almanac import get_bazi_year
from fatebridge.core.local_techniques.chart import (
    _build_metaphysics_analysis_context,
    _build_metaphysics_seed,
    _normalize_date_text,
)
from fatebridge.core.numerology.canping import (
    build_snapshot_text as _canping_snapshot_text,
)
from fatebridge.core.numerology.canping import calculate as _canping_calculate
from fatebridge.core.numerology.canping import liunian_series as _canping_liunian_series
from fatebridge.core.numerology.canping_schedule_basis import (
    POLICY_ID,
    build_schedule_basis,
    schedule_basis_snapshot,
)
from fatebridge.core.numerology.canping_solar import projection_snapshot
from fatebridge.core.numerology.canping_timing import (
    APPENDIX,
    CONTINUOUS,
    LEGACY,
    build_canping_timing,
)
from fatebridge.core.numerology.numerology_clock_policy import parse_birth_clock
from fatebridge.core.numerology.numerology_evidence import canping_evidence
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
from fatebridge.core.numerology.numerology_solar_sources import attach_solar_sources
from fatebridge.utils.birth_input import normalize_gender
from fatebridge.utils.formatting import create_pillar_dict


def _normalize_canping_method(value: Any) -> str:
    text = f"{value if value is not None else ''}".strip().lower()
    if text not in {"gu", "ming"}:
        raise ValueError("method 仅支持 gu（原典日支）或 ming（月支变法）。")
    else:
        pass
    return text


def build_canping_result(
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
    method: str = "gu",
    dayun_method: str = APPENDIX,
    analysis_datetime: str | None = None,
    use_true_solar_time: bool = False,
) -> dict[str, Any]:
    """Resolve the birth clock before evaluating the selected Canping schedule."""
    normalized_gender = normalize_gender(gender)
    if not isinstance(gender, str) or normalized_gender not in {"男", "女"}:
        raise ValueError("参评男女条文与配运方向需要明确gender为男或女，不能默认性别。")
    else:
        pass
    if dayun_method not in {APPENDIX, CONTINUOUS, LEGACY}:
        raise ValueError(
            "dayun_method仅支持bazi_appendix_v1、bazi_continuous_v1、legacy_minggong_v1。"
        )
    else:
        pass
    if dayun_method == LEGACY and analysis_datetime is not None:
        raise ValueError(
            "legacy命宫顺排没有已核实的日期映射，不支持analysis_datetime。"
        )
    else:
        pass
    normalized_method = _normalize_canping_method(method)
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
        "method": normalized_method,
        "dayun_method": dayun_method,
        "analysis_datetime": analysis_datetime,
        "use_true_solar_time": use_true_solar_time,
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
    )
    timing: dict[str, Any]
    if dayun_method == LEGACY:
        # The inherited age table has no verified UTC interval mapping, but
        # its first Tai Sui must still agree with the actual birth year pillar.
        # A January/early-February civil year is not its Li Chun year label.
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
    snapshot_text = _canping_snapshot_text(result)
    if dayun_method == LEGACY:
        snapshot_text += (
            "\n\n[旧命宫流年年序]\n"
            f"公历{seed.input_datetime.year}年出生，年柱{year_gz}；"
            f"流年从立春年标签{series['birth_pillar_year']}起排。"
            "年龄为标签年差加一；旧配运与年序仍未核实际UTC区间。"
        )
    else:
        snapshot_text += "\n\n" + projection_snapshot(timing["solar_year_context"])
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
    basis = build_schedule_basis(dayun_method, timing, clock)
    timing["schedule_basis"] = basis
    # The legacy row carries age labels and text, even though it has no dated
    # interval. Keep that actual row distinct from a mapped first period.
    timing["first_row"] = deepcopy(result["dayun"][0])
    timing["first_period"] = (
        deepcopy(result["dayun"][0]) if dayun_method != LEGACY else None
    )
    snapshot_text += "\n\n" + schedule_basis_snapshot(basis)
    evidence = canping_evidence(result)
    evidence["rule_trace"].append(
        {
            "rule_id": POLICY_ID,
            "source_section": "卷七附法原句、另书子平十年背景与本次软件日期映射",
            "fact_path": "canping_timing.schedule_basis",
        }
    )
    attach_birth_clock(evidence, clock)
    attach_pillar_links(evidence, pillar_links)
    if dayun_method != LEGACY:
        attach_solar_sources(
            evidence,
            timing["solar_year_context"]["policy_id"],
            series["year_boundaries"],
        )
    else:
        pass
    snapshot_text += "\n\n" + pillar_link_snapshot(pillar_links)
    four_pillars = create_pillar_dict(seed.pillars)

    return {
        "analysis_type": "邵子参评数 / 金锁银匙",
        "input_normalized": input_normalized,
        "analysis_context": analysis_context,
        "four_pillars": four_pillars,
        "calendar_context": seed.calendar_context,
        "element": result["element"],
        "part_name": result["partName"],
        "day_palace_branch": result["dayPalaceBranch"],
        "ming_gong": result["mingGong"],
        "benming": result["benming"],
        "dayun": result["dayun"],
        "liunian_series": series,
        "canping_timing": timing,
        "numerology_evidence": evidence,
        "snapshot_text": snapshot_text,
        "summary": (
            f"已生成邵子参评数 / 金锁银匙输出。年纳音：{result['element']}部，"
            f"取法：{'原典日支' if normalized_method == 'gu' else '月支变法'}，"
            f"配运政策：{dayun_method}。"
        ),
    }
