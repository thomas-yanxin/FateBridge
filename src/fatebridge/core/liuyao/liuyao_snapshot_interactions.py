"""Render the Liuyao line interaction and hidden-spirit readout."""

from typing import Any


def interaction_snapshot_lines(conditional: dict[str, Any]) -> list[str]:
    condition_lines: list[str] = []
    control = conditional["control_conditions"]
    for row in conditional["month_break_conditions"]["lines"]:
        if row["day_value_exception"]:
            condition_lines.append(
                f"第{row['position']}爻{row['branch']}：原月令月破，本日同支值日，本项月令反制不计入当前克制；"
                + (
                    "仍有其他反制待审，不据此确认全局不破。"
                    if row["retained_other_oppositions"]
                    else "没有因此免除其他独立条件。"
                )
            )
        changed_month = row["changed"]
        if changed_month and changed_month["day_value_exception"]:
            condition_lines.append(
                f"第{row['position']}爻本位变{changed_month['branch']}：原月破，本日同支值日，仅解除本项月令阻碍；原爻其他生克效力另审。"
            )
    for row in conditional["month_break_conditions"]["hidden"]:
        for kind, label in (("hidden", "伏神"), ("flying", "飞神")):
            if row[kind]["day_value_exception"]:
                condition_lines.append(
                    f"第{row['position']}爻{label}{row[kind]['branch']}：原月破而本日同支值日，不能只据月破认定失力；飞伏关系与其他反制另审。"
                )
    back_support = conditional["back_generation_conditions"]
    for source in back_support["sources"]:
        if not source["is_back_generation"]:
            continue
        status = (
            "回头生空破门槛匹配"
            if source["condition_match"] is True
            else (
                "巳寅申特定条款排除本位寅回头生"
                if source["condition_match"] is False
                else (
                    "三支活动待审，寅回头生不能确认"
                    if source["status"] == "own_yin_generation_triad_activity_pending"
                    else "回头生变爻空破待审"
                )
            )
        )
        relations = source["changed_calendar_relations"]
        condition_lines.append(
            f"第{source['position']}爻{source['branch']}本位化{source['changed_branch']}：{status}；"
            f"变爻所受日月关系：月{relations['month']}，日{relations['day']}；原爻生克效力另审"
        )
    condition_lines.append(back_support["scope"])
    for pair in control["controls"]:
        if not pair["emit_edge"]:
            continue
        status = (
            "所列克制条件匹配，最终效力仍待审"
            if pair["condition_match"] is True
            else (
                "克制前提未决"
                if pair["condition_match"] is None
                else {
                    "static_cannot_control_active": "静爻不克活动爻",
                    "active_control_obstructs_static_control": "静爻受活动爻克，向外克暂受阻",
                    "back_control_obstructs_outgoing_candidate": "回头克来源受阻，先审解救",
                    "own_si_growth_or_back_control_pending": "金化巳的长生或回头克资格待审",
                }.get(pair["status"], "未匹配所列克制前提")
            )
        )
        if pair["source_rescue_used"]:
            status += (
                "；本位回头生支持该条件，原日月反制仍保留"
                if any(
                    a.get("harm_condition_match", True) is True
                    for a in pair["source_calendar_oppositions"]
                )
                else "；本位回头生支持该条件，三支总作用仍待审"
            )
        elif pair["source_void_fill_used"]:
            status += (
                "；当日冲空的同日日克资格已核，原旬空与日克事实仍保留，其他门槛另审"
            )
        elif pair["source_back_generation_condition"] is False and any(
            "三支总作用待审" in reason for reason in pair["source_obstructions"]
        ):
            status += "；三支总作用待审，本位回头生支持未确认"
        condition_lines.append(
            f"第{pair['source_position']}爻{pair['source_branch']}克第{pair['target_position']}爻{pair['target_branch']}：{status}"
        )
    condition_lines.append(control["scope"])
    condition_lines.append(control["void_fill_qualification"]["scope"])
    generation = conditional["generation_conditions"]
    if generation["focus"] is not None:
        generation_focus = generation["focus"]
        condition_lines.append(
            f"明确用爻第{generation_focus['position']}爻{generation_focus['branch']}："
            + generation_focus["source_explanation"]
        )
        condition_lines.append(generation_focus["target_explanation"])
    for pair in generation["generations"]:
        if pair["status"] == "static_outside_current_all_static_generation_scope":
            continue
        source_status = (
            "生源条件匹配"
            if pair["condition_match"] is True
            else (
                "生源条件待审"
                if pair["condition_match"] is None
                else "未匹配所列生源条件"
            )
        )
        reception = (
            "受生爻未见所列承受障碍"
            if pair["target_reception_condition"] is True
            else (
                "受生爻空破前提待审"
                if pair["target_reception_condition"] is None
                else "受生爻月破日克无独立根，不能据有生即作受益"
            )
        )
        pair_text = f"第{pair['source_position']}爻{pair['source_branch']}生第{pair['target_position']}爻{pair['target_branch']}：{source_status}；{reception}"
        if qualification_note := pair.get("qualification_explanation"):
            pair_text += "；" + qualification_note
        condition_lines.append(pair_text)
    condition_lines.append(generation["scope"])
    clash = conditional["clash_conditions"]
    for row in clash["lines"]:
        if not row["clash_actors"]:
            continue
        labels = []
        if row["is_day_clash"]:
            labels.append("日冲事实")
        if row["day_void_fill_condition"]:
            labels.append("当日冲空填实条件匹配；原旬空支表保留")
        if row["day_break_condition"] is True:
            labels.append("静爻日破条件匹配；未推永久无用")
        elif row["day_break_condition"] is None:
            labels.append("静爻日冲与生扶前提未决")
        if (
            row["scatter_status"]
            == "supported_or_qi_moving_not_scattered_by_clash_alone"
        ):
            labels.append("有气或旺相，冲本身不判散；独立克制仍另审")
        elif (
            row["scatter_status"]
            == "weak_or_pending_moving_scatter_not_automatically_decided"
        ):
            labels.append("衰动或气未决，不能因冲即判散")
        if row["back_clash"]:
            labels.append(
                "本位回头冲兼克"
                if row["back_control"]
                else "本位回头冲而不克；不自动作回头克"
            )
        condition_lines.append(
            f"第{row['position']}爻{row['branch']}冲的条件：" + "；".join(labels)
        )
    condition_lines.append(clash["scope"])
    progress_states = {
        "advance_supported_now": "已列旺相条件支持乘势而进",
        "advance_waits_for_strength": "待旺相条件，不作即时进",
        "advance_waits_for_void_break_relief": "本变有空破，待填实条件",
        "retreat_held_for_near_event": "近事有扶，按已列条件不退",
        "retreat_weak_now": "已列休囚条件匹配退神，不等于向外作用归零",
        "retreat_waits_for_weakness": "有旺相，待休囚条件",
        "retreat_waits_for_void_break_relief": "本变有空破，待填实条件",
        "requires_event_horizon": "须明确近事或久远，暂不判当下退",
        "requires_strength_resolution": "旺衰条件未决，暂不判当下进退",
    }
    for row in conditional["lines"]:
        progress = row.get("progress_conditions")
        if progress:
            condition_lines.append(
                f"第{row['position']}爻{progress['structural_pair']}配对："
                + progress_states[progress["state"]]
            )
            condition_lines.append(progress["scope"])
    harmony = conditional["three_harmony"]
    harmony_statuses = {
        "formation_requires_activity_resolution": "局的活动前提待审，不能据候选认定成局",
        "static_three_branches_only": "静三支，未按成局处理",
        "single_active_text_requires_review": "一动成局的其余条件须复核原文",
        "awaiting_missing_branch": "两支待补",
        "day_month_completion_candidate": "日月补支候选，效力待审",
        "awaiting_fill_or_tomb_review": "支齐，尚有空破墓待审",
        "formation_conditions_matched": "所列成局条件匹配，强弱效力待审",
        "completed_by_scoped_changed_path": "已有指定爻位动变补支路径",
        "changed_completion_requires_fill_or_review": "已有动变补支路径，空破墓仍待审",
    }
    for candidate in harmony["candidates"]:
        members = "、".join(
            f"{m['position']}爻{'变支' if m['location'] == 'changed' else '本支'}{m['branch']}"
            for m in candidate["members"]
        )
        condition_lines.append(
            f"三合{candidate['element']}局候选：{members}；"
            + harmony_statuses[candidate["status"]]
            + (
                "；" + "、".join(o["condition"] for o in candidate["obstructions"])
                if candidate["obstructions"]
                else ""
            )
        )
    if harmony["candidates"]:
        condition_lines.append(harmony["scope"])
    for hidden in conditional["hidden_conditions"]:
        condition_lines.append(
            f"第{hidden['position']}爻伏神{hidden['branch']}，飞神{hidden['flying_branch']}"
        )
        for key, label in (
            ("supporting_conditions", "支持关系"),
            ("obstructing_conditions", "阻碍关系"),
        ):
            matched = [
                c["condition"]
                for c in hidden[key]
                if c.get("qualified_matched", c["matched"]) is True
            ]
            pending = [
                c["condition"]
                for c in hidden[key]
                if c.get("qualified_matched", c["matched"]) is None
            ]
            condition_lines.append(
                f"{label}已匹配：{'、'.join(matched) or '未见已核关系'}；"
                f"待审：{'、'.join(pending) or '无'}"
            )
        condition_lines.extend([*hidden["table_gaps"], hidden["scope"]])
        phases = hidden["stage_conditions"]
        phase_match = phases["hidden_tomb_cessation"]["condition_match"]
        condition_lines.append(
            "伏神墓绝位置关系已核，尚未认定真墓真绝。"
            if phase_match is True
            else (
                "本次所查位置不匹配伏神墓绝关系。"
                if phase_match is False
                else "伏神墓绝位置含未校项，本次条件待审。"
            )
        )
        if phases["ignored_unknown_groups"]:
            condition_lines.append(
                "飞神不构成五行克伏，该阶段缺项仅作诊断，未据此新增克伏阻碍。"
            )
        condition_lines.append(phases["scope"])
        reception = hidden["reception"]
        gate_text = (
            "所列受生引拔门槛匹配，仍未裁定最终出伏"
            if reception["condition_match"] is True
            else (
                "当前所列受生门槛不匹配，不能据生向认定已受助"
                if reception["condition_match"] is False
                else "当前受生门槛待审，不能借同位飞神的受生结果"
            )
        )
        flying_text = (
            "飞生来源资格匹配"
            if reception["flying_generation"]["condition_match"] is True
            else (
                "飞生方向或来源资格不匹配"
                if reception["flying_generation"]["condition_match"] is False
                else "飞生来源资格待审"
            )
        )
        condition_lines.append(f"伏神{hidden['branch']}：{gate_text}；{flying_text}。")
        penalty = reception["penalty"]
        if (
            penalty["day_yin_growth_applicable"]
            and penalty["condition_match"] is not False
        ):
            text = (
                "寅日不按长生或同一日生扶计入"
                if penalty["condition_match"] is True
                else "申爻活动资格待审，寅日长生生扶不能先行确认"
            )
            condition_lines.append(f"伏神巳火：{text}；刑的总作用未裁定。")
        condition_lines.append(reception["scope"])
    return condition_lines
