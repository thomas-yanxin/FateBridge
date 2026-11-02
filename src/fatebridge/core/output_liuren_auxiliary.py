"""Projection-compatible facts for seven selected 探原 德禄马 rules."""

from typing import Annotated, Any, List, Literal, Optional

from pydantic import Field, StrictBool, field_validator

from .output_base import PartialOutput

AuxiliaryId = Literal[
    "heaven_de",
    "month_de",
    "day_de",
    "branch_de",
    "day_lu",
    "day_horse",
    "heaven_horse",
]
Branch = Literal["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]


class LiurenAuxiliaryStar(PartialOutput):
    id: Optional[AuxiliaryId] = None
    name: Optional[str] = None
    category: Optional[Literal["day_stem", "day_branch", "month_building"]] = None
    source_token: Optional[str] = None
    branch: Optional[Branch] = None
    original_pdf_pages: Optional[List[int]] = None
    earth_branch: Optional[Branch] = None
    god: Optional[str] = None
    dun_stem: Optional[
        Literal["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]
    ] = None
    ganzhi: Optional[str] = None
    xun_kong: Optional[StrictBool] = None
    seated_kong: Optional[StrictBool] = None
    day_stem_life_stage: Optional[str] = None
    lesson_indices: Optional[List[Annotated[int, Field(strict=True, ge=1, le=4)]]] = (
        None
    )
    transmission_positions: Optional[List[Literal["initial", "middle", "final"]]] = None
    on_day_stem: Optional[StrictBool] = None
    on_day_branch: Optional[StrictBool] = None


class LiurenAuxiliaryStars(PartialOutput):
    ruleset_id: Optional[Literal["tanyuan_auxiliary_stars_v1"]] = None
    source_title: Optional[str] = None
    source_url: Optional[str] = None
    source_sha256: Optional[str] = None
    original_pdf_pages: Optional[List[int]] = None
    day_ganzhi: Optional[str] = None
    month_building_branch: Optional[Branch] = None
    nominal_month: Optional[Annotated[int, Field(strict=True, ge=1, le=12)]] = None
    month_basis: Optional[str] = None
    stars: Optional[List[LiurenAuxiliaryStar]] = Field(
        default=None, min_length=7, max_length=7
    )
    complete_classical_conformance: Optional[Literal[False]] = None
    scope: Optional[str] = None

    @field_validator("stars")
    @classmethod
    def unique_complete_ids(
        cls, value: Optional[List[LiurenAuxiliaryStar]]
    ) -> Optional[List[LiurenAuxiliaryStar]]:
        if value is not None and {star.id for star in value} != {
            "heaven_de",
            "month_de",
            "day_de",
            "branch_de",
            "day_lu",
            "day_horse",
            "heaven_horse",
        }:
            raise ValueError("德禄马需保留七项不同的规则标识")
        return value

    @field_validator("complete_classical_conformance", mode="before")
    @classmethod
    def no_full_book_claim(cls, value: Any) -> Any:
        if value is not None and value is not False:
            raise ValueError("所选七项定位不能声明整书符合")
        return value
