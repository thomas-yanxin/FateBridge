"""Request contracts for western timing."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from fatebridge.core.requests.base import (
    AstroHouseValidatorMixin,
    OptionalAnalysisClockFields,
    WesternChartSystemFields,
)
from fatebridge.core.requests.birth import AstroBirthRequest

WesternTimingTechnique = Literal[
    "firdaria",
    "profection",
    "solar_return",
    "lunar_return",
    "transit",
    "given_year",
    "secondary_progression",
    "solar_arc",
    "primary_directions",
    "primary_direction_chart",
    "decennials",
    "zodiacal_releasing",
]


class WesternTimingBaseRequest(
    AstroHouseValidatorMixin,
    OptionalAnalysisClockFields,
    WesternChartSystemFields,
    AstroBirthRequest,
):
    """Shared base request model for western predictive timing techniques."""

    high_latitude_fallback: Literal["error", "porphyry", "whole_sign"] = Field(
        default="error",
        description="Fallback when quadrant houses fail at high latitudes: error (default), porphyry, or whole_sign.",
    )


class WesternReturnTimingRequest(WesternTimingBaseRequest):
    """Request model for solar and lunar return timing techniques."""

    return_longitude: float | None = Field(
        default=None, ge=-180, le=180, description="Return chart longitude"
    )
    return_latitude: float | None = Field(
        default=None, ge=-90, le=90, description="Return chart latitude"
    )
    return_timezone: str | None = Field(
        default=None, description="Return chart timezone (IANA name or UTC offset)"
    )


class WesternFirdariaRequest(WesternTimingBaseRequest):
    """Request model for Firdaria planetary period timing."""

    firdaria_night_order: Literal["nodes_at_end", "nodes_after_mars"] = Field(
        default="nodes_at_end",
        description=(
            "Firdaria night order: nodes_at_end (existing default, after Mercury) "
            "or nodes_after_mars (Bonatti-labelled variant). Day order is unchanged."
        ),
    )
    firdaria_year_basis: Literal["fixed_365_2425", "calendar_anniversary"] = Field(
        default="fixed_365_2425",
        description=(
            "Firdaria year basis: fixed_365_2425 (fixed 86400-second days on UTC elapsed time) "
            "or calendar_anniversary (original-birth anniversaries, Feb 29 clamps "
            "to Feb 28 then restores; UTC elapsed subperiods). Calendar mode rejects "
            "ambiguous/nonexistent birth, analysis and generated anniversary clocks."
        ),
    )


class WesternPrimaryDirectionsBaseRequest(WesternTimingBaseRequest):
    """Shared base request model for primary directions and primary directions chart."""

    pd_method: Literal[
        "placidus",
        "regiomontanus",
        "campanus",
        "alcabitius",
        "equatorial",
        "astroapp_alchabitius",
        "fatebridge_mundane_semiarc",
    ] = Field(
        default="placidus",
        description=(
            "Primary direction method: placidus (default), regiomontanus, campanus, "
            "alcabitius, or equatorial (oblique ascension for Asc, RAMC for MC)."
        ),
    )
    pd_time_key: Literal["Ptolemy", "Naibod", "Cardan", "Solar_Arc", "Van_Dam"] = Field(
        default="Ptolemy",
        description="Primary direction time key: Ptolemy, Naibod, Cardan, Solar_Arc, or Van_Dam.",
    )
    pd_direction_mode: Literal["zodiacal", "mundane"] = Field(
        default="zodiacal",
        description="Primary direction mode: 'zodiacal' (ecliptic aspect points) or 'mundane' (in mundo).",
    )
    pd_type: int = Field(
        default=0,
        ge=0,
        le=1,
        description="Primary direction mode: 0 for direct, 1 for converse",
    )
    pd_aspects: list[int] = Field(
        default_factory=lambda: [0, 60, 90, 120, 180],
        description="Primary direction aspects in degrees",
    )
    pd_max_age_years: float = Field(
        default=100.0,
        gt=0.0,
        le=150.0,
        description="Upper age bound (years) for primary directions timeline.",
    )
    pd_window_size: int = Field(
        default=6,
        ge=1,
        le=50,
        description="Maximum events in primary directions current/exact windows.",
    )


class WesternPrimaryDirectionsTimelineFields(BaseModel):
    """Timeline scope controls shared where primary directions timeline is emitted."""

    pd_nearby_years: float = Field(
        default=5.0,
        gt=0.0,
        le=100.0,
        description="Year radius around current age when include_full_timelines is false.",
    )
    pd_timeline_limit: int = Field(
        default=25,
        ge=1,
        le=500,
        description="Maximum nearby timeline entries when include_full_timelines is false.",
    )
    include_full_timelines: bool = Field(
        default=False,
        description=(
            "Whether to include full multi-decade timelines; default False returns "
            "active states and bounded nearby windows."
        ),
    )


class WesternPrimaryDirectionsRequest(
    WesternPrimaryDirectionsTimelineFields,
    WesternPrimaryDirectionsBaseRequest,
):
    """Request model for primary directions timing."""


class WesternPrimaryDirectionsChartRequest(WesternPrimaryDirectionsBaseRequest):
    """Request model for primary directions chart."""

    show_pd_bounds: bool = Field(
        default=True,
        description="Whether to expose the bounds overlay preference for the primary direction chart",
    )


class WesternAspectHitsFields(BaseModel):
    """Shared aspect-orb and optional hit-count cap fields."""

    orb_limit: float = Field(
        default=1.5,
        ge=0.0,
        le=15.0,
        description="Maximum aspect orb in degrees (0..15, default 1.5).",
    )
    max_hits: int | None = Field(
        default=None,
        ge=1,
        le=200,
        description="Optional cap on returned aspect hits (default None returns all hits within orb_limit).",
    )


class WesternAspectTimingRequest(WesternAspectHitsFields, WesternTimingBaseRequest):
    """Request model for standalone aspect-hit timing tools (solar_arc, chart_for_year)."""


class WesternTransitRequest(WesternAspectHitsFields, WesternTimingBaseRequest):
    """Request model for transit chart and optional multi-day transit scanning."""

    scan_days: int | None = Field(
        default=None,
        ge=1,
        le=90,
        description=(
            "Optional number of daily steps (1..90) to scan transits forward "
            "from analysis_datetime."
        ),
    )


class WesternTimingRequest(
    WesternReturnTimingRequest,
    WesternFirdariaRequest,
    WesternPrimaryDirectionsChartRequest,
    WesternPrimaryDirectionsTimelineFields,
    WesternAspectHitsFields,
):
    """Request model for aggregate western predictive timing analysis."""

    techniques: list[WesternTimingTechnique] | None = Field(
        default=None,
        min_length=1,
        description=(
            "Optional subset of western timing techniques to compute; "
            "when omitted, computes all techniques."
        ),
    )
