"""The new source comparison survives actual shared transports and claims."""

import copy

import pytest

from fatebridge.application.execution import execute_tool
from fatebridge.core.execution_context import ExecutionOptions
from fatebridge.core.jyotish_aiyar_reductions import METHOD, SOURCE
from fatebridge.validation.claims import CalculationClaim, verify_calculation_claims
from tests.fixtures.surface_payloads import astro_payload
from tests.jyotish.test_jyotish_transports import AS_OF, SPECS, call_surfaces

BASE = "india.ashtakavarga.charts.D1.reduction_analysis"
COMPARISON = BASE + ".source_profile_comparison.aiyar1905_commentary"


@pytest.mark.parametrize("key", ["astro_india", "astro_vimshottari", "astro_chart"])
@pytest.mark.parametrize("projected", [False, True])
def test_distinct_commentary_counts_on_three_real_transports(
    monkeypatch, capsys, key, projected
):
    payload = {**astro_payload(), "divisions": [], "birth_time_uncertainty_minutes": 1}
    if key == "astro_vimshottari":
        payload["analysis_year"] = 2026
    if key == "astro_chart":
        payload["chart_variant"] = "india_chart"
    fields = (
        [
            COMPARISON + ".method_id",
            COMPARISON + ".source_id",
            COMPARISON + ".rao_default_replaced",
            COMPARISON + ".targets.Sun.sodhita",
            COMPARISON + ".targets.Sun.reduced_sum",
            BASE + ".targets.Sun.sodhya_pinda",
        ]
        if projected
        else ["india.ashtakavarga", "india.birth_time_sensitivity"]
    )
    result = call_surfaces(monkeypatch, capsys, key, payload, fields)
    default = result["india"]["ashtakavarga"]["charts"]["D1"]["reduction_analysis"]
    other = default["source_profile_comparison"]["aiyar1905_commentary"]
    assert other["method_id"] == METHOD and other["source_id"] == SOURCE["id"]
    assert other["rao_default_replaced"] is False
    assert type(other["targets"]["Sun"]["reduced_sum"]) is int
    if projected:
        assert set(other["targets"]) == {"Sun"}
        assert set(other["targets"]["Sun"]) == {"sodhita", "reduced_sum"}
        assert set(default["targets"]["Sun"]) == {"sodhya_pinda"}
    else:
        assert len(other["targets"]) == 7
        grid = result["india"]["birth_time_sensitivity"]["ashtakavarga_variants"]
        assert grid["sample_count"] == 5
        for sample in grid["charts"]["D1"]:
            own = sample["reduction_analysis"]["source_profile_comparison"][
                "aiyar1905_commentary"
            ]
            assert own["input_sign_indices"] == {
                p: sample["input_sign_indices"][p] for p in other["targets"]
            }
    definitions = SPECS[key].output_model.model_json_schema()["$defs"]
    assert (
        "AiyarReductionRow" in definitions and "AiyarReductionComparison" in definitions
    )


def test_same_run_claims_keep_both_authors_and_reject_a_replaced_count():
    spec = SPECS["astro_india"]
    body = execute_tool(
        spec,
        spec.request_model.model_validate({**astro_payload(), "divisions": []}),
        options=ExecutionOptions(as_of=AS_OF),
    )
    meta = body["run_metadata"]
    value = body["india"]["ashtakavarga"]["charts"]["D1"]["reduction_analysis"][
        "source_profile_comparison"
    ]["aiyar1905_commentary"]["targets"]["Sun"]["reduced_sum"]
    claims = [
        CalculationClaim(
            path=COMPARISON + ".targets.Sun.reduced_sum",
            value=value,
            run_id=meta["run_id"],
        )
    ]
    assert (
        verify_calculation_claims(body, claims)["status"] == "verified_structured_facts"
    )
    changed = copy.deepcopy(claims)
    changed[0].value += 1
    assert verify_calculation_claims(body, changed)["status"] == "rejected"
