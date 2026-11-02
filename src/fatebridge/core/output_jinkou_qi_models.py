"""Shared definitions, independent of the domain entry point."""

from typing import List, Literal, Optional

from pydantic import Field, StrictBool, StrictInt, model_validator

from fatebridge.core.output_base import PartialOutput
from fatebridge.core.output_liuren_emptiness import Branch


class JinkouInternalRelation(PartialOutput):
    source_position: Optional[str] = None
    target_position: Optional[str] = None
    source_element: Optional[str] = None
    target_element: Optional[str] = None
    relation: Optional[str] = None


class JinkouMonthBuildingCheck(PartialOutput):
    position: Optional[Literal["贵神", "将神"]] = None
    branch: Optional[str] = None
    month_building_branch: Optional[str] = None
    matched: Optional[StrictBool] = None


class JinkouQiEvidence(PartialOutput):
    ruleset_id: Optional[str] = None
    month_building_branch: Optional[Branch] = None
    month_building_checks: Optional[List[JinkouMonthBuildingCheck]] = None
    month_building_basis: Optional[str] = None
    month_building_scan_url: Optional[str] = None
    month_building_scan_sha256: Optional[str] = None
    month_building_pdf_page: Optional[int] = None
    month_building_scope: Optional[str] = None
    jiangshen_branch: Optional[Branch] = None
    month_offset: Optional[StrictInt] = Field(default=None, ge=0, le=11)
    month_qi_label: Optional[Literal["建旺", "进气相", "月破", "退气"]] = None
    month_qi_status: Optional[
        Literal["matched_excerpt", "not_classified_by_excerpt"]
    ] = None
    day_branch: Optional[Branch] = None
    day_element: Optional[Literal["木", "火", "土", "金", "水"]] = None
    jiangshen_element: Optional[Literal["木", "火", "土", "金", "水"]] = None
    day_generates_general: Optional[StrictBool] = None
    interposition_generations: Optional[List[JinkouInternalRelation]] = None
    source_url: Optional[str] = None
    source_section: Optional[str] = None
    basis: Optional[str] = None
    scope: Optional[str] = None

    @model_validator(mode="after")
    def building_follows_present_anchors(self) -> "JinkouQiEvidence":
        from fatebridge.core.output_jinkou_comparison import compare_present

        from .metaphysics.jinkou_qi import month_building_check, month_building_metadata
        from .output_jinkou_qi import validate_qi_fields

        validate_qi_fields(self.model_dump(exclude_unset=True))
        compare_present(self.model_dump(exclude_unset=True), month_building_metadata())
        positions = []
        for item in self.month_building_checks or []:
            if item.position is not None:
                positions.append(item.position)
            month = item.month_building_branch or self.month_building_branch
            if (
                item.month_building_branch is not None
                and self.month_building_branch is not None
            ):
                compare_present(item.month_building_branch, self.month_building_branch)
            if (
                item.position is not None
                and item.branch is not None
                and month is not None
            ):
                expected = month_building_check(item.position, item.branch, month)
                compare_present(item.model_dump(exclude_unset=True), expected)
        if len(positions) != len(set(positions)):
            raise ValueError("神将建旺不可重复同一位置")
        return self
