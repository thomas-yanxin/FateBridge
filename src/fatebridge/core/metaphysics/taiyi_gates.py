"""Taiyi's own eight gates: explicit frames and source-scoped counters.

The Wang annual/month counter and Li's constant-open comparison are distinct.
No Qimen door is read here. A center-five anchor cannot become a ring palace.
The hourly solstice-relative ordinal is not the classical 天正時實.
"""

from __future__ import annotations

from typing import Any

from fatebridge.core.metaphysics.taiyi_geometry import (
    PALACE_ORDER,
    PALACES,
    RING,
    count_to_taiyi,
    general_for_count,
)

from .taiyi_conditions import update_conjunction
from .taiyi_hour import KEY_HOUR_PROFILE
from .taiyi_month import KEY_MONTH_PROFILE, month_source_data

DOORS = tuple("开休生伤杜景死惊")
GOOD = {"开", "休", "生"}
JINJING = "https://zh.wikisource.org/wiki/太乙金鏡式經_(四庫全書本)/卷01#推八門占嵗計法"
TONGZONG = "https://www.shidianguji.com/zh/book/CADAL02055529/chapter/1l5erjww44w8a"
KEY = (
    "https://www.shidianguji.com/zh/book/NGJ89241199902106666022/chapter/1lq8dkylq3yn8"
)
# Four cardinal positions stand alone; each corner includes its two branches.
# Vol. 2 explicitly puts 戌亥 in 乾一 and 辰巳 in 巽九. This is a directional
# projection, not a change to the sixteen-spirit counting values.
SECTORS = {
    spirit: number
    for number, spirits in (
        (1, "戌乾亥"),
        (8, "子"),
        (3, "丑艮寅"),
        (4, "卯"),
        (9, "辰巽巳"),
        (2, "午"),
        (7, "未坤申"),
        (6, "酉"),
    )
    for spirit in spirits
}
SECTOR_SOURCE = "https://zh.wikisource.org/wiki/太乙金鏡式經_(四庫全書本)/卷02"


def key_hour_gate_cycle(accumulation: int, yin: bool) -> dict[str, Any]:
    if type(accumulation) is not int or accumulation < 1 or type(yin) is not bool:
        raise ValueError("金钥匙四门须完整正整数积时及明确阴阳遁")
    phase = (accumulation - 1) % 120
    index, in_gate = divmod(phase, 30)
    doors = tuple("杜死伤景") if yin else tuple("开生惊休")
    return {
        "accumulation": accumulation,
        "cycle_length": 120,
        "cycle_unit": "double_hour",
        "cycle_position": phase + 1,
        "units_per_gate": 30,
        "gate_index": index,
        "unit_in_gate": in_gate + 1,
        "duty_gate": doors[index],
        "epoch_basis": "金钥匙时计完整积时；阴阳各用四门，不借年计八门序",
    }


def gate_cycle(accumulation: int) -> dict[str, Any]:
    if type(accumulation) is not int or accumulation < 1:
        raise ValueError("太乙八门积数必须是正整数")
    phase = (accumulation - 1) % 240
    index, in_gate = divmod(phase, 30)
    return {
        "accumulation": accumulation,
        "cycle_length": 240,
        "cycle_unit": "selected_count_unit",
        "cycle_position": phase + 1,
        "units_per_gate": 30,
        "gate_index": index,
        "unit_in_gate": in_gate + 1,
        "duty_gate": DOORS[index],
    }


def key_day_gate_cycle(accumulation: int, yin: bool) -> dict[str, Any]:
    result = key_hour_gate_cycle(accumulation, yin)
    result.update(
        cycle_unit="day",
        source_modulus=240,
        epoch_basis="金钥匙积日先约240，再循环阴阳各四门；实际门序120日复现，不乘十二。",
    )
    return result


def gate_frame(
    anchor: int, duty_gate: str, anchor_path: str, source_position: str | None = None
) -> dict[str, Any]:
    """Rotate gates in the physical order 乾坎艮震巽離坤兌, never 1..9."""
    if type(anchor) is not int or anchor not in PALACES or duty_gate not in DOORS:
        raise ValueError("太乙门盘需要实际宫位和已知直门")
    if anchor == 5:
        return {
            "status": "not_assessed",
            "anchor_number": 5,
            "anchor_palace": "中",
            "anchor_source_path": anchor_path,
            "anchor_source_value": 5,
            "reason": "中五无八方环位，不自动寄坤布门。",
        }
    start = PALACE_ORDER.index(anchor)
    door_start = DOORS.index(duty_gate)
    rows = [
        {
            "number": number,
            "palace": PALACES[number],
            "door": DOORS[(door_start + i - start) % 8],
            "spirit_positions": [s for s in RING if SECTORS[s] == number],
        }
        for i, number in enumerate(PALACE_ORDER)
    ]
    return {
        "status": "computed",
        "anchor_number": anchor,
        "anchor_palace": PALACES[anchor],
        "anchor_source_path": anchor_path,
        "anchor_source_value": (
            source_position if source_position is not None else anchor
        ),
        "duty_gate": duty_gate,
        "rows": rows,
    }


