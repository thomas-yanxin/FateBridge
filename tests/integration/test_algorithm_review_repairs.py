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
from tests.support.transports import call_calculation

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
    preference_state: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fatebridge.services import compatibility

    # These birthdays are inputs, not an independent oracle for whether a
    # later natal algorithm resolves preferences. Exercise the declared empty
    # upstream boundary explicitly; keep both known-neutral and unknown facts.
    build_payload = compatibility.build_destiny_payload

    def empty_preferences(context):
        payload = deepcopy(build_payload(context))
        profile = payload["structure_profile"]
        preferences = dict(
            useful_elements=[],
            avoid_elements=[],
            conditional_elements=[],
            neutral_elements=(
                ["金", "木", "水", "火", "土"] if preference_state == "neutral" else []
            ),
            useful_ten_gods=[],
            assessment_status="partial",
        )
        profile.update(preferences)
        profile["engineering_reference"].update(preferences)
        payload["favorable_elements"] = []
        return payload

    monkeypatch.setattr(compatibility, "build_destiny_payload", empty_preferences)
    spec = SPECS["two_person_compatibility"]
    result = execution.execute_tool(
        spec, spec.request_model.model_validate(unresolved_pair())
    )
    assert "error" not in result
    preferences_neutral = (
        ["金", "木", "水", "火", "土"] if preference_state == "neutral" else []
    )
    for person in result["natal_contexts"].values():
        profile = person["preference_assessment"]
        assert profile["useful_elements"] == profile["avoid_elements"] == []
        assert profile["neutral_elements"] == preferences_neutral
    assert result["element_relationship"]["relationship_type"]


def test_compatibility_reports_both_out_of_range_birth_years(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import fatebridge.api as api

    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    spec = SPECS["two_person_compatibility"]
    inputs = example_input(spec) | {
        "person1_birth_year": 1899,
        "person2_birth_year": 2101,
    }

    response = TestClient(api.app).post(spec.rest_path, json=inputs)

    assert response.status_code == 422
    assert response.json()["issues"] == [
        {
            "path": "person1_birth_year",
            "code": "greater_than_equal",
            "message": "Input should be greater than or equal to 1900",
            "constraints": {"ge": 1900},
        },
        {
            "path": "person2_birth_year",
            "code": "less_than_equal",
            "message": "Input should be less than or equal to 2100",
            "constraints": {"le": 2100},
        },
    ]


@pytest.mark.parametrize(
    "key,body",
    [
        ("qimen", {"qimen": {}}),
        ("taiyi", {"taiyi": {}}),
        ("ziwei_birth", {"ziwei_birth": {}}),
        ("astro_chart", {"planets": [], "chart_profile": {}}),
        (
            "two_person_compatibility",
            {
                "natal_contexts": {},
                "cross_chart_relations": {},
                "directional_ten_gods": {},
            },
        ),
    ],
)
def test_original_empty_success_counterexamples_are_internal_errors(
    key: str, body
) -> None:
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
    key: str, root: str | None, identity: str
) -> None:
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


def test_complete_nested_fact_rules_are_published_and_fingerprinted() -> None:
    from fatebridge.core.schema_cache import model_schema

    schema = model_schema(SPECS["qimen"].output_model)
    field = schema["$defs"]["Qimen"]["properties"]["palaces"]
    assert field["x-fatebridge-full-result"] == "non_null"
    assert field["x-fatebridge-full-result-unique-by"] == "index"
    assert field["anyOf"][0]["minItems"] == field["anyOf"][0]["maxItems"] == 9


@pytest.mark.parametrize("spec", CATALOG, ids=lambda spec: spec.key)
def test_no_catalog_tool_accepts_empty_objects_for_all_required_business_roots(
    spec,
) -> None:
    body = {field: {} for field in spec.required_output_fields}
    with pytest.raises(execution.OutputContractError):
        execution.validate_output(spec, body)


def test_missing_required_timing_layer_fails_on_every_transport(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import fatebridge.api as api
    from fatebridge.cli import run
    from fatebridge.core.timing import TimingAnalysis
    from fatebridge.mcp_server import app
    from fatebridge.utils.errors import EphemerisSourceError

    def unavailable(*args, **kwargs):
        raise EphemerisSourceError("solar_de440_invalid")

    monkeypatch.setattr(TimingAnalysis, "calculate_liushi", unavailable)
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
            return await call_calculation(
                client,
                "bazi_hourly_timing",
                {**inputs, "response_char_limit": 0},
                raise_on_error=False,
            )

    protocol = asyncio.run(native())
    argv = ["bazi_hourly_timing"]
    for key, value in inputs.items():
        argv += [
            "--" + key.replace("_", "-"),
            str(value).lower() if isinstance(value, bool) else str(value),
        ]
    assert run(argv) == 1
    local = json.loads(capsys.readouterr().out)
    assert http.status_code == 503 and protocol.is_error
    for result in [http.json(), protocol.structured_content, local]:
        assert "error" in result and "liushi_info" not in result
