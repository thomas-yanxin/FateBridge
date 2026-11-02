"""Keep calendrical day names separate from named ritual phase conditions."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from fatebridge.core.sukuyo_sources import load_source

SOURCE = Path(__file__).resolve().parents[1] / "data/sukuyo_phase_clock.json"


def _numeral(value: str) -> int:
    digits = {c: i for i, c in enumerate("一二三四五六七八九", 1)}
    if value == "十":
        return 10
    if value in digits:
        return digits[value]
    tens, separator, ones = value.partition("十")
    if not separator:
        raise ValueError("未识别的原句日号")
    return (digits[tens] if tens else 1) * 10 + (digits[ones] if ones else 0)


def validate_selected_claims(data: dict[str, Any]) -> None:
    """Bind numerical controls to selected text, without judging its truth."""
    sources = {row["id"]: row for row in data["sources"]}
    if len(sources) != len(data["sources"]) or set(sources) != {"T1796", "T2216"}:
        raise ValueError("定日分时来源必须完整唯一")
    quotes: dict[tuple[str, str], str] = {}
    for source in sources.values():
        for row in source["selected_quotations"]:
            key = source["id"], row["id"]
            if key in quotes:
                raise ValueError("定日分时选段重复")
            quotes[key] = row["literal"]
    required = {
        ("T1796", "phase_condition"),
        ("T1796", "time_wording"),
        ("T2216", "morning_character"),
        ("T2216", "phase_commentary"),
        ("T2216", "thirty_time_debate"),
    }
    if set(quotes) != required:
        raise ValueError("定日分时选段不完整")
    phase = data["phase_day_distinction"]
    condition = phase["conditional_source_case"]
    text = quotes[condition["source_id"], condition["quote_id"]]
    consequence = re.search(r"其月([一二三四五六七八九十]+)日即屬([黑黒白])分", text)
    moon_days = re.search(
        r"定望或在([一二三四五六七八九十]+)日或在([一二三四五六七八九十]+)日", text
    )
    full_name = re.search(r"月望正圓滿時名為(白分[一二三四五六七八九十]+日)", text)
    quarter_name = re.search(r"月正半如弦時亦為([一二三四五六七八九十]+日)", text)
    if (
        not consequence
        or not moon_days
        or not full_name
        or not quarter_name
        or type(condition["assumed_civil_day_number"]) is not int
        or condition["assumed_civil_day_number"] != _numeral(consequence[1])
        or condition["ritual_half_under_stated_condition"]
        != consequence[2].replace("黒", "黑")
        or condition["condition_literal"] not in text
        or condition["consequence_literal"] not in text
        or phase["phase_reference"]["full_moon_civil_day_examples"]
        != [_numeral(moon_days[1]), _numeral(moon_days[2])]
        or phase["phase_reference"]["full_moon_source_name"] != full_name[1]
        or phase["phase_reference"]["quarter_source_name"] != quarter_name[1]
    ):
        raise ValueError("定日月相控制未绑定所选原句")
    comment = phase["commentarial_case"]
    text = quotes[comment["source_id"], comment["quote_id"]]
    case = re.search(
        r"月望正圓滿位在([一二三四五六七八九十]+)日.*其月([一二三四五六七八九十]+)日以屬([黑黒白])分",
        text,
    )
    if (
        not case
        or type(comment["full_moon_at_civil_day"]) is not int
        or type(comment["next_civil_day"]) is not int
        or comment["full_moon_at_civil_day"] != _numeral(case[1])
        or comment["next_civil_day"] != _numeral(case[2])
        or comment["next_day_half_under_stated_condition"]
        != case[3].replace("黒", "黑")
    ):
        raise ValueError("注疏条件日号未绑定所选原句")
    morning = data["morning_reference"]
    text = quotes[morning["source_id"], morning["quote_id"]]
    if any(
        morning[key] not in text
        for key in ("morning_gloss_literal", "character_distinction_literal")
    ):
        raise ValueError("晨辰说明未绑定所选原句")
    time = data["time_wording_reference"]
    if time["T1796_literal"] not in quotes["T1796", "time_wording"] or any(
        literal not in quotes["T2216", "thirty_time_debate"]
        for literal in [
            time["T2216_question_literal"],
            *time["T2216_unresolved_literals"],
        ]
    ):
        raise ValueError("三十时争议未绑定所选原句")


def phase_clock_reference(day: int) -> dict[str, Any]:
    if type(day) is not int or not 1 <= day <= 30:
        raise ValueError("历日命名只支持1..30整数日号")
    loaded = load_source(SOURCE)
    reference = loaded.data
    validate_selected_claims(reference)
    return {
        **reference,
        "source_bundle_sha256": loaded.sha256,
        "host_day_number_reference": {
            "lunar_day": day,
            "named_half": "白" if day <= 15 else "黑",
            "named_half_day": (day - 1) % 15 + 1,
            "basis": "selected_T1299_calendrical_day_number_nomenclature",
            "ritual_phase_condition_status": "not_evaluated",
            "physical_lunar_phase_or_tithi_computed": False,
            "source_conditional_case_applied_to_this_date": False,
            "input_day_or_mansion_changed": False,
        },
    }


def phase_clock_lines(reference: dict[str, Any]) -> list[str]:
    current = reference["host_day_number_reference"]
    return [
        f"定日与历日名分开：本次日号{current['lunar_day']}，按所选T1299历日命名为"
        f"{current['named_half']}月第{current['named_half_day']}日；这不是实测月相或角距tithi。"
        "《大毘卢遮那成佛经疏》所选段另说小月在白分内时，其月十五日即属黑分，"
        "并说定望或在十四、十六日，月正圆满名为白分十五日、如弦时亦为八日；"
        "这是另一个具名条件层，不能只凭民用小月二十九天就判定条件成立，亦未将该条件套到本次日期。",
        "《大日经疏演奥钞》所选解释以晨朝、平明释仪轨起首之晨，"
        "另辨晨与辰不可通用；它没有认证所有历日或七曜统一在某个现代钟时、太阳高度换日。"
        "该注疏另举望在十四、十五日属黑分的条件，未据此改本次日号、主宿或补配分支。",
        "分时异说：《大毘卢遮那成佛经疏》原句为昼夜各有三十时；"
        "《大日经疏演奥钞》保留日夜通计三十时与各字解释的讨论，并有尚未详、后释本据尚未分明等意见。"
        "保留所引论疏及注者意见的层次，没有把争议统一为已认证的三十或六十等分、现代分钟，"
        "也没有替换T1299昼八夜八或桧尾前后半。",
    ]
