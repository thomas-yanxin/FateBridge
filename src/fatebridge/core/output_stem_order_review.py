"""Partial-safe source observations; no alternative numerical policy adoption."""

from typing import Any, Dict, List, Literal, Optional

from pydantic import Field, model_validator

from fatebridge.core.output_base import PartialOutput
from fatebridge.core.output_stage_profile import Stem


class MonthHourSourceCandidate(PartialOutput):
    positions: Optional[List[Literal["month", "hour"]]] = Field(
        default=None, min_length=2, max_length=2
    )
    stems: Optional[List[Stem]] = Field(default=None, min_length=2, max_length=2)
    four_column_distance: Optional[Literal[2]] = None
    intervening_positions: Optional[List[Literal["day"]]] = Field(
        default=None, min_length=1, max_length=1
    )
    intervening_stem: Optional[Stem] = None
    source_geometry: Optional[Literal["adjacent_in_non_day_order"]] = None
    other_matching_stem_positions: Optional[List[Literal["year", "day"]]] = None
    recorded_relation_refs: Optional[List[str]] = None
    effective_combination: Optional[Literal["not_adjudicated"]] = None

    @model_validator(mode="after")
    def preserve_actual_geometry(self) -> "MonthHourSourceCandidate":
        if self.positions is not None and self.positions != ["month", "hour"]:
            raise ValueError("月时候选必须保留原柱顺序")
        if self.stems is not None and frozenset(self.stems) not in {
            frozenset(pair) for pair in ("甲己", "乙庚", "丙辛", "丁壬", "戊癸")
        }:
            raise ValueError("月时候选须为实际五合字对")
        if self.other_matching_stem_positions is not None and len(
            set(self.other_matching_stem_positions)
        ) != len(self.other_matching_stem_positions):
            raise ValueError("其他同字候选柱位不得重复")
        return self


class StemOrderSourceReview(PartialOutput):
    method_id: Optional[Literal["ziping_month_hour_source_review_v1"]] = None
    source: Optional[Dict[str, Any]] = None
    current_numeric_policy: Optional[Literal["four_column_adjacent_binding_v6"]] = None
    relations_status: Optional[Literal["supplied", "not_supplied"]] = None
    candidates: Optional[List[MonthHourSourceCandidate]] = Field(
        default=None, max_length=1
    )
    unrecorded_source_candidate_count: Optional[int] = Field(default=None, ge=0, le=1)
    candidate_numeric_policy_adopted: Optional[Literal[False]] = None
    effective_combination: Optional[Literal["not_adjudicated"]] = None
    calculation_effect: Optional[Literal["none"]] = None
    scope: Optional[str] = None

    @model_validator(mode="after")
    def preserve_supplied_and_unrecorded_distinction(self) -> "StemOrderSourceReview":
        if self.relations_status == "not_supplied":
            if self.unrecorded_source_candidate_count is not None or (
                self.candidates is not None
                and any(c.recorded_relation_refs is not None for c in self.candidates)
            ):
                raise ValueError("关系未供不能补成已给空事件或未记录数")
        if (
            self.candidates is not None
            and self.unrecorded_source_candidate_count is not None
            and all(c.recorded_relation_refs is not None for c in self.candidates)
        ):
            expected = sum(not c.recorded_relation_refs for c in self.candidates)
            if expected != self.unrecorded_source_candidate_count:
                raise ValueError("未记录数须忠于同次候选及事件引用")
        return self
