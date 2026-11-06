"""Projection and real adapter consistency for joined reading facts."""

import json
from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from tests.support.canping_output_injection import (
    inject_canping_output as return_frozen_output,
)
from tests.support.transports import SPECS, business
from tests.support.transports import rest as shared_rest
from tests.support.transports import run_three

rest = shared_rest
ROOT = Path(__file__).parents[1] / "fixtures/canping_reading_context_v1"
REFERENCE = json.loads((ROOT / "reference-v2.json").read_bytes())


@pytest.fixture(autouse=True)
def native_model(monkeypatch, tmp_path):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path / "empty-ephe"))


@pytest.mark.parametrize("profile", list(REFERENCE["roles_by_profile"]))
@pytest.mark.parametrize("clock", REFERENCE["clock_cases"][:2], ids=lambda r: r["zone"])
@pytest.mark.parametrize("projected", [False, True])
def test_actual_clock_condition_and_citation_identities_survive_all_adapters(
    profile, clock, projected, rest, tmp_path, capsys
):
    spec = SPECS["canping"]
    payload = {
        **REFERENCE["engineering_payload"],
        "zone": clock["zone"],
        "dayun_method": profile,
    }
    fields = ["canping_timing.schedule_basis.reading_context"]
    if not projected:
        fields += [
            "canping_timing.first_row",
            "canping_timing.first_period",
            "snapshot_text",
        ]
    response, code, cli, mcp = run_three(spec, payload, fields, rest, tmp_path, capsys)
    assert response.status_code == 200 and code == 0 and not mcp.is_error
    outputs = [response.json(), cli, mcp.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for out in outputs:
        spec.output_model.model_validate(out)
        Draft202012Validator(spec.output_model.model_json_schema()).validate(out)
        timing = out["canping_timing"]
        context = timing["schedule_basis"]["reading_context"]
        assert context["profile_id"] == profile
        assert context["future_clock_policy"] == clock["policy"]
        assert context["timezone_spec"] == clock["zone"]
        assert [cite["source_id"] for cite in context["source_citations"]] == list(
            REFERENCE["books"]
        )
        for cite in context["source_citations"]:
            original = REFERENCE["books"][cite["source_id"]]
            published = {key: original[key] for key in ("title", "url", "edition")}
            assert {key: cite[key] for key in published} == published
            assert cite["pdf_pages"] == REFERENCE["pdf_pages"][cite["source_id"]]
            assert (
                cite["roles"]
                == REFERENCE["roles_by_profile"][profile][cite["source_id"]]
            )
            if not projected:
                assert cite["edition"] in out["snapshot_text"]
        if not projected:
            assert context["date_mapping_statement"] in out["snapshot_text"]
            if profile == "legacy_minggong_v1":
                assert timing["first_period"] is None
            else:
                assert timing["first_period"] == timing["first_row"]


@pytest.mark.parametrize("unrelated", [False, True])
def test_synchronized_wrong_clock_explanation_is_rejected_before_projection(
    unrelated, monkeypatch, rest, tmp_path, capsys
):
    from fatebridge.core.local_techniques.canping import build_canping_result

    payload = {**REFERENCE["engineering_payload"], "zone": "Europe/London"}
    out = build_canping_result(**payload)
    context = out["canping_timing"]["schedule_basis"]["reading_context"]
    context["date_mapping_statement"] = "No future rule changes can affect this date."
    for row in out["numerology_evidence"]["rule_trace"]:
        if row["rule_id"] == "canping_schedule_source_mapping_v1":
            row["facts"] = deepcopy(out["canping_timing"]["schedule_basis"])
    return_frozen_output(monkeypatch, out)
    fields = (
        ["analysis_type"]
        if unrelated
        else ["canping_timing.schedule_basis.reading_context"]
    )
    response, code, cli, mcp = run_three(
        SPECS["canping"], payload, fields, rest, tmp_path, capsys
    )
    assert response.status_code == 503 and code == 1 and mcp.is_error
    for value in [response.json(), cli, mcp.structured_content]:
        assert value["error_code"] == "numerology_source_inconsistent"
        assert value["retryable"] is False
