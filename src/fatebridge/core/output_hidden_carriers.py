"""Projection-safe, literal hidden-target relation contracts."""

from typing import Any, Dict, List, Literal, Optional

from pydantic import Field, model_validator

from fatebridge.core.output_base import PartialOutput


class HiddenCarrierTarget(PartialOutput):
    hidden_stem: Optional[str] = None
    hidden_rank: Optional[int] = Field(default=None, ge=1, le=3)
    element: Optional[str] = None
    relation: Optional[
        Literal[
            "same_element",
            "hidden_generates_stem",
            "stem_generates_hidden",
            "hidden_overcomes_stem",
            "stem_overcomes_hidden",
        ]
    ] = None
    covering_candidate_if_target_desired: Optional[bool] = None
    ten_god: Optional[str] = None

    @model_validator(mode="after")
    def preserve_conditional_relation(self) -> "HiddenCarrierTarget":
        if (
            self.relation is not None
            and self.covering_candidate_if_target_desired is not None
            and self.covering_candidate_if_target_desired
            != (self.relation == "stem_overcomes_hidden")
        ):
            raise ValueError("藏干盖头候选须忠于干克该藏干；不是全支或实际喜忌裁定")
        return self


class PillarHiddenTargets(PartialOutput):
    position: Optional[Literal["year", "month", "day", "hour"]] = None
    pillar: Optional[str] = None
    pair_consistency: Optional[Literal["literal_nonsexagenary_pair"]] = None
    targets: Optional[List[HiddenCarrierTarget]] = None


class TemporalHiddenCarrier(PartialOutput):
    node_id: Optional[str] = None
    pillar: Optional[str] = None
    targets: Optional[List[HiddenCarrierTarget]] = None


class HiddenCarrierRelations(PartialOutput):
    method_id: Optional[Literal["literal_hidden_target_relations_v1"]] = None
    pillar: Optional[str] = None
    targets: Optional[List[HiddenCarrierTarget]] = None
    pillars: Optional[List[PillarHiddenTargets]] = None
    effective_force_status: Optional[Literal["not_adjudicated"]] = None
    source: Optional[Dict[str, Any]] = None
    scope: Optional[str] = None
