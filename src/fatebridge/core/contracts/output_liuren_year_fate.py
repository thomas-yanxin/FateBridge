"""Projection-compatible 年命 facts with explicit missing annual branch."""

from typing import Literal

from fatebridge.core.contracts.output_base import PartialOutput


class LiurenYearFatePlacement(PartialOutput):
    status: Literal["calculated", "not_calculated"] | None = None
    subject_ganzhi: str | None = None
    earth_branch: str | None = None
    sky_branch: str | None = None
    god: str | None = None
    upper_dun_stem: str | None = None
    upper_ganzhi: str | None = None
    upper_relation: str | None = None
    upper_xun_kong: bool | None = None
    earth_xun_kong: bool | None = None
    reason: str | None = None


class LiurenYearFate(PartialOutput):
    ruleset_id: Literal["tanyuan_year_fate_v1"] | None = None
    source_title: str | None = None
    source_url: str | None = None
    source_sha256: str | None = None
    original_pdf_pages: list[int] | None = None
    birth_year_basis: str | None = None
    placement_basis: str | None = None
    day_ganzhi: str | None = None
    guiren_profile: str | None = None
    natal: LiurenYearFatePlacement | None = None
    annual: LiurenYearFatePlacement | None = None
    scope: str | None = None
