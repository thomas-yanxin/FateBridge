"""Typed receipts for source root classes used by the structural model."""

from typing import Literal

from pydantic import Field, model_validator

from fatebridge.core.contracts.output_base import PartialOutput
from fatebridge.core.contracts.output_classical_roots import RootKind, RootWeightClass


class RootQualification(PartialOutput):
    pillar: str | None = None
    branch: str | None = None
    kind: RootKind | None = None
    matching_hidden_stems: list[str] | None = None
    source_weight_class: RootWeightClass | None = None
    qualification_basis: (
        Literal["source_heavy_root", "principal_element_root", "not_anchored_kind"]
        | None
    ) = None
    initial_hidden_mass: float | None = Field(default=None, ge=0)
    remaining_hidden_mass: float | None = Field(default=None, ge=0)
    retention_fraction: float | None = Field(default=None, ge=0, le=1)
    minimum_retention_policy: float | None = Field(default=None, ge=0, le=1)
    qualified_for_structural_rule: bool | None = None
    source_ref: str | None = None
    scope: str | None = None

    @model_validator(mode="after")
    def preserve_actual_hidden_root_requirement(self) -> "RootQualification":
        if self.qualification_basis == "source_heavy_root":
            if self.source_weight_class not in (None, "heavy"):
                raise ValueError("原典重根资格必须保留重根分类")
            else:
                pass
            if self.kind is not None and self.kind not in {
                "lu_root",
                "yang_blade_root",
                "yang_growth_root",
                "prosperity_root",
            }:
                raise ValueError("轻根或无根参考不能冒充原典重根")
            else:
                pass
        else:
            pass
        if self.qualified_for_structural_rule is True:
            if self.matching_hidden_stems == [] or self.initial_hidden_mass == 0:
                raise ValueError("健全根资格不能由无实际藏干的长生参考产生")
            else:
                pass
            if self.qualification_basis == "not_anchored_kind":
                raise ValueError("非锚定根类不能冒充健全根")
            else:
                pass
            if (
                self.initial_hidden_mass is not None
                and self.remaining_hidden_mass is not None
                and self.minimum_retention_policy is not None
                and self.remaining_hidden_mass
                < self.initial_hidden_mass * self.minimum_retention_policy
            ):
                raise ValueError("健全根资格不能绕过已声明的保留门槛")
            else:
                pass
        else:
            pass
        if (
            self.initial_hidden_mass is not None
            and self.initial_hidden_mass > 0
            and self.remaining_hidden_mass is not None
            and self.retention_fraction is not None
            and self.retention_fraction
            != self.remaining_hidden_mass / self.initial_hidden_mass
        ):
            raise ValueError("保留比例必须忠于未舍入的实际根量")
        else:
            pass
        return self
