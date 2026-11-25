"""Projection-safe, literal hidden-target relation contracts."""

from typing import Literal

from pydantic import Field, model_validator

from fatebridge.core.contracts.output_base import OpenJsonValue, PartialOutput


class HiddenCarrierTarget(PartialOutput):
    hidden_stem: str | None = None
    hidden_rank: int | None = Field(default=None, ge=1, le=3)
    element: str | None = None
    relation: (
        Literal[
            "same_element",
            "hidden_generates_stem",
            "stem_generates_hidden",
            "hidden_overcomes_stem",
            "stem_overcomes_hidden",
        ]
        | None
    ) = None
    covering_candidate_if_target_desired: bool | None = None
    ten_god: str | None = None

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
    position: Literal["year", "month", "day", "hour"] | None = None
    pillar: str | None = None
    pair_consistency: Literal["literal_nonsexagenary_pair"] | None = None
    targets: list[HiddenCarrierTarget] | None = None


class TemporalHiddenCarrier(PartialOutput):
    node_id: str | None = None
    pillar: str | None = None
    targets: list[HiddenCarrierTarget] | None = None


class HiddenCarrierRelations(PartialOutput):
    method_id: Literal["literal_hidden_target_relations_v1"] | None = None
    pillar: str | None = None
    targets: list[HiddenCarrierTarget] | None = None
    pillars: list[PillarHiddenTargets] | None = None
    effective_force_status: Literal["not_adjudicated"] | None = None
    source: dict[str, OpenJsonValue] | None = None
    scope: str | None = None
