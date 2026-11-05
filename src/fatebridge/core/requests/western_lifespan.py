"""Request contracts for western lifespan."""

from __future__ import annotations

from typing import Literal, Optional, Union

from pydantic import Field

from fatebridge.core.requests.birth import AstroBirthRequest
from fatebridge.core.requests.western_policy import WesternEphemerisRequest
from fatebridge.utils.house_systems import TWELVE_HOUSE_SYSTEM_NOTE

ClassicalPlanet = Literal[
    "Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn"
]


class AstroLifespanRequest(AstroBirthRequest, WesternEphemerisRequest):
    """Shared base for western *lifespan* techniques cast from a single natal chart."""

    house_system: Union[int, str] = Field(
        default="P",
        description="House system, any convention: SE letter ('P'=Placidus, "
        "'R'=Regiomontanus, 'W'=whole sign, 'D'=equal_mc), key ('placidus', "
        "'equal_mc'), or integer code 0..8 (3=Placidus, 8=equal_mc)."
        + TWELVE_HOUSE_SYSTEM_NOTE,
    )
    zodiac_type: str = Field(
        default="Tropic", description="Zodiac type, e.g. Tropic or Sidereal"
    )


class AstroHarmonicRequest(AstroLifespanRequest):
    """Request model for the 调波盘 (harmonic chart) tool."""

    harmonic: int = Field(
        default=9,
        ge=1,
        le=360,
        description="Harmonic number H (1-360); natal longitudes are multiplied by H mod 360",
    )
    orb: float = Field(
        default=2.0,
        ge=0,
        le=15,
        description="Conjunction orb in degrees for detecting 同频合相 (harmonic conjunctions)",
    )


class AstroPlanetaryAgesRequest(AstroLifespanRequest):
    """Request model for the 行星年龄 (Ptolemy seven ages) tool."""

    analysis_year: Optional[int] = Field(
        default=None,
        description="Reference year; with month/day, flags the active age band (omit to list all bands)",
    )
    analysis_month: Optional[int] = Field(
        default=None, ge=1, le=12, description="Reference month (1-12)"
    )
    analysis_day: Optional[int] = Field(
        default=None, ge=1, le=31, description="Reference day (1-31)"
    )


class AstroTriplicityRulersRequest(AstroLifespanRequest):
    """Request model for the 三分主星推运 (triplicity rulers) tool."""

    lifespan: float = Field(
        default=75.0,
        gt=0,
        le=200,
        description="Nominal lifespan (years) the stages divide — a dividing convention, not a prediction",
    )
    division: Literal["thirds", "halves"] = Field(
        default="thirds",
        description="Stage split: 'thirds' (three equal stages) or 'halves' (main/secondary halves + participating throughout)",
    )


class AstroLunationPhaseRequest(AstroLifespanRequest):
    """Request model for the 月相推运 (progressed lunation phase) tool."""

    max_age_years: float = Field(
        default=90.0,
        gt=0,
        le=200,
        description="Upper age bound (years) for the phase-ingress timeline",
    )


class AstroDistributionsRequest(AstroLifespanRequest):
    """Request model for the 界推运 / 分配法 (distributions) tool."""

    time_key: Literal["Ptolemy", "Naibod"] = Field(
        default="Ptolemy",
        description="Time key for directing the Ascendant: Ptolemy (1°/yr) or Naibod",
    )
    max_age_years: float = Field(
        default=90.0,
        gt=0,
        le=200,
        description="Upper age bound (years) for the distribution timeline",
    )


class AstroBalbillusRequest(AstroLifespanRequest):
    """Request model for the Balbillus 129年系统 tool."""

    start_planet: ClassicalPlanet = Field(
        default="Sun",
        description="Starting planet for the period chain (Sun/Moon/Mercury/Venus/Mars/Jupiter/Saturn)",
    )
    mode: Literal["nearest", "forward"] = Field(
        default="nearest",
        description="Exaltation-distance mode: 'nearest' (with reduction fit) or 'forward'",
    )
    max_age_years: float = Field(
        default=120.0,
        gt=0,
        le=200,
        description="Upper age bound (years) for the period table",
    )


