"""Source-specific water-clock counts, without adopting an ancient civil clock."""

from __future__ import annotations

import re
from math import gcd
from pathlib import Path
from typing import Any

from fatebridge.core.sukuyo_sources import load_source

SOURCE = Path(__file__).resolve().parents[1] / "data/sukuyo_waterclock_sources.json"


def _number(text: str) -> int:
    digits = {c: n for n, c in enumerate("一二三四五六七八九", 1)}
    if text == "兩":
        return 2
    if text in digits:
        return digits[text]
    tens, sep, ones = text.partition("十")
    if sep:
        return (digits[tens] if tens else 1) * 10 + (digits[ones] if ones else 0)
    raise ValueError("未识别的漏刻原文数词")


def _extract(pattern: str, text: str) -> int:
    match = re.search(pattern, text)
    if match is None:
        raise ValueError("漏刻数值缺少所选原文支持")
    return _number(match[1])


def _equal(value: Any, expected: Any) -> None:
    if type(value) is not type(expected) or value != expected:
        raise ValueError("漏刻控制与所选原文、单位或来源层不一致")


def validate_source_controls(data: dict[str, Any]) -> None:
    """Check the numerical and textual layers, never certify their physical truth."""
    source = data["T2125"]
    quotes = {k: v["literal"] for k, v in source["selected_quotations"].items()}
    nalanda = source["nalanda"]
    checks = [
        (
            nalanda["sinkings_per_named_part"],
            r"([一二三四五六七八九十]+)椀四下",
            "nalanda",
        ),
        (
            nalanda["named_parts_per_day_and_night"],
            r"成([一二三四五六七八九十]+)時也",
            "nalanda",
        ),
        (
            nalanda["named_parts_to_noon"],
            r"名([一二三四五六七八九十兩]+)時，即正午",
            "nalanda",
        ),
        (
            nalanda["calibration_sinkings_dawn_to_noon"],
            r"旦至午時([一二三四五六七八九十]+)椀",
            "calibration",
        ),
        (
            source["mahbodhi_kusinagara"]["sinkings_dawn_to_noon"],
            r"從旦至中椀沈([一二三四五六七八九十]+)",
            "other_places",
        ),
        (
            source["kulun"]["noon_drum_strikes"],
            r"([一二三四五六七八九十]+)椎至中",
            "other_places",
        ),
        (
            source["kulun"]["night_drum_strikes"],
            r"夜同斯([一二三四五六七八九十]+)",
            "other_places",
        ),
        (
            source["kulun"]["day_night_drum_strikes"],
            r"總成([一二三四五六七八九十]+)",
            "other_places",
        ),
    ]
    for value, pattern, key in checks:
        _equal(value, _extract(pattern, quotes[key]))
    _equal(
        nalanda["sinkings_per_named_part"] * nalanda["named_parts_to_noon"],
        nalanda["calibration_sinkings_dawn_to_noon"],
    )
    _equal(
        source["calibration"]["dawn_to_noon_sinkings"],
        nalanda["calibration_sinkings_dawn_to_noon"],
    )
    for key in (
        "ordinary_sinking_drums",
        "first_special_signal",
        "second_special_signal",
    ):
        if nalanda[key] not in quotes["nalanda"]:
            raise ValueError("计碗与报时信号未绑定原文")
    for key in ("condition_literal", "shortening_literal", "lengthening_literal"):
        if source["calibration"][key] not in quotes["calibration"]:
            raise ValueError("季节校准原句不完整")
    for key in ("literal", "quoted_rule_literal"):
        if source["local_noon"][key] not in quotes["local_context"]:
            raise ValueError("当地日中说明不在所选原段")
    for row in source["retained_unadjudicated_literals"]:
        if row["literal"] not in "".join(quotes.values()):
            raise ValueError("未定字句不在所选原段")
    for value in [
        nalanda["special_signal_hits_are_bowl_sinkings"],
        source["mahbodhi_kusinagara"]["whole_day_night_sinkings_established"],
        source["kulun"]["count_is_bowl_sinkings"],
        source["calibration"]["half_scoop_is_half_bowl"],
        source["calibration"]["adjustment_seconds_established"],
        source["local_noon"]["single_global_clock_noon_established"],
        source["clock_word_mapping_to_T1299_pingming_or_T2465_half_established"],
        data["scope"]["runtime_host_or_mansion_override"],
    ]:
        _equal(value, False)
    _equal(source["mahbodhi_kusinagara"]["whole_day_night_sinkings"], None)
    _equal(source["calibration"]["fixed_modern_seconds_per_sinking"], None)
    comparison = data["T2216_internal_comparison"]
    for row in (comparison["early"], data["T1299_control"]):
        literal = row.get("main_literal", row.get("literal", ""))
        _equal(
            row["day_parts"],
            _extract(r"[每毎]日分[為爲]([一二三四五六七八九十]+)時", literal),
        )
        _equal(
            row["night_parts"],
            _extract(r"夜亦分[為爲]([一二三四五六七八九十]+)時", literal),
        )
    later = comparison["later"]
    _equal(
        later["total_day_night_parts"],
        _extract(r"晝夜([一二三四五六七八九十]+)時", later["main_literal"]),
    )
    _equal(later["inline_small_type"]["0233b14"], ["下之十五", "晝四時夜四時"])
    note = later["inline_small_type"]["0233b14"][1]
    _equal(
        later["day_parts_in_small_type"],
        _extract(r"晝([一二三四五六七八九十]+)時", note),
    )
    _equal(
        later["night_parts_in_small_type"],
        _extract(r"夜([一二三四五六七八九十]+)時", note),
    )
    _equal(
        later["day_parts_in_small_type"] + later["night_parts_in_small_type"],
        later["total_day_night_parts"],
    )
    if later["conjectural_marker"] != "歟" or "正著時歟" not in later["main_literal"]:
        raise ValueError("不可丢失原文疑问标记")
    _equal(comparison["counts_equal"], False)
    _equal(comparison["editorial_or_witness_cause_resolved"], False)


