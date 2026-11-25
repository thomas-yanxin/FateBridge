"""Assemble Liuyao casting, Najia and conditional evidence."""

from __future__ import annotations

import random
from typing import Any

from fatebridge.core.almanac import build_calendar_context
from fatebridge.core.calendar import BaZiCalendar
from fatebridge.core.divination import lookup_hexagram_by_code
from fatebridge.core.liuyao.liuyao_casting import (
    CoinToss,
    cast_hexagram_code,
    cast_lines_from_codes,
    changed_hexagram_code,
    coin_cast,
)
from fatebridge.core.liuyao.liuyao_casting import (
    needs_random_coin_cast as needs_random_coin_cast,
)
from fatebridge.core.liuyao.liuyao_casting import (
    normalize_cast_lines,
    random_coin_tosses,
    validate_hexagram_code,
)
from fatebridge.core.liuyao.liuyao_evidence import build_liuyao_evidence
from fatebridge.core.liuyao.liuyao_najia import (
    BAGONG_BASES,
    build_sixyao_enrichment,
)
from fatebridge.core.liuyao.liuyao_patterns import detect_sixyao_patterns
from fatebridge.core.liuyao.liuyao_snapshot import build_sixyao_snapshot_text
from fatebridge.core.local_techniques.chart import (
    _normalize_date_text,
    _normalize_time_text,
    parse_local_datetime,
)
from fatebridge.core.zhouyi import moving_text_evidence
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
        "birth": calendar_context["solar_datetime"],
        "nongli": lunar.get("display"),
        "yearJieqi": f"{pillars['year'][0]}{pillars['year'][1]}",
        "year": f"{pillars['year'][0]}{pillars['year'][1]}",
        "yearGanZi": f"{pillars['year'][0]}{pillars['year'][1]}",
        "monthGanZi": f"{pillars['month'][0]}{pillars['month'][1]}",
        "dayGanZi": f"{pillars['day'][0]}{pillars['day'][1]}",
        "time": f"{pillars['hour'][0]}{pillars['hour'][1]}",
        "jieqi": calendar_context["current_solar_term"]["name"],
        "jiedelta": calendar_context["solar_term_delta"]["description"],
        "monthInt": lunar.get("month"),
        "dayInt": lunar.get("day"),
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
        "classical_source_url": detail["classical"]["source_url"],
        "raw": detail,
    }


