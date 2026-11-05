"""Task-level dependency publication, restricted MCP follow-ups and failures."""

import asyncio
import json
from copy import deepcopy
from pathlib import Path

import pytest
from fastmcp import Client

from fatebridge.application.discovery import select_specs
from fatebridge.application.scenarios import (
    definitions,
    dependency_closure,
    discover_scenarios,
    scenario_keys,
)
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.tool_catalog import CATALOG
from scripts.build_scenario_manifest import build_manifest
from tests.fixtures.surface_payloads import REST_POST_CASES


def test_packaged_scenarios_load_with_a_non_utf8_system_default(monkeypatch):
    original = Path.open

    def legacy_open(path, mode="r", buffering=-1, encoding=None, **kwargs):
        codec = "cp1252" if encoding in (None, "locale") else encoding
        return original(path, mode, buffering, encoding=codec, **kwargs)

    definitions.cache_clear()
    try:
        with monkeypatch.context() as patch:
            patch.setattr(Path, "open", legacy_open)
            record = next(
                row for row in definitions()["scenarios"] if row["id"] == "onda-shiye"
            )
            assert "事业" in record["name"]
    finally:
        definitions.cache_clear()


def test_dependency_validation_rejects_unknown_tools_targets_and_cycles():
    records = {"one": {"engine_tools": ["known"], "dependencies": []}}
    dependency = {
        "kind": "conditional_service",
        "scenario": "two",
        "condition": "if requested",
    }
    records["one"]["dependencies"] = [dependency]
    with pytest.raises(ValueError, match="Unknown scenario dependency"):
        dependency_closure(records, {"known"})
    records["two"] = {"engine_tools": ["unknown"]}
    with pytest.raises(ValueError, match="Unknown catalog keys"):
        dependency_closure(records, {"known"})
    records["two"] = {
        "engine_tools": ["known"],
        "dependencies": [{**dependency, "scenario": "one"}],
    }
    with pytest.raises(ValueError, match="Cyclic scenario dependency"):
        dependency_closure(records, {"known"})
    broken = deepcopy(records)
    broken["one"]["dependencies"][0]["tools"] = ["known"]
    with pytest.raises(ValueError, match="one scenario or tools"):
        dependency_closure(broken, {"known"})


def test_scope_conditions_publish_needed_capabilities_without_opening_everything():
    topic = scenario_keys(CATALOG, "onda-caiwu")
    assert {
        "knowledge_read",
        "knowledge_registry",
        "zr",
        "decennials",
        "profection",
        "liuri_analysis",
        "transit",
    } <= topic
    assert "qimen" not in topic and "fengshui_assess" not in topic
    composite = scenario_keys(CATALOG, "onda-zige")
    assert {
        "bazi_wealth",
        "bazi_education",
        "two_person_compatibility",
        "ziwei_horoscope",
        "profection",
    } <= composite
    assert len(composite) < len(CATALOG)
    assert "fengshui_assess" not in composite and "astro_horary" not in composite
    health = scenario_keys(CATALOG, "onda-jiankang")
    assert health == {
        "analyze_destiny",
        "bazi_health",
        "timing_analysis",
        "knowledge_registry",
        "knowledge_read",
    }
    assert "bazi_health" not in scenario_keys(CATALOG, "onda-fengshui")
    data = discover_scenarios(CATALOG, scenario="onda-zige", surface="mcp")[
        "scenarios"
    ][0]
    assert {"finance", "learning", "social", "health_culture"} <= set(
        data["consultation"]["topics"]
    )
    assert data["direct_engine_tools"] == [
        "analyze_destiny",
        "astro_chart",
        "ziwei_birth",
    ]
    assert all(
        branch["condition"] and branch["availability"]["complete"]
        for branch in data["dependencies"]
    )
    assert any(
        route["scenario"] == "onda-caiwu"
        for branch in data["dependencies"]
        for route in branch.get("routing", [])
    )


def test_family_filter_marks_missing_dependency_routes_in_restricted_mcp():
    async def run():
        async with Client(
            create_mcp_app(families="bazi", scenarios="onda-caiwu")
        ) as client:
            names = {tool.name for tool in await client.list_tools()}
            assert (
                "bazi_wealth" in names
                and "profection" not in names
                and "knowledge_read" not in names
            )
            record = json.loads(
                (await client.read_resource("fatebridge://scenarios/onda-caiwu"))[
                    0
                ].text
            )["scenarios"][0]
            assert not record["availability"]["complete"]
            time = next(
                branch
                for branch in record["dependencies"]
                if branch["kind"] == "conditional_service"
            )
            assert "profection" in time["availability"]["missing_tool_keys"]
            assert any(
                not evidence["available"]
                for routing in time["routing"]
                for row in routing["routes"]
                for evidence in row["evidence"]
            )
            assert all(
                key in {spec.key for spec in CATALOG if spec.tool_name in names}
                for key in time["available_tool_keys"]
            )

    asyncio.run(run())


