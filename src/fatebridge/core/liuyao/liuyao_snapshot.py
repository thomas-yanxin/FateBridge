"""Render the Liuyao chart and conditional evidence as a snapshot."""

from typing import Any

from fatebridge.core.liuyao.liuyao_penalty import penalty_explanation
from fatebridge.core.liuyao.liuyao_snapshot_interactions import (
    interaction_snapshot_lines,
)
from fatebridge.core.local_techniques.snapshot import join_lines, render_snapshot_text


def build_sixyao_snapshot_text(
    *,
    input_normalized: dict[str, Any],
    nongli: dict[str, Any],
    current_payload: dict[str, Any],
    changed_payload: dict[str, Any],
    lines: list[dict[str, Any]],
    evidence: dict[str, Any],
    text_evidence: dict[str, Any],
) -> str:
    line_texts = []
    for index, line in enumerate(lines, start=1):
        yao_type = "阳爻" if int(line.get("value", 0)) == 1 else "阴爻"
        moving = "（动）" if line.get("change") else "（静）"
        extras = []
        if line.get("god"):
            extras.append(f"六神:{line['god']}")
        else:
            pass
        if line.get("name"):
            extras.append(f"爻名:{line['name']}")
        else:
            pass
        suffix = f"，{'，'.join(extras)}" if extras else ""
        line_texts.append(f"第{index}爻：{yao_type}{moving}{suffix}")

    judge_lines = []
    if input_normalized.get("question"):
        judge_lines.append(f"问题：{input_normalized['question']}")
    else:
        pass
    judge_lines.append(
        f"本卦：{current_payload.get('name', input_normalized['gua_code'])}"
    )
    if current_payload.get("卦辞"):
        judge_lines.append(f"卦辞：{current_payload['卦辞']}")
    else:
        pass
    judge_lines.append(
        f"之卦：{changed_payload.get('name', input_normalized['changed_code'])}"
    )
    if changed_payload.get("卦辞"):
        judge_lines.append(f"之卦卦辞：{changed_payload['卦辞']}")
    else:
        pass

    conditional = evidence["conditional_analysis"]
    focus = conditional["focus"]
    condition_lines = [f"取用状态：{focus['status']}", focus["scope"]]
    if evidence["calendar_conventions"].get("month_model_comparison"):
        condition_lines.append("同次交气比较未完成，不能认定月令路径一致。")
    else:
        pass
    if focus["selected"]:
        selected = focus["selected"]
        location = {
            "visible": "",
            "changed": "变爻",
            "hidden": "伏神",
            "month": "月建",
            "day": "日辰",
        }[selected["location"]]
        anchor = (
            f"第{selected['position']}爻" if selected["position"] is not None else ""
        )
        condition_lines.append(
            f"明确用爻：{anchor}{location}{selected['liuqin']}{selected['branch']}；"
            "此为调用方给定的分析前提"
        )
    else:
        pass
    condition_lines.extend(
        f"第{row['position']}爻：月令层{row['monthly_strength']['category']}；{row['activity']}"
        + (f"；{'、'.join(row['binding_cues'])}" if row["binding_cues"] else "")
        + (
            "；暗动扶源待审，不能据原候选认定已活动"
            if row.get("activity_condition_status")
            == "activity_prerequisites_unresolved"
            else ""
        )
        for row in conditional["lines"]
    )
    condition_lines.extend(interaction_snapshot_lines(conditional))
    role_effects = conditional["role_effects"]
    for row in conditional["growth_conditions"]["lines"]:
        moving_si = row.get("moving_si")
        if moving_si is not None:
            for value, text in [
                (
                    True,
                    "已核本项遇长生资格，普通火克金方向与许可仍保留；同版生克合并效力待审，其他反制另审",
                ),
                (
                    None,
                    "独立生扶或动巳来源门槛待审；普通火克金方向与所列许可另列，生克合并效力未裁定",
                ),
                (
                    False,
                    "这些动巳来源当前门槛未匹配，不认定本项已获长生；不据此认定金爻无气",
                ),
            ]:
                positions = [
                    str(s["source_position"])
                    for s in moving_si["sources"]
                    if s["growth_condition_match"] is value
                ]
                if positions:
                    condition_lines.append(
                        f"第{row['position']}爻{row['branch']}金遇第{'、'.join(positions)}爻实际动巳：{text}。"
                    )
                else:
                    pass
        else:
            pass
        own_si = row.get("own_changed_si")
        if own_si is not None:
            own_text = (
                "已核独立生扶及变支门槛，本位化巳按长生，不计同一本位巳火回头克；其他反制另审"
                if own_si["condition_match"] is True
                else "本位化巳位置已列，独立生扶或变支门槛仍待审，不能将本项认定为已克或已生"
            )
            condition_lines.append(
                f"第{row['position']}爻{row['branch']}金本位化巳：{own_text}。"
            )
        else:
            pass
        if row["element"] == "金" and row["day_branch"] == "巳":
            text = (
                (
                    "已核月令独立生扶，巳日按长生条件；其他反制另审"
                    if row["independent_month_support"] is True
                    else "已核有独立根的实际动土生扶，巳日按长生条件；其他反制另审"
                )
                if row["condition_match"] is True
                else "长生位置已列，独立旺相生扶尚待裁定，不能据位置作得生"
            )
            condition_lines.append(f"第{row['position']}爻{row['branch']}金：{text}。")
        else:
            pass
    for row in conditional["penalty_conditions"]["lines"]:
        penalty_text = penalty_explanation(row)
        if penalty_text is None:
            continue
        else:
            pass
        condition_lines.append(f"第{row['position']}爻巳火：{penalty_text}。")
    for row in conditional["cessation_conditions"]["lines"]:
        if row["element"] != "土":
            continue
        else:
            pass
        for key, label in (("day", "日支"), ("changed", "本位变支")):
            query = row[key]
            if query["position_match"] is not True:
                continue
            else:
                pass
            text = (
                "已核独立生扶且未见所列反制，本项论生不论绝；其他作用另审"
                if query["condition_match"] is False
                else "气根或反制尚待裁定，不能仅据位置判真绝"
            )
            condition_lines.append(
                f"第{row['position']}爻{row['branch']}土：{label}巳见绝位；{text}。"
            )
    routing = conditional["routing_conditions"]
    for route in routing["routes"]:
        j, y, f = route["positions"]
        location = {"visible": "明爻", "hidden": "伏神"}[route["focus_location"]]
        if route["condition_match"] is True:
            message = "所列接续相生条件匹配；直接克制是否转化及最终效力仍待全局审查"
        elif route["condition_match"] is None:
            message = "接续条件待审：" + "、".join(
                s["label"] for s in route["conditions"] if s["matched"] is None
            )
        elif route["obstructed_positions"]:
            message = "回头克阻断当前接续条件，先审解救；不能据同动自动解克"
        elif y in route["binding_positions"]:
            message = "元神受合，不能据同动自动解克"
        elif j in route["binding_positions"]:
            message = "忌神受合，不能据同动自动断接续相生"
        elif "focus_reception" in route["blocked_conditions"]:
            message = "用神月破日克无独立根，不能据路径认定已受生"
        else:
            message = "接续条件未通过：" + "、".join(
                s["label"] for s in route["conditions"] if s["matched"] is False
            )
        condition_lines.append(
            f"元忌同动路径：第{j}爻忌神→第{y}爻元神→第{f}爻{location}用神；" + message
        )
    if routing["routes"]:
        condition_lines.append(routing["scope"])
    else:
        pass
    if role_effects["lines"]:
        condition_lines.append(role_effects["scope"])
        condition_lines.append(
            "第53页五字异文保留；墓法按同版第100、127页三种定义处理。"
        )
    else:
        pass
    assessed_focus = conditional["classical_assessment"]["focus"]
    if assessed_focus:
        strength_names = {
            "day_broken_unsupported": "静爻日破条件匹配，未见已列独立生扶",
            "supported_unopposed": "有根生扶，未见已列反制",
            "harmed_unsupported": "休囚受克，未见已列生扶",
            "contested_or_pending": "扶克并见或来源效力待审",
            "unresolved_no_grounded_support": "尚无充分裁定依据",
        }
        condition_lines.append(
            f"第{assessed_focus['position']}爻原典生扶裁定："
            + strength_names[assessed_focus["strength"]["status"]]
        )
        for tomb in assessed_focus["tombs"]:
            location = {"day": "日墓", "moving": "动墓", "changed": "本位化墓"}[
                tomb["location"]
            ]
            verdict = (
                "原典真墓条件匹配"
                if tomb["is_true_tomb"] is True
                else (
                    "当前不作真墓" if tomb["is_true_tomb"] is False else "真墓效力待审"
                )
            )
            condition_lines.append(
                f"{location}{tomb['branch']}：{verdict}；不据此断现实吉凶"
            )
    else:
        pass
    timing = conditional["timing_candidates"]
    condition_lines.extend([f"日级候选状态：{timing['status']}", conditional["scope"]])
    if timing.get("scope"):
        condition_lines.append(timing["scope"])
    else:
        pass
    for window in timing["windows"]:
        if civil := window.get("civil_interval"):
            condition_lines.append(
                f"日柱标签{window['effective_date']}（{window['day_ganzhi']}）"
                f"实际UTC分段{civil['interval_index']}/{civil['interval_count']}："
                f"{civil['start_utc']}至{civil['end_utc']}，"
                f"时长{civil['duration_seconds']:g}秒；"
                + "、".join(window["matched_rules"])
            )
            condition_lines.append(civil["scope"])
        else:
            pass
    for excluded in timing.get("calendar_exclusions", []):
        reason = (
            "在已加载时区规则中的钟时未定义"
            if excluded["status"] == "unresolved_timezone_offset"
            else "的钟面区间没有实际UTC时刻"
        )
        condition_lines.append(
            f"日柱标签{excluded['effective_date']}（{excluded['day_ganzhi']}）"
            f"{reason}，不输出候选窗口。"
        )
    void_conditions = conditional["void_conditions"]
    void_focus = void_conditions["focus"]
    if void_focus:
        label = (
            "伏神"
            if void_focus["location"] == "hidden"
            else f"第{void_focus['position']}爻"
        )
        vacancy = "原旬旬空" if void_focus["is_xunkong"] else "原支不在旬空"
        condition_lines.append(
            f"{label}{void_focus['branch']}：{vacancy}；空亡条件状态{void_focus['classification']}"
        )
        for rule in void_focus["not_empty_conditions"]:
            if rule.get("qualification_source_path"):
                qualified = {True: "可计入", False: "排除", None: "待审"}[
                    rule["qualified_matched"]
                ]
                condition_lines.append(f"寅日对巳的生扶经三支条件校核：{qualified}。")
            else:
                pass
            if rule["rule_id"] == "moving_generate" and rule["matched"] is None:
                condition_lines.append("本爻动爻生扶资格待审，空亡层保留该项未知。")
            else:
                pass
        if void_focus["changed_is_xunkong"] is not None:
            condition_lines.append(
                "本位变支"
                + ("在旬空" if void_focus["changed_is_xunkong"] else "不在旬空")
            )
        else:
            pass
        condition_lines.append(void_conditions["scope"])
    else:
        pass
    obstructed = [
        r["position"]
        for r in conditional["lines"]
        if r.get("outgoing_obstructions")
        and (
            conditional["growth_conditions"]["lines"][r["position"] - 1]
            .get("own_changed_si", {})
            .get("condition_match", False)
            is not None
        )
    ]
    if obstructed:
        condition_lines.append(
            f"回头克受阻爻位：{obstructed}；未按可用的向外生扶计入，解救效力仍待审"
        )
    else:
        pass
    fanfu = evidence["fanfu"]
    if fanfu["explicit_body_example"]:
        condition_lines.append(
            "底本明列卦体"
            + fanfu["explicit_body_example"]["kind"]
            + "；不由动爻支冲推得"
        )
    else:
        pass
    for region in fanfu["regions"]:
        if region["nazhi_relation"] in ("反吟", "伏吟"):
            label = "内卦" if region["region"] == "inner" else "外卦"
            condition_lines.append(
                label + "纳支" + region["nazhi_relation"] + "结构；静爻位置仅作卦盘比较"
            )
        else:
            pass
    condition_lines.append(fanfu["scope"])

    return render_snapshot_text(
        [
            (
                "起盘信息",
                join_lines(
                    [
                        f"日期：{input_normalized['date']} {input_normalized['time']}",
                        f"时区：{input_normalized['zone']}",
                        f"经纬度：{input_normalized['lon'] if input_normalized.get('lon') is not None else '无'} {input_normalized['lat'] if input_normalized.get('lat') is not None else '无'}",
                        f"起卦时间：{nongli.get('birth', '无')}",
                        f"干支：年{nongli.get('yearJieqi', '无')} 月{nongli.get('monthGanZi', '无')} 日{nongli.get('dayGanZi', '无')} 时{nongli.get('time', '无')}",
                    ]
                ),
            ),
            (
                "卦象",
                join_lines(
                    [
                        f"本卦：{current_payload.get('name', input_normalized['gua_code'])}",
                        f"之卦：{changed_payload.get('name', input_normalized['changed_code'])}",
                    ]
                ),
            ),
            ("六爻与动爻", join_lines(line_texts) or "暂无爻线数据"),
            ("卦辞与断语", join_lines(judge_lines) or "无"),
            (
                "原典动爻",
                join_lines(
                    [
                        *[
                            f"{v['label']}：{v['text']}"
                            for v in text_evidence["moving_yaoci"]
                        ],
                        f"原文来源：{text_evidence['base_source_url']}",
                        text_evidence["scope"],
                    ]
                ),
            ),
            (
                "专业关系依据",
                join_lines(
                    [
                        f"月建：{evidence['calendar_conventions']['month_branch']}；日辰：{evidence['calendar_conventions']['day_ganzhi']}；旬空：{''.join(evidence['calendar_conventions']['xunkong'])}",
                        evidence["conformance_scope"],
                        "空破冲合只是结构事实，须结合用神旺衰与动静条件解读。",
                    ]
                ),
            ),
            ("取用与条件证据", join_lines(condition_lines)),
        ]
    )
