"""Projection-safe checks on a same-calculation clash decision trace."""

from math import isclose
from typing import Any, Dict, List, Literal, Optional

from pydantic import Field, model_validator

from fatebridge.core.output_base import PartialOutput
from fatebridge.utils.data import (
    BRANCH_CONFLICTS,
    BRANCH_ELEMENTS,
    BRANCH_HIDDEN_STEMS,
    STEM_ELEMENTS,
)

Position = Literal["year", "month", "day", "hour"]
ORDER = ("year", "month", "day", "hour")


class ClashContributor(PartialOutput):
    pillar: Optional[Position] = None
    branch: Optional[
        Literal["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]
    ] = None
    stem: Optional[
        Literal["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]
    ] = None
    initial_budget: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)

    @model_validator(mode="after")
    def actual_hidden_stem(self) -> "ClashContributor":
        if self.branch is not None and self.stem is not None:
            if self.stem not in BRANCH_HIDDEN_STEMS.get(self.branch, ()):
                raise ValueError("Clash contributor must be an actual hidden stem")
        return self


class ClashPower(PartialOutput):
    element: Optional[Literal["木", "火", "土", "金", "水"]] = None
    raw_budget: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    contributors: Optional[List[ClashContributor]] = None

    @model_validator(mode="after")
    def same_budget(self) -> "ClashPower":
        if self.contributors is not None:
            keys = [(r.pillar, r.stem) for r in self.contributors]
            if all(None not in k for k in keys) and len(keys) != len(set(keys)):
                raise ValueError("A physical hidden stem cannot contribute twice")
            if self.element is not None:
                for row in self.contributors:
                    if (
                        row.stem is not None
                        and STEM_ELEMENTS[row.stem][0].value != self.element
                    ):
                        raise ValueError(
                            "Contributor element does not match comparison"
                        )
            budgets = [r.initial_budget for r in self.contributors]
            if self.raw_budget is not None and all(v is not None for v in budgets):
                if not isclose(
                    self.raw_budget,
                    sum(v for v in budgets if v is not None),
                    rel_tol=1e-12,
                    abs_tol=1e-12,
                ):
                    raise ValueError("Power must equal its supplied initial budgets")
        return self


class ClashDecision(PartialOutput):
    positions: Optional[List[Position]] = None
    branches: Optional[List[str]] = None
    distance: Optional[int] = Field(default=None, ge=1, le=3)
    event_status: Optional[
        Literal[
            "active", "resolved_by_combination", "resolved_by_ordered_generation_path"
        ]
    ] = None
    calculation_branch: Optional[
        Literal[
            "initial_hidden_budget",
            "combination_resolution",
            "storage_movement",
            "ordered_generation_path_resolution",
        ]
    ] = None
    powers: Optional[List[ClashPower]] = None
    applied_root_retention: Optional[Dict[Position, float]] = None
    source_ref: Optional[str] = None
    intermediary_positions: Optional[List[Position]] = None

    @model_validator(mode="after")
    def literal_pair(self) -> "ClashDecision":
        if self.positions is not None:
            if len(self.positions) != 2 or self.positions[0] == self.positions[1]:
                raise ValueError("A clash needs two different physical positions")
            if self.distance is not None and self.distance != abs(
                ORDER.index(self.positions[0]) - ORDER.index(self.positions[1])
            ):
                raise ValueError("Clash distance must match its positions")
        if self.branches is not None:
            if (
                len(self.branches) != 2
                or BRANCH_CONFLICTS.get(self.branches[0]) != self.branches[1]
            ):
                raise ValueError("Branches must be an actual clash pair")
        if self.powers is not None and len(self.powers) != 2:
            raise ValueError("A power comparison has exactly two sides")
        if self.powers is not None and self.branches is not None:
            for power, branch in zip(self.powers, self.branches):
                if (
                    power.element is not None
                    and power.element != BRANCH_ELEMENTS[branch][0].value
                ):
                    raise ValueError("Power sides must follow the actual branch order")
        if (
            self.calculation_branch
            in {
                "combination_resolution",
                "storage_movement",
                "ordered_generation_path_resolution",
            }
            and self.powers is not None
        ):
            raise ValueError("This calculation branch did not compare raw powers")
        if self.calculation_branch is not None and self.event_status is not None:
            expected_status = {
                "combination_resolution": "resolved_by_combination",
                "ordered_generation_path_resolution": "resolved_by_ordered_generation_path",
                "initial_hidden_budget": "active",
                "storage_movement": "active",
            }[self.calculation_branch]
            if self.event_status != expected_status:
                raise ValueError(
                    "Calculation branch must match the supplied event status"
                )
        if self.calculation_branch == "ordered_generation_path_resolution":
            if self.applied_root_retention is not None:
                raise ValueError("通关免冲分支不能同时施加根损系数")
            if self.positions is not None and self.intermediary_positions is not None:
                left, right = sorted(ORDER.index(p) for p in self.positions)
                if (
                    not self.intermediary_positions
                    or self.intermediary_positions != list(ORDER[left + 1 : right])
                ):
                    raise ValueError("通关中介必须为冲支之间实际有序柱位")
        if self.applied_root_retention is not None:
            if any(not 0 <= v <= 1 for v in self.applied_root_retention.values()):
                raise ValueError("Retention must be a finite fraction")
            if self.positions is not None and set(self.applied_root_retention) != set(
                self.positions
            ):
                raise ValueError("Retention must refer to the same two positions")
        return self


class ClashComparison(PartialOutput):
    method_id: Optional[Literal["initial_hidden_budget_clash_trace_v1"]] = None
    resource_stage: Optional[Literal["before_interactions"]] = None
    included_factors: Optional[List[str]] = None
    not_included_factors: Optional[List[str]] = None
    events: Optional[List[ClashDecision]] = None
    sources: Optional[List[Dict[str, Any]]] = None
    classical_effective_force: Optional[Literal["not_adjudicated"]] = None
    scope: Optional[str] = None
