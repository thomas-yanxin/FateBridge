#!/usr/bin/env python3
from __future__ import annotations

"""
FateBridge FastMCP Server - 命运之桥：连接古典智慧与现代技术的命理工具

Provides Chinese metaphysics and offline astrology functionality via FastMCP:
1. analyze_destiny - Individual destiny analysis
2. two_person_compatibility - Compatibility analysis between two people
3. timing_analysis - Comprehensive timing (luck period) analysis
4. astro_chart family - Core chart, relative chart, and derived chart overlays
5. export_registry / export_parse - FateBridge export helpers
6. knowledge_registry / knowledge_read - Bundled hover-knowledge helpers
7. jieqi_year / nongli_time - Calendar helper tools
8. gua_lookup / gua_meiyi - Offline trigram/hexagram lookup helpers
9. meihua_analysis - Mei Hua Yi Shu time-seeded divination
10. tongshefa - Local tongshefa analysis
11. sixyao - Local six-yao analysis
12. suzhan - Local lunar-mansion chart output
13. otherbu - Local astrology-dice output
14. sanshiunited - Local Sanshi aggregation output
15. bazi_birth - Standalone BaZi birth chart snapshot
16. liushi_analysis - Standalone flow-hour timing snapshot
17. solarreturn - Standalone solar return snapshot
18. lunarreturn - Standalone lunar return snapshot
19. transit - Standalone transit snapshot
20. solararc - Standalone solar arc snapshot
21. givenyear - Standalone given-year chart snapshot
22. profection - Standalone annual profection snapshot
23. pd - Standalone primary-directions snapshot
24. pdchart - Standalone primary-direction chart snapshot
25. zr - Standalone zodiacal releasing snapshot
26. firdaria - Standalone firdaria snapshot
27. decennials - Standalone decennials snapshot
"""

import logging
import os
from typing import Any, Dict, Optional

from fastmcp import FastMCP
from fastmcp.tools import ToolResult

from fatebridge import __version__ as APP_VERSION
from fatebridge.mcp_transport import protocol_result
from fatebridge.services.run_metadata import attach_run_metadata
from fatebridge.utils.errors import error_response_payload
from fatebridge.utils.formatting import (
    _prepare_json_response_payload,
    format_json_response,
)
from fatebridge.utils.runtime import get_log_level, load_runtime_env

# ============================================================================
# Logging Setup
# ============================================================================

load_runtime_env()

