"""A scoring assignment must never be described as geometric occupancy."""

import json
from pathlib import Path

import pytest

from tests.reference_data import verify_source_files
from tests.test_western_lilly_fortitudes import inputs, result, row

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/data/astro/lilly_house_wording"
PROTOCOL = json.loads((FIXTURE / "protocol.json").read_text())
HOUSE_CODES = {"F01", "F02", "F03", "F04", "F05", "D01", "D02"}


def test_house_wording_reference_precedes_candidate_and_keeps_real_counterexamples():
    verify_source_files(FIXTURE)
    assert len(PROTOCOL["cases"]) == 12
    assert not PROTOCOL["numeric_rule_or_source_weight_change"]


@pytest.mark.parametrize(
    "case", PROTOCOL["cases"], ids=lambda c: str(c["scored_house"])
)
def test_house_row_and_applied_text_describe_scoring_assignment(case):
    states, data = inputs()
    state = states["Mars"]
    state["occupied_house"] = case["occupied_house"]
    state["house_assignment"] = {
        "assigned_house": case["scored_house"],
        "assignment_policy": "synthetic p33 scoring assignment",
        "status": "computed_under_declared_policy",
    }
    value = result(states, data)
    r = row(value, "Mars", case["code"])
    assert r["inputs"]["occupied_house"] == case["occupied_house"]
    assert r["inputs"]["scored_house"] == case["scored_house"]
    assert r["inputs"]["occupied_house"] != r["inputs"]["scored_house"]
    assert r["satisfied"] and r["contribution"] == case["contribution"]
    assert r["source_pages"] == [33, 115]
    assert r["label_zh"] == case["expected_label"]
    applied = next(
        r
        for r in value["planets"]["Mars"]["applied_conditions"]
        if r["code"] == case["code"]
    )
    assert applied["label_zh"] == r["label_zh"]


def test_unknown_scoring_house_keeps_occupancy_known_without_claiming_its_score():
    states, data = inputs()
    states["Mars"]["occupied_house"] = 9
    states["Mars"]["house_assignment"] = {
        "assigned_house": None,
        "assignment_policy": "controlled unavailable cusp assignment",
    }
    value = result(states, data)
    for code in HOUSE_CODES:
        r = row(value, "Mars", code)
        assert r["status"] == "unknown" and r["contribution"] is None
        assert r["inputs"]["occupied_house"] == 9
        assert r["inputs"]["scored_house"] is None
        assert r["label_zh"].startswith("计分归")


def test_literal_source_occupancy_fallback_does_not_claim_cusp_computation():
    states, data = inputs()
    value = result(states, data)
    r = row(value, "Mars", "F01")
    assert r["satisfied"] and r["contribution"] == 5
    assert r["inputs"]["occupied_house"] == r["inputs"]["scored_house"] == 1
    assert (
        r["inputs"]["assignment_policy"]
        == "literal_transcribed_occupancy_no_cusp_inputs_supplied"
    )
    assert r["source_pages"] == [115]
    assert r["label_zh"].startswith("计分归")
