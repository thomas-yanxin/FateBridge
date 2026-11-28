"""Shared CLI, REST, and MCP help strings for response delivery controls."""

FIELDS_FLAG_DESC = (
    "仅返回选定字段：接受顶层键或点号子路径（如 'bazi_birth.day_master'），"
    "与 include 互斥；严格校验路径，无效报错并提示可用字段；run_metadata 始终保留。"
)

INCLUDE_FLAG_DESC = (
    "在默认输出基础上追加路径、evidence_views 视图名或 '*'（无损全量）；"
    "与 fields 互斥；支持 '*' 通配，无效报错并提示可用字段与建议。"
)
