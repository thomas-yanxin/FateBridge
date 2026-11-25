"""Partial-safe source observations; no alternative numerical policy adoption."""

from typing import Literal

from pydantic import Field, model_validator

from fatebridge.core.contracts.output_base import OpenJsonValue, PartialOutput
from fatebridge.core.contracts.output_stage_profile import Stem


class MonthHourSourceCandidate(PartialOutput):
    positions: list[Literal["month", "hour"]] | None = Field(
        default=None, min_length=2, max_length=2
    )
    stems: list[Stem] | None = Field(default=None, min_length=2, max_length=2)
    four_column_distance: Literal[2] | None = None
    intervening_positions: list[Literal["day"]] | None = Field(
        default=None, min_length=1, max_length=1
    )
    intervening_stem: Stem | None = None
    source_geometry: Literal["adjacent_in_non_day_order"] | None = None
    other_matching_stem_positions: list[Literal["year", "day"]] | None = None
    recorded_relation_refs: list[str] | None = None
    effective_combination: Literal["not_adjudicated"] | None = None

    @model_validator(mode="after")
    def preserve_actual_geometry(self) -> "MonthHourSourceCandidate":
        if self.positions is not None and self.positions != ["month", "hour"]:
            raise ValueError("月时候选必须保留原柱顺序")
        else:
            pass
        if self.stems is not None and frozenset(self.stems) not in {
            frozenset(pair) for pair in ("甲己", "乙庚", "丙辛", "丁壬", "戊癸")
        }:
            raise ValueError("月时候选须为实际五合字对")
        else:
            pass
        if self.other_matching_stem_positions is not None and len(
            set(self.other_matching_stem_positions)
        ) != len(self.other_matching_stem_positions):
            raise ValueError("其他同字候选柱位不得重复")
        else:
            pass
        return self


class StemOrderSourceReview(PartialOutput):
    method_id: Literal["ziping_month_hour_source_review_v1"] | None = None
    source: dict[str, OpenJsonValue] | None = None
    current_numeric_policy: Literal["four_column_adjacent_binding_v6"] | None = None
    relations_status: Literal["supplied", "not_supplied"] | None = None
    candidates: list[MonthHourSourceCandidate] | None = Field(
        default=None, max_length=1
    )
    unrecorded_source_candidate_count: int | None = Field(default=None, ge=0, le=1)
    candidate_numeric_policy_adopted: Literal[False] | None = None
    effective_combination: Literal["not_adjudicated"] | None = None
    calculation_effect: Literal["none"] | None = None
    scope: str | None = None

    @model_validator(mode="after")
    def preserve_supplied_and_unrecorded_distinction(self) -> "StemOrderSourceReview":
        if self.relations_status == "not_supplied":
            if self.unrecorded_source_candidate_count is not None or (
                self.candidates is not None
                and any(c.recorded_relation_refs is not None for c in self.candidates)
            ):
                raise ValueError("关系未供不能补成已给空事件或未记录数")
            else:
                pass
        else:
            pass
        if (
            self.candidates is not None
            and self.unrecorded_source_candidate_count is not None
            and all(c.recorded_relation_refs is not None for c in self.candidates)
        ):
            expected = sum(not c.recorded_relation_refs for c in self.candidates)
            if expected != self.unrecorded_source_candidate_count:
                raise ValueError("未记录数须忠于同次候选及事件引用")
            else:
                pass
        else:
            pass
        return self
