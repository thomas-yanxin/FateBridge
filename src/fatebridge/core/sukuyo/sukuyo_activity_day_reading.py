"""Render personal and action-specific statements from the supplied day evidence."""

from __future__ import annotations

from typing import Any

from fatebridge.core.sukuyo.sukuyo_candidate_reading import candidate_day_lines
from fatebridge.core.sukuyo.sukuyo_documentary import text_placement_label
from fatebridge.core.sukuyo.sukuyo_kenyu_lingbi import lingbi_reading_lines
from fatebridge.core.sukuyo.sukuyo_padas import render_palace_reference

_ACTIVITY_DETAIL_LABELS = {
    "tailoring_garments": "裁衣",
    "making_garments": "制作衣服",
    "repairing_garments": "修补衣服",
    "wearing_garments": "穿衣",
    "wearing_new_garments": "穿新衣",
    "royal_wearer": "王者着衣",
    "sale": "出售",
    "borrowing": "借入",
    "lending": "借出",
    "earning_money": "求财",
    "sale_lactating_livestock": "出售乳畜",
    "sale_livestock": "出售牲畜",
    "spending_property": "支出财物",
    "receiving_property": "收取财物",
    "returning_property": "归还财物",
    "wealth_competition": "争财",
    "purchase": "购入",
    "business_operation": "经营",
    "collecting_debt": "索取债款",
    "repaying_debt": "偿还债款",
    "purchase_precious_goods": "购入金宝",
    "purchase_livestock": "购入牲畜",
    "land_purchase": "购入田地",
    "land_sale": "出售田地",
    "long_distance_journey": "远行",
    "journey_abroad": "出国",
    "personal_departure": "自家出行",
    "private_journey": "私事出行",
    "royal_or_official_traveler": "王者或使者出行",
    "long_distance_traveler_entering_residence": "远行者入宅",
    "southbound_journey": "向南出行",
    "northbound_journey": "向北出行",
    "eastbound_journey": "向东出行",
    "westbound_journey": "向西出行",
    "water_journey": "水路出行",
    "diplomatic_mission": "使节任务",
    "skill_learning": "学习技艺",
    "founding_school": "设立学舍",
    "beginning_study": "入学",
    "learning_with_teacher": "从师学习",
    "religious_learning": "宗教学法",
    "monastic_dharma_request": "出家人求法",
    "teaching_classics": "教授经典",
    "riding_training": "学习骑乘",
    "social_gathering": "聚会",
    "forming_friendship": "结交朋友",
    "classical_text_study": "研读经典",
    "debate_learning": "学习论辩",
}