class AstroKeypointsRequest(AstroLifespanRequest):
    """Request model for the 数字相位推运 (120-year keypoints) tool."""

    release_mode: Literal["soul", "body"] = Field(
        default="soul",
        description="Release point: 'soul' (from the Moon) or 'body' (from the Ascendant)",
    )
    max_age_years: int = Field(
        default=120,
        ge=1,
        le=120,
        description="Upper age bound (years, capped at 120) for the activation timeline",
    )


class AstroYearSystem129Request(AstroLifespanRequest):
    """Request model for the 129年系统 tool."""

    start_planet: ClassicalPlanet = Field(
        default="Sun",
        description="Starting planet for the small-year rotation (Sun/Moon/Mercury/Venus/Mars/Jupiter/Saturn)",
    )
    max_age_years: float = Field(
        default=129.0,
        gt=0,
        le=200,
        description="Upper age bound (years) for the rotation timeline",
    )


class AstroPlanetaryArcRequest(AstroLifespanRequest):
    """Request model for the 行星弧方向 (planetary arc directions) tool."""

    arc_source: Union[ClassicalPlanet, Literal["Ascendant", "Medium_Coeli"]] = Field(
        default="Moon",
        description="Body whose secondary-progressed arc directs the whole chart (default Moon)",
    )
    orb: float = Field(
        default=1.0,
        ge=0,
        le=15,
        description="Aspect orb in degrees for directed-to-natal hits",
    )
    analysis_year: Optional[int] = Field(
        default=None, description="Direction target year (omit for current date)"
    )
    analysis_month: Optional[int] = Field(
        default=None, ge=1, le=12, description="Direction target month (1-12)"
    )
    analysis_day: Optional[int] = Field(
        default=None, ge=1, le=31, description="Direction target day (1-31)"
    )


class AstroPersianDirectedRequest(AstroLifespanRequest):
    """Request model for the 波斯向运 (Persian Directed) tool."""

    max_age_years: float = Field(
        default=90.0,
        gt=0,
        le=200,
        description="Upper age bound (years) for the symbolic 1°/year hit list",
    )


class AstroAgePointRequest(AstroLifespanRequest):
    """Request model for the 年龄推进点 (Age Point / Huber) tool.

    Huber's Age Point is defined on Koch houses, so the tool always casts Koch
    regardless of ``house_system``; the inherited field is accepted but ignored.
    """

    max_age_years: float = Field(
        default=72.0,
        gt=0,
        le=200,
        description="Upper age bound (years); one full Age Point cycle is 72 years",
    )


class AstroVedicProgRequest(AstroLifespanRequest):
    """Request model for the 恒星推运 (Vedic sidereal secondary progression) tool.

    The technique is read sidereally, so the tool always casts Sidereal regardless
    of ``zodiac_type``; the inherited field is accepted but ignored.
    """

    orb: float = Field(
        default=1.5,
        ge=0,
        le=15,
        description="Aspect orb (degrees) for progressed→natal hits",
    )
    analysis_year: Optional[int] = Field(
        default=None, description="Progression target year (omit for current date)"
    )
    analysis_month: Optional[int] = Field(
        default=None, ge=1, le=12, description="Progression target month (1-12)"
    )
    analysis_day: Optional[int] = Field(
        default=None, ge=1, le=31, description="Progression target day (1-31)"
    )


class AstroJaynesProgRequest(AstroLifespanRequest):
    """Request model for the 赤纬推运 (Jayne declination progression) tool."""

    orb: float = Field(
        default=1.0, ge=0, le=5, description="Declination orb (degrees) for parallels"
    )
    analysis_year: Optional[int] = Field(
        default=None, description="Progression target year (omit for current date)"
    )
    analysis_month: Optional[int] = Field(
        default=None, ge=1, le=12, description="Progression target month (1-12)"
    )
    analysis_day: Optional[int] = Field(
        default=None, ge=1, le=31, description="Progression target day (1-31)"
    )
