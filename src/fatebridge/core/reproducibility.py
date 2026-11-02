"""Declarative replay conditions, distinct from MCP environment-effect hints."""

from dataclasses import dataclass
from typing import Any, Dict, Tuple, Type

from pydantic import BaseModel

BAZI_ANALYSIS_CLOCK_TOOLS = frozenset(
    {
        "timing_analysis",
        "dayun_analysis",
        "liuyue_analysis",
        "liuri_analysis",
        "liushi_analysis",
    }
)


@dataclass(frozen=True)
class ReproducibilityPolicy:
    current_time_fields: Tuple[str, ...] = ()
    implicit_current_time: bool = False
    random_seed_field: str = ""

    def as_manifest(self) -> Dict[str, Any]:
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
            "seed_condition": (
                "method=coin without coins/lines/binary hexagram codes"
                if self.random_seed_field
                else None
            ),
            "replay_controls": ["as_of", "trace_id", "parent_run_id"],
            "scope": "business_payload; excludes run_metadata and output shaping",
            "environment_sensitive": True,
        }


def policy_for(key: str, model: Type[BaseModel]) -> ReproducibilityPolicy:
    """Default policies for the current catalog, overridable on new ToolSpecs."""
    fields = model.model_fields
    clock_fields: Tuple[str, ...] = ()
    date_fields = ("analysis_year", "analysis_month", "analysis_day")
    if key in BAZI_ANALYSIS_CLOCK_TOOLS:
        clock_fields = (*date_fields, "analysis_hour", "analysis_minute")
    elif (
        key.startswith("bazi_")
        or key.startswith("astro_")
        or key
        in {
            "western_timing_analysis",
            "solarreturn",
            "lunarreturn",
            "transit",
            "solararc",
            "givenyear",
            "profection",
            "pd",
            "pdchart",
            "zr",
            "firdaria",
            "decennials",
        }
    ):
        clock_fields = tuple(
            f for f in date_fields if f in fields and not fields[f].is_required()
        )
    elif key == "jieqi_timeline_analysis":
        clock_fields = ("target_year",)
    return ReproducibilityPolicy(
        current_time_fields=clock_fields,
        implicit_current_time=key == "analyze_destiny",
        random_seed_field="seed" if key == "sixyao" else "",
    )
