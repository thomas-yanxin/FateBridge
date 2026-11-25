"""Actual surviving hidden-stem budgets, not classical force adjudications."""

from typing import Literal

from pydantic import Field, model_validator

from fatebridge.core.contracts.output_base import PartialOutput


class HiddenStemLedgerEntry(PartialOutput):
    pillar: str | None = None
    branch: str | None = None
    stem: str | None = None
    element: str | None = None
    initial_mass: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    remaining_mass: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    retention_fraction: float | None = Field(
        default=None, ge=0, le=1, allow_inf_nan=False
    )
    combined_relation_loss_factor: float | None = Field(default=None, ge=0, le=1)
    engineering_energy: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    quantity_kind: Literal["post_interaction_hidden_stem_budget"] | None = None

    @model_validator(mode="after")
    def preserve_the_actual_surviving_budget(self) -> "HiddenStemLedgerEntry":
        if self.initial_mass is not None and self.remaining_mass is not None:
            if self.remaining_mass > self.initial_mass:
                raise ValueError("真实藏干剩余量不能借合成贡献超过原预算")
            else:
                pass
            if self.initial_mass == 0 and self.retention_fraction is not None:
                raise ValueError("原预算为零时不能伪造有定义的保留比例")
            else:
                pass
            if (
                self.combined_relation_loss_factor is not None
                and self.remaining_mass
                > self.initial_mass * self.combined_relation_loss_factor
            ):
                raise ValueError("真实根量不能撤销已经记录的关系减损")
            else:
                pass
            if (
                self.initial_mass > 0
                and self.retention_fraction is not None
                and self.retention_fraction != self.remaining_mass / self.initial_mass
            ):
                raise ValueError("真实藏干保留比例必须忠于未舍入根量")
            else:
                pass
        else:
            pass
        if self.remaining_mass == 0 and self.engineering_energy not in (None, 0):
            raise ValueError("剩余量为零的真实藏干不能生成正能量")
        else:
            pass
        return self
