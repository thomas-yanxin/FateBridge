"""Guard source completeness, rejected candidates and unchanged calculated results."""

import gzip
import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.core.elements import ElementAnalysis
from fatebridge.services.source_comparison import calculate_bazi_source_compare
from scripts.assess_bazi_capacity_three_units import assess
from tests.bazi_refactor_reference import assert_strength_matches_before_repair

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "docs/validation/bazi-capacity-caid-fenyu-enyuan-v1"


def first_result():
    path = STUDY / "prospective-first.json.gz"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == (
        "f8b5a8b1e54bc7981b1ce8eaf828050a68ef68a87a1ded40c910ed78c5e0575e"
    )
    return json.loads(gzip.decompress(path.read_bytes()))


def test_frozen_operator_fails_adoption_without_a_fresh_source_gain():
    result = first_result()
    gate = assess(result)
    assert gate["new_records"] == 12
    assert (gate["new_known"], gate["new_unknown"]) == (6, 6)
    assert gate["fresh_nonoverlap_gains"] == []
    assert gate["numerical_adoption_gate_passed"] is gate["adopted"] is False
    rejected = result["exposed_summary"]["known_regressions"]
    for name in ("capacity_v3", "hidden_seal_v5"):
        assert rejected[name] == [
            "complete_xingqing_mediated_capacity_v1/DTCW1947-XQ-02"
        ]


def test_unknowns_cannot_be_converted_to_passes():
    result = first_result()
    row = next(
        r
        for r in result["prospective_rows"]
        if r["source_case"]["expected_strength"] is None
    )
    row["matches_all_variants"]["mediated_v1"] = True
    with pytest.raises(AssertionError):
        assess(result)


@pytest.mark.parametrize(
    "kind", ["duplicate", "regression", "old_regression", "overlap"]
)
def test_gate_retains_duplicates_regressions_and_prior_exposure(kind):
    result = first_result()
    known = next(
        r
        for r in result["prospective_rows"]
        if r["source_case"]["expected_strength"] is not None
    )
    if kind == "duplicate":
        result["prospective_rows"].append(deepcopy(known))
        with pytest.raises(AssertionError):
            assess(result)
        return
    if kind == "regression":
        known["matches_all_variants"]["mediated_v1"] = False
    else:
        known["matches_all_variants"]["production_v7"] = False
        if kind == "old_regression":
            result["exposed_summary"]["known_regressions"]["mediated_v1"] = [
                "retained_counterexample"
            ]
        else:
            known["source_case"]["new_nonoverlap_input"] = False
    assert assess(result)["numerical_adoption_gate_passed"] is False


def test_new_index_preserves_every_old_record_exactly():
    package = ROOT / "src/fatebridge/data/reference"
    before = json.loads((package / "bazi-source-annotations-v3.json").read_text())
    after = json.loads((package / "bazi-source-annotations-v4.json").read_text())
    assert after["records"][:349] == before["records"]
    assert after["record_count"] == 361
    assert after["literal_input_count"] == 315
    assert {r["case_id"] for r in after["records"][349:]} == {
        r["source_case"]["id"] for r in first_result()["prospective_rows"]
    }


@pytest.mark.parametrize(
    "row", first_result()["prospective_rows"], ids=lambda r: r["source_case"]["id"]
)
def test_all_new_literal_records_preserve_same_calculation_and_unknowns(row):
    source = row["source_case"]
    result = calculate_bazi_source_compare(*source["pillars"])
    assert "error" not in result, result
    chart = dict(zip(("year", "month", "day", "hour"), map(tuple, source["pillars"])))
    strength = ElementAnalysis.analyze_day_master_strength(chart)
    assert_strength_matches_before_repair(source["pillars"], strength)
    assert result["current_calculation"]["assessment"] == strength["assessment"]
    comparison = result["source_comparison"]
    assert comparison["reference_index"]["total_registered_records"] == 367
    assert comparison["reference_index"]["total_registered_literal_inputs"] == 321
    matched = next(r for r in comparison["records"] if r["case_id"] == source["id"])
    assert matched["retained_strength_annotation"] == source["expected_strength"]
    assert matched["comparison"] == (
        "unadjudicated" if source["expected_strength"] is None else "agrees"
    )
    assert matched["source_reference"]["pdf_pages"] == source["source_pdf_pages"]
    assert (
        matched["source_reference"]["whole_pdf_sha256"]
        == "d6a7d1daf6513ce9fb9940ff8331b96804c10cdafbeac00d4d3d0a37229e1803"
    )
    assert matched["source_reference"]["edition"]
    assert comparison["calculation_overridden"] is False
    assert comparison["new_independent_validation_credit"] == 0
