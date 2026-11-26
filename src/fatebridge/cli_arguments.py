"""Build CLI arguments from the public tool catalog and transport controls."""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Sequence
from pathlib import Path
from types import UnionType
from typing import Annotated, Literal, NoReturn, get_args, get_origin

from pydantic.fields import FieldInfo

UNION_ORIGINS = (UnionType, get_origin(Annotated[int, "u"] | None))

from fatebridge.application.description import is_model_field, spec_is_cli_safe
from fatebridge.application.tool_spec import ServiceResult, ToolSpec
from fatebridge.cli_inputs import profile_field_objects
from fatebridge.core.execution_context import ExecutionOptions
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.transports.flags import RESPONSE_LIMIT_DESC

BOOL_TRUE_TOKENS = {"true", "1", "yes", "y", "on"}
BOOL_FALSE_TOKENS = {"false", "0", "no", "n", "off"}


def emit_error(payload: ServiceResult, code: int) -> int:
    """Write an error envelope to stdout and return its exit status."""
    print(json.dumps(payload, ensure_ascii=False))
    return code


class _JsonErrorParser(argparse.ArgumentParser):
    """Write argparse usage errors as JSON on stdout and exit with status 2."""

    def __init__(
        self, *, prog: str | None = None, description: str | None = None
    ) -> None:
        super().__init__(prog=prog, description=description)
        # note (argparse): Accept negative scientific notation as a numeric argument.
        self._negative_number_matcher = re.compile(
            r"^-(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$"
        )

    def error(self, message: str) -> NoReturn:
        raise SystemExit(
            emit_error(
                {
                    "error": message,
                    "error_code": "usage_error",
                    "status_code": 400,
                    "retryable": False,
                },
                2,
            )
        )


class _BooleanFlagAction(argparse.Action):
    """Accept bare flags, negated flags and explicit boolean values."""

    def __init__(
        self,
        option_strings: list[str],
        dest: str,
        default: str | bool | None = None,
        required: bool = False,
        help: str | None = None,
    ) -> None:
        expanded: list[str] = []
        for option in option_strings:
            expanded.append(option)
            if option.startswith("--"):
                expanded.append("--no-" + option[2:])
        super().__init__(
            option_strings=expanded,
            dest=dest,
            nargs="?",
            default=default,
            required=required,
            help=help,
            metavar="{true,false}",
        )

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: str | Sequence[str] | None,
        option_string: str | None = None,
    ) -> None:
        is_negated = option_string is not None and option_string.startswith("--no-")
        if is_negated:
            if values is not None:
                parser.error(
                    f"{option_string} 为关闭开关，不接受取值（直接用 {option_string}）"
                )
            result = False
        elif values is None:
            result = True
        else:
            token = str(values).strip().lower()
            if token in BOOL_TRUE_TOKENS:
                result = True
            elif token in BOOL_FALSE_TOKENS:
                result = False
            else:
                parser.error(
                    f"{option_string} 的取值无法识别为布尔值：{values!r}"
                    "（用 true/false；或省略值表示 true、用 --no- 前缀表示 false）"
                )
        setattr(namespace, self.dest, result)


def _argument_type(annotation: object) -> object:
    """Unwrap field types for lexical parsing before Pydantic validates values."""
    if get_origin(annotation) is Annotated:
        return _argument_type(get_args(annotation)[0])
    # note (unions): Keep textual branches lexical so named house systems reach validation.
    if get_origin(annotation) in UNION_ORIGINS:
        members = [a for a in get_args(annotation) if a is not type(None)]
        resolved = [_argument_type(a) for a in members]
        if str in resolved:
            return str
        if resolved:
            return resolved[0]
    return annotation


def _parse_nullable_integer(value: str) -> int | None:
    """Keep missing list positions and preserve argparse's integer error text."""
    if value == "null":
        return None
    else:
        try:
            return int(value)
        except ValueError as error:
            raise argparse.ArgumentTypeError(f"invalid int value: {value!r}") from error


