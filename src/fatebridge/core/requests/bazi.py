"""Request contracts for bazi."""

from __future__ import annotations

from typing import List, Optional

from pydantic import Field

from fatebridge.core.metaphysics.common import SEXAGENARY_CYCLE
from fatebridge.core.requests.birth import FateBridgeRequest

PILLAR_PATTERN = "^(?:" + "|".join(SEXAGENARY_CYCLE) + ")$"


class BaziDimensionRequest(FateBridgeRequest):
    """Shared base for BaZi single-dimension analyses.

    大运/流年默认由命盘 + 分析日期内部推算（analysis_* 缺省为今天），用户无需自己
    知道大运；dayun_pillar / liunian_pillar 为可选覆盖。
    """

    analysis_year: Optional[int] = Field(
        default=None, description="Analysis year (defaults to current year)"
    )
    analysis_month: Optional[int] = Field(
        default=None, ge=1, le=12, description="Analysis month (1-12)"
    )
    analysis_day: Optional[int] = Field(
        default=None, ge=1, le=31, description="Analysis day (1-31)"
    )
    dayun_pillar: Optional[str] = Field(
        default=None,
        min_length=2,
        max_length=2,
        pattern=PILLAR_PATTERN,
        description="Optional override: exactly one valid sexagenary pillar, e.g. '甲子'",
    )
    liunian_pillar: Optional[str] = Field(
        default=None,
        min_length=2,
        max_length=2,
        pattern=PILLAR_PATTERN,
        description="Optional override: exactly one valid sexagenary pillar, e.g. '丙寅'",
    )


class BaziBirthRequest(FateBridgeRequest):
    """Request model for standalone BaZi birth output."""

    analysis_year: Optional[int] = Field(default=None, description="Analysis year")
    analysis_month: Optional[int] = Field(
        default=None, ge=1, le=12, description="Analysis month (1-12)"
    )
    analysis_day: Optional[int] = Field(
        default=None, ge=1, le=31, description="Analysis day (1-31)"
    )
    selected_sections: List[str] = Field(
        default_factory=list,
        description="Optional snapshot section titles for filtered export payload",
    )


class BaziMarriageRequest(BaziDimensionRequest):
    """Request model for BaZi marriage analysis."""


class BaziCareerRequest(BaziDimensionRequest):
    """Request model for BaZi career analysis."""


class BaziWealthRequest(BaziDimensionRequest):
    """Request model for BaZi wealth analysis."""


class BaziHealthRequest(BaziDimensionRequest):
    """Request model for BaZi health analysis."""


class BaziChildrenRequest(BaziDimensionRequest):
    """Request model for BaZi children analysis."""


class BaziEducationRequest(BaziDimensionRequest):
    """Request model for BaZi education analysis."""


class BaziPersonalityRequest(BaziDimensionRequest):
    """Request model for BaZi personality analysis."""


class BaziRelativesRequest(BaziDimensionRequest):
    """Request model for BaZi relatives analysis."""


class BaziRomanceRequest(BaziDimensionRequest):
    """Request model for BaZi romance / peach-blossom analysis."""
