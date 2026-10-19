"""Publish checked call contracts in the normally loaded Codex workspace guide.

Only annotations are removed from live MCP input schemas. Constraints, defaults,
required fields and server-side validation remain intact. No example people or
expected answers are supplied to the model.
"""

import argparse
import asyncio
import json
from pathlib import Path

from fastmcp import Client

from fatebridge.application.examples import (
    call_guidance,
    evidence_views,
    suggested_fields,
)
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.tool_catalog import CATALOG

ROOT = Path(__file__).resolve().parents[1]
BEGIN = "<!-- codex-call-contracts:begin -->"
END = "<!-- codex-call-contracts:end -->"
TOOLS = (
    "bazi_career",
    "two_person_compatibility",
    "timing_analysis",
    "fengshui_assess",
    "western_timing_analysis",
)


def without_annotations(schema):
    """Strip schema annotations without stripping properties with those names."""
    if isinstance(schema, list):
        return [without_annotations(v) for v in schema]
    if not isinstance(schema, dict):
        return schema
    result = {}
    for key, value in schema.items():
        if key in {"title", "description"}:
            continue
        if key in {"properties", "$defs", "definitions", "patternProperties"}:
            result[key] = {k: without_annotations(v) for k, v in value.items()}
        else:
            result[key] = without_annotations(value)
    return result


async def call_contracts():
    """Derive definitions from the same public MCP interface clients receive."""
    async with Client(create_mcp_app()) as client:
        tools = {tool.name: tool for tool in await client.list_tools()}
    specs = {spec.tool_name: spec for spec in CATALOG}
    return [
        {
            "tool": name,
            "input": without_annotations(tools[name].inputSchema),
            "first_view": {
                "fields": suggested_fields(specs[name]),
                "strict_fields": True,
                "include_snapshot_text": False,
            },
            **(
                {"call_guidance": call_guidance(specs[name])}
                if call_guidance(specs[name])
                else {}
            ),
            **(
                {"evidence_views": evidence_views(specs[name])}
                if evidence_views(specs[name])
                else {}
            ),
        }
        for name in TOOLS
    ]


async def render_block():
    records = await call_contracts()
    lines = [
        BEGIN,
        "## 已核对的常用 MCP 调用合同",
        "",
        "此段由 `scripts/build_codex_call_contracts.py` 从实际 MCP inputSchema 与共享首轮字段生成，"
        "只删标题和说明，保留全部参数、默认值、必填项与约束。更新接口后重新生成，检查模式用 `--check`。",
        "",
        "下面五项工具已具备调用所需定义。对应计算的资料齐全且工具在连接中公开时，"
        "直接调用 `tools.mcp__fatebridge__<tool>(参数)`，无需先检索或打印 ALL_TOOLS。"
        "如需确认公开范围，可在同一次 exec 中检查 ALL_TOOLS 的名称并调用，不另起发现往返。"
        "合同未覆盖的工具或参数疑问再读取实际工具定义，不猜测。",
        "",
        "使用用户已确认的资料，不把接口默认值当成用户已提供的出生小时。"
        "这些出生接口使用公历，农历资料需先正确转换。"
        "出生日期/小时使用 birth_*（双人分别 person1_/person2_），"
        "分析日期使用 analysis_*；as_of 是带时区的 ISO 时间，仅冻结未显式指定的当前时间。"
        "性别接受男/女等已确认写法；出生时区是 IANA 名称或 UTC 偏移。"
        "太阳时默认开启；仅按用户明确要求关闭。未知经度可省略，以返回精度说明限制，不能猜经度。"
        "中式出生工具不传 birth_latitude；西占推运需要经纬度，并以 analysis_hour/minute 指定目标钟时。"
        "未指明双人关系类型用 general，"
        "不要自行传入大运/流年柱覆盖自动计算。结果仍按实际返回字段、精度和回执解读。",
        "",
    ]
    for record in records:
        lines.extend(
            [
                f"### {record['tool']}",
                "",
                "```json",
                # Schema object-key order varies across supported MCP versions.
                # Preserve every constraint and array order, but publish stable
                # object ordering so equivalent schemas do not trigger drift.
                json.dumps(
                    record,
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                ),
                "```",
                "",
            ]
        )
    lines.append(END)
    return "\n".join(lines)


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    block = await render_block()
    path = ROOT / "AGENTS.md"
    old = path.read_text()
    if BEGIN in old:
        before, rest = old.split(BEGIN, 1)
        _, after = rest.split(END, 1)
        updated = before + block + after
    else:
        updated = old.rstrip() + "\n\n" + block + "\n"
    if args.check:
        if updated != old:
            raise SystemExit(f"Codex call contracts are stale: {path}")
    else:
        path.write_text(updated)
    print(
        "Codex call contracts match live MCP schemas"
        if args.check
        else "Updated generated call contracts in root AGENTS.md"
    )


if __name__ == "__main__":
    asyncio.run(main())
