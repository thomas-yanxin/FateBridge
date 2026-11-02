"""Named commentarial day divisions and literal Pushya dates, without overrides."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

from fatebridge.core.sukuyo_profiles import fullmoon_calculation
from fatebridge.core.sukuyo_sources import load_source
from fatebridge.core.sukuyo_xuanying import source_chain_lines, standalone_reference

SOURCE = (
    Path(__file__).resolve().parents[1] / "data/sukuyo_commentarial_boundaries.json"
)
MANUSCRIPT_SOURCE = (
    Path(__file__).resolve().parents[1] / "data/sukuyo_homa_pushya_manuscript.json"
)


def _manuscript_reference(
    reference: dict[str, Any], order: Sequence[str]
) -> dict[str, Any]:
    loaded = load_source(MANUSCRIPT_SOURCE)
    manuscript = loaded.data
    cited = next(row for row in reference["sources"] if row["id"] == "T2216")
    if (
        manuscript["T2216_comparison_context"]["publisher_capture_sha256"]
        != cited["capture_sha256"]
    ):
        raise ValueError("护摩抄本对照与所用T2216来源不一致，须重新核验")
    rows = manuscript["monthly_day_observations"]
    if (
        len(rows) != 12
        or {row["month"] for row in rows} != set(range(1, 13))
        or any(
            type(row["month"]) is not int
            or type(row["day"]) is not int
            or not 1 <= row["day"] <= 30
            for row in rows
        )
    ):
        raise ValueError("护摩抄本十二月日必须完整唯一且为合法整数")
    quoted = {
        row["month"]: row["day"]
        for row in reference["monthly_pushya_reference"]["literal_days"]
    }
    comparisons = []
    for row in rows:
        calculation = fullmoon_calculation(row["month"], row["day"], order)
        comparisons.append(
            {
                "lunar_month": row["month"],
                "manuscript_lunar_day": row["day"],
                "manuscript_date_literal": row["literal"],
                "T2216_quoted_lunar_day": quoted[row["month"]],
                "date_matches_quoted_source": row["day"] == quoted[row["month"]],
                "host_mansion": calculation["direct_mansion"],
                "calculation": calculation,
                "manuscript_unique_mansion_literal_accepted": False,
                "applied_as_calendar_override": False,
            }
        )
    return {
        **manuscript,
        "source_bundle_sha256": loaded.sha256,
        "selected_date_comparisons": comparisons,
        "date_controls_matching_T2216": sum(
            row["date_matches_quoted_source"] for row in comparisons
        ),
        "new_independent_historical_observations": 0,
    }


def commentarial_boundary_reference() -> dict[str, Any]:
    # Import at call time: this reference also serves direct calendar-text calls.
    from fatebridge.core.sukuyo_relations import SU27_ORDER

    loaded = load_source(SOURCE)
    reference = loaded.data
    literal = reference["monthly_pushya_reference"]["literal_days"]
    monthly_literal = reference["monthly_pushya_reference"]["quoted_mansion_literal"]
    if (
        len(literal) != 12
        or {row["month"] for row in literal} != set(range(1, 13))
        or any(
            type(row["month"]) is not int
            or type(row["day"]) is not int
            or not 1 <= row["day"] <= 30
            for row in literal
        )
    ):
        raise ValueError("注疏所引十二月日必须完整唯一且为合法整数")
    comparisons = []
    for row in literal:
        calculation = fullmoon_calculation(row["month"], row["day"], SU27_ORDER)
        comparisons.append(
            {
                "lunar_month": row["month"],
                "lunar_day": row["day"],
                "quoted_mansion_literal": monthly_literal,
                "normalized_quoted_mansion": "鬼",
                "host_mansion": calculation["direct_mansion"],
                "matches": calculation["direct_mansion"] == "鬼",
                "calculation": calculation,
            }
        )
    reference["monthly_pushya_reference"].update(
        comparison_basis="ordinary_unsplit_T1299_month_day_not_actual_lunar_position",
        comparisons=comparisons,
        matching_controls=sum(row["matches"] for row in comparisons),
        differing_controls=sum(not row["matches"] for row in comparisons),
        hinoo_half_or_leap_assignment_applied=False,
        source_dates_changed_to_match_host=False,
    )
    reference["second_month_eighth_ninth_comparison"] = [
        fullmoon_calculation(2, day, SU27_ORDER) for day in (8, 9)
    ]
    reference["same_titled_manuscript_reference"] = _manuscript_reference(
        reference, SU27_ORDER
    )
    reference["standalone_xuanying_reference"] = standalone_reference(reference)
    reference["reading_scope"].update(
        same_titled_homa_physical_witness_available=True,
        physical_witness_identified_as_T2216_cited_exemplar=False,
        originals_scope_note=(
            "The selected same-titled Homa manuscript is now available; the exact "
            "cited exemplar is not identified. A standalone named Xuanying edition "
            "and selected facsimile page are available; its cited exemplar and "
            "other nested source originals are not identified."
        ),
    )
    return {**reference, "source_bundle_sha256": loaded.sha256}


def commentarial_boundary_lines(reference: dict[str, Any]) -> list[str]:
    monthly = reference["monthly_pushya_reference"]
    cells = "、".join(
        f"{row['lunar_month']}月{row['lunar_day']}日原引{row['quoted_mansion_literal']}（鬼）／望宿{row['host_mansion']}"
        for row in monthly["comparisons"]
    )
    pair = reference["second_month_eighth_ninth_comparison"]
    manuscript = reference["same_titled_manuscript_reference"]
    return [
        "日界注疏对照：《大日经疏演奥钞》所引《护摩法略钞》的补洒星合日逐月为："
        f"{cells}；{monthly['matching_controls']}条相合、"
        f"{monthly['differing_controls']}条不同。"
        "这里逐项比较未补配T1299普通月日，不是实际月亮位置、历法观测或桧尾半日验收；"
        "八月二十三原引日号保留，未为相合改作二十二，也未改本次主宿。",
        "同疏另述二月八／九日鬼宿之异，转引《一切经音义》的寅时、卯时以前仍属八日分，"
        "以及暦说寅剋以后可属昼分而为九日宿；这是所引两道分日的说明，"
        f"本程序T1299普通月日的二月八日为{pair[0]['direct_mansion']}、"
        f"九日为{pair[1]['direct_mansion']}。"
        "此为后疏所引说明，所选玄应直接条目与其来源层次另见下段；"
        "章实等原本仍未取得，护摩同名抄本也尚未识别为所引版本。"
        "不能认证普遍寅时或卯时换日、现代03:00／05:00、"
        "太阳高度、桧尾前后半或闰小月补配先后，也不能据此移动出生日期。",
        "《金光明最胜王经》所选句将白月八日与布洒星合并列；慧沼《金光明最胜王经疏》"
        "明确说准应但取白八与鬼星合日，未必白八日常与鬼星合。"
        "不能将每月白八自动标为鬼宿；此处没有计算角距tithi或实际月宿合，未从宗教仪轨生成现实行动许可。",
        "实物同题对照：善通寺109-5《护摩法略抄》所选十二月日中，"
        f"{manuscript['date_controls_matching_T2216']}个日号与T2216转引相同，"
        "八月也清楚作二十三；不能把它直接当成SAT的录入错误改为二十二。"
        "这是同名具名抄本，尚未识别为T2216实际引用本，也未确定独立文本谱系、实物年代或全本校勘。"
        "该抄本星名第二字暂列灑／麗候选、未接纳唯一字形，字旁此字未詳批注另存，"
        "批注的具体指字关系、作者及年代未定；"
        "不能依平行文或算法补成已校定鬼宿字样；必得速成与T2216皆得速成分别保留。"
        "十二个日期相合只比较所选日号，不是新增十二次独立观测，亦未确定古代日界、桧尾半日或闰小月先后。",
        *source_chain_lines(reference["standalone_xuanying_reference"]),
    ]
