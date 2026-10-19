"""Shared service execution, output validation and execution receipts."""

from typing import Optional

from pydantic import BaseModel, ValidationError

from fatebridge.application.tool_spec import ServiceResult, ToolSpec
from fatebridge.core.execution_context import (
    ExecutionOptions,
    call_clock,
    correlate_error,
)
from fatebridge.utils.errors import (
    VALIDATION_ERROR_CODE,
    ErrorEnvelope,
    handle_calculation_error,
)


def execute_spec(spec: ToolSpec, request: BaseModel) -> ServiceResult:
    """Run and validate a bound domain service call."""
    from fatebridge.core.consultation_policy import (
        restricted_intent_path,
        restriction_result,
    )

    # Also guard callers using model_construct/model_copy rather than validation.
    restricted = restricted_intent_path(request.model_dump())
    if restricted:
        return restriction_result(restricted)
    service, args, kwargs = spec.bind(request)
    result = service(*args, **kwargs)
    validate_output(spec, result)
    return result


def execute_tool(
    spec: ToolSpec,
    request: BaseModel,
    *,
    options: Optional[ExecutionOptions] = None,
    include_metadata: bool = True,
) -> ServiceResult:
    """Common transport execution: scoped clock, replay seed and receipt.

    execute_spec remains the metadata-free service execution contract for
    existing library callers; REST still offloads this unit through its executor.
    """
    import secrets
    from time import perf_counter

    from fatebridge.services.replay_metadata import execution_receipt
    from fatebridge.services.run_metadata import attach_run_metadata

    controls = options or ExecutionOptions()
    generated_seed = False
    data = request.model_dump()
    random_cast = False
    if spec.key == "sixyao":
        from fatebridge.core.local_techniques.sixyao import needs_random_coin_cast

        random_cast = needs_random_coin_cast(data)
    if (
        spec.reproducibility.random_seed_field == "seed"
        and random_cast
        and data.get("seed") is None
    ):
        request = request.model_copy(update={"seed": secrets.randbits(32)})
        generated_seed = True
    with call_clock(controls.as_of) as clock:
        started = perf_counter()
        try:
            result = execute_spec(spec, request)
        except ValueError:
            return correlate_error(invalid_input_result(spec), controls)
        except Exception as exc:
            return correlate_error(
                handle_calculation_error(exc, spec.operation_label_zh), controls
            )
        elapsed_ms = (perf_counter() - started) * 1000
        if result_is_error(spec, result):
            return correlate_error(result, controls)
        if not include_metadata:
            return result
        try:
            receipt = execution_receipt(
                spec,
                request,
                result,
                clock=clock,
                options=controls,
                elapsed_ms=elapsed_ms,
                generated_seed=generated_seed,
            )
            result = attach_run_metadata(result, tool_name=spec.run_metadata_name)
            result["run_metadata"] = {**result["run_metadata"], **receipt}
            if result["run_metadata"]["engine_is_approximate"]:
                result["run_metadata"]["warnings"].append("approximate_engine")
            if controls.trace_id is not None:
                result["run_metadata"]["trace_id"] = controls.trace_id
            validate_output(spec, result)
        except Exception:
            # Receipt generation, attachment and final validation are server
            # output work, never bad user input even if they raise ValueError.
            # Handle them here so every adapter retains validated correlation.
            return correlate_error(
                handle_calculation_error(
                    OutputContractError("执行元数据生成失败"), spec.operation_label_zh
                ),
                controls,
            )
        return result


class OutputContractError(RuntimeError):
    """A service bug, never a user-input error."""


def validate_output(spec: ToolSpec, result: ServiceResult) -> None:
    if result_is_error(spec, result):
        try:
            ErrorEnvelope.model_validate(result, strict=True)
        except ValidationError as exc:
            raise OutputContractError("工具错误输出不符合公开契约") from exc
        if result["error"] is None or not result["error_code"].strip():
            raise OutputContractError("工具错误输出缺少错误事实")
        return
    if any(
        field not in result or result[field] is None
        for field in spec.required_output_fields
    ):
        raise OutputContractError("完整工具输出缺少必需业务字段")
    if spec.output_model is not None:
        try:
            spec.output_model.model_validate(result)
        except ValidationError as exc:
            raise OutputContractError("工具输出不符合公开契约") from exc


def result_is_error(spec: ToolSpec, result: ServiceResult) -> bool:
    """Classify a service result as an error, honoring spec.error_is_fatal.

    Mirrors the REST transport's logic so every surface (REST/MCP/CLI) treats
    failures identically.
    """
    if spec.error_is_fatal is not None:
        return bool(spec.error_is_fatal(result))
    return "error" in result


def invalid_input_result(spec: ToolSpec) -> ServiceResult:
    """Error result for invalid input, mirroring the REST 400 path.

    REST maps a ``ValueError`` raised while binding a validated request to
    HTTP 400 with a generic ``无效的<label>`` detail
    (it deliberately does not leak the raw exception text). MCP and the CLI have
    no HTTP layer, so they render this same shape through the normal error
    renderer — keeping bad-input handling identical across every surface instead
    of leaking a raw traceback on MCP.

    The ``error_code`` reuses the same ``validation_error`` token that
    ``handle_calculation_error`` emits for service-layer ``ValueError``s, so an
    agent can branch on ``error_code`` regardless of *where* the bad input was
    caught. The two paths differ only in message detail — and that difference is
    intentional: this binding-layer path stays generic, whereas a service raises a
    hand-written domain message that is safe and useful to surface. Branch on
    ``error_code``, not on message text.
    """
    label = spec.rest_error_label or f"{spec.operation_label_zh}参数"
    return {
        "error": f"无效的{label}",
        "error_code": VALIDATION_ERROR_CODE,
        "status_code": 400,
        "retryable": False,
    }
