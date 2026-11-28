"""Shared service execution, output validation and execution receipts."""

import secrets
from collections.abc import Callable, Collection, Mapping
from contextlib import nullcontext
from dataclasses import dataclass
from time import perf_counter

from pydantic import BaseModel, JsonValue, ValidationError

from fatebridge.application.compute_limits import heavy_calculation_budget
from fatebridge.application.response_delivery import (
    deliver_response,
    validate_delivery_controls,
)
from fatebridge.application.tool_spec import (
    BoundServiceCall,
    OutputContractError,
    ServiceResult,
    ToolSpec,
)
from fatebridge.core.execution_context import ExecutionOptions, call_clock
from fatebridge.core.public_output import public_payload
from fatebridge.core.receipt_models import RunMetadata
from fatebridge.core.reproducibility import policy_for
from fatebridge.services import replay_metadata, run_metadata
from fatebridge.utils.errors import (
    DomainSourceError,
    ErrorEnvelope,
    ParameterError,
    handle_calculation_error,
)
from fatebridge.utils.runtime import is_strict_output_validation_enabled


@dataclass(frozen=True, kw_only=True)
class ToolRunOutcome:
    """Canonical execution, error-translation, and delivery result for one tool call."""

    payload: ServiceResult
    failed: bool
    status_code: int
    operation: str


def strict_output_validation_enabled() -> bool:
    """Read the opt-in flag for full output and domain validation."""
    return is_strict_output_validation_enabled()


def invoke_validated_service(
    spec: ToolSpec,
    request: BaseModel,
    *,
    strict_validation: bool | None = None,
) -> ServiceResult:
    """Run and validate a bound domain service call."""

    def invoke_service() -> ServiceResult:
        bound_call = BoundServiceCall(*spec.bind(request))
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


def execute_with_receipt(
    spec: ToolSpec,
    request: BaseModel,
    *,
    options: ExecutionOptions | None = None,
) -> ServiceResult:
    """Run a validated request with a frozen clock and attach its execution receipt."""

    controls = options or ExecutionOptions()
    seed_was_generated = False
    seed_field = (
        spec.reproducibility
        or policy_for(
            spec.request_model,
            has_time_defaults=spec.resolve_time_defaults is not None,
        )
    ).random_seed_field
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
                replay_overrides[seed_field] = seed
            result = invoke_validated_service(spec, request)
        except Exception as exc:
            return handle_calculation_error(
                exc,
                spec.operation_label_zh,
                allowed_fields=spec.request_model.model_fields.keys(),
            )
        elapsed_ms = (perf_counter() - started) * 1000
        if result_is_error(result):
            return result
        try:
            receipt = replay_metadata.execution_receipt(
                spec,
                request,
                result,
                clock=clock,
                elapsed_ms=elapsed_ms,
                generated_seed=seed_was_generated,
                replay_overrides=replay_overrides,
            )
            base_metadata = run_metadata.build_run_metadata(
                result,
                tool_name=spec.name,
                approximate_record=spec.approximate_record,
            )
            if base_metadata["engine_is_approximate"]:
                receipt["warnings"].append("approximate_engine")
            metadata: ServiceResult = {**base_metadata, **receipt}
            RunMetadata.model_validate(metadata)
            result = {**result, "run_metadata": metadata}
        except DomainSourceError as exc:
            return handle_calculation_error(exc, spec.operation_label_zh)
        except Exception as exc:
            # note (execution): Receipt failures use the server-output error envelope.
            failure = OutputContractError("执行元数据生成失败")
            failure.__cause__ = exc
            return handle_calculation_error(failure, spec.operation_label_zh)
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
        return
    if any(
        field not in result or result[field] is None or result[field] == {}
        for field in spec.required_output_fields
    ):
        raise OutputContractError("完整工具输出缺少必需业务事实或仅有空对象")
    required_validator = spec.required_output_validator
    if required_validator is not None and request is not None:
        required_validator(spec, result, request)
    if not strict:
        return
    validated = None
    if spec.output_model is not None:
        try:
            validated = spec.output_model.model_validate(
                result, context={"full_result": True}
            )
        except ValidationError as exc:
            raise OutputContractError("工具输出不符合公开契约") from exc
    if required_validator is not None and request is None:
        required_validator(spec, result, None)
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


def run_tool(
    spec: ToolSpec,
    arguments: BaseModel | Mapping[str, object] | None = None,
    *,
    include: list[str] | None = None,
    fields: list[str] | None = None,
    as_of: str | None = None,
    options: ExecutionOptions | None = None,
    raise_parameter_error: bool = False,
    executor: Callable[..., ServiceResult] | None = None,
) -> ToolRunOutcome:
    """Canonical pipeline: delivery check -> request/options validation -> execution -> delivery."""
    try:
        validate_delivery_controls(include, fields)
    except ParameterError as exc:
        if raise_parameter_error:
            raise
        failure = exc.as_result()
        return ToolRunOutcome(
            payload=failure,
            failed=True,
            status_code=int(failure.get("status_code", exc.status_code)),
            operation=spec.operation_label_zh,
        )

    try:
        resolved_options = (
            options
            if options is not None
            else ExecutionOptions.model_validate({"as_of": as_of})
        )
        request = (
            arguments
            if isinstance(arguments, BaseModel)
            else spec.request_model.model_validate(dict(arguments) if arguments else {})
        )
        result = (executor or execute_with_receipt)(
            spec,
            request,
            options=resolved_options,
        )
    except Exception as exc:  # noqa: BLE001 - canonical surface error boundary
        failure = handle_calculation_error(
            exc,
            spec.operation_label_zh,
            allowed_fields=spec.request_model.model_fields.keys(),
            root_model=spec.request_model,
        )
        return ToolRunOutcome(
            payload=failure,
            failed=True,
            status_code=int(failure.get("status_code", 500)),
            operation=spec.operation_label_zh,
        )

    failed = result_is_error(result)
    try:
        delivered = deliver_response(
            result,
            spec=spec,
            include=include,
            fields=fields,
            failed=failed,
        )
    except ParameterError as exc:
        if raise_parameter_error and not failed:
            raise
        failure = exc.as_result()
        return ToolRunOutcome(
            payload=failure,
            failed=True,
            status_code=int(failure.get("status_code", exc.status_code)),
            operation=spec.operation_label_zh,
        )

    return ToolRunOutcome(
        payload=delivered,
        failed=failed,
        status_code=int(result.get("status_code", 500)) if failed else 200,
        operation=spec.operation_label_zh,
    )


def run_guarded_operation(
    operation: str,
    action: Callable[[], ServiceResult],
    *,
    allowed_fields: Collection[str] | None = None,
    root_model: type[BaseModel] | None = None,
) -> ToolRunOutcome:
    """Execute a non-tool operation (e.g., batch) under the shared error boundary."""
    try:
        payload = action()
    except Exception as exc:  # noqa: BLE001 - canonical surface error boundary
        failure = handle_calculation_error(
            exc,
            operation,
            allowed_fields=allowed_fields,
            root_model=root_model,
        )
        return ToolRunOutcome(
            payload=failure,
            failed=True,
            status_code=int(failure.get("status_code", 500)),
            operation=operation,
        )
    return ToolRunOutcome(
        payload=payload,
        failed=False,
        status_code=200,
        operation=operation,
    )
