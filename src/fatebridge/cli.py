"""Run catalog tools and diagnostics through the installed CLI."""

from __future__ import annotations

import argparse
import json
import shlex

from pydantic import ValidationError

from fatebridge.application.description import describe_input_spec, describe_spec
from fatebridge.application.description import field_type_name as _type_name
from fatebridge.application.description import resolve_spec
from fatebridge.application.description import spec_is_cli_safe as _cli_safe
from fatebridge.application.discovery import discover_specs, select_specs
from fatebridge.application.examples import example_input
from fatebridge.application.execution import (
    execute_tool,
    result_is_error,
)
from fatebridge.application.response_delivery import deliver_response
from fatebridge.application.result_delivery import RESULT_STORE, ResultStore
from fatebridge.application.tool_spec import ServiceResult, ToolSpec
from fatebridge.cli_arguments import _unsupported_hint, build_parser, emit_error
from fatebridge.cli_inputs import (
    preload_request,
    preload_subject,
    validate_subject_fields,
)
from fatebridge.cli_profile import run_profile
from fatebridge.core.execution_context import (
    ExecutionOptions,
    correlate_error,
    safe_correlation,
)
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.utils.errors import (
    ParameterError,
    handle_calculation_error,
)
from fatebridge.utils.formatting import format_json_response
from fatebridge.utils.runtime import load_runtime_env

__all__ = ["build_parser", "main", "run"]


def _describe_spec(spec: ToolSpec, detail: str = "full") -> ServiceResult:
    """Add shell usage and an example to the shared tool descriptor."""
    descriptor = describe_input_spec(spec) if detail == "input" else describe_spec(spec)
    if descriptor["surfaces"]["cli"]:
        descriptor["cli_usage"] = _cli_usage(spec)
        example = example_input(spec)
        if example is not None:
            descriptor["example_input"] = example
            descriptor["cli_example"] = _cli_example(spec, example)
            descriptor["example_note"] = "虚构演示资料；使用时替换为已确认的用户输入。"
        else:
            pass
    else:
        descriptor["cli_hint"] = _unsupported_hint(spec)
    return descriptor


def _cli_usage(spec: ToolSpec) -> str:
    """Syntax template, explicitly distinct from a runnable example."""
    parts = ["fatebridge", spec.tool_name]
    if spec.cli_request_file:
        return " ".join(parts + ["--request-file request.json"])
    else:
        pass
    for name, field in spec.request_model.model_fields.items():
        if field.is_required():
            flag = "--" + name.replace("_", "-")
            parts.append(f"{flag} <{_type_name(field.annotation)}>")
        else:
            pass
    return " ".join(parts)


def _cli_example(spec: ToolSpec, inputs: ServiceResult) -> str:
    parts = ["fatebridge", spec.tool_name]
    for name, value in inputs.items():
        parts.append("--" + name.replace("_", "-"))
        if isinstance(value, bool):
            parts.append(str(value).lower())
        elif isinstance(value, (dict, list)) and spec.cli_request_file:
            parts.append(json.dumps(value, ensure_ascii=False))
        elif isinstance(value, list):
            parts.extend(str(item) for item in value)
        else:
            parts.append(str(value))
    return shlex.join(parts)


def _print_tools(names: set[str] | None = None) -> None:
    rows = []
    for spec in CATALOG:
        if names is not None and spec.tool_name not in names:
            continue
        else:
            pass
        mark = "" if _cli_safe(spec) else "  (CLI 不支持: 含嵌套结构)"
        rows.append(f"  {spec.tool_name:<28} {spec.operation_label_zh}{mark}")
    print("可用工具命令：\n" + "\n".join(rows))


def _run_describe(tool_name: str | None, detail: str = "full") -> int:
    if not tool_name:
        return emit_error(
            {
                "error": "用法: fatebridge describe <tool>；运行 `fatebridge list` 查看所有工具",
                "error_code": "usage_error",
                "status_code": 400,
                "retryable": False,
            },
            2,
        )
    else:
        pass
    spec = resolve_spec(CATALOG, tool_name)
    if spec is None:
        return emit_error(
            {
                "error": f"未知工具: {tool_name}",
                "error_code": "unknown_tool",
                "status_code": 404,
                "retryable": False,
            },
            2,
        )
    else:
        pass
    print(
        json.dumps(
            _describe_spec(spec, detail), ensure_ascii=False, indent=2, default=str
        )
    )
    return 0