def check_three_gates(
    frame: dict[str, Any], entities: list[dict[str, Any]], path: str
) -> dict[str, Any]:
    if frame["status"] != "computed":
        return {
            "status": "not_assessed",
            "reason": frame["reason"],
            "conditions_satisfied": None,
            "frame_source_path": path,
        }
    checks = []
    rows = frame["rows"]
    for entity in entities:
        sector = SECTORS[entity["position"]]
        i, row = next((i, r) for i, r in enumerate(rows) if r["number"] == sector)
        door = row["door"]
        checks.append(
            {
                **entity,
                "sector_number": sector,
                "door": door,
                "gate_source_path": f"{path}.rows.{i}",
                "obstructs": door in GOOD,
                "incomplete_kind": (
                    "三门不具"
                    if door == "休"
                    else "两门不具" if door in {"开", "生"} else None
                ),
            }
        )
    return {
        "status": "computed",
        "conditions_satisfied": not any(c["obstructs"] for c in checks),
        "checks": checks,
        "frame_source_path": path,
        "source": TONGZONG,
    }


def determinate_calculation(board: dict[str, Any], mode: str) -> dict[str, Any]:
    """合神加所选年/月支, locate 文昌 on that same sixteen-position rotation."""
    if (
        mode == "hour"
        and board.get("calendar_rules", {}).get("hour_profile") != KEY_HOUR_PROFILE
    ):
        return {
            "status": "not_computed_for_selected_mode",
            "reason": "时计合神现用日支，定计时支加临尚待同派独立课例，未把年/月例混入。",
        }
    core = board["core_board"]
    ruler = core["suijun"] if mode == "year" else core["ruler_branch"]
    hegod = core["heshen"]
    eyes = board["wenchang_palace"]
    shift = (RING.index(ruler) - RING.index(hegod)) % 16
    marker = RING[(RING.index(eyes) + shift) % 16]
    trace = count_to_taiyi(marker, core["taiyi_number"])
    general = general_for_count(trace["count"])
    result = {
        "status": "computed",
        "marker": marker,
        "count": trace["count"],
        "general": general,
        "vice_general": general * 3 % 10,
        "trace": trace,
        "rotation": {
            "ruler_branch": ruler,
            "hegod": hegod,
            "wenchang": eyes,
            "forward_steps": shift,
        },
        "source": KEY,
        "scope": "定计是原典所称为客重审之算，不是新的独立证据或实际成功概率。",
    }
    if mode == "hour" and core["taiyi_number"] == 9 and eyes == "乾" and ruler == "戌":
        # Key facsimile pp45/46 explicitly reads 33, 3, 9. Its listed
        # counting steps sum to 32; do not patch the count to fit the prose.
        result["source_disagreements"] = [
            {"field": field, "source_value": value, "rule_derived_value": result[field]}
            for field, value in (("count", 33), ("general", 3), ("vice_general", 9))
            if result[field] != value
        ]
        result["source_comparison_source"] = KEY
        result["source_comparison_scope"] = (
            "图45/46庚戌课例同一时计相位的定计数值参照；日期匹配另见calendar_rules.historical_date_reference，不认证完整古历、门盘或应验。"
        )
    core.update(
        dingmu=marker,
        set_count=result["count"],
        set_general=general,
        set_vice_general=result["vice_general"],
    )
    return result