logging.basicConfig(
    level=getattr(logging, get_log_level(), logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


# =============================================================================
# FastMCP 应用配置
# =============================================================================

_MCP_INSTRUCTIONS = (
    "FateBridge 提供本地计算数据。先回答用户本次问题，用普通语言给出清楚的判断和依据。"
    "用户无需掌握专业术语、经纬度、罗盘定宫或接口字段；助手负责将日常描述转成所选工具的输入。"
    "已连接时直接进入咨询；用户未要求开发排错时，不搜仓库或运行安装诊断。"
    "必要资料按所选工具和当前所问计算核对，不收集完整专业档案。"
    "工具支持从地点推断时区或坐标时使用其解析结果；可选精度资料不自动升级为必答门槛。"
    "只有缺项确实改变当前结论时，才用日常问法一次简短追问；用户不知道时说明影响并继续已有可答部分，不反复索取同一资料。"
    "八字/紫微出生排盘需有效历法、日期和出生小时；不猜未知生时，不填0或套示例。"
    "只有时段时保留不确定性，不沿用确定时刻结果；当前没有无时盘接口，可先解释不依赖生时的范围与可选路径。"
    "命卦可用birth_date，非立春当日无需出生小时；不将出生排盘门槛套用其他计算。"
    "先交付已有依据支持的结论和注明条件的解释；partial、候选观察或动作未ready不等于整题不能回答。"
    "计算所需事实、可选精度提升和动作执行确认分别处理；许可、容纳及通行等只约束实际落实，不阻塞普通解释。"
    "照片按候选观察作条件解释，不升级为用户确认；未实现或无规则的范围直接说明，不靠反复补资料替代能力。"
    "计算事实以工具返回为准；可结合场景技能及有来源的传统知识解释含义与权衡，注明来源与适用范围，不补造计算结果或规则处方。"
    "分清计算结果、传统解释和现实建议；边界在相关处简述一次，不用重复免责声明代替分析。"
    "各场景细则依对应技能与工具说明，风水专项输入不作为其他咨询门槛。"
    "双人关系未说明类型时用general，不从性别推断婚姻。"
    "先按共享硬边界检查请求：禁止生死寿命、重大灾祸断言、临床诊断治疗与医疗择时；不先计算再加免责声明。"
    "健康只解释盘内分类与传统对应，不从命盘推中医体质、器官、症状或病种，不把文化观点包装成科学证据。"
    "按用户本轮主题、对象、任务、时间范围与深度选择依据；不自动展开所有相关项，明确全面请求首轮就覆盖。"
    "专题综合主动评估有新增价值的相关视角，通常两套即可但不设数量配额；单项或限定方法可以一套。"
    "时间贯穿各主题，大运流年、紫微运限、法达等按阶段和实际粒度选择，候选时刻与事件发生时间分开。"
    "追问保留原主题、方法和已有视角，只补新增范围，不因转主题专项就退回固定单体系。"
    "信息足够且公开Schema清楚时直接调用，新增工具须补未回答的问题或独立层；仅工具或参数仍有歧义时查询对应场景或工具契约。"
    "代码模式检索ALL_TOOLS按工具名一次取得所需完整定义，不重复发现或输出所有候选。"
    "常规首轮使用建议fields、strict_fields=true、include_snapshot_text=false；完整导出首次fields=null，保留同一run，不用摘要重算全文。"
    "后续计算沿用trace_id/parent_run_id；更正资料时替换旧事实并重建受影响输入，只解释未变结果无需重算。"
    "isError=true按error_code/issues修正，仅retryable=true才重试。"
    "常规首轮约200–300字，给2–3条依据和一项现实建议，详细请求按需展开；技术回执留在工具结果。"
    "精度警告和体系分歧按实际影响简述；分数不当成功概率，不替用户决定辞职或关系成败。"
)


def _tool_response_payload(
    data: Dict[str, Any],
    *,
    compact: bool = True,
    include_snapshot_text: bool = True,
    fields: Optional[list] = None,
    strict_fields: bool = False,
    tool_name: Optional[str] = None,
) -> Dict[str, Any]:
    # tool_name is supplied by the catalog registrar (spec.run_metadata_name);
    # the neutral fallback only guards a stray non-catalog caller.
    payload = attach_run_metadata(data, tool_name=tool_name or "unknown_tool")
    # Project AFTER run_metadata is attached so provenance survives a field
    # selection (project_fields always keeps run_metadata).
    payload = project_fields(payload, fields, strict_fields=strict_fields)
    return _prepare_json_response_payload(
        payload,
        include_snapshot_text=include_snapshot_text,
    )


def _render_protocol_response(data: Dict[str, Any], **flags: Any) -> ToolResult:
    from fatebridge.application.result_delivery import bound_response

    limit = flags.pop("response_char_limit", 8192)
    payload = _tool_response_payload(data, **flags)
    payload = bound_response(payload, limit, compact=flags.get("compact", True))
    return protocol_result(
        payload,
        failed=False,
        text=format_json_response(payload, compact=flags.get("compact", True)),
    )


def _render_protocol_error(
    data: Dict[str, Any], operation: str, *, compact: bool = True
) -> ToolResult:
    payload = error_response_payload(data, operation)
    return protocol_result(
        payload, failed=True, text=format_json_response(payload, compact=compact)
    )


# ============================================================================
# Tool registration — every tool is declared once in the central catalog and
# auto-registered here. To add a tool, edit fatebridge/services/tool_catalog.py.
# ============================================================================

from fatebridge.application.discovery import select_specs
from fatebridge.application.projection import project_fields
from fatebridge.mcp_transport import (  # noqa: E402
    register_discovery_resources,
)
from fatebridge.services.tool_catalog import CATALOG  # noqa: E402
from fatebridge.transports.mcp import register_mcp


def create_mcp_app(
    families: Optional[str] = None,
    scenarios: Optional[str] = None,
) -> FastMCP:
    """Host-level family profiles; an omitted profile retains every MCP tool."""
    server = FastMCP(
        name="fatebridge",
        instructions=_MCP_INSTRUCTIONS,
        version=APP_VERSION,
        dereference_schemas=False,
    )
    exposed = select_specs(CATALOG, family=families, scenario=scenarios, surface="mcp")
    register_mcp(
        server,
        exposed,
        render_response=_render_protocol_response,
        render_error=_render_protocol_error,
    )
    register_discovery_resources(server, CATALOG, exposed)
    return server


app = create_mcp_app(
    os.getenv("FATEBRIDGE_MCP_FAMILIES") or None,
    os.getenv("FATEBRIDGE_MCP_SCENARIOS") or None,
)


def main() -> None:
    app.run(show_banner=False)


if __name__ == "__main__":
    main()
