"""A named printed witness; discrepancies never replace the selected calendar."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from fatebridge.core.sukuyo_sources import load_source

SOURCE = Path(__file__).resolve().parents[1] / "data/sukuyo_koya_1736_month_table.json"
_ALIASES = str.maketrans("虛婁畢參張軫", "虚娄毕参张轸")


def printed_month_reference(
    host: dict[str, Any], upper: dict[str, Any], selection: dict[str, Any], leap: bool
) -> dict[str, Any]:
    """Compare the ordinary month-day cell with the unsplit host calculation.

    A first-half assignment can differ from that host cell. Return both identities
    and never label the ordinary printed table as an observed leap-month result.
    """
    loaded = load_source(SOURCE)
    bundle = loaded.data
    month, day = host["lunar_month"], host["lunar_day"]
    columns = bundle["day_columns"]
    if (
        bundle["month_order"] != [*range(2, 13), 1]
        or len(columns) != 30
        or any(c["day"] != i + 1 or len(c["text"]) != 12 for i, c in enumerate(columns))
    ):
        raise ValueError("具名印本月序或360格上下文不完整")
    if (upper["lunar_month"], upper["lunar_day"]) != (month, day):
        raise ValueError("具名印本与大正异表的比较月日不一致")
    slot = bundle["month_order"].index(month)
    column = columns[day - 1]
    literal = column["text"][slot]
    disputed = next(
        (r for r in bundle["disputed_cells"] if (r["month"], r["day"]) == (month, day)),
        None,
    )
    candidates = disputed["candidate_literals"] if disputed else [literal]
    image = next(r for r in bundle["source_images"] if r["frame"] == column["frame"])
    normalized = literal.translate(_ALIASES) if not disputed else None
    source = {k: deepcopy(v) for k, v in bundle.items() if k != "day_columns"}
    from fatebridge.core.sukuyo_koya_preface import preface_reference

    return {
        "ruleset_id": bundle["id"],
        "source_bundle_sha256": loaded.sha256,
        "source_reference": source,
        "preface_scholarly_reference": preface_reference(bundle),
        "lunar_month": month,
        "lunar_day": day,
        "current_is_leap_month": leap,
        "printed_literal_mansion": literal if not disputed else None,
        "printed_normalized_mansion": normalized,
        "candidate_literal_mansions": deepcopy(candidates),
        "reading_status": (
            "unresolved_model_reading_disagreement"
            if disputed
            else "two_model_visual_readings_agree_not_human_acceptance"
        ),
        "disputed_reading": deepcopy(disputed),
        "printed_locator": {
            **deepcopy(image),
            "page_side": column["side"],
            "day_column_from_right": column["column_from_right"],
            "month_slot_from_top": slot + 1,
            "printed_month_order": deepcopy(bundle["month_order"]),
        },
        "comparison_target": "unsplit_T1299_host_month_day_not_actual_leap_or_half_assignment",
        "host_calculation": deepcopy(host),
        "matches_unsplit_host": (
            normalized == host["direct_mansion"] if not disputed else None
        ),
        "candidate_comparisons": [
            {
                "literal": candidate,
                "normalized": candidate.translate(_ALIASES),
                "matches_unsplit_host": candidate.translate(_ALIASES)
                == host["direct_mansion"],
                "matches_taisho_upper_literal": candidate.translate(_ALIASES)
                == upper["table_mansion_28"],
            }
            for candidate in candidates
        ],
        "taisho_upper_table": deepcopy(upper),
        "matches_taisho_upper_literal": (
            normalized == upper["table_mansion_28"] if not disputed else None
        ),
        "actual_profile_result": {
            "calendar_profile": selection["calendar_profile"],
            "resolved": selection["resolved"],
            "natal_su27": selection["natal_su27"],
            "candidate_su27": selection["candidate_su27"],
            "candidate_su27s": deepcopy(selection["candidate_su27s"]),
            "calendar_day_part": selection["calendar_day_part"],
        },
        "applied_to_primary": False,
        "applied_to_sanjiu": False,
        "complete_critical_edition_accepted": False,
        "scope": "具名印本普通月日字面表，与大正上卷含牛表、下卷27宿基准及本次实际补配分别交付；不校改原字，不当作独立历史观测或现实预测证据。",
    }


def printed_reference_lines(reference: dict[str, Any]) -> list[str]:
    """Keep the three textual identities and actual assignment distinct."""
    source = reference["source_reference"]
    locator = reference["printed_locator"]
    host = reference["host_calculation"]
    upper = reference["taisho_upper_table"]
    if reference["printed_literal_mansion"] is None:
        literal = (
            "未定（候选" + "／".join(reference["candidate_literal_mansions"]) + "）"
        )
        match = "两份模型读数有异，未选定原字"
    else:
        literal = reference["printed_literal_mansion"]
        match = "相合" if reference["matches_unsplit_host"] else "不同，原字保留"
    lines = [
        f"立命馆ARC {source['record']}《新刊古本宿曜经》月宿傍通历："
        f"普通{reference['lunar_month']}月{reference['lunar_day']}日印字"
        f"{literal}，下卷同月日未分半基准{host['direct_mansion']}，{match}；"
        f"大正上卷含牛字面表另为{upper['literal_mansion']}。",
        f"此格原图第{locator['frame']}画面{locator['page_side']}页，"
        f"自右第{locator['day_column_from_right']}日列、自上第{locator['month_slot_from_top']}月位；"
        "原印月序二月至十二月后列正月。印字不覆盖本次主宿、闰月／半日候选或三九结果。",
        f"原图来源{locator['permalink']}；"
        "本轮读录的是360个印刷正文格，旁批及红字未并入正文。序年为享保二十一年／1736，"
        "不据此认证实物印刷年或古本传承。序文两次释读有关键疑字与异读，未接纳为完整操作规则。",
        "全表两份模型读数358格相同，八月初三与三十日两格分别读亢／氐，"
        "两格仍未定；首次亢读数及其两处不相合的计算记录保留，不改写为首次通过。",
        "尚无独立人工转录或全本校勘验收；普通月表不确立古代平明钟时、桧尾半日映射或闰月／小月优先，"
        "也不增加独立历史观测或现实预测样本。",
    ]

    from fatebridge.core.sukuyo_koya_preface import preface_reading_lines

    lines.extend(preface_reading_lines(reference["preface_scholarly_reference"]))
    return lines
