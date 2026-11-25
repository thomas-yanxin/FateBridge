"""Attach source-specific gates and determinate calculations to a Taiyi board."""

from __future__ import annotations

from typing import Any

from fatebridge.core.metaphysics.taiyi_conditions import update_conjunction
from fatebridge.core.metaphysics.taiyi_gate_frames import (
    SECTOR_SOURCE,
)
from fatebridge.core.metaphysics.taiyi_gate_frames import SECTORS as SECTORS
from fatebridge.core.metaphysics.taiyi_gate_frames import TONGZONG
from fatebridge.core.metaphysics.taiyi_gate_frames import (
    check_three_gates as check_three_gates,
)
from fatebridge.core.metaphysics.taiyi_gate_frames import gate_cycle as gate_cycle
from fatebridge.core.metaphysics.taiyi_gate_frames import gate_frame as gate_frame
from fatebridge.core.metaphysics.taiyi_gate_frames import (
    key_day_gate_cycle as key_day_gate_cycle,
)
from fatebridge.core.metaphysics.taiyi_gate_frames import (
    key_hour_gate_cycle as key_hour_gate_cycle,
)
from fatebridge.core.metaphysics.taiyi_geometry import (
    PALACES,
    RING,
    count_to_taiyi,
    general_for_count,
)
from fatebridge.core.metaphysics.taiyi_hour import KEY_HOUR_PROFILE
from fatebridge.core.metaphysics.taiyi_month import KEY_MONTH_PROFILE, month_source_data

JINJING = "https://zh.wikisource.org/wiki/太乙金鏡式經_(四庫全書本)/卷01#推八門占嵗計法"
KEY = (
    "https://www.shidianguji.com/zh/book/NGJ89241199902106666022/chapter/1lq8dkylq3yn8"
)


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
    else:
        pass
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
    else:
        pass
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
    else:
        pass
    if (
        mode == "day"
        and board.get("calendar_rules", {}).get("day_profile")
        != "key_day_winter_jiazi_v1"
    ):
        raise ValueError("日计门盘仅支持明确的金钥匙积日配置")
    else:
        pass
    if mode == "year" and (type(year) is not int or not 1 <= year <= 9999):
        raise ValueError("年计八门必须沿用本盘已确定的整数农历年")
    else:
        pass
    core = board["core_board"]
    determinate = determinate_calculation(board, mode)
    board["determinate_calculation"] = determinate
    if determinate["status"] != "computed":
        core.update(
            dingmu=None, set_count=None, set_general=None, set_vice_general=None
        )
    else:
        pass
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
            else:
                pass
    else:
        pass
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
            else:
                pass
        else:
            pass
        update_conjunction(board["condition_assessment"])
        return
    else:
        pass
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
    else:
        pass
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
    else:
        pass
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
    else:
        pass
    board["gates"] = gates
    assessment = board["condition_assessment"]
    assessment["three_gates"] = selected_check
    update_conjunction(assessment)
