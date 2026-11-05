"""Publish one live MCP contract per file, loaded only when a tool needs it."""

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
TARGET = ROOT / "docs/contracts"
TOOLS = (
    "human_design",
    "astro_horary",
    "astro_election",
    "astro_relative_chart",
    "sixyao",
    "gua_lookup",
    "meihua_analysis",
    "meihua_cast",
    "astro_guolao_chart",
    "astro_germany_chart",
    "astro_chart13",
    "ziwei_birth",
    "ziwei_horoscope",
    "ziwei_rules",
    "qimen",
    "taiyi",
    "sanshiunited",
    "astro_india_chart",
    "astro_vimshottari",
    "bazi_career",
    "bazi_source_compare",
    "two_person_compatibility",
    "timing_analysis",
    "fengshui_assess",
    "heluo",
    "canping",
    "western_timing_analysis",
    "otherbu",
    "sukuyo_compatibility",
    "suzhan",
    "liureng_gods",
    "liureng_runyear",
    "jinkou",
    "knowledge_registry",
    "knowledge_read",
)


async def call_contracts() -> list[dict[str, object]]:
    """Derive definitions from the same public MCP interface clients receive."""
    async with Client(create_mcp_app()) as client:
        tools = {tool.name: tool for tool in await client.list_tools()}
    specs = {spec.tool_name: spec for spec in CATALOG}
    records = []
    for name in TOOLS:
        spec = specs[name]
        record: dict[str, object] = {
            "tool": name,
            "input": tools[name].model_dump(by_alias=True)["inputSchema"],
            "first_view": {
                "fields": suggested_fields(spec),
                "strict_fields": True,
                "include_snapshot_text": False,
            },
        }
        guidance = call_guidance(spec)
        if guidance:
            record["call_guidance"] = guidance
        views = evidence_views(spec)
        if views:
            record["evidence_views"] = views
        if spec.methods:
            record["method_contracts"] = [
                method.as_manifest() for method in spec.methods
            ]
        records.append(record)
    return records


def render_files(records: list[dict[str, object]]) -> dict[str, str]:
    files = {
        f"{record['tool']}.json": json.dumps(
            record, ensure_ascii=False, indent=2, sort_keys=True
        )
        + "\n"
        for record in records
    }
    lines = [
        "# 按需 MCP 调用合同",
        "",
        "由 `scripts/build_codex_call_contracts.py` 从实际 MCP 生成，不手改。",
        "已连接且定义清楚时直接调用；只有本地离线核对或定义缺失时，读取所选文件，不加载全部合同。",
        "当前连接的工具名、Schema 与公开范围优先；文件存在不代表该工具已连接。",
        "这里只保存常用工具的离线合同，不是全部公开工具清单；其他工具可用 `fatebridge describe <tool> --detail input` 离线核对。",
        "生成命令会移除本目录中已不再发布的 JSON；`--check` 同时检查缺失、内容漂移和遗留文件。",
        "",
    ]
    lines.extend(f"- [{record['tool']}]({record['tool']}.json)" for record in records)
    lines.extend(
        [
            "",
            "每个文件保留完整输入约束、参数说明、首轮字段及任务视图。视图名不是请求参数。",
            "摘要投影与完整导出分别使用 first_view 和 fields=null；完整结果读取同一 run。",
            "输入日期使用公历；不猜生时、不套示例；出生与分析时刻、时区及太阳时策略以各工具合同为准。",
        ]
    )
    files["README.md"] = "\n".join(lines) + "\n"
    return files


async def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    files = render_files(await call_contracts())
    obsolete = {path.name for path in TARGET.glob("*.json")} - files.keys()
    if args.check:
        stale = [
            name
            for name, text in files.items()
            if not (TARGET / name).is_file()
            or (TARGET / name).read_text(encoding="utf-8") != text
        ]
        if stale or obsolete:
            raise SystemExit(
                f"MCP call contracts are stale: {', '.join(stale)}; "
                f"obsolete: {', '.join(sorted(obsolete))}"
            )
    else:
        TARGET.mkdir(parents=True, exist_ok=True)
        for name, text in files.items():
            (TARGET / name).write_text(text, encoding="utf-8")
        for name in obsolete:
            (TARGET / name).unlink()
    print(
        "MCP call contracts match live schemas"
        if args.check
        else "Updated on-demand MCP call contracts in docs/contracts"
    )


if __name__ == "__main__":
    asyncio.run(main())
