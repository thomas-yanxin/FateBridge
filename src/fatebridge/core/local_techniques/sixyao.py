"""Assemble Liuyao casting, Najia, Gua Shen, Shen Sha, and compact structural evidence."""

from __future__ import annotations

import random
from typing import Any

from fatebridge.core.almanac import build_calendar_context
from fatebridge.core.bazi.calendar import BaZiCalendar
from fatebridge.core.divination import lookup_hexagram_by_code
from fatebridge.core.liuyao.casting import (
    CoinToss,
    cast_hexagram_code,
    cast_lines_from_codes,
    changed_hexagram_code,
    coin_cast,
    normalize_cast_lines,
    random_coin_tosses,
    validate_hexagram_code,
)
from fatebridge.core.liuyao.evidence import (
    build_liuyao_evidence,
    month_model_comparison,
)
from fatebridge.core.liuyao.najia import (
    build_sixyao_enrichment,
    compute_gua_shen,
    compute_hidden_spirits,
    compute_shensha,
)
from fatebridge.core.liuyao.strength import (
    SOURCES,
    build_fanfu_evidence,
    build_moving_focus_guidance,
    detect_sixyao_patterns,
)
from fatebridge.core.local_techniques.chart import (
    _normalize_date_text,
    _normalize_time_text,
    parse_local_datetime,
)
from fatebridge.core.zhouyi import moving_text_evidence
from fatebridge.utils.coordinates import parse_geo_coordinate
from fatebridge.utils.places import DEFAULT_BIRTH_TIMEZONE


def _build_context(
    *,
    date_text: str,
    time_text: str,
    timezone_name: str | None,
) -> dict[str, Any]:
    timezone_value = timezone_name or DEFAULT_BIRTH_TIMEZONE
    moment = parse_local_datetime(
        date_text, time_text, timezone_value, validate_wall=True
    )
    pillars = BaZiCalendar.get_four_pillars(moment, timezone_name=timezone_value)
    calendar_context = build_calendar_context(
        moment, timezone_name=timezone_value, pillars=pillars
    )
    lunar = calendar_context.get("lunar_calendar") or {}
    nongli = {
        "solar_datetime": calendar_context["solar_datetime"],
        "nongli": lunar.get("display"),
        "year_jieqi": f"{pillars['year'][0]}{pillars['year'][1]}",
        "year": f"{pillars['year'][0]}{pillars['year'][1]}",
        "year_ganzhi": f"{pillars['year'][0]}{pillars['year'][1]}",
        "month_ganzhi": f"{pillars['month'][0]}{pillars['month'][1]}",
        "day_ganzhi": f"{pillars['day'][0]}{pillars['day'][1]}",
        "time": f"{pillars['hour'][0]}{pillars['hour'][1]}",
        "jieqi": calendar_context["current_solar_term"]["name"],
        "jiedelta": calendar_context["solar_term_delta"]["description"],
        "month_int": lunar.get("month"),
        "day_int": lunar.get("day"),
        "month": lunar.get("month_cn"),
        "day": lunar.get("day_cn"),
        "leap": lunar.get("is_leap_month"),
    }
    return {
        "moment": moment,
        "timezone_name": timezone_value,
        "pillars": pillars,
        "calendar_context": calendar_context,
        "lunar": lunar,
        "nongli": nongli,
    }


def _hexagram_desc_payload(code: str) -> dict[str, Any]:
    detail = lookup_hexagram_by_code(code)
    return {
        "code": code,
        "name": detail.get("name"),
        "卦辞": detail["classical"]["guaci"],
        "象曰": detail["classical"]["daxiang"],
        "raw": detail,
    }


