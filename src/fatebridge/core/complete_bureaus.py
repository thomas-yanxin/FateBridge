"""Same complete bureau, multiple physical members; source and display scope."""

from typing import Any, Mapping

MEMBERSHIP_POLICY = "same_bureau_all_physical_positions_v1"
SOURCE = {
    "id": "ditian_complete_bureau_duplicate_member_v1",
    "title": "任注滴天髓闡微·衰旺（辛巳丁酉丁酉辛丑例）",
    "author": "任鐵樵增注，李雨田校訂",
    "edition": "上海大東書局，中華民國三十六年四月初版（1947）",
    "url": "https://upload.wikimedia.org/wikipedia/commons/d/db/SSID-11335994_%E6%BB%B4%E5%A4%A9%E9%AB%93%E9%97%A1%E5%BE%AE.pdf",
    "source_sha256": "d6a7d1daf6513ce9fb9940ff8331b96804c10cdafbeac00d4d3d0a37229e1803",
    "pdf_pages": [3, 181],
    "printed_pages": [39],
    "scope": "书影明示此重复酉命式仍全金局；同局实体位置并集是工程形式化，不认证其他流派、全局成格或数值转化系数。",
}


def complete_bureau_snapshot_lines(assessment: Mapping[str, Any]) -> list[str]:
    rows = assessment.get("hidden_stem_ledger") or []
    branches = {r["pillar"]: r["branch"] for r in rows}
    labels = {"year": "年支", "month": "月支", "day": "日支", "hour": "时支"}
    states = {"conditioned_transformation": "有条件转化", "binding": "合绊"}
    result = []
    for event in assessment.get("relations", []):
        positions = event.get("positions", [])
        if event.get("status") == "same_target_affiliation_only":
            seats = "、".join(labels.get(p, p) + branches[p] for p in positions)
            result.append(
                f"同目标附合：{seats}与完整{event['primary_formation']['kind']}"
                f"{event['target']}局同气，附合仅列关系，不另加合绊或转化预算；"
                "完整局按原有位置核算一次，局外支不据此转化。"
                "这不裁定全局成格或有效通关。"
            )
            continue
        if (
            event.get("kind") not in {"三合", "三会"}
            or len(positions) <= 3
            or event.get("status") not in states
            or not all(p in branches for p in positions)
        ):
            continue
        seats = "、".join(labels.get(p, p) + branches[p] for p in positions)
        result.append(
            f"完整{event['kind']}{event['target']}局：{seats}；"
            f"本次按{states[event['status']]}处理。同局重复支合并核算，每个位置只处理一次；"
            "不据此断定全局成格或现实吉凶。"
        )
    return result
