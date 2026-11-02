"""Actual root endpoint activations, candidate structures and bounded cards."""

import asyncio
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client
from jsonschema import Draft202012Validator

import fatebridge.api as api
from fatebridge.application.examples import evidence_views
from fatebridge.cli import run
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.validation.human_design import verify_human_design_reading

ROOT = Path(__file__).resolve().parents[1]
PLAN = json.loads(
    (ROOT / "tests/fixtures/human-design-root-body-plan.json").read_text()
)
SPEC = next(s for s in CATALOG if s.key == "human_design")


@pytest.fixture
def rest(monkeypatch):
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    with TestClient(api.app) as client:
        yield client


@pytest.mark.parametrize("mode", ["true", "mean"])
@pytest.mark.parametrize("empty_files", [False, True])
@pytest.mark.parametrize("case_index", [0, 2, 3])
def test_real_three_surface_full_reading_and_card(
    case_index, empty_files, mode, rest, capsys, monkeypatch, tmp_path
):
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path if empty_files else ROOT / "ephe"))
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    params = {**PLAN["cases"][case_index]["input"], "node_mode": mode}
    response = rest.post(SPEC.rest_path, json=params)
    assert response.status_code == 200, response.text
    expected = response.json()
    Draft202012Validator(SPEC.output_model.model_json_schema()).validate(expected)

    async def call():
        async with Client(create_mcp_app(families="astro")) as client:
            result = await client.call_tool(
                "human_design", {**params, "response_char_limit": 0}
            )
            assert not result.is_error
            card = await client.call_tool(
                "human_design",
                {
                    **params,
                    "fields": evidence_views(SPEC)["root_endpoints"]["fields"],
                    "strict_fields": True,
                    "include_snapshot_text": False,
                    "response_char_limit": 0,
                },
            )
            assert not card.is_error
            assert (
                card.structured_content["design_solver"]["numerical_precision"][
                    "design_body_endpoint_summary"
                ]
                == expected["design_solver"]["numerical_precision"][
                    "design_body_endpoint_summary"
                ]
            )
            return result.structured_content

    native = asyncio.run(call())
    flags = [
        "human_design",
        *(
            part
            for k, v in params.items()
            for part in ("--" + k.replace("_", "-"), str(v))
        ),
    ]
    assert run(flags) == 0
    cli = json.loads(capsys.readouterr().out)
    for value in (expected, native, cli):
        check = verify_human_design_reading(value)
        assert check["status"] == "verified_fixed_template_reading", check
        p = value["design_solver"]["numerical_precision"]
        assert p["other_bodies_bracket_sensitivity_assessed"] is True
        proof = p["design_body_endpoint_assessment"]
        assert proof["continuous_interval_stability_certified"] is False
        assert proof["physical_time_accuracy_certified"] is False
        if not empty_files and case_index == 2:
            assert "subtype" in proof["observed_structure_changed_fields"]
            assert "子型" in value["interpretation"]["design_time_precision_meaning"]
        value.pop("run_metadata")
    assert expected == native == cli