def build_sixyao_result(
    *,
    date: str,
    time: str,
    zone: str | None = None,
    lat: str | float | None = None,
    lon: str | float | None = None,
    gps_lat: float | None = None,
    gps_lon: float | None = None,
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
    render_snapshot: bool = True,
) -> dict[str, Any]:
    if event_horizon not in (None, "near", "long_term"):
        raise ValueError("event_horizon 必须是 near、long_term 或省略。")
    else:
        pass
    method = (method or "auto").strip().lower()
    if method not in {"auto", "coin", "time"}:
        raise ValueError("method 必须是 auto、coin 或 time。")
    else:
        pass
    if (
        timing_days
        and focus_line is None
        and focus_kinship is None
        and focus_kind is None
    ):
        raise ValueError("展开日级候选需要先明确focus_line或focus_kinship")
    else:
        pass

    context = _build_context(date_text=date, time_text=time, timezone_name=zone)
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
    else:
        pass
    if normalized_lines:
        if gua_code is not None and gua_code != cast_hexagram_code(normalized_lines):
            raise ValueError("gua_code 与 lines 本卦不一致")
        else:
            pass
        if changed_code is not None and changed_code != changed_hexagram_code(
            normalized_lines
        ):
            raise ValueError("changed_code 与 lines 动爻不一致")
        else:
            pass
    else:
        pass

    coin_source: str | None = None
    coin_tosses: list[CoinToss] | None = None

    if coins is not None:
        # 摇钱起卦（用户提供六掷）：调用方报来真实摇出的铜钱结果。
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
        else:
            pass
        if normalized_lines and (
            cast_hexagram_code(normalized_lines),
            changed_hexagram_code(normalized_lines),
        ) != (coin_current, coin_changed):
            raise ValueError("coins 与 lines 不一致")
        else:
            pass
        normalized_lines = coin_lines
        current_code = coin_current
        changed_hexagram_binary_code = coin_changed
    elif explicit_lines_provided or explicit_code_provided:
        # 手动起卦：调用方已指定卦码 / 爻线。
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
        else:
            pass
        # When the caller supplied codes but no explicit lines, derive the
        # canonical line set from the authoritative codes so moving-line
        # detection reflects the real request.
        if not explicit_lines_provided:
            normalized_lines = cast_lines_from_codes(
                current_code, changed_hexagram_binary_code
            )
        else:
            pass
    elif method == "coin":
        # 摇钱起卦（系统随机六掷）：真·铜钱筮法，seed 可复现。
        cast_method = "coin"
        coin_source = "random"
        seeded_cast = coin_cast(random_coin_tosses(random.Random(seed)))
        normalized_lines = seeded_cast.lines
        coin_tosses = seeded_cast.tosses
        current_code = cast_hexagram_code(normalized_lines)
        changed_hexagram_binary_code = changed_hexagram_code(normalized_lines)
    else:
        # 时间起卦（method=auto/time）：按起卦时刻以梅花口径真实装卦
        # （本卦 / 动爻 / 变卦取自同一时刻的农历上下文），而不是返回固定演示卦。
        cast_method = "time_meihua"
        meihua = (context.get("lunar") or {}).get("meihua")
        if not meihua:
            raise ValueError(
                "六爻需先起卦：当前环境缺少农历上下文，无法做时间起卦，"
                "请改为提供 coins/gua_code/changed_code 或 lines。"
            )
        else:
            pass
        current_code = validate_hexagram_code(meihua["base_hexagram"]["binary_code"])
        changed_hexagram_binary_code = validate_hexagram_code(
            meihua["changed_hexagram"]["binary_code"]
        )
        if len(current_code) != 6 or len(changed_hexagram_binary_code) != 6:
            raise ValueError("六爻卦码必须是 6 位 0/1 字符串。")
        else:
            pass
        normalized_lines = cast_lines_from_codes(
            current_code, changed_hexagram_binary_code
        )

    input_normalized = {
        "date": _normalize_date_text(date),
        "time": _normalize_time_text(time),
        "zone": zone or DEFAULT_BIRTH_TIMEZONE,
        "lat": lat,
        "lon": lon,
        "gpsLat": gps_lat,
        "gpsLon": gps_lon,
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

    # 按起卦日干 + 卦码排纳甲、世应、六亲、六神，并写回每爻。
    day_ganzhi = context.get("nongli", {}).get("dayGanZi") or ""
    day_gan = day_ganzhi[0] if day_ganzhi else None
    hexagram_info, enrichment = build_sixyao_enrichment(
        current_code=current_code,
        changed_code=changed_hexagram_binary_code,
        day_gan=day_gan,
    )
    for line_dict, extra in zip(normalized_lines, enrichment):
        # 六神与 SIX_YAO_GODS 的固定位置不同——按日干重算 god。
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
        else:
            pass

    # Only missing kinship categories are candidates for 伏神, located at the
    # same position of the original palace's pure hexagram.
    palace_base = next(
        code
        for palace, code, _ in BAGONG_BASES
        if palace == hexagram_info["current_palace"]
    )
    _, palace_lines = build_sixyao_enrichment(palace_base, palace_base, day_gan)
    present_kin = {line["liuqin"] for line in normalized_lines} | {
        line["changed_liuqin"] for line in normalized_lines if line["change"]
    }
    hidden = [
        {
            "position": row["position"],
            "branch": row["branch"],
            "element": row["element"],
            "liuqin": row["liuqin"],
            "flying_branch": normalized_lines[i]["branch"],
            "flying_liuqin": normalized_lines[i]["liuqin"],
        }
        for i, row in enumerate(palace_lines)
        if row["liuqin"] not in present_kin
    ]
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
        focus_line=focus_line,
        focus_kinship=focus_kinship,
        focus_kind=focus_kind,
        timing_days=timing_days,
        event_horizon=event_horizon,
    )

    from fatebridge.core.liuyao.liuyao_calendar_models import month_model_comparison

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
        evidence["calendar_conventions"]["month_model_comparison"] = comparison
    else:
        pass

    from fatebridge.core.liuyao.liuyao_fanfu import build_fanfu_evidence

    # The full changed chart is a structural comparison. It must never
    # populate changed_branch on an original static line.
    _, changed_chart = build_sixyao_enrichment(
        changed_hexagram_binary_code, changed_hexagram_binary_code, day_gan
    )
    evidence["fanfu"] = build_fanfu_evidence(
        current_code=current_code,
        changed_code=changed_hexagram_binary_code,
        base_branches=[r["branch"] for r in normalized_lines],
        changed_chart_branches=[r["branch"] for r in changed_chart],
    )
    evidence["rule_trace"].append(
        {
            "rule_id": "separate_body_region_and_active_line_fanfu",
            "fact_path": "liuyao_evidence.fanfu",
            "inputs": {
                "current_code": current_code,
                "changed_code": changed_hexagram_binary_code,
            },
            "sources": [evidence["fanfu"]["source_url"]],
        }
    )
    text_evidence = moving_text_evidence(current_code, changed_hexagram_binary_code)
    evidence["rule_trace"].append(
        {
            "rule_id": "actual_moving_classical_text",
            "fact_path": "classical_text_evidence",
            "inputs": {
                "current_code": current_code,
                "changed_code": changed_hexagram_binary_code,
            },
            "sources": [
                text_evidence["base_source_url"],
                text_evidence["changed_source_url"],
            ],
        }
    )

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
            "source_url": "https://zh.wikisource.org/wiki/梅花易數/卷一",
        }
    else:
        pass
    return {
        "analysis_type": "六爻 / 易卦",
        "input_normalized": input_normalized,
        "nongli": context["nongli"],
        "calendar_context": context["calendar_context"],
        "liuyao_evidence": evidence,
        "classical_text_evidence": text_evidence,
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
        **(
            {
                "snapshot_text": build_sixyao_snapshot_text(
                    input_normalized=input_normalized,
                    nongli=context["nongli"],
                    current_payload=current_payload,
                    changed_payload=changed_payload,
                    lines=normalized_lines,
                    evidence=evidence,
                    text_evidence=text_evidence,
                )
            }
            if render_snapshot
            else {}
        ),
        "summary": f"本卦{current_payload['name']}（{current_code}），之卦{changed_payload['name']}（{changed_hexagram_binary_code}），动爻{moving_lines or '无'}。已装世应、六亲、六神并列日月关系与原典动爻；尚未据用神旺衰断现实成败。",
    }
