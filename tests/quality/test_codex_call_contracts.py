"""Guard on-demand call contracts against interface and projection drift."""

import asyncio
from pathlib import Path

import pytest
from fastmcp import Client
from jsonschema import ValidationError, validate

from fatebridge.application.examples import example_input, suggested_fields
from fatebridge.services.tool_catalog import CATALOG
from scripts import build_codex_call_contracts as builder
from tests.fixtures.mcp_receipt import verified_inline_business
from tests.support.transports import cached_mcp_app, call_calculation


@pytest.fixture(scope="module")
def published_contracts():
    return asyncio.run(builder.call_contracts())


@pytest.mark.asyncio
async def test_normally_loaded_contracts_match_current_public_interface(
    published_contracts, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def contracts():
        return published_contracts

    monkeypatch.setattr(builder, "call_contracts", contracts)
    await builder.main(["--check"])


def test_contract_publication_ignores_object_order_but_preserves_constraints(
    published_contracts,
) -> None:
    baseline = builder.render_files(published_contracts)

    def reverse_objects(value):
        if isinstance(value, dict):
            return {
                key: reverse_objects(item)
                for key, item in reversed(list(value.items()))
            }
        else:
            pass
        if isinstance(value, list):
            return [reverse_objects(item) for item in value]
        else:
            pass
        return value

    reordered = reverse_objects(published_contracts)
    assert builder.render_files(reordered) == baseline
    birth_record = next(item for item in reordered if item["tool"] == "bazi_career")
    birth_record["input"]["properties"]["birth_hour"]["maximum"] = 22
    assert builder.render_files(reordered) != baseline


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["missing", "changed", "obsolete"])
async def test_contract_generation_repairs_drift_and_removes_retired_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
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
) -> None:
    record = next(item for item in published_contracts if item["tool"] == "bazi_career")
    spec = next(s for s in CATALOG if s.name == record["tool"])
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
) -> None:
    """A on-demand contract must support stage reading without rediscovery."""
    record = next(
        item for item in published_contracts if item["tool"] == "western_timing"
    )
    spec = next(s for s in CATALOG if s.name == record["tool"])
    async with Client(cached_mcp_app()) as client:
        result = await call_calculation(
            client,
            record["tool"],
            {
                **example_input(spec),
                "fields": record["evidence_views"]["stage"]["fields"],
            },
        )
        assert not result.is_error
        payload = result.structured_content
        firdaria = payload["time_lords"]["firdaria"]
        for period in (firdaria["current_major"], firdaria["current_sub"]):
            assert period["planet"] and period["start"] < period["end"]


@pytest.mark.asyncio
@pytest.mark.local_data
async def test_only_published_inputs_and_views_are_enough_for_real_mcp_calls(
    published_contracts,
) -> None:
    records = published_contracts
    specs = {s.name: s for s in CATALOG}
    async with Client(cached_mcp_app()) as client:
        for record in records:
            arguments = example_input(specs[record["tool"]])
            validate(arguments, record["input"])
            result = await client.call_tool(
                "run_calculation",
                {
                    "tool": record["tool"],
                    "arguments": arguments,
                    **record["first_view"],
                    "as_of": "2026-10-12T12:00:00+08:00",
                },
            )
            assert not result.is_error
            payload = result.structured_content
            assert payload["run_metadata"]["tool_name"] == specs[record["tool"]].name
            if record["tool"] == "bazi_career":
                career = payload["career_analysis"]
                topic_facts = career["topic_facts"]
                assert topic_facts["natal_stars"] == [
                    {"ten_god": "正官", "visible_in": [], "hidden_in": ["year(午)"]},
                    {
                        "ten_god": "七杀",
                        "visible_in": [],
                        "hidden_in": ["month(巳)", "hour(巳)"],
                    },
                    {"ten_god": "正印", "visible_in": [], "hidden_in": ["year(午)"]},
                    {
                        "ten_god": "偏印",
                        "visible_in": [],
                        "hidden_in": ["month(巳)", "day(辰)", "hour(巳)"],
                    },
                    {"ten_god": "伤官", "visible_in": [], "hidden_in": ["day(辰)"]},
                    {"ten_god": "正财", "visible_in": [], "hidden_in": ["day(辰)"]},
                ]
                assert career["timing_context"]["analysis_datetime"] == (
                    "2026-10-12T00:00:00+08:00"
                )
            elif record["tool"] == "bazi_compatibility":
                for person in ("person1", "person2"):
                    assert set(payload["natal_contexts"][person]["four_pillars"]) == {
                        "year",
                        "month",
                        "day",
                        "hour",
                    }
                assert payload["cross_chart_relations"]["pairs"]
            elif record["tool"] == "horary_chart":
                horary = payload["horary_chart"]
                assert horary["perfection"]["status"] == "same_ruler"
                assert horary["significators"]["querent"]["planet"]
                assert horary["significators"]["quesited"]["planet"]
            elif record["tool"] == "bazi_timing":
                assert payload["person_info"]["analysis_datetime"] == (
                    "2026-10-12 00:00"
                )
                calendar = payload["analysis_calendar"]["analysis_date_context"]
                assert calendar["timezone"] == "Asia/Shanghai"
                assert calendar["current_solar_term"]["name"] == "寒露"
                assert calendar["next_solar_term"]["name"] == "霜降"
                assert calendar["bazi_month_boundary"]["branch"] == "戌"
            elif record["tool"] == "fengshui_assess":
                assert "layout_analysis" in payload
                assert "calculation_scope" in payload["layout_analysis"]
            elif record["tool"] == "western_timing":
                assert (
                    payload["analysis_context"]["analysis_datetime"]
                    == "2026-10-14T12:00:00+08:00"
                )
                assert (
                    payload["transits"]["current_transit"]["analysis_datetime"]
                    == "2026-10-14T12:00:00+08:00"
                )
            else:
                pass


@pytest.mark.asyncio
async def test_fengshui_first_views_deliver_core_layers_without_audit_bloat() -> None:
    """A successful calculation delivers layers and coverage without ruleset/trace bloat."""
    async with Client(cached_mcp_app(families="fengshui")) as client:
        for spec in CATALOG:
            if spec.family != "fengshui" or not spec.expose_mcp:
                continue
            else:
                pass
            example = example_input(spec)
            if example is None:
                assert spec.name == "fengshui_monthly_stars"
                # Explicit confirmed-month fixture, independent of any user.
                example = {"effective_solar_year": 2026, "solar_month_number": 1}
            else:
                pass
            result = await call_calculation(
                client,
                spec.name,
                {
                    **example,
                    "fields": suggested_fields(spec),
                },
            )
            assert not result.is_error
            payload = await verified_inline_business(client, result.structured_content)
            assert payload["status"] in {"complete", "partial"}
            assert payload["coverage"]
            for forbidden in ("rulesets", "rule_trace", "source_catalog"):
                assert forbidden not in payload
