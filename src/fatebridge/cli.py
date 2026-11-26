"""Run catalog tools, capability discovery and diagnostics through the installed CLI."""

from __future__ import annotations

import json
import shlex

from fatebridge.application.discovery import discover_specs, select_specs
from fatebridge.application.examples import example_input
from fatebridge.application.execution import execute_with_receipt, result_is_error
from fatebridge.application.response_delivery import deliver_response
from fatebridge.application.tool_spec import ServiceResult, ToolSpec
from fatebridge.cli_arguments import build_parser, emit_error
from fatebridge.cli_inputs import preload_request
from fatebridge.core.execution_context import ExecutionOptions
from fatebridge.diagnostics import diagnose
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.utils.errors import ParameterError, handle_calculation_error
from fatebridge.utils.formatting import format_json_response
from fatebridge.utils.runtime import load_runtime_env

__all__ = ["build_parser", "main", "run"]


def _cli_example(spec: ToolSpec, inputs: ServiceResult) -> str:
    parts = ["fatebridge", spec.name]
    for name, value in inputs.items():
        parts.append("--" + name.replace("_", "-"))
        if isinstance(value, bool):
            parts.append(str(value).lower())
        elif isinstance(value, (dict, list)) and (
            spec.cli_request_file
            or isinstance(value, dict)
            or any(isinstance(item, dict) for item in value)
        ):
            parts.append(json.dumps(value, ensure_ascii=False))
        elif isinstance(value, list):
            parts.extend(str(item) for item in value)
        else:
            parts.append(str(value))
    return shlex.join(parts)


def _print_tools(specs: list[ToolSpec] | None = None) -> None:
    selected = CATALOG if specs is None else specs
    grouped: dict[str, list[ToolSpec]] = {}
    for spec in selected:
        grouped.setdefault(spec.family, []).append(spec)
    lines = ["可用工具命令："]
    for family, items in grouped.items():
        lines.append(f"\n[{family}] ({len(items)})")
        for spec in items:
            lines.append(f"  {spec.name:<30} {spec.operation_label_zh}")
    print("\n".join(lines))


def _attach_cli_examples(manifest: ServiceResult) -> ServiceResult:
    by_name = {spec.name: spec for spec in CATALOG}
    for entry in manifest.get("tools", []):
        if not isinstance(entry, dict):
            continue
        spec = by_name.get(entry.get("tool", ""))
        if spec is None:
            continue
        example = entry.get("example_input") or example_input(spec)
        if isinstance(example, dict):
            entry["cli_example"] = _cli_example(spec, example)
            entry["example_note"] = "虚构演示资料；使用时替换为已确认的用户输入。"
        elif "input_schema" in entry:
            entry["cli_example"] = f"fatebridge {spec.name} --request-file request.json"
    return manifest


def run(argv: list[str] | None = None) -> int:
    """Load runtime configuration and dispatch the requested CLI command."""
    load_runtime_env()
    try:
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
    relaxed = set(request_data) if request_data is not None else set()
    parser = build_parser(relaxed)
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        # note (argparse): The parser has already emitted help or a JSON usage error.
        return int(exc.code) if exc.code is not None else 0

    if not args.command:
        _print_tools()
        return 0

    if args.command in {"list", "discover"}:
        tool_name = getattr(args, "tool_pos", None) or args.tool
        filters = {
            "family": args.family,
            "q": args.q,
            "tool": tool_name,
            "surface": args.surface,
        }
        try:
            if args.command == "discover":
                catalog = discover_specs(CATALOG, detail=args.detail, **filters)
                if tool_name is not None or args.detail == "full":
                    _attach_cli_examples(catalog)
                print(json.dumps(catalog, ensure_ascii=False, indent=2, default=str))
            else:
                selected = select_specs(CATALOG, **filters)
                _print_tools(selected)
        except ParameterError as exc:
            return emit_error(exc.as_result(), 2 if exc.status_code == 404 else 1)
        return 0

    if args.command == "doctor":
        result = diagnose(
            mcp=args.mcp,
            family=args.family,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["ok"] else 1

    spec: ToolSpec | None = getattr(args, "_spec", None)
    if spec is None:
        parser.error(f"未知工具: {args.command}")
        return 2

    field_names = set(spec.request_model.model_fields)
    explicit_fields = {
        k: v for k, v in vars(args).items() if k in field_names
    }
    provided = (
        {**request_data, **explicit_fields}
        if request_data is not None
        else explicit_fields
    )

    try:
        controls = {
            name: getattr(args, name, None) for name in ExecutionOptions.model_fields
        }
        options = ExecutionOptions.model_validate(controls)
        request = spec.request_model(**provided)
        result = execute_with_receipt(
            spec,
            request,
            options=options,
        )
    except Exception as exc:  # noqa: BLE001 - translate failures at the CLI boundary
        return emit_error(
            handle_calculation_error(exc, spec.operation_label_zh),
            1,
        )

    is_error = result_is_error(result)

    try:
        result = deliver_response(
            result,
            spec=spec,
            fields=args.fields,
            detail=options.detail,
            failed=is_error,
        )
    except ParameterError as exc:
        return emit_error(exc.as_result(), 1)
    print(format_json_response(result, compact=False))
    return 1 if is_error else 0


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
