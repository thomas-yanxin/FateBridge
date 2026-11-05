"""Projectable rule indices with complete-result evidence requirements."""

from decimal import ROUND_HALF_EVEN, Decimal
from typing import Dict, List, Literal, Optional, Union

from pydantic import Field, JsonValue, ValidationInfo, model_validator

from fatebridge.core.output_base import FullFact, PartialOutput

DIMENSIONS = (
    "element_balance",
    "favorable_synergy",
    "ten_gods_relationship",
    "pattern_synergy",
    "traditional_analysis",
)


class PreferenceObservation(PartialOutput):
    person: FullFact[Optional[str]] = None
    element: FullFact[Optional[str]] = None
    state: FullFact[
        Optional[Literal["useful", "avoid", "conditional", "neutral", "unknown"]]
    ] = None


class CompatibilityDimension(PartialOutput):
    score: FullFact[Optional[float]] = Field(default=None, ge=0, le=100)
    details: FullFact[Optional[List[str]]] = None
    assessment_status: Optional[Literal["calculated", "partial"]] = None
    score_basis: Optional[Union[str, List[str]]] = None
    control_evidence: Optional[List[PreferenceObservation]] = None
    supportive_patterns: Optional[List[Dict[str, JsonValue]]] = None
    unresolved_patterns: Optional[List[Dict[str, JsonValue]]] = None
    tension_patterns: Optional[List[Dict[str, JsonValue]]] = None
    risk_patterns: Optional[List[Dict[str, JsonValue]]] = None
    synergy_level: Optional[str] = None
    balance_type: Optional[str] = None


class CompatibilityDetails(PartialOutput):
    element_balance: FullFact[Optional[CompatibilityDimension]] = None
    favorable_synergy: FullFact[Optional[CompatibilityDimension]] = None
    ten_gods_relationship: FullFact[Optional[CompatibilityDimension]] = None
    pattern_synergy: FullFact[Optional[CompatibilityDimension]] = None
    traditional_analysis: FullFact[Optional[CompatibilityDimension]] = None


class WeightedDimension(PartialOutput):
    score: FullFact[Optional[float]] = Field(default=None, ge=0, le=100)
    weight: FullFact[Optional[float]] = Field(default=None, ge=0, le=1)
    weighted_score: FullFact[Optional[float]] = None


class CompatibilityScoring(PartialOutput):
    method_id: FullFact[Optional[str]] = None
    score_kind: FullFact[Optional[Literal["uncalibrated_rule_index"]]] = None
    evidence_policy: FullFact[Optional[str]] = None
    dependency_policy: FullFact[Optional[str]] = None
    dimension_dependencies: FullFact[Optional[Dict[str, List[str]]]] = None
    status: FullFact[Optional[Literal["calculated", "partial"]]] = None
    unresolved_dimensions: FullFact[Optional[List[str]]] = None
    input_methods: FullFact[Optional[Dict[str, Dict[str, JsonValue]]]] = None
    dimensions: FullFact[Optional[Dict[str, WeightedDimension]]] = Field(
        default=None,
        json_schema_extra={"x-fatebridge-full-result-required-keys": list(DIMENSIONS)},
    )
    unrounded_score: FullFact[Optional[float]] = None
    rounding: FullFact[Optional[str]] = None

    @model_validator(mode="after")
    def consistent_weighted_ledger(
        self, info: ValidationInfo
    ) -> "CompatibilityScoring":
        if not info.context or not info.context.get("full_result"):
            return self
        assert self.dimensions is not None and self.dimension_dependencies is not None
        names = set(DIMENSIONS)
        if set(self.dimensions) != names or set(self.dimension_dependencies) != names:
            raise ValueError("完整合盘分项及依赖须对应五个具名维度")
        total, weights = Decimal(0), Decimal(0)
        for dimension in self.dimensions.values():
            expected = Decimal(str(dimension.score)) * Decimal(str(dimension.weight))
            if dimension.weighted_score != float(expected):
                raise ValueError("合盘加权账本与分项不一致")
            total += expected
            weights += Decimal(str(dimension.weight))
        if weights != 1 or self.unrounded_score != float(total):
            raise ValueError("合盘权重或总和不一致")
        assert self.unresolved_dimensions is not None
        if not set(self.unresolved_dimensions) <= names or self.status != (
            "partial" if self.unresolved_dimensions else "calculated"
        ):
            raise ValueError("合盘缺项状态与未裁定维度不一致")
        return self


class CompatibilitySummary(PartialOutput):
    overall_score: FullFact[Optional[float]] = Field(default=None, ge=0, le=100)
    compatibility_level: FullFact[Optional[str]] = None
    relationship_type: FullFact[Optional[str]] = None
    score_basis: FullFact[Optional[str]] = None
    status: FullFact[Optional[Literal["calculated", "partial"]]] = None
    scoring: FullFact[Optional[CompatibilityScoring]] = None

    @model_validator(mode="after")
    def consistent_summary(self, info: ValidationInfo) -> "CompatibilitySummary":
        if not info.context or not info.context.get("full_result"):
            return self
        assert self.scoring is not None
        expected = float(
            min(
                Decimal(100),
                max(Decimal(0), Decimal(str(self.scoring.unrounded_score))),
            ).quantize(Decimal("0.1"), rounding=ROUND_HALF_EVEN)
        )
        if self.overall_score != expected or self.status != self.scoring.status:
            raise ValueError("合盘摘要与实际评分账本不一致")
        return self


class TraditionalCompatibility(PartialOutput):
    score: FullFact[Optional[float]] = None
    level: FullFact[Optional[str]] = None
    details: FullFact[Optional[List[str]]] = None
    score_basis: FullFact[Optional[str]] = None
