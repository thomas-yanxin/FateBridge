"""Projection-safe actual-root and same-column timing contracts."""

from typing import Literal

from pydantic import Field, model_validator

from fatebridge.core.contracts.output_base import PartialOutput


class OwnTimingRoot(PartialOutput):
    stem: str | None = None
    rank: int | None = Field(default=None, ge=1, le=3)
    exact_stem: bool | None = None


class ExternalNatalRoot(PartialOutput):
    position: Literal["year", "month", "day", "hour"] | None = None
    hidden_stem: str | None = None
    exact_stem: bool | None = None


class TimingCarrierSummary(PartialOutput):
    node_id: str | None = None
    pillar: str | None = None
    principal_relation: str | None = None
    own_hidden_root_present: bool | None = None
    external_natal_root_count: int | None = Field(default=None, ge=0, le=4)
    branch_covered_if_desired: bool | None = None
    stem_pressure_if_desired: bool | None = None
    effective_force_status: Literal["not_adjudicated"] | None = None


class TimingCarrier(PartialOutput):
    node_id: str | None = None
    pillar: str | None = None
    stem_element: str | None = None
    branch_principal_element: str | None = None
    principal_relation: (
        Literal[
            "same_element",
            "branch_generates_stem",
            "stem_generates_branch",
            "branch_overcomes_stem",
            "stem_overcomes_branch",
        ]
        | None
    ) = None
    own_hidden_roots: list[OwnTimingRoot] | None = None
    own_hidden_root_present: bool | None = None
    external_natal_roots: list[ExternalNatalRoot] | None = None
    branch_covered_if_desired: bool | None = None
    stem_pressure_if_desired: bool | None = None
    effective_force_status: Literal["not_adjudicated"] | None = None
    source_ref: str | None = None

    @model_validator(mode="after")
    def actual_roots_and_role_conditions(self) -> "TimingCarrier":
        if (
            self.own_hidden_roots is not None
            and self.own_hidden_root_present is not None
            and bool(self.own_hidden_roots) != self.own_hidden_root_present
        ):
            raise ValueError("本柱实根状态必须忠于本柱藏干，不能拿原局外援或长生名替代")
        else:
            pass
        if self.principal_relation is not None:
            if (
                self.branch_covered_if_desired is not None
                and self.branch_covered_if_desired
                != (self.principal_relation == "stem_overcomes_branch")
            ):
                raise ValueError("喜支时的盖头条件必须忠于干克支本气")
            else:
                pass
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
            else:
                pass
        else:
            pass
        return self
