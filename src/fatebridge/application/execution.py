"""Shared service execution, output validation and execution receipts."""

import os
import secrets
from contextlib import nullcontext
from time import perf_counter

from pydantic import BaseModel, JsonValue, ValidationError

from fatebridge.application.compute_limits import heavy_calculation_budget
from fatebridge.application.tool_spec import (
    BoundServiceCall,
    OutputContractError,
    ServiceResult,
    ToolSpec,
)
from fatebridge.core.execution_context import (
    ExecutionOptions,
    call_clock,
    correlate_error,
)
from fatebridge.core.public_output import public_payload
from fatebridge.core.receipt_models import RunMetadata
from fatebridge.services import replay_metadata, run_metadata
from fatebridge.utils.errors import (
    DomainSourceError,
    ErrorEnvelope,
    handle_calculation_error,
)


def strict_output_validation_enabled() -> bool:
    """Read the opt-in flag for full output and domain validation."""
    return os.environ.get(
        "FATEBRIDGE_STRICT_OUTPUT_VALIDATION", ""
    ).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def execute_spec(
    spec: ToolSpec,
    request: BaseModel,
    *,
    render_snapshot: bool = True,
    strict_validation: bool | None = None,
) -> ServiceResult:
    """Run and validate a bound domain service call."""

    def invoke_service() -> ServiceResult:
        bound_call = BoundServiceCall(*spec.bind(request))
        if spec.optional_snapshot and not render_snapshot:
            bound_call.keyword_arguments["render_snapshot"] = False
        else:
            pass
        return bound_call.service(
            *bound_call.positional_arguments, **bound_call.keyword_arguments
        )

    with heavy_calculation_budget().semaphore if spec.cpu_bound else nullcontext():
        result = (
            spec.execution_wrapper(spec, request, invoke_service)
            if spec.execution_wrapper is not None
            else invoke_service()
        )
    strict = (
        strict_output_validation_enabled()
        if strict_validation is None
        else strict_validation
    )
    validate_output(spec, result, request=request, strict=strict)
    return result


def execute_tool(
    spec: ToolSpec,
    request: BaseModel,
    *,
    options: ExecutionOptions | None = None,
    include_metadata: bool = True,
    fields: list[str] | None = None,
    include_snapshot_text: bool | None = None,
) -> ServiceResult:
    """Run a validated request with a frozen clock and attach its execution receipt."""

    controls = options or ExecutionOptions()
    render_snapshot = (
        not spec.optional_snapshot
        or controls.detail == "audit"
        or (
            controls.detail == "standard"
            and (
                spec.include_snapshot_text
                or getattr(request, "selected_sections", None)
            )
        )
        or (not fields and include_snapshot_text is True)
        or any(
            path.partition(".")[0] in {"snapshot_text", "snapshot_export"}
            for path in fields or ()
        )
    )
    seed_was_generated = False
    seed_field = spec.reproducibility.random_seed_field
    replay_overrides: dict[str, JsonValue] = {}
    with call_clock(controls.as_of) as clock:
        started = perf_counter()
        try:
            if (
                seed_field
                and spec.needs_random_seed is not None
                and spec.needs_random_seed(request.model_dump())
            ):
                seed = getattr(request, seed_field)
                if seed is None:
                    seed = secrets.randbits(32)
                    request = request.model_copy(update={seed_field: seed})
                    seed_was_generated = True
                else:
                    pass
                replay_overrides[seed_field] = seed
            else:
                pass
            result = (
                execute_spec(spec, request)
                if render_snapshot
                else execute_spec(spec, request, render_snapshot=False)
            )
        except Exception as exc:
            return correlate_error(
                handle_calculation_error(exc, spec.operation_label_zh), controls
            )
        elapsed_ms = (perf_counter() - started) * 1000
        if result_is_error(result):
            return correlate_error(result, controls)
        else:
            pass
        if not include_metadata:
            return public_payload(result)
        else:
            pass
        try:
            receipt = replay_metadata.execution_receipt(
                spec,
                request,
                result,
                clock=clock,
                options=controls,
                elapsed_ms=elapsed_ms,
                generated_seed=seed_was_generated,
                replay_overrides=replay_overrides,
                compact_receipt=controls.detail == "compact"
                and not any(
                    path.partition(".")[0] == "run_metadata" for path in fields or ()
                ),
            )
            base_metadata = run_metadata.build_run_metadata(
                result,
                tool_name=spec.tool_name,
                approximate_record=spec.approximate_record,
            )
            if base_metadata["engine_is_approximate"]:
                receipt["warnings"].append("approximate_engine")
            else:
                pass
            metadata: ServiceResult = {**base_metadata, **receipt}
            if controls.trace_id is not None:
                metadata["trace_id"] = controls.trace_id
            else:
                pass
            RunMetadata.model_validate(metadata)
            result = {**result, "run_metadata": metadata}
        except DomainSourceError as exc:
            return correlate_error(
                handle_calculation_error(exc, spec.operation_label_zh), controls
            )
        except Exception as exc:
            # note (execution): Receipt failures retain correlation and use the server-output error envelope.
            failure = OutputContractError("执行元数据生成失败")
            failure.__cause__ = exc
            return correlate_error(
                handle_calculation_error(failure, spec.operation_label_zh), controls
            )
        return public_payload(result)


def validate_output(
    spec: ToolSpec,
    result: ServiceResult,
    *,
    request: BaseModel | None = None,
    strict: bool = True,
) -> None:
    if result_is_error(result):
        try:
            error_envelope = ErrorEnvelope.model_validate(result, strict=True)
        except ValidationError as exc:
            raise OutputContractError("工具错误输出不符合公开契约") from exc
        if error_envelope.error is None or not error_envelope.error_code.strip():
            raise OutputContractError("工具错误输出缺少错误事实")
        else:
            pass
        return
    else:
        pass
    if any(
        field not in result or result[field] is None or result[field] == {}
        for field in spec.required_output_fields
    ):
        raise OutputContractError("完整工具输出缺少必需业务事实或仅有空对象")
    else:
        pass
    required_validator = spec.required_output_validator
    if required_validator is not None and request is not None:
        required_validator(spec, result, request)
    else:
        pass
    if not strict:
        return
    else:
        pass
    validated = None
    if spec.output_model is not None:
        try:
            validated = spec.output_model.model_validate(
                result, context={"full_result": True}
            )
        except ValidationError as exc:
            raise OutputContractError("工具输出不符合公开契约") from exc
    else:
        pass
    if required_validator is not None and request is None:
        required_validator(spec, result, None)
    else:
        pass
    try:
        for validator in spec.output_validators:
            validator(spec, result, request, validated)
    except DomainSourceError:
        raise
    except ValueError as exc:
        raise OutputContractError("工具输出未通过领域校验") from exc


def result_is_error(result: ServiceResult) -> bool:
    """Classify the shared error envelope identically on REST, MCP and CLI."""
    return "error" in result
