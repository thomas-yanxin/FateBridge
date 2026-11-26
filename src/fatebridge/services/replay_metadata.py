"""Slim deterministic execution receipts for shared tool execution."""

from typing import TypedDict

from pydantic import BaseModel, JsonValue
from typing_extensions import NotRequired

from fatebridge.application.tool_spec import ServiceResult, ToolSpec
from fatebridge.core.execution_context import CallClock, ExecutionOptions
from fatebridge.core.reproducibility import policy_for


class EffectiveTimeReceipt(TypedDict):
    as_of: str
    clock_timezones: list[str]


class ReplayReceipt(TypedDict):
    as_of: str
    overrides: dict[str, JsonValue]
    requires_original_input: bool


class ExecutionReceipt(TypedDict):
    effective_time: EffectiveTimeReceipt
    warnings: list[str]
    replay: NotRequired[ReplayReceipt]
    duration_ms: NotRequired[float]


def execution_receipt(
    spec: ToolSpec,
    request: BaseModel,
    result: ServiceResult,
    *,
    clock: CallClock,
    options: ExecutionOptions,
    elapsed_ms: float,
    generated_seed: bool,
    replay_overrides: dict[str, JsonValue],
    compact_receipt: bool = False,
) -> ExecutionReceipt:
    policy = spec.reproducibility or policy_for(
        spec.request_model,
        has_time_defaults=spec.resolve_time_defaults is not None,
    )
    as_of = clock.instant.isoformat().replace("+00:00", "Z")
    time_defaults = [
        field
        for field in policy.current_time_fields
        if getattr(request, field, None) is None
    ]
    if spec.resolve_time_defaults is not None:
        time_defaults = spec.resolve_time_defaults(result, time_defaults)
    warnings = (
        ["current_time_frozen"]
        if clock.reads and (time_defaults or policy.implicit_current_time)
        else []
    ) + (["random_seed_generated"] if generated_seed else [])
    receipt: ExecutionReceipt = {
        "effective_time": {"as_of": as_of, "clock_timezones": sorted(clock.reads)},
        "warnings": warnings,
    }
    if replay_overrides:
        receipt["replay"] = {
            "as_of": as_of,
            "overrides": replay_overrides,
            "requires_original_input": True,
        }
    if compact_receipt:
        return receipt

    receipt["duration_ms"] = round(elapsed_ms, 3)
    receipt["replay"] = {
        "as_of": as_of,
        "overrides": replay_overrides,
        "requires_original_input": True,
    }
    return receipt
