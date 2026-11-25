"""Shared definitions, independent of the domain entry point."""

from __future__ import annotations

from typing import Any


def candidate_day_lines(rows: list[dict[str, Any]]) -> list[str]:
    if not rows:
        return []
    lines = [
        "以下逐宿保留条件三九日与事项证据；每支均未代入未定主宿或顶层事项，不据此选择古代日界、半日或闰小月次序。"
    ]
    for row in rows:
        name = row["day_mansion"]
        supports = []
        for condition in row["conditions"]:
            half = {"first_half": "前半", "second_half": "后半", None: "半日未绑定"}[
                condition["calendar_day_part"]
            ]
            supports.append(
                half
                + (
                    "／" + condition["reconstruction_id"]
                    if condition["reconstruction_id"]
                    else ""
                )
            )
        lines.append(
            f"条件候选{name}宿：支持条件为{'、'.join(supports)}；仅在已列候选内查表，候选集在声明重建下完整性为{row['candidate_set_complete_under_declared_reconstructions']}。"
        )
        personal = row["personal_day"]
        if personal:
            relation = personal["relation"]
            lines.append(
                f"此支以本命{relation['self_su27']}顺数至{name}为{relation['relation']}；{personal['upper_volume']['meaning']}（{personal['upper_volume']['locator']}）。"
            )
            if personal["lower_volume_variant"]:
                variant = personal["lower_volume_variant"]
                lines.append(
                    f"此支下卷异文：{variant['meaning']}（{variant['locator']}）。"
                )
            for witness in personal["source_day_evidence"]["witnesses"]:
                lines.append(
                    f"此支三九日{witness['volume']}／{witness['source_witness']}：{witness['meaning']}（{witness['locator']}）。"
                )
            priority = personal["source_day_evidence"]["priority_clause"]
            lines.append(
                f"此支三九与长行历：{priority['meaning']}（{priority['locator']}）。"
            )
        assessment = row["activity_assessment"]
        if assessment:
            for key, label in (
                ("matched_rules", "此条件支内匹配"),
                ("conditional_rules", "适用细节不足或读法待校，支内未应用"),
            ):
                for rule in assessment[key]:
                    condition = (
                        f"；条文条件：{rule['topic_condition']}"
                        if rule.get("topic_condition")
                        else ""
                    )
                    lines.append(
                        f"候选{name}宿{label} {rule['rule_id']}：{rule['meaning']}{condition}（{rule['locator']}）；未应用于主结果。"
                    )
    return lines
