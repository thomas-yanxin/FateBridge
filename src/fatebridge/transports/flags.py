"""Shared descriptions of transport output controls."""

from typing import Annotated, Literal, Union

from pydantic import Field

from fatebridge.application.result_delivery import DEFAULT_MCP_RESPONSE_CHARS

# The public schema must express the same disjoint budget as the renderer.
ResponseCharLimit = Union[Literal[0], Annotated[int, Field(ge=4096, le=65536)]]

COMPACT_FLAG_DESC = "紧凑 JSON 输出（无缩进）；设为 false 则美化缩进。默认 true。"
SNAPSHOT_FLAG_DESC = (
    "是否包含人类可读的 snapshot_text 文本段（默认随工具而定）；"
    "设为 false 可显著减少返回的 token 数。"
)
FIELDS_FLAG_DESC = (
    "仅返回选定字段以节省 token：接受顶层键（如 'snapshot_text'）或点路径"
    "子字段（如 'bazi_birth.day_master'）。run_metadata 始终保留；留空请求全部字段，"
    "超出响应字符预算的部分由 result_delivery 保留供读取。"
    "无效路径默认附 projection_warnings；strict_fields=true 时拒绝。"
)
STRICT_FIELDS_DESC = "是否拒绝无效 fields 路径；默认 false，使用宽松投影并返回警告。"
RESPONSE_LIMIT_DESC = (
    f"完整 JSON 响应字符预算：0 不限制，或 4096–65536。MCP 默认 {DEFAULT_MCP_RESPONSE_CHARS}，REST/CLI 默认 0。"
    "超限不截断数据，返回 result_delivery 完整结果引用和可读取字段；"
    "按 manifest_uri 或字段分页读取原 run 的数据，不要重新计算或解析单页为完整文档。"
)
