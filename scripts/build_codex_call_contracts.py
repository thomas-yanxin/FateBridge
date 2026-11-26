"""Publish one live MCP contract per file, loaded only when a tool needs it."""

import argparse
import asyncio
import json
from pathlib import Path

from fastmcp import Client

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
    "astro_guolao",
    "astro_germany",
    "astro_chart13",
    "ziwei_birth",
    "ziwei_horoscope",
    "ziwei_rules",
    "qimen",
    "taiyi",
    "sanshiunited",
    "astro_india",
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
    "ipip_big_five",
)


async def call_contracts() -> list[dict[str, object]]:
    """Derive definitions from the same public MCP interface clients receive."""
    specs = {spec.key: spec for spec in CATALOG}
    records = []
    async with Client(create_mcp_app()) as client:
        for key in TOOLS:
            name = specs[key].tool_name
            result = await client.call_tool("describe_capability", {"tool": name})
            contract = result.structured_content
            assert contract is not None
            record: dict[str, object] = {
                "tool": name,
                "input": contract["input_schema"],
                "first_view": {
                    "fields": contract.get("suggested_fields"),
                    "strict_fields": True,
                    "include_snapshot_text": False,
                },
            }
            for field in ("call_guidance", "evidence_views", "method_contracts"):
                if contract.get(field):
                    record[field] = contract[field]
                else:
                    pass
            records.append(record)
    return records


def render_files(records: list[dict[str, object]]) -> dict[str, str]:
    """Format generated contract JSON files and the index README."""
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
            "`input` 描述 `run_calculation.arguments`。工具名和 `first_view` 中的交付选项放在 `run_calculation` 的外层。",
            "首次摘要使用 detail=compact 并省略 fields。需要指定业务字段时，可按问题选择 first_view 或 evidence_views 中的字段。",
            "完整导出使用 detail=audit 和 fields=null，随后读取同一 run。",
            "输入日期使用公历；不猜生时、不套示例；出生与分析时刻、时区及太阳时策略以各工具合同为准。",
        ]
    )
    files["README.md"] = "\n".join(lines) + "\n"
    return files


async def main(argv: list[str] | None = None) -> None:
    """Write or verify on-demand MCP call contract files."""
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
            pass
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
else:
    pass
