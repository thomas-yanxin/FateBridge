"""Explain supplied root qualifications without calculating a second chart."""

from typing import Any, Mapping

from fatebridge.core.classical_roots import LABELS
from fatebridge.core.strength_thresholds import threshold_snapshot_lines


def root_qualification_snapshot_lines(assessment: Mapping[str, Any]) -> list[str]:
    rows = assessment.get("root_qualifications")
    decision = assessment.get("structural_decision")
    if not rows or not decision:
        return []
    positions = {"year": "年支", "month": "月支", "day": "日支", "hour": "时支"}
    rules = {
        "weighted_balance": "有效五行扶身与减身份额",
        "rooted_wealth_officer_front_without_visible_support": "财生官杀且无印比透出",
        "in_command_multiple_vigorous_roots": "得令且有含月支在内的至少两处健全根",
        "multiple_vigorous_roots_and_visible_support": "至少两处健全根且年、月、时三干均为印比",
    }
    details = []
    for row in rows:
        if row["qualification_basis"] == "not_anchored_kind":
            continue
        fraction = row["retention_fraction"]
        retention = f"{fraction:.1%}" if fraction is not None else "未有实际根量"
        inclusion = "计入" if row["qualified_for_structural_rule"] else "未计入"
        seat = positions.get(row["pillar"], row["pillar"]) + row["branch"]
        details.append(
            f"{seat}（{LABELS[row['kind']]}，实际藏干根保留{retention}，{inclusion}）"
        )
    return [
        f"结构判级：{assessment['strength_level']}；数值原判：{decision['numerical_label']}；"
        f"本次依据：{rules.get(decision['rule'], decision['rule'])}。",
        "结构根核对："
        + ("；".join(details) if details else "本次无符合资格的根")
        + "。",
        "根类依所选原典；健全根保留门槛为工程约定，判定使用未舍入根量，"
        "不等于原典全局旺衰验收或现实效果。",
    ] + threshold_snapshot_lines(assessment)
