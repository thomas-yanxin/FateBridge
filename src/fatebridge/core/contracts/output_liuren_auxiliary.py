"""Projection-compatible facts for seven selected 探原 德禄马 rules."""

from typing import Annotated, Literal

from pydantic import Field, StrictBool, field_validator

from fatebridge.core.contracts.output_base import PartialOutput

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
    id: AuxiliaryId | None = None
    name: str | None = None
    category: Literal["day_stem", "day_branch", "month_building"] | None = None
    source_token: str | None = None
    branch: Branch | None = None
    original_pdf_pages: list[int] | None = None
    earth_branch: Branch | None = None
    god: str | None = None
    dun_stem: (
        Literal["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"] | None
    ) = None
    ganzhi: str | None = None
    xun_kong: StrictBool | None = None
    seated_kong: StrictBool | None = None
    day_stem_life_stage: str | None = None
    lesson_indices: list[Annotated[int, Field(strict=True, ge=1, le=4)]] | None = None
    transmission_positions: list[Literal["initial", "middle", "final"]] | None = None
    on_day_stem: StrictBool | None = None
    on_day_branch: StrictBool | None = None


class LiurenAuxiliaryStars(PartialOutput):
    ruleset_id: Literal["tanyuan_auxiliary_stars_v1"] | None = None
    source_title: str | None = None
    source_url: str | None = None
    source_sha256: str | None = None
    original_pdf_pages: list[int] | None = None
    day_ganzhi: str | None = None
    month_building_branch: Branch | None = None
    nominal_month: Annotated[int, Field(strict=True, ge=1, le=12)] | None = None
    month_basis: str | None = None
    stars: list[LiurenAuxiliaryStar] | None = Field(
        default=None, min_length=7, max_length=7
    )
    complete_classical_conformance: Literal[False] | None = None
    scope: str | None = None

    @field_validator("stars")
    @classmethod
    def unique_complete_ids(
        cls, value: list[LiurenAuxiliaryStar] | None
    ) -> list[LiurenAuxiliaryStar] | None:
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
    def no_full_book_claim(cls, value: object) -> Literal[False] | None:
        if value is not None and value is not False:
            raise ValueError("所选七项定位不能声明整书符合")
        return value
