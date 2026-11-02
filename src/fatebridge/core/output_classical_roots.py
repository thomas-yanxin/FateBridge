"""Projection-safe contracts for source-qualified root categories."""

from typing import Any, Dict, List, Literal, Optional

from pydantic import model_validator

from fatebridge.core.output_base import PartialOutput
from fatebridge.core.output_classical_seasonal import SeasonalClimateReference
from fatebridge.core.output_stage_profile import LifeStageProfile

RootKind = Literal[
    "lu_root",
    "yang_blade_root",
    "yang_growth_root",
    "prosperity_root",
    "storage_root",
    "residual_root",
    "principal_element_root",
    "other_hidden_root",
    "yin_growth_reference",
    "no_root_in_this_profile",
]
RootWeightClass = Literal[
    "heavy", "light", "light_textual_reference", "not_ranked_by_this_rule"
]


class ClassicalRoot(PartialOutput):
    pillar: Optional[str] = None
    stem: Optional[str] = None
    branch: Optional[str] = None
    life_stage: Optional[str] = None
    kind: Optional[RootKind] = None
    label: Optional[str] = None
    matching_hidden_stems: Optional[List[str]] = None
    hidden_element_present: Optional[bool] = None
    source_weight_class: Optional[RootWeightClass] = None
    effect_status: Optional[Literal["root_effect_not_adjudicated"]] = None
    source_ref: Optional[str] = None
    clash_partners: Optional[List[str]] = None

    @model_validator(mode="after")
    def preserve_distinct_root_observations(self) -> "ClassicalRoot":
        if self.hidden_element_present is False and self.matching_hidden_stems:
            raise ValueError("无同气藏干与存在匹配藏干不能同时成立")
        if self.kind == "yin_growth_reference" and (
            self.hidden_element_present is True or self.matching_hidden_stems
        ):
            raise ValueError("阴长生原典参考不能补造成同气藏干根")
        return self


class ClassicalRootProfile(PartialOutput):
    method_id: Optional[str] = None
    day_stem: Optional[str] = None
    life_stage_profile: Optional[LifeStageProfile] = None
    roots: Optional[List[ClassicalRoot]] = None
    heavy_root_positions: Optional[List[str]] = None
    light_hidden_root_positions: Optional[List[str]] = None
    yin_growth_reference_positions: Optional[List[str]] = None
    global_strength_status: Optional[Literal["not_adjudicated"]] = None
    source: Optional[Dict[str, Any]] = None
    scope: Optional[str] = None


class ClassicalOverview(PartialOutput):
    monthly_structure: Optional[Dict[str, Any]] = None
    seasonal_climate: Optional[SeasonalClimateReference] = None
    life_stages: Optional[Dict[str, Any]] = None
    root_profile: Optional[ClassicalRootProfile] = None
