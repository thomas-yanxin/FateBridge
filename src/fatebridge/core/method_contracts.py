"""Declared method semantics; registration never implies domain acceptance."""

from dataclasses import dataclass
from typing import Literal

from pydantic import JsonValue


@dataclass(frozen=True)
class MethodContract:
    method_id: str
    output_paths: tuple[str, ...]
    quantity_kind: str
    unit: str
    prerequisites: tuple[str, ...]
    dependencies: tuple[str, ...]
    comparison_requirements: tuple[str, ...]
    limitations: tuple[str, ...]
    role: Literal["calculation", "reference", "presentation"] = "calculation"
    implementation_refs: tuple[str, ...] = ()
    source_refs: tuple[str, ...] = ()
    selector_fields: tuple[str, ...] = ()
    error_sources: tuple[str, ...] = ()
    validation_status: str = "not_fully_accepted"

    def as_manifest(self) -> dict[str, JsonValue]:
        return {
            "method_id": self.method_id,
            "output_paths": list(self.output_paths),
            "quantity_kind": self.quantity_kind,
            "unit": self.unit,
            "prerequisites": list(self.prerequisites),
            "dependencies": list(self.dependencies),
            "comparison_requirements": list(self.comparison_requirements),
            "limitations": list(self.limitations),
            "role": self.role,
            "implementation_refs": list(self.implementation_refs),
            "source_refs": list(self.source_refs),
            "selector_fields": list(self.selector_fields),
            "error_sources": list(self.error_sources),
            "validation_scope": {
                "numerical": "method_specific_reference_required",
                "source_conformity": self.validation_status,
                "real_world_validity": "not_established",
            },
        }


COMPATIBILITY_INDEX = MethodContract(
    method_id="compatibility_weighted_rules_v3",
    output_paths=("summary.overall_score", "summary.scoring"),
    quantity_kind="uncalibrated_rule_index",
    unit="index_points_0_100",
    prerequisites=(
        "两份经请求边界校验的出生资料，关系类型由用户明确或采用general",
        "喜忌及成局方向须有明确裁定；未知、条件及中性分别传递",
    ),
    dependencies=(
        "both_birth_contexts",
        "strength_assessments",
        "useful_element_profiles",
    ),
    comparison_requirements=(
        "相同评分版本、关系类型及输入判定方法",
        "相同可用分项；partial不作为完整配合结论",
    ),
    limitations=(
        "基分及权重是工程约定；未决项不改权重、不推为支持或反对",
        "多个分项共享出生和结构依据，不能视为独立证据或概率",
        "关系类型权重不等于双向角色模型或多人关系模型",
    ),
)

LIFE_DIMENSION_INDEX = MethodContract(
    method_id="life_dimension_tanh_v2",
    output_paths=("life_dimensions", "life_dimensions_assessment"),
    quantity_kind="uncalibrated_rule_index",
    unit="index_points_0_100",
    prerequisites=(
        "本命、流年、流月、流日、流时须成功计算",
        "爱情及大运依赖已知性别；未起运与资料未知分别交付",
    ),
    dependencies=("birth_context", "analysis_moment", "timing_pillars", "gender"),
    comparison_requirements=(
        "相同方法及参与层集合",
        "未知维度为null；已知零计数仍按相同连续公式变换",
    ),
    limitations=(
        "固定柱权重及tanh变换是工程约定，不构成心理测量或成功概率",
        "未建立完整行运力量、层间争合救应及寒暖模型",
        "未证明出生时间区间连续稳定；采样频数不作概率",
    ),
)
