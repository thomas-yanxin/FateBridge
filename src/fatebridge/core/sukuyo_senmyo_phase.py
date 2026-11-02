"""Named Senmyo phase-day designation; never a universal civil day boundary."""

from __future__ import annotations

import re
from fractions import Fraction
from pathlib import Path
from typing import Any

from fatebridge.core.sukuyo_sources import load_source

SOURCE = Path(__file__).resolve().parents[1] / "data/sukuyo_senmyo_phase_day.json"


def _ratio(value: Fraction | int) -> dict[str, int]:
    value = Fraction(value)
    return {"numerator": value.numerator, "denominator": value.denominator}


def _normalize(text: str) -> str:
    return re.sub(r"[\s,，.。]", "", text)


def validate_selected_rule(bundle: dict[str, Any]) -> None:
    """Preserve the exception, unit source and separate dawn terms together."""
    ref = bundle["source_reference"]
    sources = {s["id"]: s for s in ref["electronic_sources"]}
    if len(sources) != 3 or set(sources) != {"phase-rule", "clock-units", "twilight"}:
        raise ValueError("宣明弦望所选来源须完整唯一")
    rules = bundle["rules"]
    expected = {
        "quarter_or_full_before_twilight": (
            "弦望定小餘不盈昏明小餘者退一日",
            ["quarter", "full"],
        ),
        "full_moon_eclipse_exception": (
            "其望小餘雖滿此數若交有蝕虧初起在晨初已前者亦如之",
            ["full"],
        ),
    }
    literal = _normalize(sources["phase-rule"]["literal_context"])
    if set(rules) != set(expected) or any(
        rules[key]["literal"] != text
        or text not in literal
        or rules[key]["phase_scope"] != phases
        or type(rules[key]["shift"]) is not int
        or rules[key]["shift"] != -1
        for key, (text, phases) in expected.items()
    ):
        raise ValueError("宣明退日完整条件未绑定所选原句")
    if (
        rules["quarter_or_full_before_twilight"]["comparison"] != "strict_less_than"
        or rules["full_moon_eclipse_exception"]["conjunction"] is not True
        or rules["full_moon_eclipse_exception"]["condition_inputs"]
        != ["has_lunar_eclipse", "initial_before_chenchu"]
        or ref["facsimile"]["normalized_selected_literal"]
        != "".join(text for text, _ in expected.values())
    ):
        raise ValueError("宣明退日比较或食例外未绑定原文")
    unit = bundle["units"]
    keys = [
        "day_units",
        "koku_units",
        "reported_branch_koku",
        "reported_branch_fun",
        "derived_units_per_branch",
        "derived_branches_per_day",
    ]
    if (
        any(type(unit[k]) is not int for k in keys)
        or [unit[k] for k in keys] != [8400, 84, 8, 28, 700, 12]
        or ref["day_unit_source"]["literal_selected"] != "宣明統法八千四百"
        or "刻法八十四" not in _normalize(sources["clock-units"]["literal_context"])
    ):
        raise ValueError("宣明所选单位未绑定原文")
    terms = bundle["terminology"]
    if (
        [
            terms[k]
            for k in ("twilight_literal", "eclipse_morning_literal", "t1299_literal")
        ]
        != ["昏明", "晨初", "平明"]
        or terms["all_three_established_identical"] is not False
        or terms["modern_clock_or_solar_altitude_assigned"] is not False
    ):
        raise ValueError("宣明昏明、晨初与平明不得混同")
    case = bundle["reported_1117_case"]
    if (
        any(
            type(case[key]) is not int or case[key] != value
            for key, value in [
                ("reported_1117_phase_remainder", 2557),
                ("reported_1117_twilight_remainder", 2193),
                ("reported_surplus", 364),
                ("report_claimed_day_shift", 0),
            ]
        )
        or case["selected_report_literals"]
        != ["定望小余二千五百五十七", "小余二千百九十三", "故不退之直以十六日爲定望"]
        or case["has_reported_lunar_eclipse"] is not True
        or case["initial_before_chenchu_established"] is not None
    ):
        raise ValueError("1117报告量及未定晨初条件未绑定所选记录")
    variant = bundle["named_print_variant"]
    if (
        variant["selected_comparison_literal"] != "弦望小餘昏明小餘已下者退"
        or variant["inferred_comparison"] != "less_than_or_equal"
        or variant["equality_conflict_preserved"] is not True
        or variant["selected_goryeosa_rule_changed"] is not False
        or variant["kyoto_equals_cited_waseda_physical_copy"] is not False
        or variant["evaluation_scope"]
        != "selected_literal_comparison_only_not_full_ando_algorithm"
    ):
        raise ValueError("具名安藤刊本的已下边界差异不得合并为高麗史不盈")


