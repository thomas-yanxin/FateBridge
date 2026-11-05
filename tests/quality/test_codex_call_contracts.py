"""Guard on-demand call contracts against interface and projection drift."""

import copy
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
from tests.fixtures.mcp_result_delivery import first_page_uri

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "codex_contract_builder", ROOT / "scripts/build_codex_call_contracts.py"
)
builder = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(builder)


def assert_same_receipt_with_explicit_runtime_delivery(inline, complete, reference):
    restored = copy.deepcopy(inline)
    declared = {
        path
        for path in reference.get("deferred_fields", [])
        if path.startswith("run_metadata.")
    }
    restored_paths = set()
    evidence = restored.get("calculation_evidence")
    if (
        evidence
        and evidence.get("delivery_path") == "run_metadata.calculation_evidence"
    ):
        from fatebridge.utils.json_digest import digest

        path = "run_metadata.calculation_evidence"
        assert path in declared
        assert evidence["sha256"] == digest(complete["calculation_evidence"])
        assert evidence["coverage"] == complete["calculation_evidence"]["coverage"]
        restored["calculation_evidence"] = copy.deepcopy(
            complete["calculation_evidence"]
        )
        restored_paths.add(path)
    runtime = restored.get("runtime") or {}
    if runtime.get("delivery_path") == "run_metadata.runtime":
        assert "run_metadata.runtime" in declared
        actual = complete["runtime"]
        assert runtime["environment_sha256"] == actual["environment_sha256"]
        assert runtime["ephemeris_inventory_sha256"] == actual["ephemeris"]["sha256"]
        assert type(runtime["ephemeris_files_count"]) is int
        assert runtime["ephemeris_files_count"] == len(actual["ephemeris"]["files"])
        restored["runtime"] = actual
        restored_paths.add("run_metadata.runtime")
    for key in complete.keys() - restored.keys():
        # Restore only explicitly deferred supplementary metadata. Essential
        # run identities/hashes must remain inline; do not fill arbitrary gaps.
        assert key in {"provenance", "determinism"}
        path = "run_metadata." + key
        assert path in declared
        restored[key] = copy.deepcopy(complete[key])
        restored_paths.add(path)
    assert declared == restored_paths
    assert restored == complete
    assert json.dumps(restored, sort_keys=True) == json.dumps(complete, sort_keys=True)


def test_receipt_recovery_requires_exact_declarations_and_keeps_essential_identity_inline():
    complete = {
        "run_id": "same-run",
        "business_output_sha256": "a" * 64,
        "runtime": {
            "environment_sha256": "b" * 64,
            "ephemeris": {"sha256": "c" * 64, "files": {"sepl_18.se1": "d" * 64}},
        },
        "provenance": {"source": "same-run receipt"},
        "determinism": {"randomness_used": False},
    }
    inline = {
        key: copy.deepcopy(value)
        for key, value in complete.items()
        if key not in {"provenance", "determinism"}
    }
    inline["runtime"] = {
        "delivery_path": "run_metadata.runtime",
        "environment_sha256": "b" * 64,
        "ephemeris_inventory_sha256": "c" * 64,
        "ephemeris_files_count": 1,
    }
    reference = {
        "deferred_fields": [
            "run_metadata.runtime",
            "run_metadata.provenance",
            "run_metadata.determinism",
        ]
    }
    assert_same_receipt_with_explicit_runtime_delivery(inline, complete, reference)
    for patch in [
        {"deferred_fields": ["run_metadata.runtime"]},
        {"deferred_fields": [*reference["deferred_fields"], "run_metadata.unused"]},
    ]:
        with pytest.raises(AssertionError):
            assert_same_receipt_with_explicit_runtime_delivery(inline, complete, patch)
    missing_identity = {k: v for k, v in inline.items() if k != "run_id"}
    with pytest.raises(AssertionError):
        assert_same_receipt_with_explicit_runtime_delivery(
            missing_identity,
            complete,
            {"deferred_fields": [*reference["deferred_fields"], "run_metadata.run_id"]},
        )
    corrupted = copy.deepcopy(inline)
    corrupted["runtime"]["ephemeris_files_count"] = 2
    with pytest.raises(AssertionError):
        assert_same_receipt_with_explicit_runtime_delivery(
            corrupted, complete, reference
        )
    corrupted["runtime"]["ephemeris_files_count"] = True
    with pytest.raises(AssertionError):
        assert_same_receipt_with_explicit_runtime_delivery(
            corrupted, complete, reference
        )


