"""Source-specific fortnight numbering and declared yuga arithmetic only."""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path
from typing import Any

from fatebridge.core.sukuyo_calendar_witnesses import (
    calendar_witness_lines,
    calendar_witness_reference,
)
from fatebridge.core.sukuyo_sources import load_source

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
SOURCE = DATA_DIR / "sukuyo_fortnights.json"
CANONICAL_SHA256 = "e4486a41d1e4b8cd7d78d5f50119d69f2a516e1cc1d138a0b3069f53ef6a947e"


def declared_fortnight_ordinal(
    half: str, day: int, *, black_length: int, white_length: int
) -> int:
    """Count a declared black-first scheme, without selecting one for a date."""
    if (
        type(black_length) is not int
        or black_length not in (14, 15)
        or type(white_length) is not int
        or white_length != 15
    ):
        raise ValueError("本对照须显式声明黑分十四或十五、白分十五；不能默认或扩用")
    if half not in ("black", "white") or type(day) is not int:
        raise ValueError("分日必须为已声明黑白分和整数日号")
    maximum = black_length if half == "black" else white_length
    if not 1 <= day <= maximum:
        raise ValueError("分日超出已声明半月长度；不能补造不存在的黑十五")
    return day if half == "black" else black_length + day


def _declared_yuga_ledger(counts: dict[str, int]) -> dict[str, Any]:
    years = counts["years"]
    regular = years * counts["regular_months_per_year"]
    months = regular + counts["extra_months_total"]
    short = years * counts["short_months_per_year"]
    nominal = months * counts["nominal_full_month_days"]
    omissions = short * counts["days_omitted_per_short_month"]
    days = nominal - omissions
    year, month = Fraction(days, years), Fraction(days, months)
    return {
        "years": years,
        "regular_months": regular,
        "extra_months": counts["extra_months_total"],
        "all_months": months,
        "short_months": short,
        "full_months_derived": months - short,
        "nominal_days_before_short_omissions": nominal,
        "short_omissions": omissions,
        "derived_days": days,
        "derived_mean_year": {
            "numerator": year.numerator,
            "denominator": year.denominator,
        },
        "derived_mean_month": {
            "numerator": month.numerator,
            "denominator": month.denominator,
        },
        "explicit_leap_year_positions": [3, 5],
        "explicit_leap_month_positions": None,
        "actual_leap_month_lengths": None,
        "arithmetic_assumptions_are_not_complete_calendar": True,
    }


def _numbering_validation_scope(cases: list[dict[str, Any]]) -> dict[str, Any]:
    valid = rejected = 0
    for row in cases:
        try:
            value = declared_fortnight_ordinal(
                row["half"],
                row["day"],
                black_length=row["black_length"],
                white_length=row["white_length"],
            )
        except ValueError:
            if row["valid"]:
                raise ValueError("修改前有效编号被意外拒绝")
            rejected += 1
        else:
            if not row["valid"] or value != row["ordinal"]:
                raise ValueError("编号与修改前声明矩阵不一致")
            valid += 1
    if (len(cases), valid, rejected) != (68, 59, 9):
        raise ValueError("声明编号矩阵范围发生变化，须完整重新核验")
    return {
        "declared_cases": len(cases),
        "valid": valid,
        "rejected": rejected,
        "classification": "Declared-numbering input/output and boundary rejection checks",
        "historical_observations": 0,
        "real_samples": 0,
        "rejections_are_source_disagreements_or_prediction_failures": False,
        "valid_fraction_is_calendar_accuracy_or_prediction_probability": False,
    }


def fortnight_calendar_reference(rizang: dict[str, Any]) -> dict[str, Any]:
    loaded = load_source(SOURCE)
    if loaded.sha256 != CANONICAL_SHA256:
        raise ValueError("黑白分来源包已改变，须重新核验原录及编号参考")
    data = loaded.data
    if data["actual_sources"]["T13n0397.xml"]["sha256"] != rizang["source_sha256"]:
        raise ValueError("黑白分对照与日藏具名版本不一致，须重新核验")
    comparative = load_source(DATA_DIR / "sukuyo_comparative_time_units.json").data
    matches = [r for r in comparative["witnesses"] if r["id"] == "T51n2087"]
    if (
        len(matches) != 1
        or matches[0]["source_sha256"]
        != data["actual_sources"]["T51n2087.xml"]["sha256"]
    ):
        raise ValueError("黑白分对照与西域记具名版本不一致，须重新核验")
    t1299 = load_source(DATA_DIR / "sukuyo_t1299_days.json").data
    if t1299["source_sha256"] != data["actual_sources"]["T21n1299.xml"]["sha256"]:
        raise ValueError("黑白分对照与T1299具名版本不一致，须重新核验")
    ledger = _declared_yuga_ledger(data["five_year_diagnostic_assumptions"])
    if ledger != data["before_production_five_year_ledger"]:
        raise ValueError("五年原计数派生账本与修改前参考不一致")
    examples = [
        {
            "black_length": length,
            "white_length": 15,
            "half": "white",
            "day": day,
            "ordinal": declared_fortnight_ordinal(
                "white", day, black_length=length, white_length=15
            ),
        }
        for length in (14, 15)
        for day in (8, 9)
    ]
    return {
        **data,
        "source_bundle_sha256": loaded.sha256,
        "derived_ordinal_examples": examples,
        "numbering_validation_scope": _numbering_validation_scope(
            data["all68_declared_ordinal_cases"]
        ),
        "derived_five_year_ledger": ledger,
        "selected_witness_apparatus_reference": calendar_witness_reference(
            data, loaded.sha256
        ),
    }


