"""Native REST/MCP/CLI preserve the declared exact epoch and rational strings."""

import copy

import pytest

from fatebridge.application.execution import execute_tool
from fatebridge.core.execution_context import ExecutionOptions
from fatebridge.validation.claims import CalculationClaim, verify_calculation_claims
from tests.fixtures.surface_payloads import astro_payload
from tests.test_jyotish_transports import AS_OF, SPECS, call_surfaces


@pytest.mark.parametrize(
    "basis", ["sidereal_365_25636", "tropical_365_2425", "savana_360"]
)
@pytest.mark.parametrize("projected", [False, True])
def test_common_epoch_and_string_fractions_on_all_real_surfaces(
    monkeypatch, capsys, basis, projected
):
    depth = 2 if projected else 6
    fields = (
        [
            "vimshottari.time_quantization.source_mansion_fraction_exact",
            "vimshottari.birth_balance.elapsed_microseconds",
        ]
        if projected
        else [
            "vimshottari.time_quantization",
            "vimshottari.birth_balance",
            "vimshottari.subdivisions",
            "vimshottari.birth_time_sensitivity",
            "india.rulesets",
            "india.rule_trace",
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
            "year_basis": basis,
        },
        fields,
    )
    vim = body["vimshottari"]
    fraction = vim["time_quantization"]["source_mansion_fraction_exact"]
    assert all(type(fraction[k]) is str for k in ["numerator", "denominator"])
    assert type(vim["birth_balance"]["elapsed_microseconds"]) is int
    if projected:
        assert set(vim["time_quantization"]) == {"source_mansion_fraction_exact"}
    else:
        assert (
            vim["subdivisions"]["epoch_context"]["reference_epoch_utc"]
            == vim["time_quantization"]["reference_epoch_utc"]
        )
        assert all(
            type(v) is str
            for v in vim["subdivisions"]["epoch_context"][
                "complete_major_start_offset_microseconds_fraction"
            ].values()
        )
        assert len(vim["subdivisions"]["current_levels"]) == 6
        assert all(
            "time_quantization" in s for s in vim["birth_time_sensitivity"]["samples"]
        )
        sources = {row["id"]: row for row in body["india"]["rulesets"]}
        assert (
            sources[vim["time_quantization"]["source_id"]]["source_kind"]
            == "implementation_policy"
        )
    definitions = SPECS["astro_vimshottari"].output_model.model_json_schema()["$defs"]
    assert (
        "DashaExactFraction" in definitions and "DashaTimeQuantization" in definitions
    )


def test_same_run_exact_fraction_claims_reject_numeric_coercion():
    spec = SPECS["astro_vimshottari"]
    body = execute_tool(
        spec,
        spec.request_model.model_validate(
            {
                **astro_payload(),
                "analysis_year": 2026,
                "divisions": [],
                "dasha_depth": 6,
            }
        ),
        options=ExecutionOptions(as_of=AS_OF),
    )
    meta = body["run_metadata"]
    fraction = body["vimshottari"]["time_quantization"]["source_mansion_fraction_exact"]
    claims = [
        CalculationClaim(
            path=f"vimshottari.time_quantization.source_mansion_fraction_exact.{key}",
            value=fraction[key],
            run_id=meta["run_id"],
            business_output_sha256=meta["business_output_sha256"],
        )
        for key in ["numerator", "denominator"]
    ]
    assert (
        verify_calculation_claims(body, claims)["status"] == "verified_structured_facts"
    )
    changed = copy.deepcopy(claims)
    changed[0].value = int(fraction["numerator"])
    rejected = verify_calculation_claims(body, changed)
    assert rejected["status"] == "rejected"
    assert any(
        error["code"] == "value_or_type_mismatch" for error in rejected["errors"]
    )
