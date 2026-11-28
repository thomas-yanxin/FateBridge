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
    "horary_chart",
    "evaluate_election_time",
    "relationship_chart",
    "liuyao",
    "gua_lookup",
    "meihua_time_cast",
    "meihua_cast",
    "guolao_chart",
    "hamburg_midpoint_chart",
    "thirteen_sector_chart",
    "ziwei_birth_chart",
    "ziwei_timing",
    "ziwei_rules",
    "qimen",
    "taiyi",
    "sanshi_combined_chart",
    "vedic_chart",
    "vimshottari_dasha",
    "bazi_career",
    "compare_bazi_sources",
    "bazi_compatibility",
    "bazi_timing",
    "fengshui_assess",
    "heluo",
    "canping",
    "western_timing",
    "interpret_astrology_dice",
    "sukuyo_compatibility",
    "suzhan",
    "liuren_chart",
    "liuren_yearly_timing",
    "jinkou",
    "knowledge_catalog",
    "knowledge_read",
    "ipip_big_five",
)


async def call_contracts() -> list[dict[str, object]]:
    """Derive definitions from the same public MCP interface clients receive."""
    specs = {spec.name: spec for spec in CATALOG}
    records = []
    async with Client(create_mcp_app()) as client:
        for name in TOOLS:
            spec = specs[name]
            result = await client.call_tool("discover_tools", {"tool": spec.name})
            payload = result.structured_content
            assert payload is not None
            contract = payload
            record: dict[str, object] = {
                "tool": spec.name,
                "input": contract["input_schema"],
                "first_view": {
                    "fields": contract.get("suggested_fields"),
                },
            }
            for field in ("call_guidance", "evidence_views", "default_omit"):
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
        "这里只保存常用工具的离线合同，不是全部公开工具清单；其他工具可用 `fatebridge discover <tool>` 离线核对。",
        "生成命令会移除本目录中已不再发布的 JSON；`--check` 同时检查缺失、内容漂移和遗留文件。",
        "",
    ]
    lines.extend(f"- [{record['tool']}]({record['tool']}.json)" for record in records)
    lines.extend(
        [
            "",
            "`input` 描述 `run_calculation.arguments`。工具名和控制参数（`include`、`fields`、`as_of`）放在 `run_calculation` 的外层；`include` 与 `fields` 互斥。",
            '默认不传 `include` 与 `fields` 即返回核心层，并在 `run_metadata.omitted_fields` 列出实际省略的可选重型路径（对应合同中的 `default_omit`）。需要按需展开省略块时传 `include`（支持路径、`evidence_views` 名称或 `["*"]`）；需要严格只取指定子字段时按 `first_view.fields` 或 `evidence_views` 传入 `fields`。',
            '无损全量输出使用 `include=["*"]` 并省略 `fields`。',
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