def fortnight_calendar_lines(reference: dict[str, Any]) -> list[str]:
    rows = reference["derived_ordinal_examples"]
    ordinals = "、".join(
        f"黑{r['black_length']}白十五时白{r['day']}为全月第{r['ordinal']}" for r in rows
    )
    quarters = "；".join(
        f"{r['season']}三月为{'、'.join(r['names'])}，当此{r['start'][0]}月十六至{r['end'][0]}月十五"
        for r in reference[
            "T2087_four_quarters_original_groups_not12_literal_daily_intervals"
        ]
    )
    schemes = "；".join(
        f"{r['attribution']}：热{r['heat'][0][0]}月十六至{r['heat'][1][0]}月十五、"
        f"雨{r['rain'][0][0]}月十六至{r['rain'][1][0]}月十五、"
        f"寒{r['cold'][0][0]}月十六至{r['cold'][1][0]}月十五，"
        f"雨二后九／寒四后九标为{r['rain_second_white9_chinese_label'][0]}月九／{r['cold_fourth_white9_chinese_label'][0]}月九"
        for r in reference["T1821_all_four_attributed_three_season_schemes"]
    )
    ledger = reference["derived_five_year_ledger"]
    checked = reference["numbering_validation_scope"]
    return calendar_witness_lines(reference["selected_witness_apparatus_reference"]) + [
        "直接纪月来源：《西域记》卷二0875c15所选段称黑分或十四日、十五日，黑前白后合月；"
        f"其四时原组为{quarters}。这是四组三个月名与区间，未冒称十二个独立逐日换历表。"
        f"仅在显式声明的黑先白后编号中，{ordinals}；黑十四不能再取黑十五。"
        "这里的白半／黑半是半月，不是桧尾前半／后半日，也不是角距tithi的物理计算。"
        "未从当前宿主大小月自动选择源历制，原330槽比较仍是声明固定表序，80差异不删。",
        f"完整声明编号矩阵有{checked['declared_cases']}项，{checked['valid']}有效、{checked['rejected']}拒绝。"
        "有效是所声明编号范围内的输入输出相合，拒绝是越界日号的正确拒绝；"
        "九项拒绝不是九项原典冲突或九次预测失败，59／68不是历法正确率。"
        "这些工程编号检查不是独立古代观察或真实样本，不替代原82743历法条件、330槽80异及四轴门槛。",
        f"普光《俱舍论记》0187c16一段各说分层保留：{schemes}。"
        "前三为该段引述并批评的解释，最后是普光此段今解；不把所引真谛说冒称本轮取得的真谛原笔。"
        "这些方俗与论释的区间不同，不能按多数或与当前结果相合来选定古代日界、绝对年或置闰。",
        "法宝《俱舍论疏》0617a08另比较以此方七月十六、八月十六为月初时，白八分别落此方八月八、九月八，"
        "此段自取前者，并明确称节气月日、非月生月尽月日。"
        "其八日之后九日的昼夜增减说明，与玄应曙夜分属九日及后疏寅卯解释分层，不能互相替代成现代钟界。"
        "T2251所引又列此方正月十六至二月十五与十二月十六至正月十五，保留原话十五日进退；"
        "不把它机械变成给任意民用日期加十五天，也未用循环月号换算绝对纪年。",
        "《立世阿毘昙论》0195c16段另记五年一游伽两闰，第一在第三年、第二在第五年；"
        "每四月应两小月，列第三半、第七半，每年六小月，五年共少三十日。"
        f"按事先声明的十二常月／年、两增月、每足月三十日和三十个少一日月作账本，"
        f"得{ledger['all_months']}月、{ledger['short_months']}小月、{ledger['full_months_derived']}足月、"
        f"1860减30为{ledger['derived_days']}日，派生年均366日、月均915／31日。"
        "1830是声明计数的推算，不是原文逐日历表或现代回归年；未定第三、五年的哪一月闰，"
        "也未确定闰月大／小、历元、实际朔时或桧尾补配优先，不代入NAOJ或当前历日。",
        "同篇另说的冬最长日期，T1644所选主文0196b28作十一月九日；T2251引文0183c17作十二月九日，"
        "小字明确有傍本作一误也。这是所引讨论中的明示校改，不能当作新取得独立未改本支持十二；"
        "原录十一及该校改层并存，未按季节对称改写本次所选原典或当前计算。",
    ]
