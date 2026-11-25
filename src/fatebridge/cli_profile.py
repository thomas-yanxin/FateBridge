"""Run multiple catalog tools on one subject and combine their CLI results."""

from __future__ import annotations

import argparse
from typing import Protocol

from pydantic import BaseModel, ValidationError

from fatebridge.application.description import resolve_spec, spec_is_cli_safe
from fatebridge.application.execution import result_is_error
from fatebridge.application.projection import project_fields
from fatebridge.application.response_delivery import deliver_response
from fatebridge.application.result_delivery import bound_response
from fatebridge.application.tool_spec import ServiceResult, ToolSpec
from fatebridge.cli_arguments import emit_error
from fatebridge.cli_inputs import (
    PROFILE_PERSON_FIELDS,
    PROFILE_REQUIRED_FIELDS,
    validate_subject_fields,
)
from fatebridge.core.execution_context import (
    ExecutionOptions,
    call_clock,
    correlate_error,
    safe_correlation,
)
from fatebridge.services.run_metadata import attach_run_metadata
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.utils.errors import (
    ParameterError,
    handle_calculation_error,
    validation_error_result,
)
from fatebridge.utils.formatting import format_json_response
from fatebridge.utils.places import DEFAULT_BIRTH_TIMEZONE, resolve_birth_place_context


class ProfileToolExecutor(Protocol):
    def __call__(
        self,
        spec: ToolSpec,
        request: BaseModel,
        *,
        options: ExecutionOptions,
        include_metadata: bool,
        fields: list[str] | None,
        include_snapshot_text: bool | None,
    ) -> ServiceResult: ...


DEFAULT_PROFILE_SYSTEMS = "bazi,ziwei,astro"

SYSTEM_ALIASES = {
    "bazi": "bazi_birth_chart",
    "八字": "bazi_birth_chart",
    "ziwei": "ziwei_birth_chart",
    "紫微": "ziwei_birth_chart",
    "紫微斗数": "ziwei_birth_chart",
    "astro": "astrology_chart",
    "astrology": "astrology_chart",
    "西占": "astrology_chart",
    "占星": "astrology_chart",
    "personality": "bazi_personality",
    "性格": "bazi_personality",
    "career": "bazi_career",
    "事业": "bazi_career",
    "marriage": "bazi_marriage",
    "婚姻": "bazi_marriage",
    "health": "bazi_health",
    "健康": "bazi_health",
    "romance": "bazi_romance",
    "桃花": "bazi_romance",
}


def _resolve_profile_systems(
    tokens: list[str],
) -> tuple[list[tuple[str, ToolSpec]], list[str]]:
    resolved: list[tuple[str, ToolSpec]] = []
    unknown: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        name = SYSTEM_ALIASES.get(token.lower(), token)
        spec = resolve_spec(CATALOG, name)
        if spec is None or not spec_is_cli_safe(spec):
            unknown.append(token)
        elif spec.key not in seen:
            resolved.append((token, spec))
            seen.add(spec.key)
        else:
            pass
    return resolved, unknown


def _unify_birth_instant(inputs: ServiceResult) -> None:
    """Fill a missing profile timezone so each leg shares one civil instant."""
    if not inputs.get("birth_timezone"):
        resolved = resolve_birth_place_context(inputs.get("birth_place"))
        inputs["birth_timezone"] = resolved.timezone or DEFAULT_BIRTH_TIMEZONE
    else:
        pass