def build_sixyao_result(
    *,
    date: str,
    time: str,
    timezone: str | None = None,
    latitude: float | str | None = None,
    longitude: float | str | None = None,
    question: str | None = None,
    gua_code: str | None = None,
    changed_code: str | None = None,
    lines: list[dict[str, Any]] | None = None,
    method: str = "auto",
    coins: list[int] | None = None,
    seed: int | None = None,
    focus_line: int | None = None,
    focus_kinship: str | None = None,
    focus_kind: str | None = None,
    timing_days: int = 0,
    event_horizon: str | None = None,
) -> dict[str, Any]:
    """Build deterministic Liuyao Najia, Gua Shen, Shen Sha, and structural evidence."""
    if event_horizon not in (None, "near", "long_term"):
        raise ValueError("event_horizon 必须是 near、long_term 或省略。")
    method = (method or "auto").strip().lower()
    if method not in {"auto", "coin", "time"}:
        raise ValueError("method 必须是 auto、coin 或 time。")
    if (
        timing_days
        and focus_line is None
        and focus_kinship is None
        and focus_kind is None
    ):
        raise ValueError("展开日级候选需要先明确focus_line或focus_kinship")

    parsed_latitude = parse_geo_coordinate(latitude, axis="latitude")
    parsed_longitude = parse_geo_coordinate(longitude, axis="longitude")
    context = _build_context(date_text=date, time_text=time, timezone_name=timezone)
    normalized_lines = normalize_cast_lines(lines)
    explicit_lines_provided = bool(normalized_lines)
    explicit_code_provided = bool(
        validate_hexagram_code(gua_code) or validate_hexagram_code(changed_code)
    )
    if (
        changed_code is not None
        and gua_code is None
        and not normalized_lines
        and coins is None
    ):
        raise ValueError("changed_code 需要同时提供本卦 gua_code 或完整 lines/coins")
    if normalized_lines:
        if gua_code is not None and gua_code != cast_hexagram_code(normalized_lines):
            raise ValueError("gua_code 与 lines 本卦不一致")
        if changed_code is not None and changed_code != changed_hexagram_code(
            normalized_lines
        ):
            raise ValueError("changed_code 与 lines 动爻不一致")

    coin_source: str | None = None
    coin_tosses: list[CoinToss] | None = None

    if coins is not None:
        cast_method = "coin"
        coin_source = "provided"
        provided_cast = coin_cast(coins)
        coin_lines = provided_cast.lines
        coin_tosses = provided_cast.tosses
        coin_current, coin_changed = (
            cast_hexagram_code(coin_lines),
            changed_hexagram_code(coin_lines),
        )
        if (gua_code is not None and gua_code != coin_current) or (
            changed_code is not None and changed_code != coin_changed
        ):
            raise ValueError("coins 与所提供卦码不一致")
        if normalized_lines and (
            cast_hexagram_code(normalized_lines),
            changed_hexagram_code(normalized_lines),
        ) != (coin_current, coin_changed):
            raise ValueError("coins 与 lines 不一致")
        normalized_lines = coin_lines
        current_code = coin_current
        changed_hexagram_binary_code = coin_changed
    elif explicit_lines_provided or explicit_code_provided:
        cast_method = "manual"
        current_code = validate_hexagram_code(gua_code) or cast_hexagram_code(
            normalized_lines
        )
        changed_hexagram_binary_code = (
            validate_hexagram_code(changed_code)
            or (changed_hexagram_code(normalized_lines) if normalized_lines else "")
            or current_code
        )
        if len(current_code) != 6 or len(changed_hexagram_binary_code) != 6:
            raise ValueError("六爻卦码必须是 6 位 0/1 字符串。")
        if not explicit_lines_provided:
            normalized_lines = cast_lines_from_codes(
                current_code, changed_hexagram_binary_code
            )
    elif method == "coin":
        cast_method = "coin"
        coin_source = "random"
        seeded_cast = coin_cast(random_coin_tosses(random.Random(seed)))
        normalized_lines = seeded_cast.lines
        coin_tosses = seeded_cast.tosses
        current_code = cast_hexagram_code(normalized_lines)
        changed_hexagram_binary_code = changed_hexagram_code(normalized_lines)
    else:
        cast_method = "time_meihua"
        meihua = (context.get("lunar") or {}).get("meihua")
        if not meihua:
            raise ValueError(
                "六爻需先起卦：当前环境缺少农历上下文，无法做时间起卦，"
                "请改为提供 coins/gua_code/changed_code 或 lines。"
            )
        current_code = validate_hexagram_code(meihua["base_hexagram"]["binary_code"])
        changed_hexagram_binary_code = validate_hexagram_code(
            meihua["changed_hexagram"]["binary_code"]
        )
        if len(current_code) != 6 or len(changed_hexagram_binary_code) != 6:
            raise ValueError("六爻卦码必须是 6 位 0/1 字符串。")
        normalized_lines = cast_lines_from_codes(
            current_code, changed_hexagram_binary_code
        )

    input_normalized = {
        "date": _normalize_date_text(date),
        "time": _normalize_time_text(time),
        "timezone": timezone or DEFAULT_BIRTH_TIMEZONE,
        "latitude": parsed_latitude,
        "longitude": parsed_longitude,
        "question": question,
        "gua_code": current_code,
        "changed_code": changed_hexagram_binary_code,
        "focus_line": focus_line,
        "focus_kinship": focus_kinship,
        "focus_kind": focus_kind,
        "timing_days": timing_days,
        "event_horizon": event_horizon,
    }
    current_payload = _hexagram_desc_payload(current_code)
    changed_payload = _hexagram_desc_payload(changed_hexagram_binary_code)
    descriptions = {
        current_code: current_payload,
        changed_hexagram_binary_code: changed_payload,
    }

    day_ganzhi = context.get("nongli", {}).get("day_ganzhi") or ""
    day_gan = day_ganzhi[0] if len(day_ganzhi) >= 1 else ""
    day_branch = day_ganzhi[1] if len(day_ganzhi) >= 2 else ""
    hexagram_info, enrichment = build_sixyao_enrichment(
        current_code=current_code,
        changed_code=changed_hexagram_binary_code,
        day_gan=day_gan or None,
    )
    for line_dict, extra in zip(normalized_lines, enrichment):
        line_dict["god"] = extra["liushen"]
        line_dict["name"] = extra["position_label"]
        line_dict["position"] = extra["position"]
        line_dict["stem"] = extra["stem"]
        line_dict["branch"] = extra["branch"]
        line_dict["element"] = extra["element"]
        line_dict["liuqin"] = extra["liuqin"]
        line_dict["liushen"] = extra["liushen"]
        line_dict["shi_ying"] = extra["shi_ying"]
        if line_dict["change"]:
            line_dict["changed_stem"] = extra["changed_stem"]
            if extra["changed_branch"]:
                line_dict["changed_branch"] = extra["changed_branch"]
                line_dict["changed_liuqin"] = extra["changed_liuqin"]
            else:
                line_dict["changed_branch"] = extra["branch"]
                line_dict["changed_liuqin"] = extra["liuqin"]
                line_dict["is_fuyin_line"] = True

    hexagram_info["gua_shen"] = compute_gua_shen(
        lines=normalized_lines,
        shi_line=hexagram_info["shi_line"],
        palace_element=hexagram_info["current_palace_element"],
    )
    hidden = compute_hidden_spirits(
        normalized_lines=normalized_lines,
        current_palace=hexagram_info["current_palace"],
        day_gan=day_gan or None,
    )
    shensha_table, line_shensha = compute_shensha(
        day_gan=day_gan,
        day_branch=day_branch,
        lines=normalized_lines,
    )
    moving_focus_guidance = build_moving_focus_guidance(
        normalized_lines, shi_line=hexagram_info["shi_line"]
    )
    evidence = build_liuyao_evidence(
        day_ganzhi=day_ganzhi,
        month_branch=context["pillars"]["month"][1],
        current_code=current_code,
        changed_code=changed_hexagram_binary_code,
        lines=normalized_lines,
        hidden=hidden,
        palace_element=hexagram_info["current_palace_element"],
        moment=context["moment"],
        timezone_name=context["timezone_name"],
        shensha=shensha_table,
        line_shensha=line_shensha,
        moving_focus_guidance=moving_focus_guidance,
        focus_line=focus_line,
        focus_kinship=focus_kinship,
        focus_kind=focus_kind,
        timing_days=timing_days,
        event_horizon=event_horizon,
    )

    month_context = context["calendar_context"]["bazi_month_boundary"]
    comparison = month_model_comparison(
        context["moment"],
        month_branch=month_context["branch"],
        boundary_models=(
            month_context["start_term"]["ephemeris_model"],
            month_context["next_term"]["ephemeris_model"],
        ),
    )
    if comparison is not None:
        evidence["month_model_comparison"] = comparison

    _, changed_chart = build_sixyao_enrichment(
        changed_hexagram_binary_code, changed_hexagram_binary_code, day_gan or None
    )
    evidence["fanfu"] = build_fanfu_evidence(
        current_code=current_code,
        changed_code=changed_hexagram_binary_code,
        base_branches=[r["branch"] for r in normalized_lines],
        changed_chart_branches=[r["branch"] for r in changed_chart],
    )
    moving_text_evidence(current_code, changed_hexagram_binary_code)

    moving_lines = [
        index + 1 for index, line in enumerate(normalized_lines) if line.get("change")
    ]
    moving_indices = [
        i for i, line in enumerate(normalized_lines) if line.get("change")
    ]
    current_branches = [line.get("branch", "") for line in normalized_lines]
    changed_branches = [
        line.get("changed_branch") or line.get("branch", "")
        for line in normalized_lines
    ]
    pattern_info = detect_sixyao_patterns(
        current_code=current_code,
        changed_code=changed_hexagram_binary_code,
        current_branches=current_branches,
        changed_branches=changed_branches,
        moving_indices=moving_indices,
        fanfu=evidence["fanfu"],
    )
    _cast_sources = {
        "time_meihua": "梅花时间起卦（按起卦时刻装卦）",
        "coin_provided": "三枚铜钱摇卦（用户提供六掷）",
        "coin_random": "三枚铜钱摇卦（系统随机六掷）",
        "manual": "调用方指定卦码 / 爻线",
    }
    cast_info: dict[str, Any] = {
        "method": cast_method,
        "source": _cast_sources[
            f"coin_{coin_source}" if cast_method == "coin" else cast_method
        ],
    }
    if cast_method == "coin":
        cast_info["coin_source"] = coin_source
        cast_info["tosses"] = coin_tosses
    elif cast_method == "time_meihua":
        cast_info["time_ruleset"] = {
            "ruleset_id": "meihua_lunar_time_v1",
            "year_boundary": "lunar_new_year",
            "seed": context["lunar"]["meihua"]["seed"],
        }
    return {
        "analysis_type": "六爻 / 易卦",
        "analysis_context": input_normalized,
        "nongli": context["nongli"],
        "calendar_context": context["calendar_context"],
        "liuyao_evidence": evidence,
        "current_code": current_code,
        "changed_code": changed_hexagram_binary_code,
        "cast": cast_info,
        "lines": normalized_lines,
        "moving_lines": moving_lines,
        "hexagram_info": hexagram_info,
        "patterns": pattern_info["patterns"],
        "pattern_flags": {
            "liuchong_base": pattern_info["is_liuchong_base"],
            "liuhe_base": pattern_info["is_liuhe_base"],
            "liuchong_changed": pattern_info["is_liuchong_changed"],
            "liuhe_changed": pattern_info["is_liuhe_changed"],
        },
        "question": question,
        "descriptions": descriptions,
        "current_hexagram": current_payload["raw"],
        "changed_hexagram": changed_payload["raw"],
        "summary": (
            f"本卦{current_payload['name']}（{current_code}），"
            f"之卦{changed_payload['name']}（{changed_hexagram_binary_code}），"
            f"动爻{moving_lines or '无'}。"
            f"卦身{hexagram_info['gua_shen']['branch']}，"
            f"伏神{len(hidden)}项。"
        ),
    }
