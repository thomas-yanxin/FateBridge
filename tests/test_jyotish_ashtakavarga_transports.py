"""Real transports, field projection and same-run count-claim verification."""

import copy
import hashlib
import json

import pytest
from fastapi.testclient import TestClient

import fatebridge.api as api
from fatebridge.application.description import describe_spec
from fatebridge.application.execution import execute_tool
from fatebridge.core.execution_context import ExecutionOptions
from fatebridge.core.jyotish_ashtakavarga import RULE
from fatebridge.validation.claims import CalculationClaim, verify_calculation_claims
from tests.fixtures.surface_payloads import astro_payload
from tests.test_jyotish_transports import AS_OF, SPECS, call_surfaces


@pytest.mark.parametrize("key", ["astro_india", "astro_vimshottari", "astro_chart"])
@pytest.mark.parametrize("projected", [False, True])
def test_counts_and_birth_grid_through_all_real_surfaces(
    monkeypatch, capsys, key, projected
):
    payload = {
        **astro_payload(),
        "divisions": [9, 10, 30],
        "birth_time_uncertainty_minutes": 1,
    }
    if key == "astro_vimshottari":
        payload["analysis_year"] = 2026
    if key == "astro_chart":
        payload["chart_variant"] = "india_chart"
    fields = (
        [
            "india.ashtakavarga.charts.D1.bhinna.Sun",
            "india.ashtakavarga.charts.D30.samudaya_total",
        ]
        if projected
        else [
            "india.ashtakavarga",
            "india.birth_time_sensitivity.ashtakavarga_variants",
        ]
    )
    result = call_surfaces(monkeypatch, capsys, key, payload, fields)
    av = result["india"]["ashtakavarga"]
    if projected:
        assert len(av["charts"]["D1"]["bhinna"]["Sun"]) == 12
        assert av["charts"]["D30"]["samudaya_total"] == 337
        assert "prastara" not in av["charts"]["D1"]
    else:
        assert set(av["charts"]) == {"D1", "D9", "D10", "D30"}
        assert av["reductions_applied"] is False
        assert (
            result["india"]["birth_time_sensitivity"]["ashtakavarga_variants"][
                "sample_count"
            ]
            == 5
        )
    assert "ashtakavarga" in describe_spec(SPECS[key])["evidence_views"]
    assert "AshtakavargaChart" in SPECS[key].output_model.model_json_schema()["$defs"]


def test_same_run_count_claims_reject_modified_values():
    spec = SPECS["astro_india"]
    body = execute_tool(
        spec,
        spec.request_model.model_validate({**astro_payload(), "divisions": []}),
        options=ExecutionOptions(as_of=AS_OF),
    )
    meta = body["run_metadata"]
    claims = []
    for topic in body["india"]["topic_evidence"].values():
        for factor in topic["factors"]:
            if factor["rule_id"] == RULE:
                for row in [
                    *factor["calculation_context"]["scenarios"],
                    *factor["calculation_context"]["constraints"],
                ]:
                    claims.append(
                        CalculationClaim(
                            path=row["fact_path"],
                            value=row["value"],
                            run_id=meta["run_id"],
                            business_output_sha256=meta["business_output_sha256"],
                        )
                    )
    assert len(claims) == 33
    assert (
        verify_calculation_claims(body, claims)["status"] == "verified_structured_facts"
    )
    bad = copy.deepcopy(claims)
    bad[0].value += 1
    assert verify_calculation_claims(body, bad)["status"] == "rejected"


def test_complete_pav_and_grid_survive_same_run_pagination(monkeypatch, tmp_path):
    from fatebridge.application import result_delivery as delivery
    from fatebridge.services import jyotish

    store = delivery.ResultStore(tmp_path / "saved-counts")
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
            "birth_time_uncertainty_minutes": 1,
        },
        params={
            "as_of": AS_OF,
            "include_snapshot_text": "false",
            "response_char_limit": 4096,
        },
    )
    assert response.status_code == 200
    shaped = response.json()
    ref = shaped["result_delivery"]

    def forbidden(*args, **kwargs):
        pytest.fail("Saved result pages cannot recompute Ashtakavarga")

    monkeypatch.setattr(jyotish, "calculate_vimshottari", forbidden)
    chunks, offset = [], 0
    while True:
        page_response = client.get(
            f"/api/results/{ref['result_id']}/pages", params={"offset": offset}
        )
        assert page_response.status_code == 200
        page = page_response.json()
        chunks.append(page["text"])
        if page["next_offset"] is None:
            break
        offset = page["next_offset"]
    text = "".join(chunks)
    assert hashlib.sha256(text.encode()).hexdigest() == ref["sha256"]
    full = json.loads(text)
    assert full["run_metadata"]["run_id"] == shaped["run_metadata"]["run_id"]
    av = full["india"]["ashtakavarga"]
    assert set(av["charts"]) == {"D1", "D9", "D10"}
    assert len(av["charts"]["D1"]["prastara"]["Sun"]) == 8
    assert av["charts"]["D1"]["samudaya_total"] == 337
    grid = full["india"]["birth_time_sensitivity"]["ashtakavarga_variants"]
    assert grid["sample_count"] == 5
    assert sum(g["sample_count"] for g in grid["charts"]["D1"]) == 5
    for packet in av["charts"].values():
        analysis = packet["reduction_analysis"]
        assert analysis["occupancy_planets"] == [
            "Sun",
            "Moon",
            "Mars",
            "Mercury",
            "Jupiter",
            "Venus",
            "Saturn",
        ]
        assert len(analysis["targets"]) == 7
        assert all("sodhya_pinda" in row for row in analysis["targets"].values())