def attach_gate_board(
    board: dict[str, Any], mode: str, year: int | None = None
) -> None:
    if mode not in {"year", "month", "day", "hour"}:
        raise ValueError("太乙八门仅接受本盘明确的year/month/day/hour计法")
    if (
        mode == "day"
        and board.get("calendar_rules", {}).get("day_profile")
        != "key_day_winter_jiazi_v1"
    ):
        raise ValueError("日计门盘仅支持明确的金钥匙积日配置")
    if mode == "year" and (type(year) is not int or not 1 <= year <= 9999):
        raise ValueError("年计八门必须沿用本盘已确定的整数农历年")
    core = board["core_board"]
    determinate = determinate_calculation(board, mode)
    board["determinate_calculation"] = determinate
    if determinate["status"] != "computed":
        core.update(
            dingmu=None, set_count=None, set_general=None, set_vice_general=None
        )
    if determinate["status"] == "computed":
        marks = {
            p["palace"]: p["markers"]
            for p in board["palace_marks"] + [board["center_marks"]]
        }
        for label, position in [
            ("定目", determinate["marker"]),
            ("定大", PALACES[determinate["general"]]),
            ("定参", PALACES[determinate["vice_general"]]),
        ]:
            if label not in marks[position]:
                marks[position].append(label)
    source = {
        "id": "jinjing_wang_gates_240_v1",
        "version": "1.1.0",
        "author": "FateBridge contributors",
        "classical_author": "唐·王希明；旧法记李淳风；后本补证分别标注",
        "sources": [JINJING, TONGZONG],
        "sector_rule_id": "jinjing_four_cardinals_four_corners_v1",
        "sector_sources": [SECTOR_SOURCE],
        "classical_conformance": "partial_source_scoped_gate_rules_not_full_classical_judgment",
        "classical_acceptance_passed": False,
        "open_issues": [
            "统宗纪年门表有年号、干支及门序冲突；完整18行另立未通过审计，不据表值改起元。",
            "金钥匙戊戌月例的积月、门周余数与死门四月互不吻合；月门采用本盘连续积月通则，未称该课例全符。",
            "统宗甲戌例三十二算、大将三宫、参将六宫，与去十余二不合；定计保留正文通则，扫描读数另列未通过。",
        ],
    }
    gates: dict[str, Any] = {
        "ruleset": source,
        "calculation_mode": mode,
        "reason": None,
        "counter": None,
        "moving_frame": None,
        "old_open_frames": None,
        "old_open_summary": None,
        "dingmu_comparison_frame": None,
        "dingmu_comparison_source": None,
        "scope": "太乙门盘按本次太乙方位布列，不是奇门门盘；分野不对应现代地区，门具将发不表示现实成败。",
    }
    is_key_month = (
        mode == "month"
        and board.get("calendar_rules", {}).get("month_profile") == KEY_MONTH_PROFILE
    )
    if (
        is_key_month
        or mode == "day"
        or (
            mode == "hour"
            and board.get("calendar_rules", {}).get("hour_profile") == KEY_HOUR_PROFILE
        )
    ):
        is_day = mode == "day"
        key_profile = (
            "key_month_eight_gates_240_v1"
            if is_key_month
            else (
                "key_day_four_gates_120_v1" if is_day else "key_hour_four_gates_120_v1"
            )
        )
        if is_key_month:
            counter = gate_cycle(core["accumulation"])
            counter.update(
                cycle_unit="solar_month",
                remaining_units_after_current=30 - counter["unit_in_gate"],
                epoch_basis="金钥匙完年乘十二加天地二正；完整积月连续入240门周，不先约360；现代节月界",
            )
        else:
            counter = (key_day_gate_cycle if is_day else key_hour_gate_cycle)(
                core["accumulation"], board["rotation"] == "逆布"
            )
        moving = gate_frame(
            SECTORS[determinate["marker"]],
            counter["duty_gate"],
            "taiyi.core_board.dingmu",
            determinate["marker"],
        )
        gates.update(
            status="computed",
            selected_profile=key_profile,
            counter=counter,
            moving_frame=moving,
            scope="本书所直门加定计目；仅布门，太乙主客主体及课例门具语待独立裁定。未借用王法或奇门门盘。",
            ruleset={
                "id": key_profile,
                "version": "1.1.0",
                "author": "FateBridge contributors",
                "classical_author": "《太乙金钥匙续集》底本题署，作者未独立考定",
                "sources": [KEY],
                "sector_rule_id": "jinjing_four_cardinals_four_corners_v1",
                "sector_sources": [SECTOR_SOURCE],
                "classical_conformance": (
                    "partial_day_counter_door_sequence_and_determinate_anchor_only"
                    if is_day
                    else "partial_hour_counter_door_sequence_and_determinate_anchor_only"
                ),
                "classical_acceptance_passed": False,
                "open_issues": [
                    "课例三门主体及门具将发语未裁定，不把已布门当作已具门。",
                    (
                        "古历日期未复原；日计现代所选钟面零时换日为明确约定。"
                        if is_day
                        else "古历日期与子正夜半未复原；现代钟表/真太阳钟及23时子初为明确约定。"
                    ),
                ],
            },
        )
        board["gates"] = gates
        board["condition_assessment"]["three_gates"] = {
            "status": "not_assessed",
            "conditions_satisfied": None,
            "reason": (
                "金钥匙日计的太乙主客三门核对主体未裁定；已布门不等于门具。"
                if is_day
                else "金钥匙时计的太乙主客核对主体及课例门具语尚未裁定；已布门不等于门具。"
            ),
            "frame_source_path": "taiyi.gates.moving_frame",
            "source": KEY,
        }
        if is_key_month:
            gates["ruleset"].update(
                classical_conformance="partial_month_origin_counter_and_determinate_anchor_only",
                open_issues=board["ruleset"]["unresolved"],
            )
            gates.update(
                source_comparisons=[],
                source_counter_alternatives=[],
                source_comparison_source=KEY,
                source_comparison_scope="仅与金钥匙月例同一720月数值相位比较；不是同一历史月份或全盘断法认证。",
            )
            board["condition_assessment"]["three_gates"][
                "reason"
            ] = "金钥匙月计太乙主客三门核对主体尚未裁定；已布门不等于门具，不代入王法太乙/文昌两主体。"
            origin = board["calendar_rules"]["month_origin"]
            source_month = month_source_data()["month_example"]
            if (origin["shortcut_count"] - source_month["counter"]) % 720 == 0:
                gates["source_comparisons"] = [
                    {
                        "field": field,
                        "source_value": value,
                        "rule_derived_value": actual,
                        "scope": "图38原门段读数；本盘沿前段天地二正完整积月通则。",
                        "source": KEY,
                    }
                    for field, value, actual in (
                        (
                            "month_origin.shortcut_count",
                            source_month["gate_input"],
                            origin["shortcut_count"],
                        ),
                        (
                            "counter.cycle_position",
                            source_month["gate_remainder"],
                            counter["cycle_position"],
                        ),
                        (
                            "counter.duty_gate",
                            source_month["duty_gate"],
                            counter["duty_gate"],
                        ),
                        (
                            "counter.unit_in_gate",
                            source_month["unit_in_gate"],
                            counter["unit_in_gate"],
                        ),
                        (
                            "counter.remaining_units_after_current",
                            source_month["remaining_units"],
                            counter["remaining_units_after_current"],
                        ),
                    )
                ]
                for name, value in (
                    ("原门段所写积月，仅算术诊断", source_month["gate_input"]),
                    ("原门段所报余数，仅算术诊断", source_month["gate_remainder"]),
                ):
                    alternative = gate_cycle(value)
                    alternative["epoch_basis"] = (
                        name + "，不是本盘所用积月，不能择优替换"
                    )
                    gates["source_counter_alternatives"].append(alternative)
        update_conjunction(board["condition_assessment"])
        return
    if mode == "hour":
        gates.update(
            status="not_computed_for_selected_mode",
            selected_profile=None,
            reason="当前时计是至点后置一的现代时钟序数；原典门数须天正时实，不能拿该序数冒充。",
        )
        board["gates"] = gates
        board["condition_assessment"]["three_gates"] = {
            "status": "not_assessed",
            "conditions_satisfied": None,
            "reason": gates["reason"],
        }
        update_conjunction(board["condition_assessment"])
        return
    accumulation = (
        3361 + year - 724
        if mode == "year" and year is not None
        else core["accumulation"]
    )
    counter = gate_cycle(accumulation)
    counter.update(
        cycle_unit="year" if mode == "year" else "solar_month",
        epoch_basis=(
            "卷四与小游同：724年3361"
            if mode == "year"
            else "本盘连续六纪节月积数，不先约去360；现代节月适配"
        ),
    )
    moving = gate_frame(
        core["taiyi_number"], counter["duty_gate"], "taiyi.core_board.taiyi_number"
    )
    entities = [
        {
            "label": "太乙",
            "source_path": "taiyi.taiyi_palace",
            "position": board["taiyi_palace"],
        },
        {
            "label": "文昌",
            "source_path": "taiyi.wenchang_palace",
            "position": board["wenchang_palace"],
        },
    ]
    selected_check = check_three_gates(moving, entities, "taiyi.gates.moving_frame")
    # Li's annual constant-open frames have different anchors and subjects.
    # Keep their outcomes separately; never choose whichever frame says True.
    old_frames = {}
    if mode == "year":
        for key, field, targets in [
            ("taiyi", "taiyi_number", entities[1:]),
            ("main", "main_general", entities),
            (
                "guest",
                "guest_general",
                [
                    entities[0],
                    {
                        "label": "始击",
                        "source_path": "taiyi.core_board.shiji",
                        "position": core["shiji"],
                    },
                ],
            ),
        ]:
            frame = gate_frame(core[field], "开", "taiyi.core_board." + field)
            frame["three_gates"] = check_three_gates(
                frame, targets, "taiyi.gates.old_open_frames." + key
            )
            old_frames[key] = frame
        # Volume 1 also lists a constant-open frame anchored on 定计大将.
        # The explicit subject list in Tongzong only resolves the three above.
        frame = gate_frame(core["set_general"], "开", "taiyi.core_board.set_general")
        frame["three_gates"] = {
            "status": "not_assessed",
            "conditions_satisfied": None,
            "reason": "卷一列定计大将门盘；本条三门核对主体未独立裁定，仅布门。",
            "frame_source_path": "taiyi.gates.old_open_frames.determinate",
        }
        old_frames["determinate"] = frame
    gates.update(
        status="computed",
        selected_profile=(
            "wang_annual_240"
            if mode == "year"
            else "wang_month_240_with_modern_jie_adapter"
        ),
        counter=counter,
        moving_frame=moving,
        old_open_frames=old_frames,
        old_open_summary={
            key: {
                **{field: value for field, value in frame.items() if field != "rows"},
                "source_path": "taiyi.gates.old_open_frames." + key,
            }
            for key, frame in old_frames.items()
        },
    )
    if determinate["status"] == "computed":
        # The Key's sequel explicitly anchors the duty gate on 定计目 instead.
        # Return that comparison frame without silently replacing Wang's frame.
        gates["dingmu_comparison_frame"] = gate_frame(
            SECTORS[determinate["marker"]],
            counter["duty_gate"],
            "taiyi.core_board.dingmu",
            determinate["marker"],
        )
        gates["dingmu_comparison_source"] = KEY
    board["gates"] = gates
    assessment = board["condition_assessment"]
    assessment["three_gates"] = selected_check
    update_conjunction(assessment)


