"""Shared execution receipt output contracts, independent of domain models."""

from pydantic import Field, JsonValue

from fatebridge.core.contracts.output_base import PartialOutput

Object = dict[str, JsonValue]


class EffectiveTime(PartialOutput):
    as_of: str
    clock_timezones: list[str]


class ReplayControls(PartialOutput):
    as_of: str
    overrides: Object
    requires_original_input: bool


class RunMetadata(PartialOutput):
    run_id: str
    tool_name: str
    generated_at: str
    engine: str
    engine_is_approximate: bool
    duration_ms: float | None = Field(default=None, ge=0)
    effective_time: EffectiveTime | None = None
    replay: ReplayControls | None = None
    warnings: list[str] | None = None
    omitted_fields: list[str] | None = None
