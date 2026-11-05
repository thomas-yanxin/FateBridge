"""Observed review failures retain unknowns and reject incomplete computation."""

import asyncio
import json
import subprocess
import sys
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

from fatebridge.application import execution
from fatebridge.application.examples import example_input
from fatebridge.services.tool_catalog import CATALOG
from tests.fixtures.surface_payloads import REST_POST_CASES

SPECS = {spec.key: spec for spec in CATALOG}


def unresolved_pair():
    inputs = example_input(SPECS["two_person_compatibility"])
    for index, day in ((1, 2), (2, 17)):
        for key, value in {
            "birth_year": 1990,
            "birth_month": 5,
            "birth_day": day,
            "birth_hour": 10,
            "birth_minute": 30,
            "birth_timezone": "Asia/Shanghai",
            "use_true_solar_time": False,
        }.items():
            inputs[f"person{index}_{key}"] = value
    return inputs


@pytest.mark.parametrize("preference_state", ["neutral", "unknown"])
def test_empty_preferences_do_not_become_penalty_support_or_definite_match(
    preference_state, monkeypatch
):
    from fatebridge.services import compatibility

    # These birthdays are inputs, not an independent oracle for whether a
    # later natal algorithm resolves preferences. Exercise the declared empty
    # upstream boundary explicitly; keep both known-neutral and unknown facts.
    build_payload = compatibility.build_destiny_payload

    def empty_preferences(context):
        payload = deepcopy(build_payload(context))
        profile = payload["structure_profile"]
        profile.update(
            useful_elements=[],
            avoid_elements=[],
            conditional_elements=[],
            neutral_elements=(
                ["金", "木", "水", "火", "土"] if preference_state == "neutral" else []
            ),
            useful_ten_gods=[],
            assessment_status="partial",
        )
        payload["favorable_elements"] = []
        return payload

    monkeypatch.setattr(compatibility, "build_destiny_payload", empty_preferences)
    spec = SPECS["two_person_compatibility"]
    result = execution.execute_tool(
        spec, spec.request_model.model_validate(unresolved_pair())
    )
    assert "error" not in result
    for person in result["person_info"].values():
        profile = person["preference_assessment"]
        assert profile["useful_elements"] == profile["avoid_elements"] == []
    balance = result["detailed_analysis"]["element_balance"]
    assert balance["balance_type"] == (
        "相克中性参考" if preference_state == "neutral" else "相克取用待定"
    )
    assert {row["state"] for row in balance["control_evidence"]} == {preference_state}
    assert not any("压制感" in line for line in balance["details"])
    synergy = result["detailed_analysis"]["favorable_synergy"]
    assert synergy["synergy_level"] == "待取用裁定"
    assert not synergy["score_evidence"]["base_score_is_support_evidence"]
    assert result["summary"]["status"] == "partial"
    assert "未裁定" in result["summary"]["compatibility_level"]
    scoring = result["summary"]["scoring"]
    assert (
        scoring["dependency_policy"]
        == "shared_natal_inputs_not_independent_evidence_v1"
    )
    assert set(scoring["dimension_dependencies"]) == set(scoring["dimensions"])
    assert "both_natal_pillars" in scoring["dimension_dependencies"]["pattern_synergy"]
    assert (
        "both_natal_pillars"
        in scoring["dimension_dependencies"]["traditional_analysis"]
    )
    for path in (
        ("summary", "overall_score"),
        ("summary", "scoring", "unrounded_score"),
        ("summary", "scoring", "dimensions", "element_balance", "weighted_score"),
    ):
        damaged = deepcopy(result)
        owner = damaged
        for key in path[:-1]:
            owner = owner[key]
        owner[path[-1]] += 1
        with pytest.raises(execution.OutputContractError):
            execution.validate_output(spec, damaged)
    spec.output_model.model_validate(
        {"summary": {"scoring": {"dimensions": {"element_balance": {"score": 74.0}}}}}
    )


@pytest.mark.parametrize("key", ["two_person_compatibility", "liushi_analysis"])
def test_versioned_method_semantics_agree_on_discovery_transports(
    key, monkeypatch, capsys
):
    import fatebridge.api as api
    from fatebridge.cli import run
    from fatebridge.mcp_server import app

    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    spec = SPECS[key]
    assert run(["describe", key]) == 0
    local = json.loads(capsys.readouterr().out)
    http = (
        TestClient(api.app).get("/api/tools", params={"tool": key}).json()["tools"][0]
    )

    async def native():
        async with Client(app) as client:
            contents = await client.read_resource(
                f"fatebridge://tools/{spec.tool_name}"
            )
            return json.loads(contents[0].text)["tools"][0]

    protocol = asyncio.run(native())
    expected = [method.as_manifest() for method in spec.methods]
    for record in (local, http, protocol):
        assert record["method_contracts"] == expected
        assert record["method_contract_coverage"] == "declared_subset"
    inputs = example_input(spec) or REST_POST_CASES[spec.rest_path]()
    result = execution.execute_spec(spec, spec.request_model.model_validate(inputs))
    method = (
        result["summary"]["scoring"]["method_id"]
        if key == "two_person_compatibility"
        else result["life_dimensions_assessment"]["method_id"]
    )
    assert method == expected[0]["method_id"]


