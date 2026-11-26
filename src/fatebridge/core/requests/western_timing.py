"""Request contracts for western timing."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from fatebridge.core.requests.base import (
    AstroHouseValidatorMixin,
    OptionalAnalysisClockFields,
    WesternChartSystemFields,
)
from fatebridge.core.requests.birth import AstroBirthRequest
from fatebridge.core.requests.western_policy import WesternEphemerisRequest


class WesternTimingBaseRequest(
    AstroHouseValidatorMixin,
    OptionalAnalysisClockFields,
    WesternChartSystemFields,
    AstroBirthRequest,
    WesternEphemerisRequest,
):
    """Shared base request model for western predictive timing techniques."""


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


class WesternPrimaryDirectionsRequest(WesternTimingBaseRequest):
    """Request model for primary directions timing."""

    pd_method: Literal[
        "astroapp_alchabitius", "equatorial", "fatebridge_mundane_semiarc"
    ] = Field(
        default="astroapp_alchabitius",
        description=(
            "Primary direction method identifier, e.g. astroapp_alchabitius, "
            "equatorial, or fatebridge_mundane_semiarc"
        ),
    )
    pd_time_key: Literal["Ptolemy", "Naibod", "Cardan"] = Field(
        default="Ptolemy",
        description="Primary direction time key: Ptolemy, Naibod or Cardan",
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


class WesternPrimaryDirectionsChartRequest(WesternPrimaryDirectionsRequest):
    """Request model for primary directions chart."""

    show_pd_bounds: bool = Field(
        default=True,
        description="Whether to expose the bounds overlay preference for the primary direction chart",
    )


class WesternTimingRequest(
    WesternReturnTimingRequest,
    WesternFirdariaRequest,
    WesternPrimaryDirectionsChartRequest,
):
    """Request model for aggregate western predictive timing analysis."""
