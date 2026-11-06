"""Guard on-demand call contracts against interface and projection drift."""

import asyncio

import pytest
from fastmcp import Client
from jsonschema import ValidationError, validate

from fatebridge.application.examples import example_input, suggested_fields
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.tool_catalog import CATALOG
from scripts import build_codex_call_contracts as builder
from tests.fixtures.mcp_result_delivery import read_full_result


@pytest.fixture(scope="module")
def published_contracts():
    return asyncio.run(builder.call_contracts())


@pytest.mark.asyncio
async def test_normally_loaded_contracts_match_current_public_interface(
    published_contracts, monkeypatch
):
    async def contracts():
        return published_contracts

    monkeypatch.setattr(builder, "call_contracts", contracts)
    await builder.main(["--check"])


def test_contract_publication_ignores_object_order_but_preserves_constraints(
    published_contracts,
):
    baseline = builder.render_files(published_contracts)

    def reverse_objects(value):
        if isinstance(value, dict):
            return {
                key: reverse_objects(item)
                for key, item in reversed(list(value.items()))
            }
        if isinstance(value, list):
            return [reverse_objects(item) for item in value]
        return value

    reordered = reverse_objects(published_contracts)
    assert builder.render_files(reordered) == baseline
    birth_record = next(item for item in reordered if item["tool"] == "bazi_career")
    birth_record["input"]["properties"]["birth_hour"]["maximum"] = 22
    assert builder.render_files(reordered) != baseline


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["missing", "changed", "obsolete"])
async def test_contract_generation_repairs_drift_and_removes_retired_json(
    tmp_path, monkeypatch, change
):
    async def contracts():
        return [{"tool": "active", "input": {"type": "object"}}]

    monkeypatch.setattr(builder, "call_contracts", contracts)
    monkeypatch.setattr(builder, "TARGET", tmp_path)
    await builder.main([])
    note = tmp_path / "maintenance.md"
    note.write_text("Keep authored notes")
    active = tmp_path / "active.json"
    retired = tmp_path / "retired.json"
    if change == "missing":
        active.unlink()
    elif change == "changed":
        active.write_text("{}")
    else:
        retired.write_text("{}")
    with pytest.raises(SystemExit, match="active.json|retired.json"):
        await builder.main(["--check"])
    # Checking is read-only; generation repairs the exact publication set.
    assert retired.exists() is (change == "obsolete")
    assert active.exists() is (change != "missing")
    await builder.main([])
    await builder.main(["--check"])
    assert {p.name for p in tmp_path.glob("*.json")} == {"active.json"}
    assert note.read_text() == "Keep authored notes"


def test_published_contract_keeps_required_time_and_solar_flag_constraints(
    published_contracts,
):
    record = next(item for item in published_contracts if item["tool"] == "bazi_career")
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
async def test_published_stage_view_retains_actual_period_boundaries(
    published_contracts,
):
    """A on-demand contract must support stage reading without rediscovery."""
    record = next(
        item
        for item in published_contracts
        if item["tool"] == "western_timing_analysis"
    )
    spec = next(s for s in CATALOG if s.tool_name == record["tool"])
    async with Client(create_mcp_app()) as client:
        result = await client.call_tool(
            record["tool"],
            {
                **example_input(spec),
                "fields": record["evidence_views"]["stage"]["fields"],
                "strict_fields": True,
                "include_snapshot_text": False,
            },
        )
        assert not result.is_error
        payload = await read_full_result(client, result.structured_content)
        firdaria = payload["time_lords"]["firdaria"]
        for period in (firdaria["current_major"], firdaria["current_sub"]):
            assert period["planet"] and period["start"] < period["end"]


@pytest.mark.asyncio
@pytest.mark.local_data
async def test_only_published_inputs_and_views_are_enough_for_real_mcp_calls(
    published_contracts,
):
    from tests.support.compatibility_reference import (
        assert_source_condition_score_reference,
    )

    records = published_contracts
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
            payload = await read_full_result(client, result.structured_content)
            assert (
                payload["run_metadata"]["tool_name"]
                == specs[record["tool"]].run_metadata_name
            )
            if record["tool"] == "bazi_career":
                # Published 庚午 辛巳 庚辰 辛巳: non-day stems have weight 1,
                # all four branches' hidden stems weight .5. This is a manual
                # occurrence ledger, not values copied from the program.
                career = payload["career_analysis"]
                assert career["dominant_ten_gods"]["weighted_counts"] == {
                    "比肩": 2,
                    "劫财": 2,
                    "食神": 0,
                    "伤官": 0.5,
                    "正财": 0.5,
                    "偏财": 0,
                    "正官": 0.5,
                    "七杀": 1,
                    "正印": 0.5,
                    "偏印": 1.5,
                }
                assert {
                    s["label"]: s["score_delta"]
                    for s in career["career_structure"]["rule_signals"]
                } == {
                    "官印相生": 15,
                    "食伤生财": 10,
                    "财官双美": 8,
                }
                # v4/v5 root qualification makes this particular model label
                # 强: the unchanged +5 branch and cap apply, 98 -> 95.
                assert career["career_structure"]["score"] == min(
                    95, 60 + 15 + 10 + 8 + 5
                )
                assert any(
                    "日主强旺" in note for note in career["career_structure"]["notes"]
                )
                assert "timing_context" in payload["career_analysis"]
            elif record["tool"] == "two_person_compatibility":
                # This live source case has no first-person preference decision;
                # the original full-profile literal ledger is a different input.
                first = payload["person_info"]["person1"]["preference_assessment"]
                assert first["useful_elements"] == first["avoid_elements"] == []
                assert set(first["conditional_elements"]) == {"火", "土", "水"}
                assert set(first["neutral_elements"]) == {"木", "金"}
                assert_source_condition_score_reference(
                    payload["summary"], payload["detailed_analysis"]
                )
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
    async with Client(create_mcp_app(families="fengshui")) as client:
        for spec in CATALOG:
            if spec.family != "fengshui" or not spec.mcp_name:
                continue
            example = example_input(spec)
            if example is None:
                assert spec.key == "fengshui_monthly_stars"
                # Explicit confirmed-month fixture, independent of any user.
                example = {"effective_solar_year": 2026, "solar_month_number": 1}
            result = await client.call_tool(
                spec.tool_name,
                {
                    **example,
                    "fields": suggested_fields(spec),
                    "strict_fields": True,
                    "include_snapshot_text": False,
                },
            )
            assert not result.is_error
            payload = await read_full_result(client, result.structured_content)
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
