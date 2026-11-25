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


class Determinism(PartialOutput):
    uses_current_time: bool
    current_time_fields_defaulted: list[str]
    randomness_used: bool
    seed_generated: bool
    replayable_with_receipt: bool
    scope: str


class RunMetadata(PartialOutput):
    run_id: str
    trace_id: str
    tool_name: str
    generated_at: str
    engine: str
    engine_is_approximate: bool
    parent_run_id: str | None = None
    metadata_schema_version: str | None = None
    package_version: str | None = None
    duration_ms: float | None = Field(default=None, ge=0)
    effective_time: EffectiveTime | None = None
    determinism: Determinism | None = None
    runtime: Object | None = None
    provenance: dict[str, list[str]] | None = None
    calculation_evidence: Object | None = None
    replay: ReplayControls | None = None
    warnings: list[str] | None = None
