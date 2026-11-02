"""Narrow primary-diagram facts and qualifiers survive all three adapters."""

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


@pytest.mark.parametrize("empty_files", [False, True])
@pytest.mark.parametrize(
    "case_id", ["cross-left-09", "cross-left-16", "cross-right-16"]
)
@pytest.mark.parametrize("node_mode", ["true", "mean"])
def test_primary_diagram_and_qualifications_on_all_three_surfaces(
    rest, capsys, monkeypatch, tmp_path, empty_files, case_id, node_mode
):
    if empty_files:
        monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    root = Path(__file__).resolve().parents[1]
    if not empty_files:
        monkeypatch.setenv("SE_EPHE_PATH", str(root / "ephe"))
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    cohort = json.loads(
        (root / "tests/fixtures/human-design-official-cross-charts.json").read_text()
    )
    case = next(c for c in cohort["cases"] if c["id"] == case_id)
    params = {**case["birth_input"], "node_mode": node_mode}
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
                    "fields": evidence_views(SPEC)["primary_diagrams"]["fields"],
                    "strict_fields": True,
                    "include_snapshot_text": False,
                    "response_char_limit": 0,
                },
            )
            assert not card.is_error
            assert (
                card.structured_content["source_consistency"][
                    "primary_transcript_diagrams"
                ]
                == expected["source_consistency"]["primary_transcript_diagrams"]
            )
            return result.structured_content

    native = asyncio.run(call())
    flags = ["human_design"]
    for key, value in params.items():
        flags.extend(["--" + key.replace("_", "-"), str(value)])
    assert run(flags) == 0
    cli = json.loads(capsys.readouterr().out)
    for value in (expected, native, cli):
        check = verify_human_design_reading(value)
        assert check["status"] == "verified_fixed_template_reading", check
        matched = case_id in {"cross-left-09", "cross-left-16"}
        assert check["checked_statement_count"] == (11 if matched else 10)
        proof = value["source_consistency"]["primary_transcript_diagrams"]
        assert len(proof["observations"]) == (1 if matched else 0)
        assert proof["transcription_proofed"] is False
        assert proof["publisher_master_authenticated"] is False
        assert proof["publisher_erratum_obtained"] is False
        assert proof["all_source_disagreements_resolved"] is False
        assert proof["full_source_acceptance_passed"] is False
        if matched:
            assert (
                proof["observations"][0]["gates"] == value["incarnation_cross"]["gates"]
            )
            assert value["interpretation"]["statements"][-1]["text"] == proof["reading"]
        assert (
            value["source_consistency"]["version_comparison"]["literal_name_matches"]
            == 4
        )
        assert value["validation"]["all_three_axes_full_marks"] is False
        value.pop("run_metadata")
    assert expected == native == cli