def test_scenario_vocabulary_search_includes_dependencies_and_respects_scope():
    expected = scenario_keys(CATALOG, "onda-zige")
    assert {spec.key for spec in select_specs(CATALOG, q="全面画像")} == expected
    family = [spec for spec in CATALOG if spec.family == "bazi"]
    allowed = {"bazi_wealth", "bazi_education"}
    result = select_specs(
        family, q="全面画像", family="bazi", surface="mcp", allowed_names=allowed
    )
    assert {spec.key for spec in result} == allowed
    assert {
        spec.key for spec in select_specs(CATALOG, q="全面画像", surface="rest")
    } == {spec.key for spec in CATALOG if spec.key in expected and spec.rest_path}


@pytest.mark.parametrize(
    "scenario,sequence",
    [
        (
            "onda-shiye",
            ["bazi_career", "profection", "knowledge_registry", "knowledge_read"],
        ),
        (
            "onda-zige",
            [
                "analyze_destiny",
                "bazi_wealth",
                "bazi_education",
                "two_person_compatibility",
                "ziwei_horoscope",
                "firdaria",
            ],
        ),
    ],
)
def test_actual_restricted_mcp_can_complete_topic_and_stage_followups(
    scenario, sequence
):
    """Invoke real calculators through a single restricted MCP conversation.

    This is a deterministic transport dialogue, not an independent LLM review.
    Each follow-up reuses confirmed fictional inputs and correlates its parent.
    """

    async def run():
        async with Client(create_mcp_app(scenarios=scenario)) as client:
            previous = None
            payloads = {}
            confirmed = {
                **REST_POST_CASES["/api/cn/bazi/birth"](),
                "birth_latitude": 31.2304,
            }
            for key in sequence:
                spec = next(spec for spec in CATALOG if spec.key == key)
                inputs = REST_POST_CASES[spec.rest_path or "/api/cn/bazi/birth"]()
                inputs = {
                    k: v
                    for k, v in inputs.items()
                    if k in spec.request_model.model_fields
                }
                inputs.update(
                    {
                        k: value
                        for k, value in confirmed.items()
                        if k in spec.request_model.model_fields
                    }
                )
                inputs.pop("dayun_pillar", None)
                inputs.pop("liunian_pillar", None)
                if key == "two_person_compatibility":
                    inputs["relationship_type"] = "friendship"
                    inputs.update(
                        {
                            f"person1_{k}": value
                            for k, value in confirmed.items()
                            if f"person1_{k}" in spec.request_model.model_fields
                        }
                    )
                result = await client.call_tool(
                    spec.tool_name,
                    {
                        **inputs,
                        "as_of": "2026-10-20T10:00:00+08:00",
                        "trace_id": f"dependency-{scenario}",
                        "parent_run_id": previous,
                        "response_char_limit": 0,
                        "include_snapshot_text": False,
                    },
                )
                payload = result.structured_content
                assert not result.is_error and payload and "error_code" not in payload
                assert payload["run_metadata"].get("parent_run_id") == previous
                previous = payload["run_metadata"]["run_id"]
                payloads[key] = payload
            if scenario == "onda-zige":
                assert payloads["bazi_wealth"]["wealth_analysis"]
                assert payloads["bazi_education"]["education_analysis"]
                assert payloads["ziwei_horoscope"]["ziwei_horoscope"]["scopes"]
                assert payloads["firdaria"]["firdaria"]["current_major"]
            else:
                assert payloads["bazi_career"]["career_analysis"]
                assert payloads["profection"]["profection"]
                assert payloads["knowledge_read"]["citation"]

    asyncio.run(run())


def test_generator_resolves_interface_dependencies_before_packaging():
    manifest = build_manifest()
    records = {record["id"]: record for record in manifest["scenarios"]}
    closure = dependency_closure(records, {spec.key for spec in CATALOG})
    assert "profection" in closure["onda-zige"]
    assert all(record.get("dependencies") for record in records.values())
