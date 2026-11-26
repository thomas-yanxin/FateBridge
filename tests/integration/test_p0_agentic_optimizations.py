"""Verify P0 agentic optimizations: tiered payloads, single-run knowledge, slim MCP."""

from __future__ import annotations

import asyncio
import json

import pytest
from fastmcp import Client

import fatebridge.services.knowledge as kn
from fatebridge.application.examples import example_input, suggested_fields
from fatebridge.application.execution import execute_tool
from fatebridge.application.response_delivery import deliver_response
from fatebridge.application.result_delivery import DEFAULT_MCP_RESPONSE_CHARS
from fatebridge.core.execution_context import ExecutionOptions
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services import bazi, replay_metadata
from fatebridge.services.tool_catalog import CATALOG
from tests.support.transports import call_calculation


def test_knowledge_registry_runs_once_without_redundant_reexecution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    orig = kn.build_knowledge_registry
    calls = 0

    def spy(*args, **kwargs):
        nonlocal calls
        calls += 1
        return orig(*args, **kwargs)

    monkeypatch.setattr(kn, "build_knowledge_registry", spy)
    spec = next(s for s in CATALOG if s.key == "knowledge_registry")
    request = spec.request_model()
    compact_options = ExecutionOptions(detail="compact")
    result = execute_tool(spec, request, options=compact_options)
    assert calls == 1 and "domains" in result
    assert "snapshot_text" not in result and "snapshot_export" not in result

    with_snapshot = execute_tool(
        spec, request, options=compact_options, fields=["snapshot_export"]
    )
    assert calls == 2 and with_snapshot["domains"] == result["domains"]
    assert with_snapshot["snapshot_text"] and with_snapshot["snapshot_export"]


def test_bazi_birth_tiered_detail_and_inline_suggested_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec = next(s for s in CATALOG if s.key == "bazi_birth")
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
    snapshot_calls = 0
    original_snapshot = bazi._build_snapshot_text

    def inventory():
        nonlocal inventory_calls
        inventory_calls += 1
        return original_inventory()

    def snapshot(**kwargs):
        nonlocal snapshot_calls
        snapshot_calls += 1
        return original_snapshot(**kwargs)

    monkeypatch.setattr(replay_metadata, "ephemeris_inventory", inventory)
    monkeypatch.setattr(bazi, "_build_snapshot_text", snapshot)
    compact = ExecutionOptions(detail="compact", as_of="2026-11-23T04:00:00Z")
    compact_raw = execute_tool(spec, req, options=compact)
    assert inventory_calls == 0
    assert snapshot_calls == 0
    assert "runtime" not in compact_raw["run_metadata"]
    assert "snapshot_text" not in compact_raw
    assert "snapshot_export" not in compact_raw

    explicit = execute_tool(
        spec, req, options=compact, fields=["run_metadata.runtime.solar_term_policy"]
    )
    assert inventory_calls == 1
    assert snapshot_calls == 0
    assert "solar_term_policy" in explicit["run_metadata"]["runtime"]

    standard_raw = execute_tool(
        spec, req, options=compact.model_copy(update={"detail": "standard"})
    )
    audit_raw = execute_tool(
        spec, req, options=compact.model_copy(update={"detail": "audit"})
    )
    assert inventory_calls == 3
    assert snapshot_calls == 2
    assert (
        compact_raw["bazi_birth"]
        == standard_raw["bazi_birth"]
        == audit_raw["bazi_birth"]
    )

    compact_out = deliver_response(compact_raw, spec=spec, detail="compact")
    assert (
        deliver_response(compact_raw, spec=spec, detail="compact", fields=[])
        == compact_out
    )
    standard_out = deliver_response(standard_raw, spec=spec, detail="standard")
    audit_out = deliver_response(audit_raw, spec=spec, detail="audit")

    assert "calculation_evidence" not in compact_out["run_metadata"]
    assert "calculation_evidence" not in standard_out["run_metadata"]
    assert "calculation_evidence" in audit_out["run_metadata"]

    assert dump_len(compact_out) < dump_len(standard_out) < dump_len(audit_out)
    assert dump_len(standard_out) < 120_000

    with_snapshot = execute_tool(spec, req, options=compact, include_snapshot_text=True)
    with_export = execute_tool(spec, req, options=compact, fields=["snapshot_export"])
    assert snapshot_calls == 4
    assert with_snapshot["snapshot_text"] == standard_raw["snapshot_text"]
    assert with_export["snapshot_export"] == standard_raw["snapshot_export"]

    # With suggested_fields, bazi_birth fits inline within the default MCP budget.
    mcp_view = deliver_response(
        standard_raw,
        spec=spec,
        fields=suggested_fields(spec),
        strict_fields=True,
        include_snapshot_text=False,
        response_char_limit=DEFAULT_MCP_RESPONSE_CHARS,
        detail="standard",
    )
    assert "result_delivery" not in mcp_view
    assert "bazi_birth" in mcp_view
    assert dump_len(mcp_view) <= DEFAULT_MCP_RESPONSE_CHARS


