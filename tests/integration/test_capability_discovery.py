"""Agent-facing capability-discovery contracts.

Guards the surface an LLM uses to find and call tools without scraping prose
docs: the ``GET /api/tools`` manifest, cross-surface (REST↔MCP) parity, and the
self-describing MCP transport flags.
"""

from __future__ import annotations

import asyncio
import json

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

from fatebridge.api import app
from fatebridge.application.description import describe_spec
from fatebridge.cli import run
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.tool_catalog import CATALOG, mcp_specs, rest_specs
from fatebridge.utils.errors import ParameterError
from tests.support.transports import cached_mcp_app, discover_capabilities, rest

__all__ = ["rest"]


def _tools_payload() -> dict:
    return TestClient(app).get("/api/tools").json()


def test_tools_endpoint_counts_match_catalog() -> None:
    payload = _tools_payload()
    assert payload["counts"]["rest"] == len(rest_specs())
    assert payload["counts"]["mcp"] == len(mcp_specs())
    assert payload["counts"]["total"] == len(CATALOG)
    assert len(payload["tools"]) == len(CATALOG)
    assert sum(payload["families"].values()) == len(CATALOG)


def test_tools_endpoint_records_are_well_formed() -> None:
    payload = _tools_payload()
    assert {t["tool"] for t in payload["tools"]} == {s.name for s in CATALOG}
    for record in payload["tools"]:
        assert record["summary"]
        assert record["family"]
        assert set(record["surfaces"]) == {"cli", "rest", "mcp"}


def test_every_tool_declares_the_same_public_name_across_surfaces() -> None:
    for spec in CATALOG:
        surfaces = describe_spec(spec)["surfaces"]
        assert surfaces["rest"] == spec.rest_path
        assert surfaces["mcp"] is spec.expose_mcp
        assert surfaces["cli"] is True


def test_mcp_transport_flags_are_self_describing() -> None:
    async def fetch():
        async with Client(create_mcp_app()) as client:
            tools = {t.name: t for t in await client.list_tools()}
            return (
                tools["run_calculation"].input_schema["properties"],
                tools["run_batch"].input_schema,
            )

    properties, batch_schema = asyncio.run(fetch())
    assert set(properties) == {"tool", "arguments", "include", "fields", "as_of"}
    assert properties["include"]["description"]
    assert properties["fields"]["description"]
    assert "detail" not in batch_schema["properties"]
    batch_call_props = batch_schema["$defs"]["BatchCall"]["properties"]
    assert {"include", "fields"} <= set(batch_call_props)
    assert "detail" not in batch_call_props


def test_reference_discovery_uses_public_names(
    rest: TestClient, capsys: pytest.CaptureFixture[str]
) -> None:
    names = {"knowledge_catalog", "knowledge_read", "place_lookup"}
    records = {}
    for name in sorted(names):
        response = rest.get(
            "/api/tools", params={"tool": name, "surface": "mcp", "detail": "summary"}
        )
        assert response.status_code == 200, response.text
        record = response.json()
        assert record["tool"] == name
        assert record["surfaces"]["mcp"] is True
        assert (
            run(["discover", "--tool", name, "--surface", "mcp", "--detail", "summary"])
            == 0
        )
        cli_record = json.loads(capsys.readouterr().out)
        assert {
            k: v
            for k, v in cli_record.items()
            if k not in {"cli_example", "example_note"}
        } == record
        records[name] = record["surfaces"]

    retired = {
        "export_registry",
        "export_formats",
        "export_parse",
        "knowledge_registry",
        "calculate_knowledge_read",
    }
    for name in sorted(retired):
        assert rest.get("/api/tools", params={"tool": name}).status_code == 404
        assert run(["discover", "--tool", name]) == 2
        issues = json.loads(capsys.readouterr().out)["issues"]
        assert len(issues) == 1
        assert issues[0]["path"] == "tool"
        assert issues[0]["code"] == "unknown_tool"

    async def check_mcp_discovery() -> None:
        async with Client(cached_mcp_app(families="knowledge")) as client:
            assert set(await discover_capabilities(client)) == names
            for name in sorted(names):
                discovered = await client.call_tool(
                    "discover_tools", {"tool": name, "detail": "summary"}
                )
                contract = discovered.structured_content
                assert contract["tool"] == name
                assert contract["surfaces"] == records[name]
            for name in sorted(retired):
                result = await client.call_tool(
                    "run_calculation",
                    {"tool": name, "arguments": {}},
                    raise_on_error=False,
                )
                assert result.is_error
                assert result.structured_content["error_code"] == "unknown_tool"

    asyncio.run(check_mcp_discovery())


@pytest.mark.parametrize("blank_q", ["", "   "])
def test_blank_q_with_full_detail_requires_filter_across_surfaces(
    rest: TestClient,
    capsys: pytest.CaptureFixture[str],
    blank_q: str,
) -> None:
    import fatebridge

    # 1. Python SDK
    with pytest.raises(ParameterError) as py_err:
        fatebridge.discover(q=blank_q, detail="full")
    assert py_err.value.status_code == 422
    assert py_err.value.issues[0]["code"] == "filter_required_for_full_detail"

    # 2. REST GET /api/tools
    rest_res = rest.get("/api/tools", params={"q": blank_q, "detail": "full"})
    assert rest_res.status_code == 422
    assert rest_res.json()["error_code"] == "validation_error"
    assert rest_res.json()["issues"][0]["code"] == "filter_required_for_full_detail"

    # 3. CLI discover --q
    capsys.readouterr()
    assert run(["discover", "--q", blank_q, "--detail", "full"]) == 1
    cli_err = json.loads(capsys.readouterr().out)
    assert cli_err["status_code"] == 422
    assert cli_err["issues"][0]["code"] == "filter_required_for_full_detail"

    # 4. MCP discover_tools
    async def mcp_blank_q():
        async with Client(cached_mcp_app()) as client:
            return await client.call_tool(
                "discover_tools",
                {"q": blank_q, "detail": "full"},
                raise_on_error=False,
            )

    mcp_res = asyncio.run(mcp_blank_q())
    assert mcp_res.is_error
    assert mcp_res.structured_content["status_code"] == 422
    assert (
        mcp_res.structured_content["issues"][0]["code"]
        == "filter_required_for_full_detail"
    )