def _add_field_argument(
    parser: argparse.ArgumentParser,
    name: str,
    field: FieldInfo,
    *,
    relax_required: bool = False,
    json_structures: bool = False,
) -> None:
    annotation = _argument_type(field.annotation)
    origin = get_origin(annotation)
    required = field.is_required() and not relax_required
    # note (precedence): Keep only explicit flags so model defaults cannot mask file values.
    default = argparse.SUPPRESS
    flag = "--" + name.replace("_", "-")
    help_text = field.description or ""

    if origin is dict or (
        json_structures and (is_model_field(field.annotation) or origin is list)
    ):
        parser.add_argument(
            flag,
            dest=name,
            type=json.loads,
            default=default,
            required=required,
            help=help_text + "（JSON 对象或数组；也可使用 --request-file）",
        )
    elif annotation is bool:
        no_flag = flag.replace("--", "--no-", 1)
        bool_hint = f"开关；亦可写 {flag} true/false，关闭用 {no_flag}"
        bool_help = f"{help_text}（{bool_hint}）" if help_text else bool_hint
        parser.add_argument(
            flag,
            dest=name,
            action=_BooleanFlagAction,
            default=default,
            help=bool_help,
        )
    elif origin is list:
        list_members = get_args(annotation)
        element_annotation = list_members[0] if list_members else str
        element_type = _argument_type(element_annotation)
        if get_origin(element_type) is Literal:
            choices = get_args(element_type)
            element_type = (
                type(choices[0])
                if choices
                and all(type(choice) is type(choices[0]) for choice in choices)
                else str
            )
        is_nullable_integer = element_type is int and type(None) in get_args(
            element_annotation
        )
        scalar_type = (
            int if element_type is int else float if element_type is float else str
        )
        parser.add_argument(
            flag,
            dest=name,
            nargs="*",
            type=_parse_nullable_integer if is_nullable_integer else scalar_type,
            default=default,
            help=help_text,
        )
    else:
        parser.add_argument(
            flag,
            dest=name,
            type=int if annotation is int else float if annotation is float else str,
            default=default,
            required=required,
            help=help_text,
        )


def build_parser(
    relaxed_required: set[str] | None = None,
) -> argparse.ArgumentParser:
    relaxed = relaxed_required or set()
    parser = _JsonErrorParser(
        prog="fatebridge",
        description="FateBridge 命理/占星离线计算 CLI（数据驱动自中央工具目录）。",
    )
    parser.add_argument(
        "--no-metadata", action="store_true", help="不附加 run_metadata"
    )
    sub = parser.add_subparsers(dest="command", metavar="<tool>")

    listing = sub.add_parser("list", help="以文本列出工具，支持筛选")
    _add_discovery_flags(listing)
    discovery = sub.add_parser(
        "discover", help="先查看目录摘要，再按工具读取完整契约（JSON）"
    )
    _add_discovery_flags(discovery)
    discovery.add_argument(
        "--detail", choices=("index", "summary", "full"), default="summary"
    )
    describe_parser = sub.add_parser(
        "describe", help="输出某工具的参数 schema、可用接口与示例（JSON）"
    )
    describe_parser.add_argument(
        "tool", nargs="?", help="工具命令名（见 `fatebridge list`）"
    )
    describe_parser.add_argument(
        "--detail",
        choices=("input", "full"),
        default="full",
        help="input 只取输入契约及示例；full 还含输出契约",
    )

    result_reader = sub.add_parser(
        "result-read", help="核验存储完整性并分页读取原结果，不重算"
    )
    result_reader.add_argument("result_id")
    result_reader.add_argument("--run-id", help="指定原回执的 run_id。无回执时可省略。")
    result_reader.add_argument(
        "--path", help="对象或数组数字索引点路径；省略读取全文分页"
    )
    result_reader.add_argument("--offset", type=int, default=0)
    result_reader.add_argument(
        "--directory", type=Path, help="可选：原交付文件所在的私有目录；不创建目录"
    )

    doctor = sub.add_parser("doctor", help="检查安装；--mcp 验证独立 stdio 进程")
    doctor.add_argument("--mcp", action="store_true")
    doctor.add_argument("--family", help="检查这些 MCP 分类（CSV）")

    _add_profile_parser(sub)

    for spec in CATALOG:
        name = spec.tool_name
        is_cli_safe = spec_is_cli_safe(spec)
        sp = sub.add_parser(
            name,
            help=(
                spec.summary
                if is_cli_safe
                else f"{spec.summary}（请用 REST 或扁平命令）"
            ),
        )
        if not is_cli_safe:
            sp.set_defaults(
                _spec=spec, _cli_unsupported=True, _hint=_unsupported_hint(spec)
            )
            continue
        for fname, field in spec.request_model.model_fields.items():
            _add_field_argument(
                sp,
                fname,
                field,
                relax_required=fname in relaxed,
                json_structures=spec.cli_request_file,
            )
        if spec.cli_request_file:
            sp.add_argument(
                "--request-file",
                metavar="PATH",
                help="完整住宅请求 JSON 文件；显式字段参数覆盖文件中的同名顶层字段，仍按公开模型校验",
            )
        _add_transport_flags(sp)
        sp.set_defaults(_spec=spec)
    return parser


