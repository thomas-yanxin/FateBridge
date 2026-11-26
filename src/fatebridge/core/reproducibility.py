"""Declarative replay conditions, distinct from MCP environment-effect hints."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, TypedDict

if TYPE_CHECKING:
    from pydantic import BaseModel


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


def policy_for(
    model: type[BaseModel], *, has_time_defaults: bool = False
) -> ReproducibilityPolicy:
    """Derive reproducibility policy from request field declarations."""
    fields = model.model_fields
    date_fields = ("analysis_year", "analysis_month", "analysis_day")
    clock_fields: tuple[str, ...] = ()
    if has_time_defaults:
        clock_fields = tuple(
            f
            for f in (*date_fields, "analysis_hour", "analysis_minute")
            if f in fields and not fields[f].is_required()
        )
    elif all(f in fields and not fields[f].is_required() for f in date_fields):
        clock_fields = date_fields
    has_seed = "seed" in fields
    return ReproducibilityPolicy(
        current_time_fields=clock_fields,
        random_seed_field="seed" if has_seed else "",
        seed_condition=(
            "method=coin without coins/lines/binary hexagram codes"
            if has_seed
            else None
        ),
    )
