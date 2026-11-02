"""Scoped 1992 author transcriptions of three Shogonji calendars.

Month headings and untimed marginal annotations do not establish Hinoo's
half-day clock or the priority of two modern reconstructions.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from fatebridge.core.sukuyo_sources import load_source

SOURCE = Path(__file__).resolve().parents[1] / "data/sukuyo_naoj_shogonji_headers.json"
ALIASES = str.maketrans("畢參張虛", "毕参张虚")


def month_header_reference(
    year: int, month: int, leap: bool, day: int
) -> dict[str, Any] | None:
    if year not in (1345, 1346, 1347):
        return None
    record = load_source(SOURCE)
    bundle = record.data
    row = next(
        (
            r
            for r in bundle["records"]
            if (r["lunar_year"], r["month"], r["leap"]) == (year, month, leap)
        ),
        None,
    )
    if row is None:
        return None
    return {
        "id": bundle["id"],
        "source_url": bundle["source_url"],
        "publisher_pdf_sha256": bundle["publisher_pdf_sha256"],
        "source_bundle_sha256": record.sha256,
        "pre_comparison_transcription_sha256": bundle[
            "pre_comparison_transcription_sha256"
        ],
        "authors": deepcopy(bundle["authors"]),
        "title": bundle["title"],
        "publication": bundle["publication"],
        "header": deepcopy(row),
        "year_header_variants": [
            deepcopy(v)
            for v in bundle["year_header_variants"]
            if v["lunar_year_author_assignment"] == year
        ],
        "author_placement_notes": [
            deepcopy(v)
            for v in bundle["author_placement_notes"]
            if (v["lunar_year"], v["month"]) == (year, month)
        ],
        "current_day_is_month_first": day == 1,
        "marginal_annotation_records_half_or_clock": False,
        "original_manuscript_images_independently_read": False,
        "source_is_study_author_transcription": True,
        "generic_prose_anchors_fill_missing_annotations": False,
        "ancient_day_boundary_accepted": False,
        "hinoo_rule_priority_accepted": False,
        "reference_applied_to_primary_mansion": False,
        "corpus": {
            "years": [1345, 1346, 1347],
            "month_headers": 37,
            "clear_marginal_pairs": 27,
            "qualified_marginal_pairs": 2,
            "marginals_not_visible_in_selected_header": 8,
            "total_days_from_month_lengths": 1092,
            "daily_annotations_transcribed": False,
            "independent_real_world_prediction_samples": 0,
        },
        "scope": bundle["scope"],
        "absence_policy": bundle["absence_policy"],
        "placement_policy": bundle["placement_policy"],
    }


def header_reading(
    reference: dict[str, Any], selection: dict[str, Any] | None = None
) -> list[str]:
    row = reference["header"]
    lines = [
        f"神田泰、伊藤節子、岡田芳朗1992年《荘厳寺で発見された仮名暦の調査》"
        f"第{row['printed_page']}页月首转写：{row['lunar_year']}年"
        f"{'闰' if row['leap'] else ''}{row['month']}月，月长{row['length_days']}日；"
        f"月首初一干支{row['day_one_ganzhi']}。这是研究作者转写，未独立校读原卷；"
        "37个月首不等于1092天逐日宿曜实录或预测样本。"
    ]
    lines.append(
        "其中27条清晰朱注、2条带限定，8处所选栏未见可读朱注；"
        "1092是月长合计，没有逐日转写，不增加独立历史或现实预测样本。"
    )
    if reference["year_header_variants"]:
        lines.append(
            "首年1345沿用研究作者的康永四年归属；附录第237页岁首字面却为"
            "康永二年，同栏年干支为乙酉。二／四差异未改字，未独立核读原卷"
            "或确定刊误原因，也未据此重置历法年份。"
        )
    if row["lunar_year"] == 1345 and row["month"] == 4:
        lines.append(
            "作者第232页说明3指出四月朱印位于初一与初二之间，并判断应属初一；"
            "位置、作者订正意见与假名字形疑读分别保留。"
        )
    mansion = row["marginal_mansion_normalized_candidate"]
    if mansion is None:
        lines.append(
            "所选月首栏未见可读宿曜朱注；未用作者转引的渡边敏夫配宿表补缺，"
            "也未断言原卷无注。"
        )
    else:
        literal = "／".join(row["marginal_mansion_literal_candidates"])
        lines.append(
            f"月首宿注读作{literal}，规范化候选为{mansion.translate(ALIASES)}；"
            f"曜注{row['marginal_weekday_literal']}，规范化候选为"
            f"{row['marginal_weekday_normalized_candidate']}曜。"
        )
        if row["marginal_status"] == "kana_glyph_uncertain":
            lines.append("该宿注假名字形仍有疑读，两个读字候选均保留。")
        if row["marginal_status"] == "displaced_stamp":
            lines.append(
                "1345年五月朱印在表中偏至二日栏上；按作者正文归属月首，"
                "保留错位，未改成二日实录。"
            )
        if reference["current_day_is_month_first"] and selection:
            selected = selection.get("natal_su27")
            if selected:
                relationship = (
                    "相同" if selected == mansion.translate(ALIASES) else "不同"
                )
                lines.append(
                    f"本次主宿{selected}与月首朱注候选{relationship}；"
                    "朱注未记前后半或钟时，该比较不能验收所选半日规则。"
                )
            else:
                lines.append("本次主宿未定，月首朱注未用于消除补配候选。")
    if not reference["current_day_is_month_first"]:
        lines.append("本日不是初一，上述宿曜朱注不作为本日的直接观测或记载。")
    if row["leap"]:
        lines.append(
            "1346年闰九月虽记同宿，两种已声明补配次序在此同得氐；"
            "此例没有区分力，不能确立次序优先级。"
        )
    lines.append(
        "该历书未提供所选朱注的半日或钟时，不能据此确定平明、民用正午或"
        "Hinoo半日界，也未证明全部古代历法；1345年正文五行是纳音，不能当七曜。"
    )
    return lines
