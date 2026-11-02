"""Projection-compatible 年命 facts with explicit missing annual branch."""

from typing import List, Literal, Optional

from .output_base import PartialOutput


class LiurenYearFatePlacement(PartialOutput):
    status: Optional[Literal["calculated", "not_calculated"]] = None
    subject_ganzhi: Optional[str] = None
    earth_branch: Optional[str] = None
    sky_branch: Optional[str] = None
    god: Optional[str] = None
    upper_dun_stem: Optional[str] = None
    upper_ganzhi: Optional[str] = None
    upper_relation: Optional[str] = None
    upper_xun_kong: Optional[bool] = None
    earth_xun_kong: Optional[bool] = None
    reason: Optional[str] = None


class LiurenYearFate(PartialOutput):
    ruleset_id: Optional[Literal["tanyuan_year_fate_v1"]] = None
    source_title: Optional[str] = None
    source_url: Optional[str] = None
    source_sha256: Optional[str] = None
    original_pdf_pages: Optional[List[int]] = None
    birth_year_basis: Optional[str] = None
    placement_basis: Optional[str] = None
    day_ganzhi: Optional[str] = None
    guiren_profile: Optional[str] = None
    natal: Optional[LiurenYearFatePlacement] = None
    annual: Optional[LiurenYearFatePlacement] = None
    scope: Optional[str] = None
