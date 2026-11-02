"""The ten annual markers in Jinjing volume five, with separate epochs.

This is not the 1,937,281-year epoch of the eight generals. The source gives
285,011, 13,331 and 3,361 at 724 CE for different families. Keep every epoch,
counting step and unlocated extra palace visible rather than shifting labels.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from fatebridge.core.metaphysics.taiyi_geometry import PALACES

SOURCE = "https://zh.wikisource.org/wiki/太乙金鏡式經_(四庫全書本)/卷05"
RULESET_ID = "jinjing_annual_ten_markers_v1"
BRANCH_SEQUENCE = tuple("戌亥子丑寅卯辰巳午未申酉")
TWELVE_PALACES = tuple("123456789") + ("绛", "明", "玉")
FOUR_ORIGINS = {"sishen": "1", "tianyi": "6", "diyi": "9", "zhifu": "5"}
LABELS = {
    "junji": "君基",
    "chenji": "臣基",
    "minji": "民基",
    "wufu": "五福",
    "dayou": "大游",
    "dayou_tianmu": "大游天目",
    "xiaoyou": "小游",
    "sishen": "四神",
    "tianyi": "天乙",
    "diyi": "地乙",
    "zhifu": "直符",
}
SECTIONS = {
    "junji": "推君基太乙法",
    "chenji": "推臣基太乙法",
    "minji": "推民基太乙法",
    "wufu": "推五福太乙法",
    "dayou": "推大遊太乙所在",
    "dayou_tianmu": "推大遊天目所在法",
    "xiaoyou": "推小遊太乙積年法",
    "sishen": "推四神太乙法",
    "tianyi": "推天乙太乙法",
    "diyi": "四神三元五紀立成",
    "zhifu": "推直符太乙法",
}


def _rotated(sequence: tuple[str, ...], start: str) -> tuple[str, ...]:
    i = sequence.index(start)
    return sequence[i:] + sequence[:i]


def _moving_marker(
    accumulation: int, sequence: tuple[str, ...], years: int
) -> dict[str, Any]:
    if type(accumulation) is not int or accumulation < 1:
        raise ValueError("太乙年运积数必须是正整数")
    cycle_length = len(sequence) * years
    offset = (accumulation - 1) % cycle_length
    index, in_position = divmod(offset, years)
    position = sequence[index]
    number = int(position) if position.isdigit() else None
    if number is not None:
        palace = PALACES[number]
        space = "taiyi_nine_palaces"
    elif position in {"绛", "明", "玉"}:
        palace = {"绛": "绛宫", "明": "明堂", "玉": "玉堂"}[position]
        space = "three_extra_palaces_unmapped"
    else:
        palace = position
        space = "sixteen_palaces"
    return {
        "position": position,
        "palace": palace,
        "palace_number": number,
        "space": space,
        "accumulation": accumulation,
        "cycle_length": cycle_length,
        "cycle_year": offset + 1,
        "years_per_position": years,
        "position_index": index,
        "year_in_palace": in_position + 1,
    }


def four_spirit_records(accumulation: int) -> dict[str, dict[str, Any]]:
    """Each three-year dwell traverses 1..9,绛,明,玉 from its source origin.

    The missing Siku 地乙 paragraph is corroborated by NCL-06604 pp. 73/74.
    Its epoch remains the Siku epoch, not an uncollated Ming value.
    The raw table remains an independent audit; its
    直符 middle-yuan column has unresolved disagreements with the prose rule.
    """
    result = {
        name: _moving_marker(accumulation, _rotated(TWELVE_PALACES, start), 3)
        for name, start in FOUR_ORIGINS.items()
    }
    table = _source_table()
    phase = (accumulation - 1) % 180
    yuan = ("upper", "middle", "lower")[phase // 60]
    row = table["rows"][phase % 60]
    for name, record in result.items():
        record["table_position"] = row["expected"][name + "." + yuan]
        record["table_disagreement"] = record["table_position"] != record["position"]
        record["table_row"] = row["ganzhi"]
        record["table_yuan"] = yuan
        record["source_method"] = (
            "siku_table_corroborated_by_ming_prose"
            if name == "diyi"
            else "prose_rule_compared_to_raw_table"
        )
        if name == "diyi":
            record["source_reference"] = (
                "https://upload.wikimedia.org/wikipedia/commons/8/81/NCL-06604_%E5%A4%AA%E4%B9%99%E9%87%91%E9%8F%A1%E5%BC%8F%E7%B6%93.pdf#page=74"
            )
            record["source_edition"] = (
                "四库积年及三元表；明钞本地乙推法补证起九行序，未替换积年"
            )
    return result


@lru_cache(maxsize=1)
def _source_table() -> dict[str, Any]:
    path = (
        Path(__file__).resolve().parents[2]
        / "data/classical/taiyi-jinjing-vol5-v1.json"
    )
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def annual_long_cycles(year: int) -> dict[str, Any]:
    if type(year) is not int or not 1 <= year <= 9999:
        raise ValueError("太乙年运需要1至9999之间的整数公元年份")
    delta = year - 724
    sanji = 285011 + delta
    long_count = 13331 + delta
    short_count = 3361 + delta
    records = {
        "junji": _moving_marker(sanji, BRANCH_SEQUENCE, 30),
        "chenji": _moving_marker(sanji, BRANCH_SEQUENCE, 3),
        "minji": _moving_marker(sanji, BRANCH_SEQUENCE, 1),
        "wufu": _moving_marker(long_count, ("1", "3", "9", "7", "5"), 45),
        "dayou": _moving_marker(long_count, tuple("78912346"), 36),
        "dayou_tianmu": _moving_marker(
            long_count, tuple("未坤坤申酉戌乾乾亥子丑艮寅卯辰巽巳午"), 1
        ),
        "xiaoyou": _moving_marker(short_count, tuple("12346789"), 3),
        **four_spirit_records(short_count),
    }
    for key, record in records.items():
        record.update(
            label=LABELS[key],
            source_section=SECTIONS[key],
            epoch_id=(
                "sanji"
                if key in {"junji", "chenji", "minji"}
                else (
                    "long_you_wufu"
                    if key in {"wufu", "dayou", "dayou_tianmu"}
                    else "short_you_spirits"
                )
            ),
        )
    wufu_names = {"1": "黄秘", "3": "黄始", "9": "黄室", "7": "黄庭", "5": "玄师"}
    records["wufu"]["classical_palace_name"] = wufu_names[records["wufu"]["position"]]
    records["dayou"]["administration_phase"] = ("治天", "治地", "治人")[
        (records["dayou"]["year_in_palace"] - 1) // 12
    ]
    records["dayou_tianmu"][
        "source_method"
    ] = "explicit_remainder_rule_rate_constants_pending_collation"
    return {
        "status": "computed",
        "year": year,
        "time_granularity": "year",
        "ruleset": {
            "id": RULESET_ID,
            "version": "1.0.0",
            "author": "FateBridge contributors",
            "classical_author": "唐·王希明",
            "source": SOURCE,
            "classical_conformance": "partial_with_unresolved_table_disagreements",
            "classical_acceptance_passed": False,
        },
        "epochs": {
            "sanji": {
                "year": 724,
                "accumulation": 285011,
                "equivalent_short_epoch_accumulation": 611,
                "equivalence_modulus": 360,
            },
            "long_you_wufu": {"year": 724, "accumulation": 13331},
            "short_you_spirits": {"year": 724, "accumulation": 3361},
        },
        "counting_convention": "积数含本年；每宫年序1至行率，满行率后的次年换宫；三元五纪按连续180年解释。",
        "records": records,
        "interpretation_scope": "原典年度巡行位置及年序；不是天空实测星体坐标，不把古代分野对应现代行政区或个人命运。",
        "unresolved": [
            "卷五直符中元表有多项与顺行九宫接绛明玉通则不符，原表保留，未据程序覆盖。",
            "四库缺载地乙推法已由NCL-06604图73/74补证起九行序；未将该本其他未决积年读数混入四库起元，完整断法仍未验收。",
            "绛宫、明堂、玉堂保留原名，未校定其与十六宫/后天九宫的物理对应。",
            "五福及三基原典分野、合神吉凶和完整治乱断法未作联合验收。",
            "大游天目依所在法的七十二、十八余数规则计算；总则216周率及18行率与此条关系仍需独立校勘。",
        ],
    }


def long_cycle_text(cycles: dict[str, Any] | None) -> str:
    if cycles is None or cycles.get("status") == "not_computed_for_selected_mode":
        return (
            "本盘采用月/时计，未附加年度十神；需要年计时以相同资料另选year并分层解释。"
        )
    lines = [
        f"卷五年度巡行：{cycles['year']}；{cycles['ruleset']['id']}。",
        cycles["interpretation_scope"],
    ]
    for record in cycles["records"].values():
        lines.append(
            f"{record['label']}：{record['palace']}，入宫第{record['year_in_palace']}年；积数{record['accumulation']}，{record['cycle_length']}年一周，每位{record['years_per_position']}年。"
        )
        if record.get("table_disagreement"):
            yuan_label = {"upper": "上元", "middle": "中元", "lower": "下元"}[
                record["table_yuan"]
            ]
            lines.append(
                f"本年{record['label']}有异文：正文通则{record['position']}，原表{record['table_position']}（{yuan_label}／{record['table_row']}）；双方保留。"
            )
    lines.append(
        "直符中元表文与通则仍有分歧；地乙起九有明钞本补证，额外三宫物理对应仍待校勘，不能据这些位置单独断成败。"
    )
    return "\n".join(lines)


def attach_long_cycles(board: dict[str, Any], year: int) -> None:
    """Put all located markers on the existing board, retaining extra palaces."""
    cycles = annual_long_cycles(year)
    board["long_cycles"] = cycles
    board["long_cycle_summary"] = {
        "status": "computed",
        "time_granularity": "year",
        "year": year,
        "ruleset_id": RULESET_ID,
        "source": SOURCE,
        "positions": {
            r["label"]: f"{r['palace']}／第{r['year_in_palace']}年"
            for r in cycles["records"].values()
        },
        "table_disagreements": [
            f"{r['label']}：通则{r['position']}、原表{r['table_position']}"
            for r in cycles["records"].values()
            if r.get("table_disagreement")
        ],
        "scope": cycles["interpretation_scope"],
    }
    positions = {row["palace"]: row["markers"] for row in board["palace_marks"]}
    positions["中"] = board["center_marks"]["markers"]
    extra: dict[str, list[str]] = {}
    for record in cycles["records"].values():
        label = record["label"] + (
            "（表异）" if record.get("table_disagreement") else ""
        )
        if record["palace"] in positions:
            positions[record["palace"]].append(label)
        else:
            extra.setdefault(record["palace"], []).append(label)
    for marks in positions.values():
        marks.sort()
    board["extra_palace_marks"] = [
        {"palace": palace, "markers": sorted(marks)} for palace, marks in extra.items()
    ]