def _remainder(value: Fraction | int, day_units: int) -> Fraction:
    if type(value) is not int and not isinstance(value, Fraction):
        raise ValueError("小余须为整数或精确分数，不接受浮点或布尔值")
    result = Fraction(value)
    if not 0 <= result < day_units:
        raise ValueError("所选8400统法小余须在[0,8400)内，不隐式进退日")
    return result


def _evaluate(
    phase: str,
    point: Fraction,
    twilight: Fraction,
    has_lunar_eclipse: bool | None,
    initial_before_chenchu: bool | None,
) -> dict[str, Any]:
    if phase not in {"quarter", "full"}:
        raise ValueError("退日原段仅限弦或望，不扩为朔日规则")
    if any(
        type(v) is not bool and v is not None
        for v in (has_lunar_eclipse, initial_before_chenchu)
    ):
        raise ValueError("食条件须明确为布尔或未知")
    if (
        phase == "quarter"
        and (has_lunar_eclipse is True or initial_before_chenchu is not None)
    ) or (has_lunar_eclipse is False and initial_before_chenchu is True):
        raise ValueError("inconsistent_eclipse_context: 食初条件与弦或无食矛盾")
    early = point < twilight
    if (
        phase == "quarter"
        or has_lunar_eclipse is False
        or initial_before_chenchu is False
    ):
        exception: bool | None = False
    elif has_lunar_eclipse is True and initial_before_chenchu is True:
        exception = True
    else:
        exception = None
    candidates = (
        [-1] if early or exception is True else ([0] if exception is False else [-1, 0])
    )
    return {
        "phase": phase,
        "phase_remainder": _ratio(point),
        "twilight_remainder": _ratio(twilight),
        "has_lunar_eclipse": has_lunar_eclipse,
        "initial_before_chenchu": initial_before_chenchu,
        "phase_before_twilight": early,
        "full_moon_eclipse_exception_applies": exception,
        "candidate_annotation_day_shifts": candidates,
        "annotation_day_shift": candidates[0] if len(candidates) == 1 else None,
        "status": "computed" if len(candidates) == 1 else "partial",
        "shift_scope": "selected_phase_day_designation_not_civil_calendar_rewrite",
        "applied_to_current_input_or_host_calendar": False,
        "physical_eclipse_or_visibility_evaluated": False,
        "chenchu_equal_to_twilight_inferred": False,
    }


def goryeosa_phase_annotation(
    phase: str,
    phase_remainder: Fraction | int,
    twilight_remainder: Fraction | int,
    *,
    has_lunar_eclipse: bool | None = None,
    initial_before_chenchu: bool | None = None,
) -> dict[str, Any]:
    """Evaluate the two explicit clauses with exact units and unknowns retained.

    ``initial_before_chenchu`` is the independently declared truth of that
    source condition. It is never derived by equating 晨初 with 昏明 or a clock.
    """
    loaded = load_source(SOURCE)
    validate_selected_rule(loaded.data)
    unit = loaded.data["units"]["day_units"]
    result = _evaluate(
        phase,
        _remainder(phase_remainder, unit),
        _remainder(twilight_remainder, unit),
        has_lunar_eclipse,
        initial_before_chenchu,
    )
    result = {
        **result,
        "ruleset_id": loaded.data["id"],
        "day_units": unit,
        "source_reference": loaded.data["source_reference"],
        "named_print_variant": loaded.data["named_print_variant"],
        "condition_provenance": "caller_declared_not_independently_verified_by_function",
        "independent_adjudicator_identity": None,
        "source_bundle_sha256": loaded.sha256,
    }
    result["reading_text"] = phase_annotation_reading(result)
    return result