@pytest.mark.asyncio
async def test_normally_loaded_contracts_match_current_public_interface():
    for name, text in (await builder.render_files()).items():
        assert (builder.TARGET / name).read_text(encoding="utf-8") == text
    guidance = (ROOT / "AGENTS.md").read_bytes()
    assert len(guidance) < 8192  # Repository context budget, below Codex's default cap.
    assert b'"properties"' not in guidance


@pytest.mark.asyncio
async def test_contract_publication_ignores_object_order_but_preserves_constraints(
    monkeypatch,
):
    records = await builder.call_contracts()
    baseline = await builder.render_files()

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
    assert await builder.render_files() == baseline
    # Published tools need not all be birth_* interfaces (e.g. heluo/canping).
    birth_record = next(item for item in reordered if item["tool"] == "bazi_career")
    birth_record["input"]["properties"]["birth_hour"]["maximum"] = 22
    assert await builder.render_files() != baseline


@pytest.mark.asyncio
async def test_published_contract_keeps_required_time_and_solar_flag_constraints():
    record = next(
        item for item in await builder.call_contracts() if item["tool"] == "bazi_career"
    )
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
async def test_published_stage_view_retains_actual_period_boundaries():
    """A on-demand contract must support stage reading without rediscovery."""
    record = next(
        item
        for item in await builder.call_contracts()
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
        payload = result.structured_content
        if "result_delivery" in payload:
            reference = payload["result_delivery"]
            pieces = []
            uri = await first_page_uri(client, reference)
            while uri:
                page = json.loads((await client.read_resource(uri))[0].text)
                pieces.append(page["text"])
                uri = page["next_uri"]
            payload = json.loads("".join(pieces))
        assert not result.is_error
        firdaria = payload["time_lords"]["firdaria"]
        for period in (firdaria["current_major"], firdaria["current_sub"]):
            assert period["planet"] and period["start"] < period["end"]


@pytest.mark.asyncio
@pytest.mark.local_data
async def test_only_published_inputs_and_views_are_enough_for_real_mcp_calls():
    from tests.support.compatibility_reference import (
        assert_source_condition_score_reference,
    )

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
                uri = await first_page_uri(client, reference)
                while uri:
                    page = json.loads((await client.read_resource(uri))[0].text)
                    pieces.append(page["text"])
                    uri = page["next_uri"]
                text = "".join(pieces)
                assert hashlib.sha256(text.encode()).hexdigest() == reference["sha256"]
                original_receipt = payload["run_metadata"]
                payload = json.loads(text)
                assert_same_receipt_with_explicit_runtime_delivery(
                    original_receipt, payload["run_metadata"], reference
                )
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
    async with Client(create_mcp_app(scenarios="onda-fengshui")) as client:
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
            payload = result.structured_content
            if "result_delivery" in payload:
                reference = payload["result_delivery"]
                pieces = []
                uri = await first_page_uri(client, reference)
                while uri:
                    page = json.loads((await client.read_resource(uri))[0].text)
                    pieces.append(page["text"])
                    uri = page["next_uri"]
                text = "".join(pieces)
                assert hashlib.sha256(text.encode()).hexdigest() == reference["sha256"]
                original_receipt = payload["run_metadata"]
                payload = json.loads(text)
                assert_same_receipt_with_explicit_runtime_delivery(
                    original_receipt, payload["run_metadata"], reference
                )
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
