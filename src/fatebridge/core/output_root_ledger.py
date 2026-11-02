"""Actual surviving hidden-stem budgets, not classical force adjudications."""

from typing import Literal, Optional

from pydantic import Field, model_validator

from fatebridge.core.output_base import PartialOutput


class HiddenStemLedgerEntry(PartialOutput):
    pillar: Optional[str] = None
    branch: Optional[str] = None
    stem: Optional[str] = None
    element: Optional[str] = None
    initial_mass: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    remaining_mass: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    retention_fraction: Optional[float] = Field(
        default=None, ge=0, le=1, allow_inf_nan=False
    )
    combined_relation_loss_factor: Optional[float] = Field(default=None, ge=0, le=1)
    engineering_energy: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    quantity_kind: Optional[Literal["post_interaction_hidden_stem_budget"]] = None

    @model_validator(mode="after")
    def preserve_the_actual_surviving_budget(self) -> "HiddenStemLedgerEntry":
        if self.initial_mass is not None and self.remaining_mass is not None:
            if self.remaining_mass > self.initial_mass:
                raise ValueError("真实藏干剩余量不能借合成贡献超过原预算")
            if self.initial_mass == 0 and self.retention_fraction is not None:
                raise ValueError("原预算为零时不能伪造有定义的保留比例")
            if (
                self.combined_relation_loss_factor is not None
                and self.remaining_mass
                > self.initial_mass * self.combined_relation_loss_factor
            ):
                raise ValueError("真实根量不能撤销已经记录的关系减损")
            if (
                self.initial_mass > 0
                and self.retention_fraction is not None
                and self.retention_fraction != self.remaining_mass / self.initial_mass
            ):
                raise ValueError("真实藏干保留比例必须忠于未舍入根量")
        if self.remaining_mass == 0 and self.engineering_energy not in (None, 0):
            raise ValueError("剩余量为零的真实藏干不能生成正能量")
        return self
