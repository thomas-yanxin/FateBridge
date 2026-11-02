"""Own-source raw counts and their two-author claim paths on actual transports."""

import copy

import pytest

from fatebridge.application.description import describe_spec
from fatebridge.application.execution import execute_tool
from fatebridge.core.execution_context import ExecutionOptions
from fatebridge.core.jyotish_aiyar_ashtakavarga import METHOD, SOURCE
from fatebridge.validation.claims import CalculationClaim, verify_calculation_claims
from tests.fixtures.surface_payloads import astro_payload
from tests.test_jyotish_transports import AS_OF, SPECS, call_surfaces

PREFIX = "india.ashtakavarga.charts.D1.source_profile_comparison.aiyar1905"


@pytest.mark.parametrize("key", ["astro_india", "astro_vimshottari", "astro_chart"])
@pytest.mark.parametrize("projected", [False, True])
def test_own_source_profile_and_partial_projection_on_all_real_surfaces(
    monkeypatch, capsys, key, projected
):
    payload = {**astro_payload(), "divisions": [], "birth_time_uncertainty_minutes": 1}
    if key == "astro_vimshottari":
        payload["analysis_year"] = 2026
    elif key == "astro_chart":
        payload["chart_variant"] = "india_chart"
    fields = (
        [PREFIX, "india.birth_time_sensitivity"]
        if not projected
        else [
            PREFIX + ".source_id",
            PREFIX + ".bhinna.Moon",
            PREFIX + ".samudaya",
            PREFIX + ".reduction_analysis.targets.Moon.reduced_sum",
            PREFIX + ".comparison_to_default",
        ]
    )
    body = call_surfaces(monkeypatch, capsys, key, payload, fields)
    profile = body["india"]["ashtakavarga"]["charts"]["D1"][
        "source_profile_comparison"
    ]["aiyar1905"]
    assert profile["source_id"] == SOURCE["id"]
    assert all(type(v) is int for v in profile["bhinna"]["Moon"])
    assert type(profile["reduction_analysis"]["targets"]["Moon"]["reduced_sum"]) is int
    if projected:
        assert set(profile["bhinna"]) == {"Moon"}
        assert set(profile["reduction_analysis"]["targets"]["Moon"]) == {"reduced_sum"}
    else:
        assert profile["method_id"] == METHOD
        assert len(profile["bhinna"]) == 7 and "Ascendant" not in profile["bhinna"]
        assert profile["samudaya_total"] == 337
        groups = body["india"]["birth_time_sensitivity"]["ashtakavarga_variants"][
            "charts"
        ]["D1"]
        for group in groups:
            own = group["source_profile_comparison"]["aiyar1905"]
            assert own["input_sign_indices"] == group["input_sign_indices"]
    assert "ashtakavarga_source_profiles" in describe_spec(SPECS[key])["evidence_views"]
    assert "AiyarBavProfile" in SPECS[key].output_model.model_json_schema()["$defs"]


def test_same_run_two_source_claims_reject_numeric_and_source_tampering():
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
            method = factor.get("calculation_context", {}).get("method_context", {})
            other = method.get("source_profile_comparisons", {}).get("aiyar1905")
            if other is None:
                continue
            for row in [*method["input_claims"], *other["input_claims"]]:
                claims.append(
                    CalculationClaim(
                        path=row["fact_path"],
                        value=row["value"],
                        run_id=meta["run_id"],
                        business_output_sha256=meta["business_output_sha256"],
                    )
                )
    assert len(claims) == 60
    assert (
        verify_calculation_claims(body, claims)["status"] == "verified_structured_facts"
    )
    numeric = copy.deepcopy(claims)
    numeric[-1].value = 2
    assert verify_calculation_claims(body, numeric)["status"] == "rejected"
    provenance = copy.deepcopy(claims)
    provenance[9].value = "pretend-rao"
    assert verify_calculation_claims(body, provenance)["status"] == "rejected"
