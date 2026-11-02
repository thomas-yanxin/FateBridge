"""Projection-safe actual-root and same-column timing contracts."""

from typing import List, Literal, Optional

from pydantic import Field, model_validator

from fatebridge.core.output_base import PartialOutput


class OwnTimingRoot(PartialOutput):
    stem: Optional[str] = None
    rank: Optional[int] = Field(default=None, ge=1, le=3)
    exact_stem: Optional[bool] = None


class ExternalNatalRoot(PartialOutput):
    position: Optional[Literal["year", "month", "day", "hour"]] = None
    hidden_stem: Optional[str] = None
    exact_stem: Optional[bool] = None


class TimingCarrierSummary(PartialOutput):
    node_id: Optional[str] = None
    pillar: Optional[str] = None
    principal_relation: Optional[str] = None
    own_hidden_root_present: Optional[bool] = None
    external_natal_root_count: Optional[int] = Field(default=None, ge=0, le=4)
    branch_covered_if_desired: Optional[bool] = None
    stem_pressure_if_desired: Optional[bool] = None
    effective_force_status: Optional[Literal["not_adjudicated"]] = None


class TimingCarrier(PartialOutput):
    node_id: Optional[str] = None
    pillar: Optional[str] = None
    stem_element: Optional[str] = None
    branch_principal_element: Optional[str] = None
    principal_relation: Optional[
        Literal[
            "same_element",
            "branch_generates_stem",
            "stem_generates_branch",
            "branch_overcomes_stem",
            "stem_overcomes_branch",
        ]
    ] = None
    own_hidden_roots: Optional[List[OwnTimingRoot]] = None
    own_hidden_root_present: Optional[bool] = None
    external_natal_roots: Optional[List[ExternalNatalRoot]] = None
    branch_covered_if_desired: Optional[bool] = None
    stem_pressure_if_desired: Optional[bool] = None
    effective_force_status: Optional[Literal["not_adjudicated"]] = None
    source_ref: Optional[str] = None

    @model_validator(mode="after")
    def actual_roots_and_role_conditions(self) -> "TimingCarrier":
        if (
            self.own_hidden_roots is not None
            and self.own_hidden_root_present is not None
            and bool(self.own_hidden_roots) != self.own_hidden_root_present
        ):
            raise ValueError("本柱实根状态必须忠于本柱藏干，不能拿原局外援或长生名替代")
        if self.principal_relation is not None:
            if (
                self.branch_covered_if_desired is not None
                and self.branch_covered_if_desired
                != (self.principal_relation == "stem_overcomes_branch")
            ):
                raise ValueError("喜支时的盖头条件必须忠于干克支本气")
            if (
                self.stem_pressure_if_desired is not None
                and self.stem_pressure_if_desired
                != (
                    self.principal_relation
                    not in {"same_element", "branch_generates_stem"}
                )
            ):
                raise ValueError(
                    "喜干时的承载压力须与主气生克一致，不能冒充完整截脚裁决"
                )
        return self
