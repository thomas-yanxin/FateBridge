"""Shared definitions, independent of the domain entry point."""

from typing import Literal

from pydantic import Field, StrictBool, StrictInt, model_validator

from fatebridge.core.contracts.output_base import PartialOutput
from fatebridge.core.contracts.output_jinkou_comparison import compare_present
from fatebridge.core.contracts.output_jinkou_qi import validate_qi_fields
from fatebridge.core.contracts.output_liuren_emptiness import Branch
from fatebridge.core.metaphysics.jinkou_qi import (
    month_building_check,
    month_building_metadata,
)


class JinkouInternalRelation(PartialOutput):
    source_position: str | None = None
    target_position: str | None = None
    source_element: str | None = None
    target_element: str | None = None
    relation: str | None = None


class JinkouMonthBuildingCheck(PartialOutput):
    position: Literal["贵神", "将神"] | None = None
    branch: str | None = None
    month_building_branch: str | None = None
    matched: StrictBool | None = None


class JinkouQiEvidence(PartialOutput):
    ruleset_id: str | None = None
    month_building_branch: Branch | None = None
    month_building_checks: list[JinkouMonthBuildingCheck] | None = None
    month_building_basis: str | None = None
    month_building_scan_url: str | None = None
    month_building_scan_sha256: str | None = None
    month_building_pdf_page: int | None = None
    month_building_scope: str | None = None
    jiangshen_branch: Branch | None = None
    month_offset: StrictInt | None = Field(default=None, ge=0, le=11)
    month_qi_label: Literal["建旺", "进气相", "月破", "退气"] | None = None
    month_qi_status: Literal["matched_excerpt", "not_classified_by_excerpt"] | None = (
        None
    )
    day_branch: Branch | None = None
    day_element: Literal["木", "火", "土", "金", "水"] | None = None
    jiangshen_element: Literal["木", "火", "土", "金", "水"] | None = None
    day_generates_general: StrictBool | None = None
    interposition_generations: list[JinkouInternalRelation] | None = None
    source_url: str | None = None
    source_section: str | None = None
    basis: str | None = None
    scope: str | None = None

    @model_validator(mode="after")
    def building_follows_present_anchors(self) -> "JinkouQiEvidence":

        validate_qi_fields(self.model_dump(exclude_unset=True))
        compare_present(self.model_dump(exclude_unset=True), month_building_metadata())
        positions = []
        for item in self.month_building_checks or []:
            if item.position is not None:
                positions.append(item.position)
            else:
                pass
            month = item.month_building_branch or self.month_building_branch
            if (
                item.month_building_branch is not None
                and self.month_building_branch is not None
            ):
                compare_present(item.month_building_branch, self.month_building_branch)
            else:
                pass
            if (
                item.position is not None
                and item.branch is not None
                and month is not None
            ):
                expected = month_building_check(item.position, item.branch, month)
                compare_present(item.model_dump(exclude_unset=True), expected)
            else:
                pass
        if len(positions) != len(set(positions)):
            raise ValueError("神将建旺不可重复同一位置")
        else:
            pass
        return self