def gates_text(board: dict[str, Any]) -> str:
    gates = board["gates"]
    if gates["status"] != "computed":
        return f"太乙八门未计算：{gates['reason']}"
    counter = gates["counter"]
    lines = [
        f"太乙八门：{gates['selected_profile']}，积数{counter['accumulation']}，{counter['duty_gate']}门入第{counter['unit_in_gate']}计数单位。"
    ]
    is_key = gates["selected_profile"] in {
        "key_hour_four_gates_120_v1",
        "key_day_four_gates_120_v1",
        "key_month_eight_gates_240_v1",
    }
    label = {"day": "日计阴阳四门", "hour": "时计阴阳四门", "month": "月计八门"}.get(
        gates["calculation_mode"], "本计八门"
    )
    lines.append(
        f"所选门法来源：金钥匙{label}（{KEY}），直门加定计目。"
        if is_key
        else f"所选门法来源：王希明卷一新术（{JINJING}）；三门主体补证：统宗卷二（{TONGZONG}）。"
    )
    lines.append(
        "；".join(
            f"{r['palace']}：{r['door']}门" for r in gates["moving_frame"]["rows"]
        )
    )
    for check in board["condition_assessment"]["three_gates"].get("checks", []):
        lines.append(
            f"{check['label']}在{check['position']}，按本门盘临{check['door']}门：{check['incomplete_kind'] or '未触发三门不具条款'}。"
        )
    if is_key:
        lines.append(board["condition_assessment"]["three_gates"]["reason"])
        for comparison in gates.get("source_comparisons", []):
            lines.append(
                f"月门原文差异：{comparison['field']}原文{comparison['source_value']}，本盘规则推算{comparison['rule_derived_value']}；原读数保留。"
            )
        for alternative in gates.get("source_counter_alternatives", []):
            lines.append(
                f"月门诊断：{alternative['epoch_basis']}；{alternative['accumulation']}按240门周得{alternative['cycle_position']}，为{alternative['duty_gate']}门第{alternative['unit_in_gate']}月。"
            )
    else:
        lines.append(
            "李法常开四盘及定计目加临门盘另列比较，未混成同一判断；定计大将门盘仅布门，三门主体未裁定。"
        )
    result = board["determinate_calculation"]
    if result["status"] == "computed":
        path = " + ".join(f"{p['palace']}{p['value']}" for p in result["trace"]["path"])
        lines.append(
            f"定计目{result['marker']}：{path} = {result['count']}；定计大/参将{result['general']}/{result['vice_general']}。"
        )
        lines.append(f"定计补证：金钥匙续集（{KEY}），不把重审之算当另一份独立证据。")
        for item in result.get("source_disagreements", []):
            lines.append(
                f"定计原文分歧：{item['field']}原文{item['source_value']}，按本盘算路{item['rule_derived_value']}；两值保留，未据程序改原文。"
            )
    return "\n".join(lines)
