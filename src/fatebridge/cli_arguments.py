"""Build CLI arguments from the public tool catalog and transport controls."""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Sequence
from types import UnionType
from typing import TYPE_CHECKING, Annotated, Literal, NoReturn, get_args, get_origin

from fatebridge.application.tool_spec import ServiceResult
from fatebridge.services.tool_catalog import all_catalog, get_spec
from fatebridge.transports.flags import FIELDS_FLAG_DESC

if TYPE_CHECKING:
    from pydantic.fields import FieldInfo

    from fatebridge.application.tool_spec import ToolSpec

UNION_ORIGINS = (UnionType, get_origin(Annotated[int, "u"] | None))

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


def _is_nested_list(annotation: object) -> bool:
    from fatebridge.application.description import is_model_field, unwrap_optional

    if get_origin(annotation) is not list:
        return False
    members = get_args(annotation)
    if not members:
        return False
    element = unwrap_optional(_argument_type(members[0]))
    return is_model_field(element) or get_origin(element) is dict


def _add_field_argument(
    parser: argparse.ArgumentParser,
    name: str,
    field: FieldInfo,
    *,
    relax_required: bool = False,
) -> None:
    from fatebridge.application.description import is_model_field

    annotation = _argument_type(field.annotation)
    origin = get_origin(annotation)
    required = field.is_required() and not relax_required
    # note (precedence): Keep only explicit flags so model defaults cannot mask file values.
    default = argparse.SUPPRESS
    flag = "--" + name.replace("_", "-")
    help_text = field.description or ""

    if (
        origin is dict
        or is_model_field(field.annotation)
        or _is_nested_list(annotation)
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
    *,
    command: str | None = None,
) -> argparse.ArgumentParser:
    relaxed = relaxed_required or set()
    parser = _JsonErrorParser(
        prog="fatebridge",
        description="FateBridge 确定性计算 CLI（由中央工具目录动态生成）。",
    )
    sub = parser.add_subparsers(dest="command", metavar="<tool>")

    listing = sub.add_parser("list", help="以分类文本列出工具，支持筛选")
    _add_discovery_flags(listing)

    discovery = sub.add_parser(
        "discover", help="发现工具目录或读取指定工具的调用契约与示例（JSON）"
    )
    discovery.add_argument(
        "tool_pos",
        nargs="*",
        metavar="tool",
        help="可选：精确查询一个或多个工具的调用契约与示例（支持 batch）",
    )
    _add_discovery_flags(discovery)
    discovery.add_argument(
        "--tools",
        help="精确选择多个工具，可用逗号分隔",
    )
    discovery.add_argument(
        "--detail",
        choices=("brief", "summary", "full"),
        default="summary",
        help="brief 返回必填与字段类型极简契约；summary 返回摘要或单工具输入 schema；full 附带 output_fields",
    )
    discovery.add_argument(
        "--include-output-schema",
        action="store_true",
        default=False,
        help="与 --detail full 联用时附带完整 output_schema",
    )

    doctor = sub.add_parser("doctor", help="检查安装；--mcp 验证独立 stdio 进程")
    doctor.add_argument("--mcp", action="store_true")
    doctor.add_argument("--family", help="检查这些 MCP 分类（CSV）")

    batch = sub.add_parser(
        "batch",
        help="从 JSON 请求文件（或标准输入 -）批量执行多对象多工具计算；支持 --schema / --example",
    )
    batch.add_argument(
        "--request-file",
        required=False,
        default=None,
        metavar="PATH|-",
        help="批量计算 JSON 请求文件路径，或传 - 从标准输入读取",
    )
    batch.add_argument(
        "--schema",
        action="store_true",
        default=False,
        help="输出 batch 接口契约、限制与 BatchRequest JSON Schema",
    )
    batch.add_argument(
        "--example",
        action="store_true",
        default=False,
        help="输出可配合 --request-file 使用的批量计算示例 JSON",
    )

    target_specs: list[ToolSpec]
    if command is None or command == "__root__":
        target_specs = all_catalog()
    elif command in {"list", "discover", "doctor", "batch"}:
        target_specs = []
    else:
        matched_spec = get_spec(command)
        target_specs = [matched_spec] if matched_spec is not None else []

    for spec in target_specs:
        sp = sub.add_parser(spec.name, help=spec.summary)
        if command is not None and command != spec.name:
            continue
        for fname, field in spec.request_model.model_fields.items():
            _add_field_argument(
                sp,
                fname,
                field,
                relax_required=fname in relaxed,
            )
        sp.add_argument(
            "--request-file",
            metavar="PATH",
            help="完整 JSON 请求文件；显式字段参数覆盖文件中的同名顶层字段，按公开模型严格校验",
        )
        _add_transport_flags(sp)
        sp.set_defaults(_spec=spec)
    return parser


def _add_execution_flags(parser: argparse.ArgumentParser) -> None:
    from fatebridge.core.execution_context import ExecutionOptions

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
    """Attach shared execution and field-projection controls to each tool command."""
    _add_execution_flags(parser)
    parser.add_argument(
        "--fields",
        nargs="*",
        default=None,
        metavar="KEY",
        help=FIELDS_FLAG_DESC,
    )


def _add_discovery_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--family", help="工具分类，可用逗号指定多个分类")
    parser.add_argument("--query", dest="q", help="按工具名称、分类和描述搜索")
    parser.add_argument("--tool", help="精确选择一个工具")
    parser.add_argument("--surface", choices=("rest", "mcp", "cli"))