def run(argv: list[str] | None = None) -> int:
    """Load runtime configuration and dispatch the requested CLI command."""
    load_runtime_env()
    try:
        subject_data = preload_subject(argv)
        request_data = preload_request(argv)
    except ValueError as error:
        return emit_error(
            {
                "error": str(error),
                "error_code": "usage_error",
                "status_code": 400,
                "retryable": False,
            },
            2,
        )
    relaxed = set(subject_data) if subject_data else set()
    if request_data is not None:
        relaxed.update(request_data)
    else:
        pass
    parser = build_parser(relaxed)
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        # note (argparse): The parser has already emitted help or a JSON usage error.
        return int(exc.code) if exc.code is not None else 0

    if not args.command:
        _print_tools()
        return 0
    else:
        pass

    if args.command == "result-read":
        try:
            store = (
                ResultStore(args.directory)
                if args.directory is not None
                else RESULT_STORE
            )
            if args.run_id is None:
                page = store.page(
                    args.result_id, args.offset, args.path, verify_integrity=True
                )
            else:
                page = store.verified_page(
                    args.result_id, args.run_id, args.offset, args.path
                )
        except ParameterError as exc:
            return emit_error(exc.as_result(), 1)
        print(json.dumps(page, ensure_ascii=False, separators=(",", ":")))
        return 0
    else:
        pass

    if args.command in {"list", "discover"}:
        filters = {
            "family": args.family,
            "q": args.q,
            "tool": args.tool,
            "surface": args.surface,
        }
        try:
            if args.command == "discover":
                catalog = discover_specs(CATALOG, detail=args.detail, **filters)
                print(json.dumps(catalog, ensure_ascii=False, indent=2))
            else:
                selected = select_specs(CATALOG, **filters)
                _print_tools({spec.tool_name for spec in selected})
        except ParameterError as exc:
            return emit_error(exc.as_result(), 1)
        return 0
    else:
        pass

    if args.command == "describe":
        return _run_describe(args.tool, args.detail)
    else:
        pass

    if args.command == "doctor":
        # note (startup): Ordinary tool calls do not need installation diagnostics.
        from fatebridge.diagnostics import diagnose

        result = diagnose(
            mcp=args.mcp,
            family=args.family,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["ok"] else 1
    else:
        pass

    if args.command == "profile":
        return run_profile(args, subject_data, execute_tool=execute_tool)
    else:
        pass

    spec: ToolSpec | None = getattr(args, "_spec", None)
    if spec is None:
        parser.error(f"未知工具: {args.command}")
        return 2
    else:
        pass

    if getattr(args, "_cli_unsupported", False):
        return emit_error(
            {
                "error": getattr(args, "_hint", "该工具 CLI 暂不支持。"),
                "error_code": "cli_unsupported",
                "status_code": 400,
                "retryable": False,
            },
            2,
        )
    else:
        pass

    field_names = set(spec.request_model.model_fields)
    provided = {
        k: v for k, v in vars(args).items() if k in field_names and v is not None
    }
    explicit_fields = dict(provided)

    # note (precedence): Subject defaults fill only fields absent from explicit CLI flags.
    if subject_data:
        defaults = {
            k: v
            for k, v in subject_data.items()
            if k in field_names and k not in provided
        }
        provided = {**defaults, **provided}
    else:
        pass

    if request_data is not None and spec.cli_request_file:
        # note (validation): Model validation must see unknown request-file fields.
        provided = {**provided, **request_data, **explicit_fields}
    else:
        pass

    include_snapshot_text = args.include_snapshot_text
    try:
        controls = {
            name: getattr(args, name, None) for name in ExecutionOptions.model_fields
        }
        options = ExecutionOptions.model_validate(controls)
        validate_subject_fields(subject_data, [spec])
        request = spec.request_model(**provided)
        result = execute_tool(
            spec,
            request,
            options=options,
            include_metadata=not args.no_metadata,
            fields=args.fields,
            include_snapshot_text=include_snapshot_text,
        )
    except Exception as exc:  # noqa: BLE001 - translate failures at the CLI boundary
        return emit_error(
            correlate_error(
                handle_calculation_error(exc, spec.operation_label_zh),
                safe_correlation(controls),
            ),
            1,
        )

    is_error = result_is_error(result)

    try:
        result = deliver_response(
            result,
            spec=spec,
            fields=args.fields,
            strict_fields=args.strict_fields,
            include_snapshot_text=include_snapshot_text,
            response_char_limit=args.response_char_limit,
            compact=args.compact,
            detail=options.detail,
            failed=is_error,
        )
    except ParameterError as exc:
        return emit_error(correlate_error(exc.as_result(), options), 1)
    print(format_json_response(result, compact=args.compact))
    return 1 if is_error else 0


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
else:
    pass
