"""Qualified day/month quotations and exact arithmetic on written quantities."""

from __future__ import annotations

import hashlib
import json
import re
from fractions import Fraction
from pathlib import Path
from typing import Any

from fatebridge.core.sukuyo_sources import load_source
from fatebridge.core.sukuyo_zhidu_pointer_scope import (
    pointer_count_scope,
    pointer_scope_lines,
    strict_reference_equal,
)

SOURCE = Path(__file__).resolve().parents[1] / "data/sukuyo_zhidu_month_context_v1.json"
DATA_SHA256 = "b140a869f1b4a13eb8e1ab72061160393118d17f9ee9b3867f08a1a80fc5d3c2"
FACTS_SHA256 = "5b6846ff81f7a097ab9cc00d2fb09f928c09119c21e2738604235a1d3f4a7cff"
NUMERAL = r"[一二三四五六七八九十百]+"


def validate_zhidu(data: dict[str, Any]) -> None:
    raw = json.dumps(
        data, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    if hashlib.sha256(raw).hexdigest() != FACTS_SHA256:
        raise ValueError("日月岁原文、校记归属或未定条件改变，须重新核验")


def _number(literal: str) -> int:
    digits = {c: n for n, c in enumerate("一二三四五六七八九", 1)}
    match = re.fullmatch(
        r"(?:([一二三四五六七八九])百)?"
        r"(?:([一二三四五六七八九])?十)?"
        r"([一二三四五六七八九])?",
        literal,
    )
    if not literal or match is None:
        raise ValueError("所选月长数词不在已核语法内")
    hundreds, tens, ones = match.groups()
    return (
        (digits[hundreds] * 100 if hundreds else 0)
        + ((digits[tens] if tens else 1) * 10 if "十" in literal else 0)
        + (digits[ones] if ones else 0)
    )


def _compact(literal: str) -> str:
    return re.sub(r"[\s，。；：、]", "", literal)


def _month_quantity(row: dict[str, Any]) -> Fraction:
    literal = _compact(row["main_literal"])
    prefix = row["main_term"] + "者"
    if not literal.startswith(prefix):
        raise ValueError("月名与该位次的定义不一致")
    match = re.fullmatch(
        rf"({NUMERAL})日(?:(半)|加({NUMERAL})分之({NUMERAL}))?",
        literal[len(prefix) :],
    )
    if match is None:
        raise ValueError("所选月长缺少可核的原句")
    whole, half, denominator, numerator = match.groups()
    kind = (
        "half_increment" if half else "fraction_increment" if denominator else "whole"
    )
    if row["definition_kind"] != kind:
        raise ValueError("月长运算类型不符合该位次原句")
    result = Fraction(_number(whole))
    if half:
        return result + Fraction(1, 2)
    if denominator is not None and numerator is not None:
        return result + Fraction(_number(numerator), _number(denominator))
    return result


def _rational(value: Fraction) -> dict[str, int]:
    return {"numerator": value.numerator, "denominator": value.denominator}


def _nominal_ledger(data: dict[str, Any]) -> dict[str, Any]:
    values: dict[str, dict[str, Fraction]] = {}
    models = {}
    for source_id, rows in data["month_definitions"].items():
        if [row["slot_id"] for row in rows] != [f"month_{i}" for i in range(1, 5)]:
            raise ValueError("四种月的位次不得按重名合并或重排")
        values[source_id] = {row["slot_id"]: _month_quantity(row) for row in rows}
        models[source_id] = [
            {"slot_id": row["slot_id"], **_rational(values[source_id][row["slot_id"]])}
            for row in rows
        ]
        year = re.search(
            rf"是歲({NUMERAL})日",
            _compact(data["intercalation_and_year"][source_id]["year_literal"]),
        )
        if year is None or _number(year[1]) != 366:
            raise ValueError("名义岁数未保留所选原字")
    # This deliberately added uniform-cycle hypothesis uses the first two
    # T1509 definitions. It is not a reconstruction of either book's calendar.
    first12 = 12 * values["T1509"]["month_1"]
    second12 = 12 * values["T1509"]["month_2"]
    gap = first12 - second12
    return {
        "source_unit": "formal written日 quantities only; no modern second or measured day equivalence established",
        "models": models,
        "month4_written_T2122_minus_T1509": _rational(
            values["T2122"]["month_4"] - values["T1509"]["month_4"]
        ),
        "conditional_12_month1_days": _rational(first12),
        "conditional_12_month2_days": _rational(second12),
        "conditional_cycle_gap_days": _rational(gap),
        "conditional5_cycle_gap_days": _rational(5 * gap),
        "conditional5_cycle_gap_in_month2_units": _rational(
            5 * gap / values["T1509"]["month_2"]
        ),
        "historical_intercalation_schedule_established": False,
    }


def zhidu_reference() -> dict[str, Any]:
    loaded = load_source(SOURCE)
    if loaded.sha256 != DATA_SHA256:
        raise ValueError("日月岁资料字节改变，须重新冻结来源")
    data = loaded.data
    validate_zhidu(data)
    return {
        "source_data": data,
        "source_bundle_sha256": loaded.sha256,
        "before_code_reference_sha256": DATA_SHA256,
        "nominal_arithmetic": _nominal_ledger(data),
        "apparatus_pointer_scope": pointer_count_scope(data, loaded.sha256),
    }


def zhidu_lines(reference: dict[str, Any]) -> list[str]:
    data = reference["source_data"]
    validate_zhidu(data)
    if any(
        type(reference.get(key)) is not str or reference[key] != DATA_SHA256
        for key in ["source_bundle_sha256", "before_code_reference_sha256"]
    ):
        raise ValueError("日月岁说明的来源身份与已冻结原文不一致")
    if not strict_reference_equal(
        reference["nominal_arithmetic"], _nominal_ledger(data)
    ):
        raise ValueError("名义月长诊断与本次所选来源不一致")
    scope = pointer_count_scope(data, reference["source_bundle_sha256"])
    if not strict_reference_equal(reference.get("apparatus_pointer_scope"), scope):
        raise ValueError("校记定位说明与本次来源口径不一致")
    return [
        "上游日月岁语境：《大智度論》卷48《四念處品第十九》所选日段作从旦至旦，"
        "并列五月至、十一月至及具体昼夜数。后出的《演密鈔》和《指心鈔》所选引段"
        "省至字并缩作十一月翻，三分中各五时是后引说明，未反写成原论原句。"
        "《法苑珠林》所选段为卷四、日月篇第三、虧盈部第七；"
        "引文开头的阿鞞跋致品来自原论前一解释，不能改作本段实际品题。"
        "这些是引用比较，具体古代引本与完整传承仍未认证。",
        "原论四种月按定义位次分别保留：日月61/2、世间月30、月月914/31、"
        "星宿月1830/67，均是原文名义日量。《法苑珠林》星宿月另作547/20；"
        "两个字面有理数之差为49/1340，不是实测天文误差或现代秒数。"
        "月长概列与详细分数分层，不按枚举位次配对；二十九日与二十九日半、"
        "概列的七／九【石】异读均保留，不自动改详细星宿月公式。"
        "第三项月月的首月另报日【石】，会与第一项日月重名，仍按四个定义位次保留；"
        "同条校记的两处复用不是两份见证，也未重建完整石本。",
        "闰月句说从日月、世间月二事中出；原论所选岁句列或十二月或十三月，"
        "《法苑珠林》所选引段只载或十三月，未替它补入十二月，也不解释为每年一律十三月。"
        "两处三百六十六日原数保留。另加十二个61/2与十二个30均匀周期的假设，"
        "相差6，重复五个理想周期得30，只是额外假设下的算术，未成为实际五年置闰表。"
        "月长中的半日量不是日内前后半或白黑半月，不能据此选择本次原典半日、"
        "平明钟点或闰小月补配先后。",
        "所选大正印页p409页眉为卷49，历法段仍在卷48卷末之前；卷末校注另报"
        "四十八＝十五【石】，未据连续卷序改字。《法苑珠林》末旦／日校记属于该书日名句，"
        "与原论月月的月／日及《指心鈔》夕／且各有归属，不能互移。"
        "该页后段滅／減仍未唯一，双行小字与圈点的复视更正另存，未宣称全页图文一致。"
        "印页、电子正文和校记均不独立认证古本谱系、现代切日或现实预测效力；"
        "本组名义数没有改写本次宿主历日或主宿候选。",
    ] + pointer_scope_lines(scope)
