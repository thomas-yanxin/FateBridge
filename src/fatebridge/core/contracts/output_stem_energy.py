"""Projection-safe contract for the actual, unrounded stem-energy ledger."""

from math import isclose
from typing import Literal

from pydantic import Field, model_validator

from fatebridge.core.contracts.output_base import PartialOutput
from fatebridge.core.contracts.output_stem_order_review import StemOrderSourceReview
from fatebridge.utils.data import STEM_ELEMENTS


class StemEnergyRow(PartialOutput):
    pillar: Literal["year", "month", "hour"] | None = None
    physical_stem: str | None = None
    physical_element: Literal["木", "火", "土", "金", "水"] | None = None
    effective_element: Literal["木", "火", "土", "金", "水"] | None = None
    initial_budget: float | None = Field(default=None, ge=1, le=1)
    available_budget: float | None = Field(default=None, ge=0, le=1)
    binding_multiplier: float | None = Field(default=None, ge=0, le=1)
    activation_root_mass: float | None = Field(default=None, ge=0)
    activation: float | None = Field(default=None, ge=0, le=1)
    seasonal_factor: float | None = Field(default=None, ge=0)
    energy: float | None = Field(default=None, ge=0)
    quantity_kind: Literal["non_day_stem_budget_weighted_energy"] | None = None

    @model_validator(mode="after")
    def preserve_physical_identity_and_equation(self) -> "StemEnergyRow":
        if self.physical_stem is not None:
            if self.physical_stem not in STEM_ELEMENTS:
                raise ValueError("天干原字不合法")
            else:
                pass
            if (
                self.physical_element is not None
                and self.physical_element != STEM_ELEMENTS[self.physical_stem][0].value
            ):
                raise ValueError("原字五行必须忠于原柱")
            else:
                pass
        else:
            pass
        if (
            self.available_budget is not None
            and self.binding_multiplier is not None
            and self.available_budget != self.binding_multiplier
        ):
            raise ValueError("可用天干预算必须忠于合绊乘数")
        else:
            pass
        if all(
            v is not None
            for v in (
                self.available_budget,
                self.activation,
                self.seasonal_factor,
                self.energy,
            )
        ):
            assert (
                self.available_budget is not None
                and self.activation is not None
                and self.seasonal_factor is not None
                and self.energy is not None
            )
            if not isclose(
                self.energy,
                self.available_budget * self.activation * self.seasonal_factor,
                rel_tol=1e-12,
                abs_tol=1e-12,
            ):
                raise ValueError("天干计力必须使用未舍入的预算、激活与季相")
            else:
                pass
        else:
            pass
        return self


class StemEnergyAccounting(PartialOutput):
    method_id: Literal["unrounded_non_day_stem_budget_v1"] | None = None
    arithmetic_policy: Literal["round_only_for_display"] | None = None
    conversion_policy: Literal["not_applied"] | None = None
    ledger: list[StemEnergyRow] | None = None
    source_order_review: StemOrderSourceReview | None = None
    quantity_kind: Literal["non_day_stem_budget_weighted_energy"] | None = None
    scope: str | None = None

    @model_validator(mode="after")
    def no_duplicate_or_unadopted_transformation(self) -> "StemEnergyAccounting":
        if self.ledger is not None:
            positions = [r.pillar for r in self.ledger if r.pillar is not None]
            if len(positions) != len(set(positions)):
                raise ValueError("每个原柱天干只能计一次")
            else:
                pass
            for row in self.ledger:
                if (
                    self.conversion_policy is not None
                    and row.physical_element is not None
                    and row.effective_element is not None
                    and row.physical_element != row.effective_element
                ):
                    raise ValueError("未启用成化政策不能宣称已转换作用元素")
                else:
                    pass
        else:
            pass
        return self
