"""Request contracts for western timing."""

from __future__ import annotations

from typing import List, Literal, Optional, Union

from pydantic import Field

from fatebridge.core.requests.birth import AstroBirthRequest


class WesternTimingRequest(AstroBirthRequest):
    """Request model for western predictive timing analysis."""

    analysis_year: Optional[int] = Field(default=None, description="Analysis year")
    analysis_month: Optional[int] = Field(
        default=None, ge=1, le=12, description="Analysis month (1-12)"
    )
    analysis_day: Optional[int] = Field(
        default=None, ge=1, le=31, description="Analysis day (1-31)"
    )
    analysis_hour: Optional[int] = Field(
        default=None,
        ge=0,
        le=23,
        description=(
            "Analysis hour (0-23), in birth_timezone. "
            "If omitted, keeps the birth hour for date-only compatibility."
        ),
    )
    analysis_minute: Optional[int] = Field(
        default=None,
        ge=0,
        le=59,
        description=(
            "Analysis minute (0-59), in birth_timezone. "
            "If omitted, keeps the birth minute for date-only compatibility."
        ),
    )
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
            "Firdaria year basis: fixed_365_2425 (existing local-wall arithmetic) "
            "or calendar_anniversary (original-birth anniversaries, Feb 29 clamps "
            "to Feb 28 then restores; UTC elapsed subperiods). Calendar mode rejects "
            "ambiguous/nonexistent birth, analysis and generated anniversary clocks."
        ),
    )
    return_longitude: Optional[float] = Field(
        default=None, ge=-180, le=180, description="Return chart longitude"
    )
    return_latitude: Optional[float] = Field(
        default=None, ge=-90, le=90, description="Return chart latitude"
    )
    return_timezone: Optional[str] = Field(
        default=None, description="Return chart timezone (IANA name or UTC offset)"
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
    pd_method: Literal[
        "astroapp_alchabitius", "equatorial", "fatebridge_mundane_semiarc"
    ] = Field(
        default="astroapp_alchabitius",
        description=(
            "Primary direction method identifier, e.g. astroapp_alchabitius, "
            "equatorial, or fatebridge_mundane_semiarc"
        ),
    )
    pd_time_key: str = Field(
        default="Ptolemy",
        description="Primary direction time key, e.g. Ptolemy or Naibod",
    )
    pd_type: int = Field(
        default=0,
        ge=0,
        le=1,
        description="Primary direction mode: 0 for direct, 1 for converse",
    )
    pd_aspects: List[int] = Field(
        default_factory=lambda: [0, 60, 90, 120, 180],
        description="Primary direction aspects in degrees",
    )
    show_pd_bounds: bool = Field(
        default=True,
        description="Whether to expose the bounds overlay preference for the primary direction chart",
    )


class WesternTimingModuleRequest(WesternTimingRequest):
    """Request model for standalone western timing module tools."""

    selected_sections: List[str] = Field(
        default_factory=list,
        description="Optional export sections to keep in snapshot_export",
    )
