"""Verify P0 agentic optimizations: tiered payloads, single-run knowledge, slim MCP."""

from __future__ import annotations

import asyncio
import json

import pytest
from fastmcp import Client

import fatebridge.services.knowledge as kn
from fatebridge.application.examples import example_input, suggested_fields
from fatebridge.application.execution import execute_with_receipt
from fatebridge.application.response_delivery import deliver_response
from fatebridge.core.execution_context import ExecutionOptions
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services import replay_metadata
from fatebridge.services.tool_catalog import CATALOG
from tests.support.transports import call_calculation


def test_knowledge_catalog_runs_once_without_redundant_reexecution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    orig = kn.build_knowledge_registry
    calls = 0

    def spy(*args, **kwargs):
        nonlocal calls
        calls += 1
        return orig(*args, **kwargs)

    monkeypatch.setattr(kn, "build_knowledge_registry", spy)
    spec = next(s for s in CATALOG if s.name == "knowledge_catalog")
    request = spec.request_model()
    compact_options = ExecutionOptions(detail="compact")
    result = execute_with_receipt(spec, request, options=compact_options)
    assert calls == 1 and "domains" in result
    assert "snapshot_text" not in result and "snapshot_export" not in result


def test_bazi_birth_tiered_detail_and_inline_suggested_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec = next(s for s in CATALOG if s.name == "bazi_birth_chart")
    req = spec.request_model(
        birth_year=1990,
        birth_month=5,
        birth_day=15,
        birth_hour=10,
        birth_minute=30,
        gender="男",
        birth_place="北京",
        birth_timezone="Asia/Shanghai",
    )

    def dump_len(obj):
        return len(json.dumps(obj, ensure_ascii=False, separators=(",", ":")))

    inventory_calls = 0
    original_inventory = replay_metadata.ephemeris_inventory

    def inventory():
        nonlocal inventory_calls
        inventory_calls += 1
        return original_inventory()

    monkeypatch.setattr(replay_metadata, "ephemeris_inventory", inventory)
    compact = ExecutionOptions(detail="compact", as_of="2026-11-23T04:00:00Z")
    compact_raw = execute_with_receipt(spec, req, options=compact)
    assert inventory_calls == 0
    assert "runtime" not in compact_raw["run_metadata"]
    assert "snapshot_text" not in compact_raw
    assert "snapshot_export" not in compact_raw

    audit_raw = execute_with_receipt(
        spec, req, options=compact.model_copy(update={"detail": "audit"})
    )
    assert inventory_calls == 1
    assert compact_raw["bazi_birth"] == audit_raw["bazi_birth"]

    compact_out = deliver_response(compact_raw, spec=spec, detail="compact")
    assert (
        deliver_response(compact_raw, spec=spec, detail="compact", fields=[])
        == compact_out
    )
    audit_out = deliver_response(audit_raw, spec=spec, detail="audit")

    assert "calculation_evidence" not in compact_out["run_metadata"]
    assert "calculation_evidence" in audit_out["run_metadata"]
    assert dump_len(compact_out) < dump_len(audit_out)

    # With suggested_fields, bazi_birth_chart fits cleanly without result_delivery.
    mcp_view = deliver_response(
        audit_raw,
        spec=spec,
        fields=suggested_fields(spec),
        detail="compact",
    )
    assert "result_delivery" not in mcp_view
    assert "bazi_birth" in mcp_view
    assert dump_len(mcp_view) <= 8192


def test_mcp_exposes_two_tools_and_zero_resources() -> None:
    app = create_mcp_app()
    by_name = {spec.name: spec for spec in CATALOG}

    async def check():
        async with Client(app) as client:
            tools = await client.list_tools()
            names = {t.name for t in tools}
            assert names == {"discover_tools", "run_calculation"}
            assert all(tool.output_schema is None for tool in tools)
            assert await client.list_resources() == []
            assert await client.list_resource_templates() == []
            direct = await client.call_tool(
                "bazi_birth_chart", {}, raise_on_error=False
            )
            assert direct.is_error
            wire_size = sum(
                len(t.description or "")
                + len(
                    json.dumps(
                        t.input_schema, ensure_ascii=False, separators=(",", ":")
                    )
                )
                for t in tools
            )
            assert wire_size < 5_000

            found = await client.call_tool("discover_tools", {"family": "bazi"})
            assert not found.is_error
            tool_names = {t["tool"] for t in found.structured_content["tools"]}
            assert "bazi_birth_chart" in tool_names

            described = await client.call_tool(
                "discover_tools", {"tool": "bazi_birth_chart", "detail": "summary"}
            )
            assert not described.is_error
            assert "suggested_fields" in described.structured_content["tools"][0]

            ran = await client.call_tool(
                "run_calculation",
                {
                    "tool": "bazi_birth_chart",
                    "arguments": {
                        "birth_year": 1990,
                        "birth_month": 5,
                        "birth_day": 15,
                        "birth_hour": 10,
                        "birth_minute": 30,
                        "gender": "男",
                        "birth_place": "北京",
                        "birth_timezone": "Asia/Shanghai",
                    },
                    "fields": ["bazi_birth.four_pillars", "bazi_birth.day_master"],
                    "detail": "compact",
                },
            )
            assert not ran.is_error
            payload = ran.structured_content
            assert "result_delivery" not in payload
            assert payload["bazi_birth"]["day_master"]["stem"] == "庚"

            for name in ("qimen", "fengshui_assess", "liuyao"):
                spec = by_name[name]
                arguments = example_input(spec)
                if name == "liuyao":
                    arguments = {**arguments, "method": "coin"}
                response = await client.call_tool(
                    "run_calculation",
                    {"tool": spec.name, "arguments": arguments},
                )
                business = response.structured_content
                assert "result_delivery" not in business
                if name == "qimen":
                    assert len(business["qimen"]["palaces"]) == 9
                elif name == "fengshui_assess":
                    findings = business["layout_analysis"]["placement_findings"]
                    assert {item["object_id"] for item in findings} == {"stove", "bed"}
                    assert business["rule_trace"]
                    assert all(
                        ruleset["source_ids"] for ruleset in business["rulesets"]
                    )
                else:
                    assert len(business["lines"]) == 6
                    assert business["run_metadata"]["replay"]["overrides"]["seed"] == 42
                    assert len(business["current_code"]) == 6
                    assert business["current_hexagram"]["name"]
                    assert business["classical_text_evidence"]["base_guaci"]
                    evidence = business["liuyao_evidence"]
                    assert evidence["calendar_conventions"]["day_ganzhi"]
                    assert evidence["sources"]

    asyncio.run(check())