def activity_day_reading_lines(
    day: dict[str, Any],
    calendar: dict[str, Any],
    name: str | None,
) -> list[str]:
    lines: list[str] = []
    personal = day.get("personal_day")
    if day.get("kenyu_lingbi_reference"):

        lines.extend(lingbi_reading_lines(day["kenyu_lingbi_reference"]))
    else:
        pass
    if personal:
        relation = personal["relation"]
        lines.append(
            f"以本命{relation['self_su27']}为命，顺数至历日{relation['other_su27']}为{relation['relation']}；此为有向三九日关系。"
        )
        lines.append(
            f"上卷条文：{personal['upper_volume']['meaning']}（{personal['upper_volume']['locator']}）"
        )
        if personal.get("lower_volume_variant"):
            alternative = personal["lower_volume_variant"]
            lines.append(
                f"下卷异文：{alternative['meaning']}（{alternative['locator']}）"
            )
        else:
            pass
        if personal["textual_conflict"]:
            subject = "业日所作" if relation["relation"] == "業" else "危日婚姻"
            lines.append(
                f"{subject}的所选原文存在宜忌冲突，保留已列相反见证，不投票或互相覆盖。"
            )
        else:
            pass
        witnesses = personal.get("source_day_evidence")
        if witnesses:
            for row in witnesses["witnesses"]:
                volume = "上卷" if row["volume"] == "upper" else "下卷"
                kind = "又一说" if row["source_witness"] == "another_saying" else "主文"
                lines.append(
                    f"三九日{volume}{kind}见证：{row['meaning']}（{row['locator']}）"
                )
            priority = witnesses["priority_clause"]
            lines.append(
                f"三九与长行历：{priority['meaning']}（{priority['locator']}）"
            )
        else:
            pass
    else:
        pass
    doctrine = day.get("conjunction_doctrine") or {}
    group = doctrine.get("selected_group")
    if group:
        lines.append(
            f"历日宿名在下卷宿月配合段归入{group['label']}（{group['locator']}）；仅为文献分类，未据此移动物理月亮或推定过宿钟时。"
        )
        if group["membership_basis"].startswith("inferred_"):
            lines.append(
                "此组九宿成员由27宿序扣除已列六宿及十二宿推得；原文本段没有逐宿列名。"
            )
        else:
            pass
    else:
        pass
    lower = day.get("lower_mansion_day") or {}
    for note in lower.get("mapping_notes", []):
        lines.append(
            f"下卷逐宿原段限定：{note}；与具体服务事项规则分别保留，未据此作现实行动总裁决。"
        )
    if not day.get("activity_assessment"):
        for rule in lower.get("topic_rules", []):
            excerpts = rule.get("source_excerpts") or [rule["source_excerpt"]]
            condition = (
                f"；适用条件为{rule['topic_condition']}"
                if rule.get("topic_condition")
                else ""
            )
            lines.append(
                f"下卷逐宿条件参考：{rule['meaning']}；原文"
                + "／".join(dict.fromkeys(excerpts))
                + f"{condition}（{rule['locator']}）；未据此补造事项或实际行为。"
            )
    else:
        pass
    for issue in lower.get("textual_issues", []):
        lines.append(
            f"下卷逐宿文本问题：{issue['issue']}（{issue['locator']}）"
            + (
                f"；归属未定原文为{issue['literal']}，未应用于事项。"
                if issue.get("literal")
                else ""
            )
        )
    if day.get("palace_reference"):

        lines.append(render_palace_reference(day["palace_reference"]))
    else:
        pass
    directions = day.get("directional_travel")
    if directions and directions["selected_records"]:
        lines.append(
            "下卷行动禁闭法另按明列日宿查方向；宫名只作本段标签，不是本命宫，方向未从出生地或GPS推定。"
        )
        for record in directions["selected_records"]:
            placement = text_placement_label(record)
            lines.append(
                f"方向条件文：{record['meaning']}（{record['locator']}；{placement}）。"
                "正文／夹注层次据所选出版方TEI标记，夹注作者身份未独立核定。"
            )
            opposing = [
                rule
                for rule in lower.get("topic_rules", [])
                if "travel" in rule["activities"]
                and rule["assessment"] != record["assessment"]
                and set(rule.get("activity_detail_any_of", []))
                & set(record["activity_detail_any_of"])
            ]
            for rule in opposing:
                lines.append(
                    f"下卷逐宿章同向条件文（{text_placement_label(rule)}）：{rule['meaning']}；"
                    f"条件为{rule['topic_condition']}（{rule['locator']}）。"
                )
            if opposing:
                lines.append(
                    "两章同向出行证言相反，分别保留，未据此改变本次事项匹配状态；"
                    "未声明出行方向时仍是条件参考。"
                )
            else:
                pass
            for variant in record["textual_variants"]:
                lines.append(
                    f"方向校记：{variant['literal']}（{variant['locator']}）；未替换大正主文。"
                )
    else:
        pass
    if directions:
        if name and not directions["selected_records"]:
            lines.append(
                f"下卷行动禁闭法未找到已识别的{name}宿方向条文；"
                "空匹配不能证明准许或禁止某行向，不能补齐未列方向。"
            )
        else:
            pass
        for issue in directions.get("textual_issues", []):
            lines.append(
                f"方向原文校勘问题：{issue['issue']}（{issue['locator']}）；"
                "未定选择字及另一见证的增删均未改写当前主文或事项。"
            )
    else:
        pass
    activity = day.get("activity_assessment")
    direction_names = {
        "northbound_journey": "向北出行",
        "eastbound_journey": "向东出行",
        "southbound_journey": "向南出行",
        "westbound_journey": "向西出行",
    }
    declared_directions = [
        detail
        for detail in (activity or {}).get("activity_details", [])
        if detail in direction_names
    ]
    if declared_directions:
        lines.append(
            "本次已明确行向："
            + "、".join(direction_names[d] for d in declared_directions)
            + "；行向不自动代表远行。"
        )
    else:
        pass
    if directions and directions.get("candidate_records"):
        complete = calendar.get("profile_calculation", {}).get(
            "candidate_set_complete_under_declared_reconstructions"
        )
        if complete is True:
            lines.append(
                "所列日宿候选在本次声明的现代重建下完整；不代表所有古法已穷尽。"
            )
        else:
            lines.append("下列仅为已列日宿候选的方向参考，未据此证明候选已穷尽。")
        for branch in directions["candidate_records"]:
            for record in branch["records"]:
                required = record.get("activity_detail_any_of", [])
                applies = bool(set(required).intersection(declared_directions))
                condition = (
                    "本次已声明行向与该支本条方向相符"
                    if applies
                    else (
                        "本次已声明行向与该支本条方向不符"
                        if declared_directions
                        else "本次未明确本条所需行向"
                    )
                )
                lines.append(
                    f"候选{branch['mansion']}方向条文：{record['meaning']}；"
                    f"{condition}（{record['locator']}；{text_placement_label(record)}）。"
                )
        lines.append(
            "以上只核对各候选条文与已声明行向，未代入未定主宿或顶层事项；不能将一支方向相符提升为全案宜行。"
        )
    else:
        pass
    if activity:
        if activity.get("activity_details"):
            lines.append(
                "本次已确认事项细节："
                + "、".join(
                    _ACTIVITY_DETAIL_LABELS[detail]
                    for detail in activity["activity_details"]
                )
                + "；只呈现已声明输入，推导分类另列，不补其他事实。"
            )
        else:
            pass
        if activity.get("detail_inferences"):
            lines.append(
                "行为分类仅从已声明细节推出："
                + "；".join(
                    f"{r['from_detail']}归入{r['implied_detail']}"
                    for r in activity["detail_inferences"]
                )
                + "；未推断方向、路程、付款方式或其他事实。"
            )
        else:
            pass
        topic = {
            "social": "社交",
            "marriage": "婚姻",
            "travel": "出行",
            "relocation": "迁居",
            "commerce": "交易",
            "study": "学习",
            "clothing": "衣事",
        }[activity["activity"]]
        status = {
            "favorable": "所匹配文献仅列宜条",
            "caution": "所匹配文献仅列忌条",
            "conflicted": "所匹配条文兼有宜与忌，须核对动作和卷别后判断是否构成同条件冲突",
            "uncovered": "选定条文未覆盖此事项",
            "conditional_only": "只有尚未满足适用条件或读法待校定的条文，未取确定宜忌",
        }[activity["evidence_status"]]
        lines.append(f"所问{topic}：{status}；不是全天综合判断或现实成功概率。")
        for rule in activity["matched_rules"]:
            condition = (
                f"；本次适用条件：{rule['topic_condition']}"
                if rule.get("applicability_status")
                == "matched_declared_activity_detail"
                else ""
            )
            lines.append(
                f"{rule['rule_id']}：{rule['meaning']}{condition}（{rule['locator']}）"
            )
        if activity.get("conditional_rules"):
            lines.append(
                "以下条文的适用条件未满足或文本读法未校定，未计入上述宜忌状态："
            )
            for rule in activity["conditional_rules"]:
                required = [
                    d
                    for d in rule.get("activity_detail_any_of", [])
                    if d in direction_names
                ]
                if (
                    required
                    and declared_directions
                    and not set(required).intersection(declared_directions)
                ):
                    lines.append(
                        "本次已声明行向不满足此条所需的"
                        + "、".join(direction_names[d] for d in required)
                        + "；不能将已知其他行向说成方向全部未知。"
                    )
                else:
                    pass
                lines.append(
                    f"{rule['rule_id']}：{rule['meaning']}；条件为{rule['topic_condition']}（{rule['locator']}）。"
                )
        else:
            pass
    else:
        pass
    if not activity:
        lines.append(
            "本次没有事项输入，以上保留各层文献证言，未形成事项汇总；"
            "不据一般吉日、单条宜慎或来源标签裁决现实行动。"
        )
    else:
        pass

    lines.extend(candidate_day_lines(day.get("candidate_mansion_days", [])))
    return lines
