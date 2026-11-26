"""Stages have a fixed named convention; they are not numerical strength."""

from typing import Literal

from fatebridge.core.contracts.output_base import PartialOutput

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
    name: Literal["墓乘长生", "长生乘墓"] | None = None
    sky_branch: str | None = None
    earth_branch: str | None = None
    required_earth_branch: str | None = None
    sky_stage: LiurenLifeStage | None = None
    earth_stage: LiurenLifeStage | None = None
    matched: bool | None = None


class LiurenLifeStages(PartialOutput):
    ruleset_id: Literal["tanyuan_ten_stem_life_stages_v1"] | None = None
    source_title: str | None = None
    source_url: str | None = None
    source_sha256: str | None = None
    original_pdf_pages: list[int] | None = None
    day_stem: str | None = None
    direction: Literal["顺", "逆"] | None = None
    changsheng_branch: str | None = None
    linguan_branch: str | None = None
    tomb_branch: str | None = None
    stage_by_branch: dict[str, LiurenLifeStage] | None = None
    placements: list[LiurenLifePlacement] | None = None
    scope: str | None = None
