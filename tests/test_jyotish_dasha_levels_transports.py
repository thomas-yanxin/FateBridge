"""Shared schema, actual transports, projections and same-run nested facts."""

import copy
import hashlib
import json

import pytest
from fastapi.testclient import TestClient

import fatebridge.api as api
import fatebridge.application.result_delivery as delivery
import fatebridge.services.jyotish as service
from fatebridge.application.description import describe_spec
from fatebridge.application.execution import execute_tool
from fatebridge.core.execution_context import ExecutionOptions
from fatebridge.validation.claims import CalculationClaim, verify_calculation_claims
from tests.fixtures.surface_payloads import astro_payload
from tests.test_jyotish_transports import AS_OF, SPECS, call_surfaces


@pytest.mark.parametrize("depth", [3, 6])
@pytest.mark.parametrize("projected", [False, True])
def test_nested_periods_on_real_rest_mcp_cli(monkeypatch, capsys, depth, projected):
    fields = (
        ["vimshottari.subdivisions.current_levels", "vimshottari.subdivisions.depth"]
        if projected
        else [
            "summary",
            "vimshottari.subdivisions",
            "vimshottari.birth_time_sensitivity",
            "vimshottari.natal_ruler_context",
        ]
    )
    body = call_surfaces(
        monkeypatch,
        capsys,
        "astro_vimshottari",
        {
            **astro_payload(),
            "analysis_year": 2026,
            "divisions": [],
            "birth_time_uncertainty_minutes": 1,
            "dasha_depth": depth,
        },
        fields,
    )
    v = body["vimshottari"]
    s = v["subdivisions"]
    assert len(s["current_levels"]) == s["depth"] == depth
    if projected:
        assert set(s) == {"current_levels", "depth"}
    else:
        assert all(
            len(g["period_lord_chain"]) == depth
            for g in v["birth_time_sensitivity"]["stage_variants"]
        )
        assert all(len(g["periods"]) == 9 for g in s["siblings_by_level"])
        assert all(p["period_roles"] for p in v["natal_ruler_context"])
    defs = SPECS["astro_vimshottari"].output_model.model_json_schema()["$defs"]
    assert all(
        key in defs for key in ["DashaSubdivisions", "DashaLevel", "DashaSiblings"]
    )
    assert "dasha_levels" in describe_spec(SPECS["astro_vimshottari"])["evidence_views"]


def test_saved_full_nested_result_pages_and_claims_do_not_recompute(
    monkeypatch, tmp_path
):
    store = delivery.ResultStore(tmp_path / "nested-results")
    monkeypatch.setattr(delivery, "RESULT_STORE", store)
    monkeypatch.setattr(api, "RESULT_STORE", store)
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    client = TestClient(api.app)
    response = client.post(
        "/api/astro/vimshottari",
        json={
            **astro_payload(),
            "analysis_year": 2026,
            "dasha_depth": 6,
            "divisions": [],
            "birth_time_uncertainty_minutes": 1,
        },
        params={
            "as_of": AS_OF,
            "include_snapshot_text": "true",
            "response_char_limit": 4096,
        },
    )
    assert response.status_code == 200, response.text
    shaped = response.json()
    ref = shaped["result_delivery"]

    def forbidden(*args, **kwargs):
        pytest.fail("Same-run nested pages cannot recalculate periods")

    monkeypatch.setattr(service, "calculate_vimshottari", forbidden)
    chunks = []
    offset = 0
    while True:
        page = client.get(
            f"/api/results/{ref['result_id']}/pages", params={"offset": offset}
        )
        assert page.status_code == 200
        item = page.json()
        chunks.append(item["text"])
        if item["next_offset"] is None:
            break
        offset = item["next_offset"]
    text = "".join(chunks)
    assert hashlib.sha256(text.encode()).hexdigest() == ref["sha256"]
    full = json.loads(text)
    meta = full["run_metadata"]
    assert meta["run_id"] == shaped["run_metadata"]["run_id"]
    assert len(full["vimshottari"]["subdivisions"]["current_levels"]) == 6
    claims = [
        CalculationClaim(
            path=f"vimshottari.subdivisions.current_levels.{i}.{field}",
            value=row[field],
            run_id=meta["run_id"],
            business_output_sha256=meta["business_output_sha256"],
        )
        for i, row in enumerate(full["vimshottari"]["subdivisions"]["current_levels"])
        for field in ["lord", "start", "end"]
    ]
    assert (
        verify_calculation_claims(full, claims)["status"] == "verified_structured_facts"
    )
    incomplete = copy.deepcopy(full)
    assert "snapshot_text" in incomplete
    del incomplete["snapshot_text"]
    rejected = verify_calculation_claims(incomplete, claims)
    assert rejected["status"] == "rejected"
    assert {"code": "incomplete_or_changed_business_payload"} in rejected["errors"]
    bad = copy.deepcopy(claims)
    bad[-1].value = "2000-01-01T00:00:00+00:00"
    assert verify_calculation_claims(full, bad)["status"] == "rejected"
