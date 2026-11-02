"""Projection-safe contracts that prevent conflating two seasonal criteria."""

from typing import Dict, List, Literal, Optional

from pydantic import model_validator

from fatebridge.core.bureau_season import KNOWN_PHASE_GATES
from fatebridge.core.output_base import PartialOutput
from fatebridge.core.output_classical_force import ForceSource
from fatebridge.utils.data import BRANCH_ELEMENTS

ElementName = Literal["木", "火", "土", "金", "水"]
PhaseName = Literal["旺", "相", "休", "囚", "死"]
GROUPS = {"寅卯辰": "木", "巳午未": "火", "申酉戌": "金", "亥子丑": "水"}


class BureauSeasonObservation(PartialOutput):
    positions: Optional[List[Literal["year", "month", "day", "hour"]]] = None
    target_element: Optional[Literal["木", "火", "金", "水"]] = None
    month_is_member: Optional[bool] = None
    month_in_target_branch_group: Optional[bool] = None
    calculated_target_phase: Optional[PhaseName] = None
    supplied_season_support_flag: Optional[bool] = None
    supplied_relation_status: Optional[str] = None
    criteria_differ: Optional[bool] = None
    classical_transformation: Optional[Literal["not_adjudicated"]] = None

    @model_validator(mode="after")
    def preserve_position_and_criteria(self) -> "BureauSeasonObservation":
        if (
            "supplied_season_support_flag" in self.model_fields_set
            and self.supplied_season_support_flag is None
            and self.criteria_differ is not None
        ):
            raise ValueError("门槛未提供时不能虚构相同或不同")
        if self.positions is not None:
            if len(self.positions) < 3 or len(set(self.positions)) != len(
                self.positions
            ):
                raise ValueError("完整三会须保留至少三个不同实体柱位")
            if self.month_is_member is not None and self.month_is_member != (
                "month" in self.positions
            ):
                raise ValueError("月支是否参与须忠于实际柱位")
        if (
            self.criteria_differ is not None
            and self.supplied_season_support_flag is not None
            and self.month_in_target_branch_group is not None
        ):
            if self.criteria_differ != (
                self.supplied_season_support_flag != self.month_in_target_branch_group
            ):
                raise ValueError("两种季节条件不得混写成同一个布尔值")
        return self


class BureauSeasonReference(PartialOutput):
    method_id: Optional[Literal["month_branch_group_and_supplied_phase_gate_v1"]] = None
    source: Optional[ForceSource] = None
    month_branch: Optional[str] = None
    principal_branch_element: Optional[ElementName] = None
    branch_seasonal_group: Optional[Literal["寅卯辰", "巳午未", "申酉戌", "亥子丑"]] = (
        None
    )
    branch_group_element: Optional[Literal["木", "火", "金", "水"]] = None
    strength_method_id: Optional[str] = None
    calculated_phases: Optional[Dict[ElementName, PhaseName]] = None
    combination_gate_basis: Optional[
        Literal["supplied_phase_equals_wang", "method_not_identified"]
    ] = None
    combination_observations: Optional[List[BureauSeasonObservation]] = None
    source_force_adjudication: Optional[Literal["not_adjudicated"]] = None
    calculation_effect: Optional[Literal["none"]] = None
    scope: Optional[str] = None

    @model_validator(mode="after")
    def preserve_supplied_phase_gate(self) -> "BureauSeasonReference":
        if (
            self.strength_method_id is not None
            and self.combination_gate_basis is not None
        ):
            expected = (
                "supplied_phase_equals_wang"
                if self.strength_method_id in KNOWN_PHASE_GATES
                else "method_not_identified"
            )
            if self.combination_gate_basis != expected:
                raise ValueError("未知旺衰方法不能冒用已核对的相位门槛")
        if self.month_branch is not None:
            if self.month_branch not in BRANCH_ELEMENTS:
                raise ValueError("月支不合法")
            if (
                self.principal_branch_element is not None
                and self.principal_branch_element
                != BRANCH_ELEMENTS[self.month_branch][0].value
            ):
                raise ValueError("月支本气须忠于原月支")
            if (
                self.branch_seasonal_group is not None
                and self.month_branch not in self.branch_seasonal_group
            ):
                raise ValueError("季支归组须包含实际月支")
        if (
            self.branch_seasonal_group is not None
            and self.branch_group_element is not None
            and self.branch_group_element != GROUPS[self.branch_seasonal_group]
        ):
            raise ValueError("土本气不能替换三会季支归组的目标五行")
        for row in self.combination_observations or []:
            if (
                self.branch_group_element is not None
                and row.target_element is not None
                and row.month_in_target_branch_group is not None
            ):
                if row.month_in_target_branch_group != (
                    self.branch_group_element == row.target_element
                ):
                    raise ValueError("实际目标与月支归组不同须保留")
            if (
                self.calculated_phases is not None
                and row.target_element is not None
                and row.calculated_target_phase is not None
            ):
                if (
                    self.calculated_phases.get(row.target_element)
                    != row.calculated_target_phase
                ):
                    raise ValueError("目标季相须引用同次已提供值")
            if (
                self.combination_gate_basis == "supplied_phase_equals_wang"
                and row.calculated_target_phase is not None
                and row.supplied_season_support_flag is not None
            ):
                if row.supplied_season_support_flag != (
                    row.calculated_target_phase == "旺"
                ):
                    raise ValueError("现行门槛须忠于同次旺相判定，不能伪写为季支归组")
        return self