def test_western_timing_snapshots_are_available_on_request() -> None:
    spec = next(s for s in CATALOG if s.key == "profection")
    request = spec.request_model.model_validate(example_input(spec))
    as_of = "2026-10-12T02:00:00Z"
    standard = ExecutionOptions(as_of=as_of, detail="standard")
    result = execute_tool(spec, request, options=standard)
    assert "snapshot_text" not in result and "snapshot_export" not in result

    audit = execute_tool(
        spec, request, options=ExecutionOptions(as_of=as_of, detail="audit")
    )
    assert result["profection"] == audit["profection"]
    audit = deliver_response(audit, spec=spec, detail="audit")
    assert audit["snapshot_text"] and audit["snapshot_export"]

    fields = ["snapshot_text", "snapshot_export"]
    requested = execute_tool(spec, request, options=standard, fields=fields)
    projected = deliver_response(
        requested, spec=spec, fields=fields, strict_fields=True
    )
    assert projected["snapshot_text"] == audit["snapshot_text"]
    assert projected["snapshot_export"] == audit["snapshot_export"]

    selected = request.model_copy(update={"selected_sections": ["出生时间"]})
    requested_sections = execute_tool(spec, selected, options=standard)
    assert requested_sections["snapshot_export"]["selected_sections"] == ["出生时间"]


def test_election_renders_snapshot_only_on_request() -> None:
    spec = next(s for s in CATALOG if s.key == "astro_election")
    request = spec.request_model.model_validate(example_input(spec))
    standard = execute_tool(spec, request)
    assert "election" in standard and "snapshot_text" not in standard
    audit = execute_tool(spec, request, options=ExecutionOptions(detail="audit"))
    assert audit["election"] == standard["election"]
    assert (
        "[候选盘条件]"
        in deliver_response(audit, spec=spec, detail="audit")["snapshot_text"]
    )


def test_mcp_exposes_four_tools_and_executes_end_to_end() -> None:
    app = create_mcp_app()
    by_key = {spec.key: spec for spec in CATALOG}

    async def check():
        async with Client(app) as client:
            tools = await client.list_tools()
            names = {t.name for t in tools}
            assert names == {
                "discover_capabilities",
                "describe_capability",
                "run_calculation",
                "read_result",
            }
            assert all(tool.output_schema is None for tool in tools)
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

            summary = (await client.read_resource("fatebridge://catalog/summary"))[0]
            assert len(summary.text.encode("utf-8")) < 12_000
            index = json.loads(summary.text)
            assert index["matched_count"] == len(index["tools"])
            assert {record["tool"] for record in index["tools"]} == {
                spec.tool_name for spec in CATALOG if spec.mcp_name
            }

            found = await client.call_tool("discover_capabilities", {"family": "bazi"})
            assert not found.is_error
            tool_names = {t["tool"] for t in found.structured_content["tools"]}
            assert by_key["bazi_birth"].tool_name in tool_names

            described = await client.call_tool(
                "describe_capability", {"tool": "bazi_birth_chart", "detail": "input"}
            )
            assert not described.is_error
            assert "suggested_fields" in described.structured_content

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
                    "strict_fields": True,
                    "include_snapshot_text": False,
                    "detail": "compact",
                },
            )
            assert not ran.is_error
            payload = ran.structured_content
            assert "result_delivery" not in payload
            assert payload["bazi_birth"]["day_master"]["stem"] == "庚"

            for key in ("qimen", "fengshui_assess", "sixyao"):
                spec = by_key[key]
                arguments = example_input(spec)
                if key == "sixyao":
                    arguments = {**arguments, "method": "coin"}
                else:
                    pass
                response = await client.call_tool(
                    "run_calculation",
                    {"tool": spec.tool_name, "arguments": arguments},
                )
                business = response.structured_content
                assert "result_delivery" not in business
                if key == "qimen":
                    assert len(business["qimen"]["palaces"]) == 9
                elif key == "fengshui_assess":
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
