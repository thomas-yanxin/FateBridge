"""A named printed hour table, kept separate from physical clock conversion."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fatebridge.core.sukuyo_sources import load_source

SOURCE = Path(__file__).resolve().parents[1] / "data/sukuyo_kenyu_selected_clock.json"


def lookup_printed_hour(
    day_luminary: str, branch: str, night_part: str | None = None
) -> dict[str, Any]:
    """Read the literal matrix; 上/下 is not the Hinoo first/second half.

    Day branches use one row each. Each night branch spans two rows of the
    same matrix. In particular, the night does not continue at matrix row 2.
    No branch, day ruler, or half is inferred from a civil timestamp.
    """
    loaded = load_source(SOURCE)
    table = loaded.data["clock_selected"]
    if day_luminary not in table["day_columns"]:
        raise ValueError("印本直日曜须为日月火水木金土之一")
    if night_part not in {None, "upper", "lower"}:
        raise ValueError("夜分仅支持upper或lower，不接受桧尾前后半代称")
    column = table["day_columns"].index(day_luminary)
    if branch in table["day_branches"]:
        if night_part is not None:
            raise ValueError("此印本昼分支只占一行，不能指定夜分上下刻")
        indices = [table["day_branches"].index(branch)]
        phase = "day"
    elif branch in table["night_branches"]:
        index = 2 * table["night_branches"].index(branch)
        indices = (
            [index, index + 1]
            if night_part is None
            else [index + (night_part == "lower")]
        )
        phase = "night"
    else:
        raise ValueError("印本支时须为十二支单字")
    rows = [
        {
            "row_one_based": index + 1,
            "night_part": (
                ("upper" if index % 2 == 0 else "lower") if phase == "night" else None
            ),
            "hour_luminary": table["table_rows"][index]["luminaries"][column],
        }
        for index in indices
    ]
    return {
        "ruleset_id": loaded.data["id"],
        "source_bundle_sha256": loaded.sha256,
        "condition_day_luminary": day_luminary,
        "condition_branch": branch,
        "condition_night_part": night_part,
        "printed_phase": phase,
        "rows": rows,
        "selected_hour_luminary": rows[0]["hour_luminary"] if len(rows) == 1 else None,
        "physical_clock_mapping_established": False,
        "hinoo_half_mapping_established": False,
    }


def printed_clock_reference(day_luminary: str, weekday_basis: str) -> dict[str, Any]:
    """Publish every branch conditional on the returned civil weekday label."""
    loaded = load_source(SOURCE)
    result = loaded.data
    table = result["clock_selected"]
    result.update(
        source_bundle_sha256=loaded.sha256,
        condition_day_luminary=day_luminary,
        condition_weekday_basis=weekday_basis,
        conditional_branch_readings=[
            lookup_printed_hour(day_luminary, branch)
            for branch in table["day_branches"] + table["night_branches"]
        ],
        civil_time_used_to_select_branch=False,
        ancient_day_ruler_established=False,
        selected_branch=None,
        selected_night_part=None,
        selected_hour_luminary=None,
        applied_to_primary_or_activities=False,
    )
    return result


def printed_clock_reading_lines(reference: dict[str, Any]) -> list[str]:
    day = []
    night = []
    for row in reference["conditional_branch_readings"]:
        if row["printed_phase"] == "day":
            day.append(f"{row['condition_branch']}{row['selected_hour_luminary']}")
        else:
            first, second = row["rows"]
            night.append(
                f"{row['condition_branch']}上{first['hour_luminary']}下{second['hour_luminary']}"
            )
    return [
        "堅雄《宿曜經撮要》名古屋大学藏148.8-Ke、NIJL100159236帧17另有直时七曜图："
        "右傍八支为昼分、左傍四支为夜分；夜分每支两曜，上、下分列。"
        "原文例为日曜直日午时当水曜、土曜直日寅时上金下土。"
        f"仅条件于本次{reference['condition_weekday_basis']}的{reference['condition_day_luminary']}曜标签查该图，"
        f"昼分为{'、'.join(day)}；夜分为{'、'.join(night)}。"
        "未用民用钟时选择支或上下刻，未认定古代直日，当前时曜仍未选定；"
        "夜分上下两项不等同桧尾初一前后半。"
        "两角色对56个曜字读格相合，上刻／上判、晝／畫形、主時后小字、所引行号及旁数仍有未定，未按语义补原字。",
        "该馆藏题录自序1849、阁笔1833、无刊记而据内容估1859，分别保留，未定精确印次或传承。"
        "帧8左页原写潤月朔宿全如本月，该句仅明说朔宿；左页还记月大小取曜、正月室宿与朔字对位、朔日二日兩日之宿兩度値，"
        "并称牛宿配每日午时、遇牛越至女宿。这些来源主张未代入本次算法，尚未复原整套轮图或定闰小月优先。"
        "《大日經疏演奧鈔》T2216_.59.0058a26-27另引晝夜八時名目如何之问；"
        "其后每日轮曜说明不是该日内序列的逐时答案。"
        f"具名印本来源{reference['source_url']}，所选帧17；"
        "它补入一种可核对的后出解释，没有认证为T1299唯一时制、现代日界或现实效力。",
    ]
