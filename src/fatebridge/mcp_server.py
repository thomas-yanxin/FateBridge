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
from typing import Optional

from fastmcp import FastMCP
from fastmcp.tools import ToolResult

from fatebridge import __version__ as APP_VERSION
from fatebridge.application.response_delivery import deliver_response
from fatebridge.application.result_delivery import DEFAULT_MCP_RESPONSE_CHARS
from fatebridge.application.tool_spec import ServiceResult
from fatebridge.mcp_transport import protocol_result
from fatebridge.utils.errors import error_response_payload
from fatebridge.utils.formatting import format_json_response
from fatebridge.utils.runtime import get_log_level, load_runtime_env

load_runtime_env()

logging.basicConfig(
    level=getattr(logging, get_log_level(), logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


_MCP_INSTRUCTIONS = (
    "FateBridge 提供本地计算，助手按当前问题选择工具并解释实际结果。"
    "计算前排除生死寿命、灾祸断言、临床诊断治疗和医疗择时。"
    "只用已确认资料，不猜生时、不套默认或示例；必要缺项简短追问，未知后继续已有可答部分。"
    "区分计算、传统解释和现实建议；分数不是成功概率。"
    "已连接且定义清楚时直接调用，不为咨询查仓库或运行诊断。"
    "按当前问题、指定方法和实际时间范围选择公开能力；照片是候选，partial 只限制对应层，动作许可不阻塞普通解释。"
    "摘要按任务视图选 fields，strict_fields=true、include_snapshot_text=false；"
    "完整导出首次 fields=null，再读同一 run 的 result_delivery。"
    "isError 按 error_code/issues 修正，仅 retryable=true 才重试。"
    "更正资料重建受影响输入并沿用 trace_id/parent_run_id；解释未变结果不重算。"
    "工具不明确时只查所需定义；精简配置可能未公开条件分支，以当前连接和场景 availability 为准。"
    "先回答要点、实际依据及现实建议，详细程度服从用户请求。"
)


def _render_protocol_response(
    data: ServiceResult,
    *,
    compact: bool = True,
    include_snapshot_text: bool = True,
    fields: Optional[list[str]] = None,
    strict_fields: bool = False,
    response_char_limit: int = DEFAULT_MCP_RESPONSE_CHARS,
) -> ToolResult:
    payload = deliver_response(
        data,
        fields=fields,
        strict_fields=strict_fields,
        include_snapshot_text=include_snapshot_text,
        response_char_limit=response_char_limit,
        compact=compact,
    )
    return protocol_result(
        payload,
        failed=False,
        text=format_json_response(payload, compact=compact),
    )


def _render_protocol_error(
    data: ServiceResult, operation: str, *, compact: bool = True
) -> ToolResult:
    payload = error_response_payload(data, operation)
    return protocol_result(
        payload, failed=True, text=format_json_response(payload, compact=compact)
    )


# Tool registration — every tool is declared once in the central catalog and
# auto-registered here. To add a tool, edit fatebridge/services/tool_catalog.py.

from fatebridge.application.discovery import select_mcp_specs
from fatebridge.mcp_transport import (  # noqa: E402
    register_discovery_resources,
)
from fatebridge.services.tool_catalog import CATALOG  # noqa: E402
from fatebridge.transports.mcp import register_mcp


def create_mcp_app(
    families: Optional[str] = None,
    scenarios: Optional[str] = None,
    tool_scope: str = "complete",
) -> FastMCP:
    """Host-level family profiles; an omitted profile retains every MCP tool."""
    server = FastMCP(
        name="fatebridge",
        instructions=_MCP_INSTRUCTIONS,
        version=APP_VERSION,
        dereference_schemas=False,
    )
    exposed = select_mcp_specs(
        CATALOG, family=families, scenario=scenarios, tool_scope=tool_scope
    )
    if not exposed:
        raise ValueError("MCP 分类、场景与工具范围的交集为空")
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
    os.getenv("FATEBRIDGE_MCP_TOOL_SCOPE") or "complete",
)


def main() -> None:
    app.run(show_banner=False)


if __name__ == "__main__":
    main()
