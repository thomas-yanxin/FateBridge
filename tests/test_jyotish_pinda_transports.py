"""Typed Pinda source scope and integer/null delivery on real transports."""

import copy

import pytest

from fatebridge.application.description import describe_spec
from fatebridge.application.execution import execute_tool
from fatebridge.core.execution_context import ExecutionOptions
from fatebridge.core.jyotish_pinda import METHOD, PLANETS, SOURCE
from fatebridge.validation.claims import CalculationClaim, verify_calculation_claims
from tests.fixtures.surface_payloads import astro_payload
from tests.test_jyotish_transports import AS_OF, SPECS, call_surfaces


@pytest.mark.parametrize("key", ["astro_india", "astro_vimshottari", "astro_chart"])
@pytest.mark.parametrize("projected", [False, True])
def test_declared_scope_and_nullable_pinda_on_all_surfaces(
    monkeypatch, capsys, key, projected
):
    payload = {**astro_payload(), "divisions": [], "birth_time_uncertainty_minutes": 1}
    if key == "astro_vimshottari":
        payload["analysis_year"] = 2026
    if key == "astro_chart":
        payload["chart_variant"] = "india_chart"
    prefix = "india.ashtakavarga.charts.D1.reduction_analysis"
    fields = (
        [
            f"{prefix}.targets.Sun.sodhya_pinda",
            f"{prefix}.targets.Sun.status",
            f"{prefix}.occupancy_planets",
            f"{prefix}.method_id",
        ]
        if projected
        else [prefix, "india.birth_time_sensitivity"]
    )
    result = call_surfaces(monkeypatch, capsys, key, payload, fields)
    analysis = result["india"]["ashtakavarga"]["charts"]["D1"]["reduction_analysis"]
    assert analysis["method_id"] == METHOD
    assert analysis["occupancy_planets"] == list(PLANETS)
    if projected:
        assert set(analysis["targets"]) == {"Sun"}
        assert set(analysis["targets"]["Sun"]) == {"sodhya_pinda", "status"}
    else:
        assert analysis["source_id"] == SOURCE["id"]
        assert set(analysis["targets"]) == set(PLANETS)
        assert analysis["bhinna_fact_path"] == "india.ashtakavarga.charts.D1.bhinna"
        for row in analysis["targets"].values():
            if row["source_ambiguities"]:
                assert row["status"] == "partial_source_rule"
                assert row["sodhya_pinda"] is None
                assert row["rasi_pinda"] is None
            else:
                assert type(row["sodhya_pinda"]) is int
                assert row["sodhya_pinda"] == row["rasi_pinda"] + row["graha_pinda"]
        grid = result["india"]["birth_time_sensitivity"]["ashtakavarga_variants"]
        assert grid["sample_count"] == 5
        for variant in grid["charts"]["D1"]:
            assert "bhinna_fact_path" not in variant["reduction_analysis"]
            assert variant["reduction_analysis"]["method_id"] == METHOD
    assert "ashtakavarga_reductions" in describe_spec(SPECS[key])["evidence_views"]
    definitions = SPECS[key].output_model.model_json_schema()["$defs"]
    assert "PindaAnalysis" in definitions and "PindaRow" in definitions


def test_same_run_pinda_claims_retain_integer_null_and_reject_tampering():
    spec = SPECS["astro_india"]
    body = execute_tool(
        spec,
        spec.request_model.model_validate({**astro_payload(), "divisions": []}),
        options=ExecutionOptions(as_of=AS_OF),
    )
    meta = body["run_metadata"]
    analysis = body["india"]["ashtakavarga"]["charts"]["D1"]["reduction_analysis"]
    claims = []
    for planet, row in analysis["targets"].items():
        for field in ["rasi_pinda", "graha_pinda", "sodhya_pinda"]:
            claims.append(
                CalculationClaim(
                    path=f"india.ashtakavarga.charts.D1.reduction_analysis.targets.{planet}.{field}",
                    value=row[field],
                    run_id=meta["run_id"],
                    business_output_sha256=meta["business_output_sha256"],
                )
            )
    assert len(claims) == 21
    assert (
        verify_calculation_claims(body, claims)["status"] == "verified_structured_facts"
    )
    bad = copy.deepcopy(claims)
    index = next((i for i, c in enumerate(bad) if c.value is None), 0)
    bad[index].value = 0 if bad[index].value is None else bad[index].value + 1
    assert verify_calculation_claims(body, bad)["status"] == "rejected"
