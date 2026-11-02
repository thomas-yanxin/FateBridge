"""Stages have a fixed named convention; they are not numerical strength."""

from typing import Dict, List, Literal, Optional

from .output_base import PartialOutput

LiurenLifeStage = Literal[
    "长生",
    "沐浴",
    "冠带",
    "临官",
    "帝旺",
    "衰",
    "病",
    "死",
    "墓",
    "绝",
    "胎",
    "养",
]


class LiurenLifePlacement(PartialOutput):
    name: Optional[Literal["墓乘长生", "长生乘墓"]] = None
    sky_branch: Optional[str] = None
    earth_branch: Optional[str] = None
    required_earth_branch: Optional[str] = None
    sky_stage: Optional[LiurenLifeStage] = None
    earth_stage: Optional[LiurenLifeStage] = None
    matched: Optional[bool] = None


class LiurenLifeStages(PartialOutput):
    ruleset_id: Optional[Literal["tanyuan_ten_stem_life_stages_v1"]] = None
    source_title: Optional[str] = None
    source_url: Optional[str] = None
    source_sha256: Optional[str] = None
    original_pdf_pages: Optional[List[int]] = None
    day_stem: Optional[str] = None
    direction: Optional[Literal["顺", "逆"]] = None
    changsheng_branch: Optional[str] = None
    linguan_branch: Optional[str] = None
    tomb_branch: Optional[str] = None
    stage_by_branch: Optional[Dict[str, LiurenLifeStage]] = None
    placements: Optional[List[LiurenLifePlacement]] = None
    scope: Optional[str] = None