def _add_execution_flags(parser: argparse.ArgumentParser) -> None:
    for name, definition in ExecutionOptions.model_fields.items():
        parser.add_argument(
            "--" + name.replace("_", "-"),
            default=definition.default,
            help=definition.description,
            choices=(
                get_args(definition.annotation)
                if get_origin(definition.annotation) is Literal
                else None
            ),
        )


def _add_transport_flags(parser: argparse.ArgumentParser) -> None:
    """Attach execution, output and subject options to each tool command."""
    _add_execution_flags(parser)
    _add_output_flags(parser)
    parser.add_argument(
        "--subject-file",
        dest="subject_file",
        default=None,
        metavar="PATH",
        help="从 JSON/YAML 档案读取命主默认值；显式参数优先。",
    )


def _add_output_flags(parser: argparse.ArgumentParser) -> None:
    # note (precedence): Keep a --no-metadata seen before the subcommand.
    parser.add_argument(
        "--no-metadata",
        action="store_true",
        default=argparse.SUPPRESS,
        help="不附加 run_metadata",
    )
    parser.add_argument(
        "--strict-fields",
        action=_BooleanFlagAction,
        default=False,
        help="无效投影路径返回校验失败；默认使用宽松投影并附 projection_warnings",
    )
    parser.add_argument(
        "--fields",
        nargs="*",
        default=None,
        metavar="KEY",
        help=(
            "只输出这些字段（token 预算控制；run_metadata 始终保留）。"
            "支持顶层 key 或点号子路径，如 bazi_birth.day_master"
        ),
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        default=False,
        help="紧凑 JSON 输出（无缩进），便于脚本管道；默认美化缩进。",
    )
    parser.add_argument(
        "--response-char-limit", type=int, default=0, help=RESPONSE_LIMIT_DESC
    )
    parser.add_argument(
        "--include-snapshot-text",
        dest="include_snapshot_text",
        action=_BooleanFlagAction,
        default=None,
        help=(
            "是否包含人类可读的 snapshot_text 文本段（默认随工具而定）；"
            "用 --no-include-snapshot-text 关闭可显著省 token。"
        ),
    )


def _add_profile_parser(sub: argparse._SubParsersAction[_JsonErrorParser]) -> None:
    parser = sub.add_parser(
        "profile",
        help="综合命盘：一次为同一命主排多套盘（默认 八字/紫微/西占）",
    )
    _add_execution_flags(parser)
    _add_output_flags(parser)
    parser.add_argument(
        "--systems",
        default=None,
        metavar="LIST",
        help=(
            "逗号分隔的体系或工具，默认 bazi,ziwei,astro。"
            "支持别名（八字/紫微/西占/性格/事业/婚姻/健康/桃花）或直接用工具命令名。"
        ),
    )
    # note (profile): Check required fields after merging CLI and subject values.
    for fname, field in profile_field_objects().items():
        _add_field_argument(parser, fname, field, relax_required=True)
    parser.add_argument(
        "--subject-file",
        dest="subject_file",
        default=None,
        metavar="PATH",
        help="从 JSON/YAML 档案读取命主信息；命令行参数优先于档案值。",
    )
    parser.set_defaults(_profile=True)


def _unsupported_hint(spec: ToolSpec) -> str:
    target = spec.rest_path or (
        f"MCP 工具 {spec.mcp_name}" if spec.mcp_name else "REST/MCP 接口"
    )
    return f"该工具含嵌套结构，CLI 暂不支持；请改用 {target}。"


def _add_discovery_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--family", help="工具分类，可用逗号指定多个分类")
    parser.add_argument("--query", dest="q", help="按工具名称、分类和描述搜索")
    parser.add_argument("--tool", help="精确选择一个工具")
    parser.add_argument("--surface", choices=("rest", "mcp", "cli"))