def _counter_row(completed: int, per_part: int) -> dict[str, Any]:
    groups, remainder = divmod(completed, per_part)
    divisor = gcd(completed, per_part)
    return {
        "completed_sinkings": completed,
        "complete_groups": groups,
        "remaining_sinkings": remainder,
        "elapsed_named_parts": {
            "numerator": completed // divisor,
            "denominator": per_part // divisor,
        },
    }


def nalanda_group_count(completed_sinkings: int) -> dict[str, Any]:
    loaded = load_source(SOURCE)
    data = loaded.data
    validate_source_controls(data)
    n = data["T2125"]["nalanda"]
    limit = n["sinkings_per_named_part"] * n["named_parts_per_day_and_night"]
    if type(completed_sinkings) is not int or not 0 <= completed_sinkings <= limit:
        raise ValueError(
            f"声明的一周期累计计碗须为0..{limit}整数；不接受布尔、钟时或自动取模"
        )
    row = _counter_row(completed_sinkings, n["sinkings_per_named_part"])
    fraction = row["elapsed_named_parts"]
    return {
        **row,
        "source_bundle_sha256": loaded.sha256,
        "physical_clock_conversion": False,
        "reading_text": (
            f"按所选那烂陀每{n['sinkings_per_named_part']}碗一时的累计计碗模型，"
            f"{completed_sinkings}碗为{row['complete_groups']}组余{row['remaining_sinkings']}碗，"
            f"即{fraction['numerator']}/{fraction['denominator']}个本书名时计数单位。"
            "零是声明计数器的起点，不是已观测时刻；未据此换算现代秒数，"
            "也未建立T1299平明、古代民用日界或桧尾前后半的映射。"
        ),
    }


