"""Run catalog tools, capability discovery and diagnostics through the installed CLI."""

from __future__ import annotations

import json
import shlex
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from fatebridge.cli_arguments import build_parser, emit_error
from fatebridge.cli_inputs import preload_request
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.utils.runtime import load_runtime_env

if TYPE_CHECKING:
    from fatebridge.application.tool_spec import ServiceResult, ToolSpec

__all__ = ["build_parser", "main", "run"]


def _cli_command_token(argv: list[str] | None) -> str:
    tokens = sys.argv[1:] if argv is None else argv
    for token in tokens:
        if token in {"-h", "--help"}:
            return "__root__"
        if not token.startswith("-"):
            return token
    return "__root__"


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


def _print_tools(
    specs: list[ToolSpec] | None = None, *, include_footer: bool = True
) -> None:
    selected = CATALOG if specs is None else specs
    grouped: dict[str, list[ToolSpec]] = {}
    for spec in selected:
        grouped.setdefault(spec.family, []).append(spec)
    lines = ["可用工具命令："]
    for family, items in grouped.items():
        lines.append(f"\n[{family}] ({len(items)})")
        for spec in items:
            lines.append(f"  {spec.name:<30} {spec.operation_label_zh}")
    if include_footer:
        lines.append("\n[commands] 辅助与批量命令")
        lines.append(
            "  batch                          多对象多工具批量计算（--schema / --example / --request-file PATH|-）"
        )
        lines.append(
            "  discover [tool]                查看工具契约与示例（支持 discover batch）"
        )
        lines.append("  doctor                         检查安装、依赖与 MCP 连通性")
    print("\n".join(lines))


def _attach_cli_examples(manifest: ServiceResult) -> ServiceResult:
    from fatebridge.application.examples import example_input

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


def _load_batch_payload(request_file: str) -> dict[str, object]:
    try:
        raw_text = (
            sys.stdin.read()
            if request_file == "-"
            else Path(request_file).expanduser().read_text(encoding="utf-8")
        )
        data = json.loads(raw_text)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("request-file 必须为可读的合法 JSON 文件或标准输入") from exc
    if not isinstance(data, dict):
        raise ValueError("request-file 顶层必须是 JSON 对象")
    return data


def run(argv: list[str] | None = None) -> int:
    """Load runtime configuration and dispatch the requested CLI command."""
    load_runtime_env()
    command = _cli_command_token(argv)
    request_data: dict[str, object] | None = None
    if command != "batch":
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
    parser = build_parser(relaxed, command=command)
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        # note (argparse): The parser has already emitted help or a JSON usage error.
        return int(exc.code) if exc.code is not None else 0

    if not args.command:
        _print_tools()
        return 0

    if args.command == "batch":
        from fatebridge.application.batch import BatchRequest, execute_batch
        from fatebridge.application.discovery import describe_batch_interface
        from fatebridge.utils.errors import handle_calculation_error
        from fatebridge.utils.formatting import format_json_response

        if args.schema:
            print(json.dumps(describe_batch_interface(), ensure_ascii=False, indent=2))
            return 0
        if args.example:
            print(
                json.dumps(
                    describe_batch_interface()["example_input"],
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0
        if not args.request_file:
            return emit_error(
                {
                    "error": "batch 需要提供 --request-file PATH|-、--schema 或 --example",
                    "error_code": "usage_error",
                    "status_code": 400,
                    "retryable": False,
                },
                2,
            )

        try:
            batch_data = _load_batch_payload(args.request_file)
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

        try:
            batch_request = BatchRequest.model_validate(batch_data)
            payload = execute_batch(
                {spec.name: spec for spec in CATALOG},
                batch_request,
            )
        except (
            Exception
        ) as exc:  # noqa: BLE001 - translate failures at the CLI boundary
            return emit_error(
                handle_calculation_error(
                    exc,
                    "batch",
                    allowed_fields=BatchRequest.model_fields.keys(),
                ),
                1,
            )

        print(format_json_response(payload, compact=False))
        return 0

    if args.command in {"list", "discover"}:
        from fatebridge.application.discovery import (
            describe_batch_interface,
            discover_specs,
            select_specs,
        )
        from fatebridge.utils.errors import ParameterError

        tool_name = getattr(args, "tool_pos", None) or args.tool
        filters = {
            "family": args.family,
            "q": args.q,
            "tool": tool_name,
            "surface": args.surface,
        }
        try:
            if args.command == "discover":
                if (
                    tool_name == "batch"
                    and args.family is None
                    and args.q is None
                    and args.surface is None
                ):
                    print(
                        json.dumps(
                            describe_batch_interface(),
                            ensure_ascii=False,
                            indent=2,
                            default=str,
                        )
                    )
                    return 0
                catalog = discover_specs(
                    CATALOG,
                    detail=args.detail,
                    include_output_schema=args.include_output_schema,
                    **filters,
                )
                if tool_name is not None or args.detail == "full":
                    _attach_cli_examples(catalog)
                print(json.dumps(catalog, ensure_ascii=False, indent=2, default=str))
            else:
                selected = select_specs(CATALOG, **filters)
                _print_tools(selected, include_footer=not any(filters.values()))
        except ParameterError as exc:
            return emit_error(exc.as_result(), 2 if exc.status_code == 404 else 1)
        return 0

    if args.command == "doctor":
        from fatebridge.diagnostics import diagnose

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

    from fatebridge.application.execution import execute_with_receipt, result_is_error
    from fatebridge.application.response_delivery import deliver_response
    from fatebridge.core.execution_context import ExecutionOptions
    from fatebridge.utils.errors import ParameterError, handle_calculation_error
    from fatebridge.utils.formatting import format_json_response

    field_names = set(spec.request_model.model_fields)
    explicit_fields = {k: v for k, v in vars(args).items() if k in field_names}
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
            handle_calculation_error(
                exc,
                spec.operation_label_zh,
                allowed_fields=spec.request_model.model_fields.keys(),
            ),
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
