"""The alternative witness is visible and explicitly not the active calculator."""

import copy
import json
from pathlib import Path

import pytest

from fatebridge.core.jyotish_balas import PLANETS, aspect_strength
from fatebridge.core.jyotish_evidence import strength_context
from fatebridge.core.output_jyotish import ConditionalDrik
from tests.fixtures.surface_payloads import astro_payload
from tests.jyotish.test_jyotish_transports import call_surfaces

ROOT = Path(__file__).resolve().parents[2]


def assert_witness(drik):
    assert drik["method"] == "raman_113_120_additive_specials"
    assert len(drik["source_reading_conflicts"]) == 3
    alternative = drik["alternative_source_witnesses"]["santhanam_26_27_19"]
    assert alternative["applied_to_native_drik"] is False
    assert alternative["complete_single_original_accepted"] is False
    assert alternative["commentary_mars_upper_degree_literal"] == 249
    assert alternative["selected_raman_mars_upper_degree"] == 240
    assert alternative["ordinary_speculum"]["printed_cells"] == 540
    assert alternative["ordinary_speculum"]["ordinary_scalar_relation_conflicts"] == 2
    assert alternative["ordinary_speculum"]["terminal300_not_printed"] is True
    return alternative


def test_typed_native_witness_does_not_change_the_selected_scalar_method():
    raw = {**dict.fromkeys(PLANETS, 0.0), "Sun": 240.0}
    drik = aspect_strength(raw)
    assert_witness(drik)
    assert drik["matrix"]["Mars"]["Sun"] == 30
    assert ConditionalDrik.model_validate(drik).alternative_source_witnesses
    context = strength_context("drik_bala", "Sun", drik)
    assert (
        "india.strengths.drik_bala.alternative_source_witnesses"
        in context["context_paths"]
    )


@pytest.mark.parametrize("key", ["astro_india", "astro_chart", "astro_vimshottari"])
def test_alternative_witness_survives_actual_three_surface_strict_projection(
    monkeypatch, capsys, key
):
    views = json.loads((ROOT / "src/fatebridge/data/agent_examples.json").read_text())
    fields = views["evidence_views"][key]["santhanam_drishti_witnesses"]["fields"]
    payload = {**astro_payload(), "divisions": []}
    if key == "astro_chart":
        payload["chart_variant"] = "india_chart"
    elif key == "astro_vimshottari":
        payload["analysis_year"] = 2026
    packet = call_surfaces(monkeypatch, capsys, key, payload, fields)
    assert_witness(packet["india"]["strengths"]["drik_bala"])


def test_real_run_claim_cannot_promote_the_alternative_to_applied_source():
    from fatebridge.application.execution import execute_tool
    from fatebridge.core.execution_context import ExecutionOptions
    from fatebridge.services.tool_catalog import CATALOG
    from fatebridge.validation.claims import CalculationClaim, verify_calculation_claims

    spec = next(s for s in CATALOG if s.key == "astro_india")
    body = execute_tool(
        spec,
        spec.request_model.model_validate({**astro_payload(), "divisions": []}),
        options=ExecutionOptions(as_of="2026-10-23T00:00:00Z"),
    )
    metadata = body["run_metadata"]
    path = "india.strengths.drik_bala.alternative_source_witnesses.santhanam_26_27_19.applied_to_native_drik"
    claim = CalculationClaim(
        path=path,
        value=False,
        run_id=metadata["run_id"],
        business_output_sha256=metadata["business_output_sha256"],
    )
    assert (
        verify_calculation_claims(body, [claim])["status"]
        == "verified_structured_facts"
    )
    forged = copy.deepcopy(claim)
    forged.value = True
    assert verify_calculation_claims(body, [forged])["status"] == "rejected"