def source_specific_time_reference() -> dict[str, Any]:
    from fatebridge.core.sukuyo_daybreak_criteria import daybreak_reference

    loaded = load_source(SOURCE)
    data = loaded.data
    validate_source_controls(data)
    n = data["T2125"]["nalanda"]
    k = data["T2125"]["kulun"]
    comparison = data["T2216_internal_comparison"]
    early, later = comparison["early"], comparison["later"]
    total = n["sinkings_per_named_part"] * n["named_parts_per_day_and_night"]
    return {
        **data,
        "source_bundle_sha256": loaded.sha256,
        "daybreak_source_comparison": daybreak_reference(),
        "count_arithmetic": {
            "nalanda_source_count_consistency": {
                "sinkings_before_first_special_signal": n["sinkings_per_named_part"],
                "sinkings_before_second_special_signal": n["sinkings_per_named_part"]
                * n["named_parts_to_noon"],
                "derived_sinkings_per_eight_named_parts": total,
            },
            "kulun_day_strikes": k["day_night_drum_strikes"] - k["night_drum_strikes"],
            "T2216_parts_totals": [
                early["day_parts"] + early["night_parts"],
                later["total_day_night_parts"],
            ],
        },
        "nalanda_counter_table": [
            _counter_row(i, n["sinkings_per_named_part"]) for i in range(total + 1)
        ],
        "counter_table_is_observed_clock_measurements": False,
    }


def source_specific_time_lines(reference: dict[str, Any]) -> list[str]:
    source = reference["T2125"]
    n = source["nalanda"]
    m = source["mahbodhi_kusinagara"]
    k = source["kulun"]
    counts = reference["count_arithmetic"]
    total = counts["nalanda_source_count_consistency"][
        "derived_sinkings_per_eight_named_parts"
    ]
    return [
        "义净《南海寄归内法传》卷三所选CBETA电子正文"
        f"（{source['selected_complete_context_locator']}）记漏法，从平旦计碗："
        f"那烂陀每{n['sinkings_per_named_part']}碗一时，{n['named_parts_to_noon']}时为正午，"
        f"一日夜共{n['named_parts_per_day_and_night']}时；依此分组为{total}次碗沉。"
        f"普通逐碗击鼓原句为‘{n['ordinary_sinking_drums']}’，续四碗为‘更過四椀同前打四’。"
        f"{n['sinkings_per_named_part']}碗后的吹螺两声另打一声、"
        f"{n['calibration_sinkings_dawn_to_noon']}碗后的另打两声是报时信号，"
        "不能把特别两打读成只沉两碗。"
        "这些是具名来源的计数组合，不是新取得的古代钟表实测或现代分钟。",
        f"同段莫诃菩提及俱尸那寺从旦至中为{m['sinkings_dawn_to_noon']}碗，"
        "没有据半日记录补造全日六十四碗；"
        f"骨崙国为穿孔铜釜水尽一打，至中{k['noon_drum_strikes']}椎，"
        f"夜{k['night_drum_strikes']}打、日夜{k['day_night_drum_strikes']}打。"
        "碗沉、釜尽鼓击、名时和特别报时击数分别保留，不能因数字相同就认作同一单位。",
        "漏器校准原句为先取昼夜停时、旦至午八碗；日夜渐短增其半抄、渐长减其半酌。"
        "半抄、半酌没有被量化为半碗、秒数或线性季节修正式。"
        "原文海东日午、关西未中并引当处日中，不给统一UTC正午；"
        "洛州無影、椀水既盡原字保留，地理／物理解释和校改均未接纳，不能将其改为观测精度证据。",
        "同一《演奥钞》电子版0058a23段引昼八夜八，0233b14段正文则为昼夜八时，"
        "旁排小字为昼四时夜四时，另有下之十五定位小字；不能把十五加入分时数或擅定现代页码。"
        f"两处字面分组总数为{counts['T2216_parts_totals'][0]}与{counts['T2216_parts_totals'][1]}，"
        "后段正著時歟的歟保留。旁排文字作者年代与差异原因未定，两处不是两个独立见证；"
        "未据此改写T1299昼八夜八、宿主参考日、主宿或桧尾半日及闰小月优先。",
    ] + _daybreak_comparison_lines(reference)


def _daybreak_comparison_lines(reference: dict[str, Any]) -> list[str]:
    from fatebridge.core.sukuyo_daybreak_criteria import daybreak_lines

    compared = reference.get("daybreak_source_comparison")
    return daybreak_lines(compared) if compared is not None else []
