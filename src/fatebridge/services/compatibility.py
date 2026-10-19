"""
FateBridge Compatibility Services
"""

from typing import Any, Dict

from fatebridge.analysis.compatibility import AdvancedCompatibility, RelationshipType
from fatebridge.core.export_parser import parse_export_content
from fatebridge.core.rules import BaZiRules
from fatebridge.services.birth_context import build_birth_computation_context
from fatebridge.services.birth_payload import build_destiny_payload
from fatebridge.services.structured_snapshot import render_structured_snapshot_text
from fatebridge.utils.birth_input import PersonInfo
from fatebridge.utils.elements import get_element_relationship
from fatebridge.utils.errors import ParameterError, calculation_guard


@calculation_guard("配合度分析")
def calculate_compatibility_analysis(
    person1: PersonInfo, person2: PersonInfo, relationship_type: str = "general"
) -> Dict:
    """
    计算双人配合度，分析两人的命理相互关系和配合程度

    Args:
        person1: 第一人的个人信息对象
        person2: 第二人的个人信息对象
        relationship_type: 关系类型

    Returns:
        dict: 配合度分析结果
    """
    rel_type_map = {kind.value: kind for kind in RelationshipType}
    if not isinstance(relationship_type, str) or relationship_type not in rel_type_map:
        return ParameterError(
            "relationship_type 必须为 general、marriage、friendship、business 或 family",
            [
                {
                    "path": "relationship_type",
                    "code": "literal_error",
                    "constraints": {
                        "expected": "'general', 'marriage', 'friendship', 'business' or 'family'"
                    },
                }
            ],
        ).as_result()
    rel_type = rel_type_map[relationship_type]

    context1 = build_birth_computation_context(person1)
    context2 = build_birth_computation_context(person2)
    analysis1 = build_destiny_payload(context1)
    analysis2 = build_destiny_payload(context2)

    # 使用高级合盘分析
    advanced_analysis = AdvancedCompatibility.analyze_comprehensive_compatibility(
        analysis1, analysis2, rel_type
    )

    # 分别提供传统四柱规则与多维关系分析。
    pillars1 = context1.birth_pillars
    pillars2 = context2.birth_pillars
    traditional_compatibility = BaZiRules.calculate_compatibility_score(
        pillars1, pillars2
    )

    # 五行关系分析
    element1 = analysis1["day_master"]["element"]
    element2 = analysis2["day_master"]["element"]
    element_relationship = get_element_relationship(element1, element2)

    # 优化的JSON输出格式
    result: Dict[str, Any] = {
        "summary": {
            "overall_score": advanced_analysis["overall_score"],
            "compatibility_level": advanced_analysis["summary"],
            "relationship_type": relationship_type,
            "score_basis": "多维度规则加权的 0–100 分；不是关系成功概率。",
            "scoring": advanced_analysis["scoring"],
        },
        "detailed_analysis": {
            "element_balance": advanced_analysis["detailed_analysis"][
                "element_balance"
            ],
            "favorable_synergy": advanced_analysis["detailed_analysis"][
                "favorable_synergy"
            ],
            "ten_gods_relationship": advanced_analysis["detailed_analysis"][
                "ten_gods_relationship"
            ],
            "pattern_synergy": advanced_analysis["detailed_analysis"][
                "pattern_synergy"
            ],
            "traditional_analysis": {
                **advanced_analysis["detailed_analysis"]["traditional_analysis"],
                "score": advanced_analysis["detailed_analysis"]["traditional_analysis"][
                    "normalized_score"
                ],
                "score_basis": (
                    "从 50 分起，按跨盘冲、害、刑扣分并截断至 0–100；"
                    "是综合分的一个维度，与 traditional_compatibility 的净分独立。"
                ),
            },
        },
        "strengths": advanced_analysis["strengths"],
        "challenges": advanced_analysis["challenges"],
        "recommendations": advanced_analysis["recommendations"],
        "person_info": {
            "person1": {
                "name": analysis1["person_info"]["name"],
                "birth_datetime": analysis1["person_info"]["birth_datetime"],
                "day_master": f"{analysis1['day_master']['stem']}({analysis1['day_master']['element']})",
                "strength": analysis1["day_master"]["strength"],
                "favorable_elements": analysis1.get("favorable_elements", []),
            },
            "person2": {
                "name": analysis2["person_info"]["name"],
                "birth_datetime": analysis2["person_info"]["birth_datetime"],
                "day_master": f"{analysis2['day_master']['stem']}({analysis2['day_master']['element']})",
                "strength": analysis2["day_master"]["strength"],
                "favorable_elements": analysis2.get("favorable_elements", []),
            },
        },
        "element_relationship": {
            "person1_element": element1,
            "person2_element": element2,
            "relationship_type": element_relationship["type"],
            "description": element_relationship["description"],
        },
        "traditional_compatibility": {
            "score": traditional_compatibility["overall_score"],
            "level": traditional_compatibility["level"],
            "details": traditional_compatibility.get("details", []),
            "score_basis": (
                "合与冲、刑、害等规则加减后的净分，0 为中性；不是 0–100 分。"
                "level 只评价该净分，不能替代 summary 的综合等级；"
                "与 detailed_analysis.traditional_analysis 使用不同计分规则。"
            ),
        },
    }
    snapshot_text = render_structured_snapshot_text(result, title="双人配合度分析")
    result["snapshot_text"] = snapshot_text
    result["snapshot_export"] = parse_export_content(
        technique="generic", content=snapshot_text
    )
    return result
