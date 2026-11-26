"""Partial-safe provenance for the actual fixed twelve-stage lookup."""

from typing import Literal

from pydantic import Field, model_validator

from fatebridge.core.contracts.output_base import OpenJsonValue, PartialOutput

Branch = Literal["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]
Stem = Literal["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]


class StageAnchor(PartialOutput):
    growth_branch: Branch | None = None
    direction: Literal[-1, 1] | None = None


class LifeStageProfile(PartialOutput):
    profile_id: Literal["ten_stem_yang_forward_yin_reverse_fire_earth_v1"] | None = None
    branch_cycle: list[Branch] | None = Field(
        default=None, min_length=12, max_length=12
    )
    stage_cycle: list[str] | None = Field(default=None, min_length=12, max_length=12)
    growth_starts: dict[Stem, StageAnchor] | None = None
    soil_convention: str | None = None
    source_basis: (
        Literal["implementation_lookup_with_selected_text_crosscheck"] | None
    ) = None
    sources: list[dict[str, OpenJsonValue]] | None = None
    independent_expert_review: Literal["not_completed"] | None = None
    calculation_effect: Literal["none_existing_values_only"] | None = None
    scope: str | None = None

    @model_validator(mode="after")
    def preserve_lookup_structure(self) -> "LifeStageProfile":
        if self.branch_cycle is not None and len(set(self.branch_cycle)) != 12:
            raise ValueError("十二支查表顺序不能丢失或重复地支")
        if self.stage_cycle is not None and len(set(self.stage_cycle)) != 12:
            raise ValueError("十二阶段查表顺序不能丢失或重复阶段")
        return self
