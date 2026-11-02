"""Numerical and seasonal conditions in the Wenming Shuju Heluo printing.

These are literal conditions, not a combined xie/buxie judgment. Source ranges
overlap: neither chronological priority nor a favorable rule may erase another.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from fatebridge.core.almanac import (
    _term_window,
    get_solar_term_environment_key,
    localize_datetime,
    require_calculated_solar_term,
)
from fatebridge.utils.errors import NumerologySourceError

RULESET_ID = "heluo_wenming_number_conditions_v1"
SOURCE_URL = "https://upload.wikimedia.org/wikipedia/commons/4/4a/NLC416-13jh000625-42999_%E6%B2%B3%E6%B4%9B%E7%90%86%E6%95%B8.pdf"
SOURCE_SHA256 = "fd203ebcd4dc355dbb1ddd3cbee0a72051a2ca6f7a3e0945027690aac8de0b0c"

# PDF p67 (卷一五五). The two overlaps are in the text, not a table error.
SEASON_WINDOWS = (
    ("yang_insufficient", "阳数不及", "tian", "冬至", "雨水", "below_reference"),
    ("yang_middle", "阳数得中", "tian", "立春", "春分", "middle_not_quantified"),
    ("yang_high", "阳数太过", "tian", "清明", "小满", "range_40_60"),
    ("yin_insufficient", "阴数不及", "di", "夏至", "处暑", "below_reference"),
    ("yin_middle", "阴数得中", "di", "立秋", "秋分", "middle_not_quantified"),
    ("yin_high", "阴数太过", "di", "寒露", "小雪", "at_least_50"),
)


def _numbers(tian: int, di: int) -> None:
    if any(type(n) is not int or n <= 0 for n in (tian, di)):
        raise ValueError("天地数须为正整数，不能用布尔或去正数后的余数代替。")


def numerical_conditions(tian: int, di: int) -> list[dict[str, Any]]:
    """All eleven literal formulae on pp69–74, including overlapping formulae.

    Odd/even applies to the surplus after subtracting 25/30. For example 26
    has odd surplus 1. The separate 30/40/50 rule must not silently suppress it.
    """
    _numbers(tian, di)
    cases = (
        (
            "lone_yang_unpaired",
            "孤阳不耦",
            69,
            "26<=天<=40; (天-25)%2=1; 地=30",
            26 <= tian <= 40 and (tian - 25) % 2 == 1 and di == 30,
        ),
        (
            "lone_yin_back_yang",
            "孤阴背阳",
            70,
            "32<=地<=60; (地-30)%2=0; 天=25",
            32 <= di <= 60 and (di - 30) % 2 == 0 and tian == 25,
        ),
        (
            "lone_yang_self_pair",
            "孤阳自耦",
            70,
            "天 in {30,40,50}; 地=30",
            tian in {30, 40, 50} and di == 30,
        ),
        (
            "lone_yin_toward_yang",
            "孤阴向阳",
            71,
            "天=25; 40<=地<=60",
            tian == 25 and 40 <= di <= 60,
        ),
        ("yang_partial", "阳偏", 72, "4<=天<=24; 地=30", 4 <= tian <= 24 and di == 30),
        ("yin_partial", "阴偏", 72, "18<=地<=28; 天=25", 18 <= di <= 28 and tian == 25),
        (
            "strong_subdues_weak",
            "以强伏弱",
            72,
            "天 in {30,40,50}; 地<=30",
            tian in {30, 40, 50} and di <= 30,
        ),
        (
            "weak_opposes_strong",
            "以弱敌强",
            73,
            "天=24; 30<=地<=60",
            tian == 24 and 30 <= di <= 60,
        ),
        (
            "peaceful_exact_numbers",
            "安和自宁",
            73,
            "天=25; 地=30",
            tian == 25 and di == 30,
        ),
        ("both_deficient", "天地俱羸", 74, "天<25; 地<30", tian < 25 and di < 30),
        ("both_excess", "阴阳战胜", 74, "天>25; 地>30", tian > 25 and di > 30),
    )
    return [
        {
            "rule_id": key,
            "label": label,
            "source_pdf_page": page,
            "condition": expression,
            "matched": matched,
        }
        for key, label, page, expression, matched in cases
    ]


def _number_fact(
    value: int,
    reference: int,
    weak: tuple[int, int],
    high: int,
    high_upper: Optional[int] = None,
) -> dict:
    high_match = value >= high and (high_upper is None or value <= high_upper)
    weak_match = weak[0] <= value <= weak[1]
    return {
        "value": value,
        "reference": reference,
        "difference": value - reference,
        "comparison": (
            "正数" if value == reference else ("不足" if value < reference else "有余")
        ),
        "extreme_band": ("至弱" if weak_match else ("太过" if high_match else None)),
        "extreme_band_status": (
            "source_range_match"
            if weak_match or high_match
            else (
                "outside_cited_high_range"
                if high_upper is not None and value > high_upper
                else "not_in_cited_extreme_range"
            )
        ),
        "weak_range": list(weak),
        "high_lower_bound": high,
        "high_upper_bound": high_upper,
        "source_pdf_pages": [64, 66],
        "scope": "absolute_numeric_conditions; seasonal_得中_is_not_equality_to_reference",
    }


def seasonal_number_evidence(
    tian: int, di: int, birth: Optional[datetime], *, context_timezone: str = "+00:00"
) -> dict:
    _numbers(tian, di)
    if birth is not None and (birth.tzinfo is None or birth.utcoffset() is None):
        raise ValueError("时令条件需要带时区的出生瞬间，不能猜出生时刻。")
    conditions = numerical_conditions(tian, di)
    result: dict[str, Any] = {
        "ruleset_id": RULESET_ID,
        "version": "1.0.0",
        "source_url": SOURCE_URL + "#page=64",
        "source_pdf_sha256": SOURCE_SHA256,
        "source_pdf_pages": list(range(64, 75)),
        "assessment_status": "literal_conditions_only",
        "numbers": {
            "tian": _number_fact(tian, 25, (4, 8), 40, 60),
            "di": _number_fact(di, 30, (8, 12), 50),
        },
        "numerical_conditions": conditions,
        "matched_pattern_ids": [c["rule_id"] for c in conditions if c["matched"]],
        "seasonal_status": (
            "not_evaluated_missing_birth_instant" if birth is None else "evaluated"
        ),
        "birth_instant_utc": (
            None if birth is None else birth.astimezone(timezone.utc).isoformat()
        ),
        "seasonal_windows": [],
        "overlap_policy": "retain_all_matches; no_priority_or_favorable_override",
        "boundary_policy": "modern_term_instants_start_inclusive_end_exclusive",
        "complete_assessment": False,
        "unresolved": [
            "得中还须时令、爻位、势援与辞理，未以25/30或区间中点代替。",
            "原文阳数不及与得中、阴数不及与得中的时窗重叠，原样保留。",
            "孤阴背阳与向阳、孤阳不耦与自耦等原文数式重叠，不裁定优先级或互相覆盖。",
            "原文俱多以超过正数25/30作具名比较；更广版本及综合强弱仍待校勘。",
            "阳数太过只按本段四十至六十的所录数段比较；超过六十保留未定，不外推其季节适宜性。",
            "数式名只标识原典算式，不是对人的性格、亲属、生死或现实结果的判断。",
        ],
    }
    if birth is None:
        return result
    anchor = birth.astimezone(timezone.utc)
    local_year = localize_datetime(birth, context_timezone).year
    environment = get_solar_term_environment_key(year=local_year)
    terms = _term_window(birth, context_timezone)
    windows = []
    for key, label, axis, start_name, end_name, band in SEASON_WINDOWS:
        try:
            start = max(
                (
                    t
                    for t in terms
                    if t.name == start_name
                    and t.moment.astimezone(timezone.utc) <= anchor
                ),
                key=lambda t: t.moment.astimezone(timezone.utc),
            )
            end = min(
                (
                    t
                    for t in terms
                    if t.name == end_name
                    and t.moment.astimezone(timezone.utc)
                    > start.moment.astimezone(timezone.utc)
                ),
                key=lambda t: t.moment.astimezone(timezone.utc),
            )
        except ValueError as exc:
            raise NumerologySourceError("runtime_heluo_solar_context_conflict") from exc
        for term in (start, end):
            try:
                require_calculated_solar_term(term)
            except RuntimeError as exc:
                raise NumerologySourceError(
                    "runtime_heluo_solar_context_conflict"
                ) from exc
        active = (
            start.moment.astimezone(timezone.utc)
            <= anchor
            < end.moment.astimezone(timezone.utc)
        )
        value, reference = (tian, 25) if axis == "tian" else (di, 30)
        band_match = (
            value < reference
            if band == "below_reference"
            else (
                40 <= value <= 60
                if band == "range_40_60"
                else value >= 50 if band == "at_least_50" else None
            )
        )
        band_status = (
            "not_quantified" if band == "middle_not_quantified" else "compared"
        )
        if band == "range_40_60" and value > 60:
            band_match = None
            band_status = "outside_cited_high_range"
        windows.append(
            {
                "rule_id": key,
                "label": label,
                "axis": axis,
                "source_pdf_page": 67,
                "start_term": start_name,
                "end_term": end_name,
                "start_at": start.moment.astimezone(timezone.utc).isoformat(),
                "end_at": end.moment.astimezone(timezone.utc).isoformat(),
                "start_source": start.as_dict(),
                "end_source": end.as_dict(),
                "start_provider": start.resolution_provider,
                "end_provider": end.resolution_provider,
                "active": active,
                "numeric_condition": band,
                "numeric_band_match": band_match,
                "numeric_band_status": band_status,
                "scope": "numeric_condition_only; not_combined_seasonal_judgment",
            }
        )
    result["seasonal_windows"] = windows
    result["context_timezone"] = context_timezone
    result["context_local_year"] = local_year
    if get_solar_term_environment_key(year=local_year) != environment:
        raise NumerologySourceError("runtime_heluo_solar_context_conflict")
    return result


def seasonal_snapshot(evidence: dict) -> str:
    numbers = evidence["numbers"]
    lines = [
        "[二数与时令·原典条件]",
        "; ".join(
            f"{name}{numbers[axis]['value']}（{numbers[axis]['comparison']}"
            + (
                f"；绝对数段{numbers[axis]['extreme_band']}"
                if numbers[axis]["extreme_band"]
                else ""
            )
            + "）"
            for axis, name in (("tian", "天数"), ("di", "地数"))
        ),
    ]
    matched = [c["label"] for c in evidence["numerical_conditions"] if c["matched"]]
    lines.append("数式条件：" + ("、".join(matched) if matched else "本组未命中"))
    if evidence["seasonal_status"] == "evaluated":
        active = [w for w in evidence["seasonal_windows"] if w["active"]]
        for window in active:
            match = window["numeric_band_match"]
            detail = (
                (
                    "超出所核数段，不外推"
                    if window["numeric_band_status"] == "outside_cited_high_range"
                    else "数值条件未量化，不作自动裁定"
                )
                if match is None
                else ("对应绝对数段命中" if match else "对应绝对数段未命中")
            )
            lines.append(
                f"时窗{window['label']}：{window['start_term']}至{window['end_term']}；{detail}"
            )
        if not active:
            lines.append("出生瞬间不在该段列出的六个时窗内；其他时令规则须另查。")
    else:
        lines.append("缺出生瞬间，未评估时令条件。")
    lines.append("保留同时成立的数式和时窗；尚未裁定综合得中或葉否。")
    return "\n".join(lines)
