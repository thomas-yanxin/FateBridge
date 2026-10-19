"""Guard normally loaded call contracts against interface and projection drift."""

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest
from fastmcp import Client
from jsonschema import ValidationError, validate

from fatebridge.application.examples import example_input, suggested_fields
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.tool_catalog import CATALOG
from tests.fixtures.compatibility import assert_score_reference

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "codex_contract_builder", ROOT / "scripts/build_codex_call_contracts.py"
)
builder = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(builder)


@pytest.mark.asyncio
async def test_normally_loaded_contracts_match_current_public_interface():
    path = ROOT / "AGENTS.md"
    block = path.read_text().split(builder.BEGIN, 1)[1].split(builder.END, 1)[0]
    assert builder.BEGIN + block + builder.END == await builder.render_block()


@pytest.mark.asyncio
async def test_contract_publication_ignores_object_order_but_preserves_constraints(
    monkeypatch,
):
    records = await builder.call_contracts()
    baseline = await builder.render_block()

    def reverse_objects(value):
        if isinstance(value, dict):
            return {
                key: reverse_objects(item)
                for key, item in reversed(list(value.items()))
            }
        if isinstance(value, list):
            return [reverse_objects(item) for item in value]
        return value

    reordered = reverse_objects(records)

    async def contracts():
        return reordered

    monkeypatch.setattr(builder, "call_contracts", contracts)
    assert await builder.render_block() == baseline
    reordered[0]["input"]["properties"]["birth_hour"]["maximum"] = 22
    assert await builder.render_block() != baseline


@pytest.mark.asyncio
async def test_preloaded_contract_keeps_required_time_and_solar_flag_constraints():
    record = (await builder.call_contracts())[0]
    spec = next(s for s in CATALOG if s.tool_name == record["tool"])
    params = example_input(spec)
    validate(params, record["input"])
    for invalid in [
        {k: v for k, v in params.items() if k != "birth_hour"},
        {**params, "birth_hour": 24},
        {**params, "use_true_solar_time": None},
        {**params, "birth_latitude": 39.9},
    ]:
        with pytest.raises(ValidationError):
            validate(invalid, record["input"])
    validate({**params, "use_true_solar_time": False}, record["input"])


@pytest.mark.asyncio
async def test_only_preloaded_inputs_and_views_are_enough_for_real_mcp_calls():
    records = await builder.call_contracts()
    specs = {s.tool_name: s for s in CATALOG}
    async with Client(create_mcp_app()) as client:
        for record in records:
            params = {
                **example_input(specs[record["tool"]]),
                **record["first_view"],
                "as_of": "2026-10-12T12:00:00+08:00",
            }
            validate(params, record["input"])
            result = await client.call_tool(record["tool"], params)
            assert not result.is_error
            payload = result.structured_content
            if "result_delivery" in payload:
                reference = payload["result_delivery"]
                pieces = []
                uri = reference["first_page_uri"]
                while uri:
                    page = json.loads((await client.read_resource(uri))[0].text)
                    pieces.append(page["text"])
                    uri = page["next_uri"]
                text = "".join(pieces)
                assert hashlib.sha256(text.encode()).hexdigest() == reference["sha256"]
                original_receipt = payload["run_metadata"]
                payload = json.loads(text)
                assert payload["run_metadata"] == original_receipt
            assert payload["run_metadata"]["tool_name"] == record["tool"]
            if record["tool"] == "bazi_career":
                assert payload["career_analysis"]["career_structure"]["score"] == 75
                assert "timing_context" in payload["career_analysis"]
            elif record["tool"] == "two_person_compatibility":
                assert_score_reference(payload["summary"], payload["detailed_analysis"])
                assert "score_basis" in payload["traditional_compatibility"]
            elif record["tool"] == "timing_analysis":
                assert "analysis_calendar" in payload
                assert "time_adjustment" in payload["personal_info"]
            elif record["tool"] == "fengshui_assess":
                assert "layout_analysis" in payload
                assert "calculation_scope" in payload["layout_analysis"]
            elif record["tool"] == "western_timing_analysis":
                assert (
                    payload["analysis_context"]["analysis_datetime"]
                    == "2026-10-14T12:00:00+08:00"
                )
                assert (
                    payload["transits"]["current_transit"]["analysis_datetime"]
                    == "2026-10-14T12:00:00+08:00"
                )


@pytest.mark.asyncio
async def test_fengshui_first_views_deliver_resolvable_rule_sources():
    """A successful calculation must also leave enough evidence to cite it."""
    async with Client(create_mcp_app(scenarios="onda-fengshui")) as client:
        for spec in CATALOG:
            if spec.family != "fengshui" or not spec.mcp_name:
                continue
            result = await client.call_tool(
                spec.tool_name,
                {
                    **example_input(spec),
                    "fields": suggested_fields(spec),
                    "strict_fields": True,
                    "include_snapshot_text": False,
                },
            )
            assert not result.is_error
            payload = result.structured_content
            assert payload["rulesets"] and payload["rule_trace"]
            sources = {}
            for ruleset in payload["rulesets"]:
                assert ruleset["version"]
                records = {s["source_id"]: s for s in ruleset["sources"]}
                assert set(ruleset["source_ids"]) <= records.keys()
                for source in records.values():
                    assert source["title"] and source["url"]
                sources.update(records)
            for trace in payload["rule_trace"]:
                assert set(trace["source_ids"]) <= sources.keys()


def test_schema_annotations_do_not_remove_similarly_named_input_properties():
    source = {
        "title": "Schema",
        "properties": {
            "title": {"title": "Field", "type": "string"},
            "description": {"description": "Field", "type": "integer"},
        },
    }
    assert builder.without_annotations(source) == {
        "properties": {"title": {"type": "string"}, "description": {"type": "integer"}}
    }