@pytest.mark.parametrize(
    "key,body",
    [
        ("qimen", {"qimen": {}}),
        ("taiyi", {"taiyi": {}}),
        ("ziwei_birth", {"ziwei_birth": {}}),
        ("astro_chart", {"planets": [], "chart_profile": {}}),
        (
            "two_person_compatibility",
            {"summary": {}, "detailed_analysis": {}, "traditional_compatibility": {}},
        ),
    ],
)
def test_original_empty_success_counterexamples_are_internal_errors(key, body):
    spec = SPECS[key]
    request = spec.request_model.model_validate(example_input(spec))
    broken = replace(spec, bind=lambda _: (lambda: body, (), {}))
    result = execution.execute_tool(broken, request)
    assert result["error_code"] == "internal_error"
    assert "run_metadata" not in result
    # An explicitly projected object may omit facts; it is not a full execution.
    spec.output_model.model_validate({})


@pytest.mark.parametrize(
    "key,root,identity",
    [
        ("qimen", "qimen", "palaces"),
        ("ziwei_birth", "ziwei_birth", "palaces"),
        ("astro_chart", None, "planets"),
    ],
)
def test_complete_collections_require_distinct_members_without_restricting_projection(
    key, root, identity
):
    spec = SPECS[key]
    request = spec.request_model.model_validate(example_input(spec))
    result = execution.execute_spec(spec, request)
    damaged = deepcopy(result)
    owner = damaged[root] if root else damaged
    owner[identity][-1] = deepcopy(owner[identity][0])
    with pytest.raises(execution.OutputContractError):
        execution.validate_output(spec, damaged)
    projected = {identity: [{}]} if root is None else {root: {identity: [{}]}}
    # Projection keeps the original array length. Object fields may disappear.
    count = len(owner[identity])
    (projected[root] if root else projected)[identity] = [{} for _ in range(count)]
    spec.output_model.model_validate(projected)


def test_complete_nested_fact_rules_are_published_and_fingerprinted():
    from fatebridge.core.schema_cache import model_schema

    schema = model_schema(SPECS["qimen"].output_model)
    field = schema["$defs"]["Qimen"]["properties"]["palaces"]
    assert field["x-fatebridge-full-result"] == "non_null"
    assert field["x-fatebridge-full-result-unique-by"] == "index"
    assert field["anyOf"][0]["minItems"] == field["anyOf"][0]["maxItems"] == 9


@pytest.mark.parametrize("spec", CATALOG, ids=lambda spec: spec.key)
def test_no_catalog_tool_accepts_empty_objects_for_all_required_business_roots(spec):
    body = {field: {} for field in spec.required_output_fields}
    with pytest.raises(execution.OutputContractError):
        execution.validate_output(spec, body)


def test_missing_required_timing_layer_fails_on_every_transport(monkeypatch, capsys):
    import fatebridge.api as api
    from fatebridge.cli import run
    from fatebridge.core.timing import TimingAnalysis
    from fatebridge.mcp_server import app
    from fatebridge.utils.errors import EphemerisSourceError

    def unavailable(*args, **kwargs):
        raise EphemerisSourceError("solar_de440_invalid")

    monkeypatch.setattr(TimingAnalysis, "calculate_liuyue", unavailable)
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    spec = SPECS["liushi_analysis"]
    inputs = REST_POST_CASES[spec.rest_path]()
    http = TestClient(api.app).post(spec.rest_path, json=inputs)

    async def native():
        async with Client(app) as client:
            return await client.call_tool(
                "liushi_analysis",
                {**inputs, "response_char_limit": 0},
                raise_on_error=False,
            )

    protocol = asyncio.run(native())
    argv = ["liushi_analysis"]
    for key, value in inputs.items():
        argv += [
            "--" + key.replace("_", "-"),
            str(value).lower() if isinstance(value, bool) else str(value),
        ]
    assert run(argv) == 1
    local = json.loads(capsys.readouterr().out)
    assert http.status_code == 503 and protocol.is_error
    for result in [http.json(), protocol.structured_content, local]:
        assert "error" in result and "life_dimensions" not in result


def test_human_design_audit_direct_entry_resolves_its_actual_script_dependencies(
    tmp_path,
):
    script = Path(__file__).resolve().parents[1] / "scripts/audit_human_design.py"
    result = subprocess.run(
        [sys.executable, str(script), "--help"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "--require-professional-acceptance" in result.stdout
