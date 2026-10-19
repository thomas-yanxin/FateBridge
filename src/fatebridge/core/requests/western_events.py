"""Request contracts for western events."""

from __future__ import annotations

from typing import Literal, Optional, Union

from pydantic import Field

from fatebridge.core.requests.base import _DeferredModel
from fatebridge.core.requests.western_lifespan import AstroLifespanRequest


class AstroMundaneRequest(_DeferredModel):
    """Request model for the 世俗入宫盘 (mundane ingress) tool — cast at a solar ingress, no birth data."""

    name: Optional[str] = Field(default=None, description="Optional chart name")
    year: int = Field(description="Civil year of the ingress, e.g. 2026")
    ingress_term: str = Field(
        default="春分",
        description="Cardinal ingress: 春分 (spring equinox) / 夏至 / 秋分 / 冬至",
    )
    longitude: float = Field(
        ge=-180,
        le=180,
        description="Observation longitude (e.g. capital / place of interest)",
    )
    latitude: float = Field(ge=-90, le=90, description="Observation latitude")
    timezone_name: str = Field(
        default="+08:00", description="Observation timezone (IANA name or UTC offset)"
    )
    house_system: Union[int, str] = Field(
        default="P",
        description="House system, any convention: SE letter ('P'=Placidus, "
        "'R'=Regiomontanus, 'W'=whole sign, 'D'=equal_mc), key ('placidus', "
        "'equal_mc'), or integer code 0..8 (3=Placidus, 8=equal_mc).",
    )
    zodiac_type: str = Field(
        default="Tropic", description="Zodiac type, e.g. Tropic or Sidereal"
    )


class AstroExtraReturnsRequest(AstroLifespanRequest):
    """Request model for the 多重回归 (Saturn/Jupiter/node returns) tool."""

    analysis_year: Optional[int] = Field(
        default=None,
        description="Reference year for the returns (omit for current date)",
    )
    analysis_month: Optional[int] = Field(
        default=None, ge=1, le=12, description="Reference month (1-12)"
    )
    analysis_day: Optional[int] = Field(
        default=None, ge=1, le=31, description="Reference day (1-31)"
    )


class AstroHoraryRequest(_DeferredModel):
    """Request model for the 卜卦 (horary) tool — chart cast at the question moment."""

    name: Optional[str] = Field(default=None, description="Optional chart name")
    question_year: int = Field(description="Year the question was asked")
    question_month: int = Field(
        ge=1, le=12, description="Month the question was asked (1-12)"
    )
    question_day: int = Field(
        ge=1, le=31, description="Day the question was asked (1-31)"
    )
    question_hour: int = Field(
        ge=0, le=23, description="Hour the question was asked (0-23)"
    )
    question_minute: int = Field(
        default=0, ge=0, le=59, description="Minute the question was asked"
    )
    timezone_name: str = Field(
        default="+08:00", description="Question timezone (IANA name or UTC offset)"
    )
    longitude: float = Field(
        ge=-180, le=180, description="Longitude where the question was asked"
    )
    latitude: float = Field(
        ge=-90, le=90, description="Latitude where the question was asked"
    )
    category: Literal[
        "general",
        "wealth",
        "family",
        "property",
        "marriage",
        "lawsuit",
        "theft",
        "travel",
        "career",
        "hope",
        "enemy",
    ] = Field(
        default="general",
        description=(
            "Question topic, selecting the quesited house: general/wealth/family/"
            "property/marriage/lawsuit/theft/travel/career/hope/enemy; "
            "生死、疾病与生育临床判断不开放"
        ),
    )
    house_system: Union[int, str] = Field(
        default="R",
        description="House system, any convention (SE letter / key / integer "
        "code 0..8); Regiomontanus (R, code 2) is traditional for horary.",
    )
    zodiac_type: str = Field(
        default="Tropic", description="Zodiac type, e.g. Tropic or Sidereal"
    )


class AstroElectionRequest(_DeferredModel):
    """Request model for the 择日 (electional) tool — chart cast at the candidate moment."""

    name: Optional[str] = Field(default=None, description="Optional chart name")
    candidate_year: int = Field(
        description="Year of the candidate moment being evaluated"
    )
    candidate_month: int = Field(
        ge=1, le=12, description="Month of the candidate moment (1-12)"
    )
    candidate_day: int = Field(
        ge=1, le=31, description="Day of the candidate moment (1-31)"
    )
    candidate_hour: int = Field(
        ge=0, le=23, description="Hour of the candidate moment (0-23)"
    )
    candidate_minute: int = Field(
        default=0, ge=0, le=59, description="Minute of the candidate moment"
    )
    timezone_name: str = Field(
        default="+08:00",
        description="Candidate-moment timezone (IANA name or UTC offset)",
    )
    longitude: float = Field(
        ge=-180, le=180, description="Longitude where the act will take place"
    )
    latitude: float = Field(
        ge=-90, le=90, description="Latitude where the act will take place"
    )
    topic_id: Literal[
        "marriage",
        "business",
        "move_in",
        "buy_property",
        "trade",
        "buy_car",
        "contract",
        "travel",
        "job_hunt",
        "general",
    ] = Field(
        default="marriage",
        description=(
            "Undertaking type, selecting the rule pack: marriage/business/move_in/"
            "buy_property/trade/buy_car/contract/travel/job_hunt/general; 不提供医疗择时"
        ),
    )
    house_system: Union[int, str] = Field(
        default="R",
        description="House system, any convention (SE letter / key / integer "
        "code 0..8); Regiomontanus (R, code 2) is traditional for elections.",
    )
    zodiac_type: str = Field(
        default="Tropic", description="Zodiac type, e.g. Tropic or Sidereal"
    )