def run_profile(
    args: argparse.Namespace,
    subject_data: dict[str, object] | None,
    *,
    execute_tool: ProfileToolExecutor,
) -> int:
    controls = {
        name: getattr(args, name, None) for name in ExecutionOptions.model_fields
    }
    try:
        options = ExecutionOptions.model_validate(controls)
    except ValidationError as exc:
        return emit_error(
            correlate_error(validation_error_result(exc), safe_correlation(controls)), 1
        )
    raw: str | None = args.systems
    if raw is None:
        raw = DEFAULT_PROFILE_SYSTEMS
    else:
        pass
    tokens = [t.strip() for t in raw.split(",") if t.strip()]
    if not tokens:
        return emit_error(
            {
                "error": "--systems 至少需要一个体系或工具",
                "error_code": "usage_error",
                "retryable": False,
            },
            2,
        )
    else:
        pass
    resolved, unknown = _resolve_profile_systems(tokens)
    if unknown:
        return emit_error(
            {
                "error": (
                    f"未知体系/工具: {', '.join(unknown)}；"
                    "可用别名见 `fatebridge profile --help`，或用 `fatebridge list` 的命令名。"
                ),
                "error_code": "usage_error",
                "status_code": 400,
                "retryable": False,
            },
            2,
        )
    else:
        pass

    try:
        validate_subject_fields(subject_data, [spec for _, spec in resolved])
    except ValidationError as exc:
        return emit_error(correlate_error(validation_error_result(exc), options), 1)

    # note (precedence): Explicit CLI flags override subject values.
    inputs: ServiceResult = {}
    if subject_data:
        inputs.update(subject_data)
    else:
        pass
    for fname in PROFILE_PERSON_FIELDS:
        if fname in vars(args):
            inputs[fname] = getattr(args, fname)
        else:
            pass

    missing = [f for f in PROFILE_REQUIRED_FIELDS if inputs.get(f) is None]
    if missing:
        flags = ", ".join("--" + f.replace("_", "-") for f in missing)
        return emit_error(
            {
                "error": (
                    f"综合命盘缺少必填出生信息: {flags}（可由 --subject-file 提供）。"
                ),
                "error_code": "usage_error",
                "status_code": 400,
                "retryable": False,
            },
            2,
        )
    else:
        pass

    is_civil_clock = inputs.get("birth_clock_basis", "civil") == "civil"
    if is_civil_clock:
        _unify_birth_instant(inputs)
    else:
        pass

    root_metadata = attach_run_metadata({}, tool_name="profile")["run_metadata"]
    if options.trace_id is not None:
        root_metadata["trace_id"] = options.trace_id
    else:
        pass
    if options.parent_run_id is not None:
        root_metadata["parent_run_id"] = options.parent_run_id
    else:
        pass
    with call_clock(options.as_of) as clock:
        as_of = clock.instant.isoformat().replace("+00:00", "Z")
    child_options = ExecutionOptions(
        as_of=as_of,
        trace_id=root_metadata["trace_id"],
        parent_run_id=root_metadata["run_id"],
        detail=options.detail,
    )

    include_snapshot_text = getattr(args, "include_snapshot_text", None)
    requested_fields = list(args.fields) if args.fields else None
    profile: ServiceResult = {}
    has_error = False
    for token, spec in resolved:
        field_names = set(spec.request_model.model_fields)
        if not is_civil_clock:
            # note (clock basis): Pass solar labels to each request model for validation.
            field_names.add("birth_clock_basis")
        else:
            pass
        provided = {k: v for k, v in inputs.items() if k in field_names}
        prefix = f"profile.{token}."
        subpaths = (
            [
                path.removeprefix(prefix)
                for path in requested_fields
                if path.startswith(prefix)
            ]
            if requested_fields
            else []
        )
        whole_leg = not requested_fields or (
            "profile" in requested_fields or f"profile.{token}" in requested_fields
        )
        exec_fields = subpaths or None
        deliver_fields = None if whole_leg else (subpaths or None)
        leg_snapshot = (
            True
            if whole_leg
            and include_snapshot_text is None
            and any(p.partition(".")[0] == "snapshot_text" for p in subpaths)
            else include_snapshot_text
        )
        try:
            raw_result = execute_tool(
                spec,
                spec.request_model(**provided),
                options=child_options,
                include_metadata=not args.no_metadata,
                fields=exec_fields,
                include_snapshot_text=leg_snapshot,
            )
            failed = result_is_error(raw_result)
            result = deliver_response(
                raw_result,
                spec=spec,
                fields=deliver_fields,
                strict_fields=False,
                include_snapshot_text=leg_snapshot,
                response_char_limit=0,
                compact=args.compact,
                detail=options.detail,
                failed=failed,
            )
            if whole_leg and not failed:
                if (
                    any(p.partition(".")[0] == "run_metadata" for p in subpaths)
                    and "run_metadata" in raw_result
                ):
                    result["run_metadata"] = raw_result["run_metadata"]
                else:
                    pass
                if (
                    any(p.partition(".")[0] == "snapshot_export" for p in subpaths)
                    and "snapshot_export" in raw_result
                ):
                    result["snapshot_export"] = raw_result["snapshot_export"]
                else:
                    pass
            else:
                pass
        except Exception as exc:  # noqa: BLE001 - report each leg independently
            result = correlate_error(
                handle_calculation_error(exc, spec.operation_label_zh), child_options
            )
        if result_is_error(result):
            has_error = True
        else:
            pass
        profile[token] = result

    output: ServiceResult = {
        "analysis_type": "综合命盘",
        "systems": [token for token, _ in resolved],
        "profile": profile,
    }
    if not args.no_metadata:
        output["run_metadata"] = {**root_metadata, "effective_time": {"as_of": as_of}}
    else:
        pass
    if requested_fields:
        try:
            output = project_fields(
                output, requested_fields, strict_fields=args.strict_fields
            )
        except ParameterError as exc:
            return emit_error(correlate_error(exc.as_result(), options), 1)
        # note (projection): Keep failed legs visible under unrelated field selections.
        for token, _ in resolved:
            leg = profile[token]
            if result_is_error(leg):
                output.setdefault("profile", {})[token] = leg
            elif token in output.get("profile", {}) and "run_metadata" in leg:
                output["profile"][token]["run_metadata"] = leg["run_metadata"]
            else:
                pass
    else:
        pass
    try:
        output = bound_response(
            output,
            args.response_char_limit,
            compact=args.compact,
            selected_fields=requested_fields,
        )
    except ParameterError as exc:
        return emit_error(correlate_error(exc.as_result(), options), 1)
    print(format_json_response(output, compact=args.compact))
    return 1 if has_error else 0