def phase_annotation_reading(result: dict[str, Any]) -> str:
    """Explain the actual conditional domain result, without choosing a date."""

    def number(value: dict[str, int]) -> str:
        n, d = value["numerator"], value["denominator"]
        return str(n) if d == 1 else f"{n}/{d}"

    choices = "／".join(
        "退一日" if shift == -1 else "不退"
        for shift in result["candidate_annotation_day_shifts"]
    )
    comparison = "严格小于" if result["phase_before_twilight"] else "不小于"
    phase = "望" if result["phase"] == "full" else "弦"
    eclipse = {True: "成立", False: "不成立", None: "未知"}
    return (
        f"按所选《高麗史》卷五十宣明历弦望记日条，{phase}定小余"
        f"{number(result['phase_remainder'])}，昏明小余{number(result['twilight_remainder'])}，"
        f"前者{comparison}后者；不盈采用严格小于。"
        "判定须使用两项小余的精确值，不能先四舍五入再比较；显示近似值不能替换判定输入。"
        "取整可能把严格小于变成相等，改变不盈分支；是否仍退还须保留望食例外的独立条件。"
        f"交有月食条件{eclipse[result['has_lunar_eclipse']]}，"
        f"已声明的食初在晨初以前条件{eclipse[result['initial_before_chenchu']]}。"
        + (
            "弦不应用望食例外。"
            if result["phase"] == "quarter"
            else f"望食例外合取条件{eclipse[result['full_moon_eclipse_exception_applies']]}。"
        )
        + (
            f"所选完整条款下仍未定，保留{choices}两候选。"
            if result["status"] == "partial"
            else f"所选条款及声明条件下记日结果为{choices}。"
        )
        + (
            "在相同小余和已声明有月食的前提下对照：晨初条件若未知，保留退一日／不退；"
            "若成立，望食例外使记日退一日；若不成立，则不退。"
            if result["phase"] == "full"
            and not result["phase_before_twilight"]
            and result["has_lunar_eclipse"] is True
            else ""
        )
        + "这些条件由调用者声明；本函数未取得独立核定者身份，"
        "也未从历史文书或天象计算核定条件真伪。"
        + "这是本地领域函数的条件核算，没有确定现代日期、地方钟时、实际月相、"
        "食的可见性或出生历日；晨初条件独立声明，未令晨初等于昏明或T1299平明，"
        "也未裁定桧尾半日、闰小月优先或现实效力。"
        + (
            "另列京都大学藏《長慶宣明暦筭法》所选弦望条“已下”，"
            "按包含相等的文本解释，与此处《高麗史》“不盈”在相等处有差异；"
            "两版本未合并，所选高麗史规则未被替换。京都本未被认作论文所引"
            "早稻田同一实物，也未认证安藤全套食例外或完整宣明历。"
            if result["named_print_variant"]["equality_conflict_preserved"]
            else ""
        )
    )


def phase_annotation_reference() -> dict[str, Any]:
    loaded = load_source(SOURCE)
    data = loaded.data
    validate_selected_rule(data)
    case = data["reported_1117_case"]
    point, twilight = (
        case["reported_1117_phase_remainder"],
        case["reported_1117_twilight_remainder"],
    )
    # A reported eclipse is not the missing 晨初 predicate. The old report's
    # non-retreat claim stays separate from this complete conditional reading.
    evaluation = _evaluate("full", Fraction(point), Fraction(twilight), True, None)
    return {
        **data,
        "source_bundle_sha256": loaded.sha256,
        "reported_case_full_rule_evaluation": evaluation,
        "reported_case_exact_surplus_units": _ratio(point - twilight),
        "current_input_phase_annotation_status": "not_evaluated",
        "historical_report_or_research_error_certified": False,
    }


def phase_annotation_lines(reference: dict[str, Any]) -> list[str]:
    case = reference["reported_1117_case"]
    evaluation = reference["reported_case_full_rule_evaluation"]
    choices = "／".join(
        "退" if shift == -1 else "不退"
        for shift in evaluation["candidate_annotation_day_shifts"]
    )
    return [
        "宣明历弦望记日另作具名对照：《高麗史》卷五十所选原文记弦望定小余不盈昏明小余者退一日；"
        "望若交有食、初亏在晨初以前，即使小余已满前数也有退日例外。"
        "不盈按严格小于比较，不能漏掉望食例外，也不把该段套作所有朔日或民用时刻的统一日界。",
        f"长田直树研究所引1117年勘申记定望小余{case['reported_1117_phase_remainder']}、"
        f"昏明{case['reported_1117_twilight_remainder']}，差{case['reported_surplus']}，报告称不退。"
        "仅按前一比较确实不触发退日；按所选完整望食规则，"
        + (
            "晨初条件尚缺，"
            if evaluation["initial_before_chenchu"] is None
            else "依声明晨初条件，"
        )
        + (
            f"保留{choices}两候选，"
            if evaluation["status"] == "partial"
            else f"条件结果为{choices}，"
        )
        + "未把晨初等同昏明、T1299平明或民用钟点，也未据此认证该历史报告错误。"
        "这是引述例题的条件核算，不是本次输入日期的月相或退日计算；"
        "未改变历日、宿名、桧尾半日或闰小月先后。",
        "京都大学藏《長慶宣明暦筭法》具名刊本所选弦望条作“已下”，"
        "按该词包含相等的文本解释，与《高麗史》“不盈”的严格小于在相等处有差异。"
        "此差异保留为版本对照，没有覆盖所选高麗史规则；京都本也未被认作论文所引早稻田同一实物。"
        "这只核对选定条句，未认证安藤全套食例外或完整宣明历。",
    ]