def test_calculate_knowledge_registry_and_read_match_reference_samples() -> None:
    from fatebridge.services.knowledge import (
        calculate_knowledge_read,
        calculate_knowledge_registry,
    )

    registry = calculate_knowledge_registry(domain="astro")
    liureng = calculate_knowledge_read(domain="liureng", category="shen", key="子")
    qimen = calculate_knowledge_read(domain="qimen", category="door", key="休门")
    astro = calculate_knowledge_read(
        domain="astro",
        category="aspect",
        aspect_degree=90,
        object_a="Sun",
        object_b="Jupiter",
    )

    assert registry["domains"][0]["domain"] == "astro"
    assert any(
        category["name"] == "planet"
        for category in registry["domains"][0]["categories"]
    )
    assert "snapshot_text" not in registry and "snapshot_export" not in registry
    assert liureng["title"] == "神后子神"
    assert "类象" in liureng["rendered_text"]
    assert qimen["key"] == "休门"
    assert "休门属水，本宫为坎" in qimen["rendered_text"]
    assert "卷二·门迫宫迫" in qimen["citation"]
    assert astro["title"].startswith("太阳 - 木星")
    assert "相位角：90°" in astro["tips"]
    assert "snapshot_text" not in qimen and "snapshot_export" not in qimen


def test_knowledge_read_auto_resolves_category_and_reports_ambiguous_or_unknown() -> (
    None
):
    from fatebridge.services.knowledge import (
        calculate_knowledge_read,
        calculate_knowledge_registry,
    )

    bazi = calculate_knowledge_read(domain="bazi", key="伤官见官")
    assert "error" not in bazi
    assert bazi["category"] == "education"
    assert bazi["key"] == "伤官见官"

    astro = calculate_knowledge_read(domain="astro", key="Mars")
    assert astro["category"] == "planet"
    assert astro["lines"] == ["入庙：白羊、天蝎", "擢升：摩羯"]
    qimen = calculate_knowledge_read(domain="qimen", key="休门")
    assert qimen["category"] == "door"

    explicit = calculate_knowledge_read(
        domain="bazi", category="education", key="伤官见官"
    )
    assert explicit["key"] == "伤官见官"

    ambiguous = calculate_knowledge_read(domain="bazi", key="偏财")
    assert ambiguous["code"] == "knowledge.bazi.ambiguous_key"
    assert set(ambiguous["details"]["candidate_categories"]) == {"ten_gods", "wealth"}

    unknown = calculate_knowledge_read(domain="bazi", key="不存在的词条")
    assert unknown["code"] == "knowledge.bazi.unknown_key"
    retired = calculate_knowledge_read(domain="astro", category="planet", key="Uranus")
    assert retired["code"] == "knowledge.astro.unknown_key"
    assert "education" in unknown["details"]["available_categories"]

    registry = calculate_knowledge_registry()
    assert [item["domain"] for item in registry["domains"]] == [
        "astro",
        "bazi",
        "liureng",
        "qimen",
        "heluo",
        "canping",
        "human_design",
    ]
    sources = {item["domain"]: item["source"] for item in registry["domains"]}
    assert sources["astro"] == sources["qimen"] == "fatebridge_rule_references"
    assert sources["bazi"] == sources["liureng"] == "xingque_hover_docs"
    assert all(
        item["source"] == "fatebridge_numerology_references"
        for item in registry["domains"][4:6]
    )
    assert registry["domains"][6]["source"] == "fatebridge_human_design_line_references"


def test_knowledge_catalog_keys_sample_limit_and_mcp_payloads() -> None:
    import fatebridge
    from tests.fixtures.transports import mcp_payload

    knowledge_registry_result = mcp_payload("knowledge_catalog", domain="astro")
    knowledge_read_result = mcp_payload(
        "knowledge_read",
        domain="qimen",
        category="door",
        key="休门",
    )
    assert knowledge_registry_result["domains"][0]["domain"] == "astro"
    assert knowledge_read_result["key"] == "休门"
    assert "休门属水，本宫为坎" in knowledge_read_result["rendered_text"]

    small = fatebridge.run("knowledge_catalog", {"keys_sample_limit": 2})
    large = fatebridge.run("knowledge_catalog", {"keys_sample_limit": 10})
    for dom_s, dom_l in zip(small["domains"], large["domains"], strict=True):
        for cat_s, cat_l in zip(dom_s["categories"], dom_l["categories"], strict=True):
            assert len(cat_s["keys_sample"]) <= 2
            assert len(cat_l["keys_sample"]) <= 10
            assert cat_s["keys_complete"] is (
                len(cat_s["keys_sample"]) == cat_s["count"]
            )
            assert cat_l["keys_complete"] is (
                len(cat_l["keys_sample"]) == cat_l["count"]
            )
            if cat_s["count"] >= 10:
                assert len(cat_s["keys_sample"]) < len(cat_l["keys_sample"])
