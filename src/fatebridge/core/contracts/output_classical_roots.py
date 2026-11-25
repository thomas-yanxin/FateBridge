"""Projection-safe contracts for source-qualified root categories."""

from typing import Literal

from pydantic import model_validator

from fatebridge.core.contracts.output_base import OpenJsonValue, PartialOutput
from fatebridge.core.contracts.output_classical_seasonal import SeasonalClimateReference
from fatebridge.core.contracts.output_stage_profile import LifeStageProfile

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
    pillar: str | None = None
    stem: str | None = None
    branch: str | None = None
    life_stage: str | None = None
    kind: RootKind | None = None
    label: str | None = None
    matching_hidden_stems: list[str] | None = None
    hidden_element_present: bool | None = None
    source_weight_class: RootWeightClass | None = None
    effect_status: Literal["root_effect_not_adjudicated"] | None = None
    source_ref: str | None = None
    clash_partners: list[str] | None = None

    @model_validator(mode="after")
    def preserve_distinct_root_observations(self) -> "ClassicalRoot":
        if self.hidden_element_present is False and self.matching_hidden_stems:
            raise ValueError("无同气藏干与存在匹配藏干不能同时成立")
        else:
            pass
        if self.kind == "yin_growth_reference" and (
            self.hidden_element_present is True or self.matching_hidden_stems
        ):
            raise ValueError("阴长生原典参考不能补造成同气藏干根")
        else:
            pass
        return self


class ClassicalRootProfile(PartialOutput):
    method_id: str | None = None
    day_stem: str | None = None
    life_stage_profile: LifeStageProfile | None = None
    roots: list[ClassicalRoot] | None = None
    heavy_root_positions: list[str] | None = None
    light_hidden_root_positions: list[str] | None = None
    yin_growth_reference_positions: list[str] | None = None
    global_strength_status: Literal["not_adjudicated"] | None = None
    source: dict[str, OpenJsonValue] | None = None
    scope: str | None = None


class ClassicalOverview(PartialOutput):
    monthly_structure: dict[str, OpenJsonValue] | None = None
    seasonal_climate: SeasonalClimateReference | None = None
    life_stages: dict[str, OpenJsonValue] | None = None
    root_profile: ClassicalRootProfile | None = None
