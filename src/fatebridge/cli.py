"""Run catalog tools, capability discovery and diagnostics through the installed CLI."""

from __future__ import annotations

import json
import shlex
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from fatebridge.cli_arguments import build_parser, emit_error
from fatebridge.cli_inputs import preload_request
from fatebridge.services.tool_catalog import (
    all_catalog,
    get_spec,
    get_specs,
    known_tool_names,
)
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
    selected = all_catalog() if specs is None else specs
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
            "  discover [tool ...]            查看工具契约与示例（支持多工具、--detail brief 与 batch）"
        )
        lines.append("  doctor                         检查安装、依赖与 MCP 连通性")
    print("\n".join(lines))


def _attach_cli_examples(
    manifest: ServiceResult,
    *,
    specs_by_name: dict[str, ToolSpec] | None = None,
) -> ServiceResult:
    from fatebridge.application.examples import example_input

    def _annotate_entry(entry: dict[str, object], by_name: dict[str, ToolSpec]) -> None:
        tool_id = entry.get("tool")
        if not isinstance(tool_id, str):
            return
        spec = by_name.get(tool_id) or get_spec(tool_id)
        if spec is None:
            return
        example = entry.get("example_input") or example_input(spec)
        if isinstance(example, dict):
            entry["cli_example"] = _cli_example(spec, example)
            entry["example_note"] = "虚构演示资料；使用时替换为已确认的用户输入。"
        elif "input_schema" in entry:
            entry["cli_example"] = f"fatebridge {spec.name} --request-file request.json"

    by_name = specs_by_name if specs_by_name is not None else {}
    if "tools" in manifest:
        if not by_name:
            by_name = {spec.name: spec for spec in all_catalog()}
        for entry in manifest.get("tools", []):
            if isinstance(entry, dict):
                _annotate_entry(entry, by_name)
    elif isinstance(manifest.get("tool"), str):
        _annotate_entry(manifest, by_name)
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
        from fatebridge.application.execution import run_guarded_operation
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

        def _execute_cli_batch() -> ServiceResult:
            batch_request = BatchRequest.model_validate(batch_data)
            known = set(known_tool_names())
            requested_names = [call.tool for call in batch_request.calls]
            batch_specs = (
                get_specs(requested_names)
                if all(name in known for name in requested_names)
                else all_catalog()
            )
            return execute_batch(
                {spec.name: spec for spec in batch_specs},
                batch_request,
            )

        outcome = run_guarded_operation(
            "batch",
            _execute_cli_batch,
            allowed_fields=BatchRequest.model_fields.keys(),
            root_model=BatchRequest,
        )
        if outcome.failed:
            return emit_error(outcome.payload, 1)

        print(format_json_response(outcome.payload, compact=False))
        return 0

    if args.command in {"list", "discover"}:
        from fatebridge.application.discovery import (
            describe_batch_interface,
            discover_specs,
            select_specs,
        )
        from fatebridge.utils.errors import ParameterError

        pos_tools: list[str] = (
            list(getattr(args, "tool_pos", None) or [])
            if args.command == "discover"
            else []
        )
        flag_tool: str | None = args.tool
        flag_tools: str | None = (
            getattr(args, "tools", None) if args.command == "discover" else None
        )
        if pos_tools and (flag_tool is not None or flag_tools is not None):
            return emit_error(
                ParameterError(
                    "位置工具参数不能与 --tool / --tools 同时指定",
                    [{"path": "tools", "code": "conflicting_tool_filters"}],
                ).as_result(),
                1,
            )
        tool_name = pos_tools[0] if len(pos_tools) == 1 else flag_tool
        tools_csv = ",".join(pos_tools) if len(pos_tools) > 1 else flag_tools
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
                    and tools_csv is None
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
                requested_exact: list[str] = []
                if tool_name is not None:
                    requested_exact = [tool_name]
                elif tools_csv is not None:
                    requested_exact = [
                        part.strip() for part in tools_csv.split(",") if part.strip()
                    ]
                known = set(known_tool_names())
                if (
                    requested_exact
                    and args.family is None
                    and args.q is None
                    and all(name in known for name in requested_exact)
                ):
                    source_specs = get_specs(requested_exact)
                else:
                    source_specs = all_catalog()
                catalog = discover_specs(
                    source_specs,
                    tools=tools_csv,
                    detail=args.detail,
                    include_output_schema=args.include_output_schema,
                    **filters,
                )
                if (
                    tool_name is not None
                    or tools_csv is not None
                    or args.detail == "full"
                ):
                    _attach_cli_examples(
                        catalog,
                        specs_by_name={spec.name: spec for spec in source_specs},
                    )
                print(json.dumps(catalog, ensure_ascii=False, indent=2, default=str))
            else:
                selected = select_specs(all_catalog(), **filters)
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

    from fatebridge.application.execution import run_tool
    from fatebridge.utils.formatting import format_json_response

    field_names = set(spec.request_model.model_fields)
    explicit_fields = {k: v for k, v in vars(args).items() if k in field_names}
    provided = (
        {**request_data, **explicit_fields}
        if request_data is not None
        else explicit_fields
    )

    outcome = run_tool(
        spec,
        provided,
        include=args.include,
        fields=args.fields,
        as_of=getattr(args, "as_of", None),
    )
    if outcome.failed:
        return emit_error(outcome.payload, 1)
    print(format_json_response(outcome.payload, compact=False))
    return 0


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
