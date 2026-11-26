"""Declarative replay conditions, distinct from MCP environment-effect hints."""

from dataclasses import dataclass
from typing import Literal, TypedDict

from pydantic import BaseModel

BAZI_ANALYSIS_CLOCK_TOOLS = frozenset(
    {
        "bazi_timing",
        "bazi_luck_cycles",
        "bazi_monthly_timing",
        "bazi_daily_timing",
        "bazi_hourly_timing",
    }
)


class ReproducibilityManifest(TypedDict):
    deterministic: Literal["conditional", "fixed_input_and_environment"]
    may_use_current_time: bool
    current_time_fields: list[str]
    random_seed_field: str | None
    requires_seed_for_replay: bool
    seed_condition: str | None
    replay_controls: list[str]
    scope: str
    environment_sensitive: bool


@dataclass(frozen=True)
class ReproducibilityPolicy:
    current_time_fields: tuple[str, ...] = ()
    implicit_current_time: bool = False
    random_seed_field: str = ""
    seed_condition: str | None = None

    def as_manifest(self) -> ReproducibilityManifest:
        return {
            "deterministic": (
                "conditional"
                if self.current_time_fields
                or self.implicit_current_time
                or self.random_seed_field
                else "fixed_input_and_environment"
            ),
            "may_use_current_time": bool(
                self.current_time_fields or self.implicit_current_time
            ),
            "current_time_fields": list(self.current_time_fields),
            "random_seed_field": self.random_seed_field or None,
            "requires_seed_for_replay": bool(self.random_seed_field),
            "seed_condition": self.seed_condition,
            "replay_controls": ["as_of"],
            "scope": "business_payload; excludes run_metadata and output shaping",
            "environment_sensitive": True,
        }


def policy_for(name: str, model: type[BaseModel]) -> ReproducibilityPolicy:
    """Default policies for the current catalog, overridable on new ToolSpecs."""
    fields = model.model_fields
    clock_fields: tuple[str, ...] = ()
    date_fields = ("analysis_year", "analysis_month", "analysis_day")
    if name in BAZI_ANALYSIS_CLOCK_TOOLS:
        clock_fields = (*date_fields, "analysis_hour", "analysis_minute")
    elif name.startswith("bazi_") or name in {
        "vimshottari_dasha",
        "planetary_returns",
        "planetary_ages",
        "planetary_arc_directions",
        "sidereal_progressions",
        "declination_progressions",
        "western_timing",
        "solar_return",
        "lunar_return",
        "transit_chart",
        "solar_arc",
        "chart_for_year",
        "profection",
        "primary_directions",
        "primary_directions_chart",
        "zodiacal_releasing",
        "firdaria",
        "decennials",
    }:
        clock_fields = tuple(
            f for f in date_fields if f in fields and not fields[f].is_required()
        )
    elif name == "solar_term_timeline":
        clock_fields = ("analysis_year",)
    return ReproducibilityPolicy(
        current_time_fields=clock_fields,
        implicit_current_time=name == "bazi_overview",
        random_seed_field="seed" if name == "liuyao" else "",
        seed_condition=(
            "method=coin without coins/lines/binary hexagram codes"
            if name == "liuyao"
            else None
        ),
    )
