"""Original source disagreements cannot disappear behind edited score summaries."""

import copy
import json

import pytest

from scripts.audit_bazi_disagreements import ROOT, audit
from tests.test_bazi_seasonal_studies import frozen

BASELINE = ROOT / "docs/validation/bazi-shuaiwang-public-frozen-v1.json"


def replay(tmp_path, mutate):
    data = json.loads(BASELINE.read_text())
    source = frozen(ROOT / "tests/fixtures/bazi_disagreement_review_v1/review.json")[
        "cases"
    ][0]
    rows = data["groups"][source["baseline_group"]]["rows"]
    row = next(r for r in rows if r["id"] == source["id"])
    mutate(data, rows, row)
    path = tmp_path / "replay.json"
    path.write_text(json.dumps(data))
    return path


def test_all_nineteen_original_anchors_reconcile_without_becoming_classical_truth():
    result = audit(BASELINE)
    assert result["original_disagreements_retained"] == 19
    assert len(result["unresolved"]) == 19
    assert result["resolved_under_original_label"] == []
    assert all(
        r["components"]["reconciles_supplied_support_and_weaken"]
        for r in result["rows"]
    )
    assert not result["classical_acceptance_passed"]
    assert result["overall_score"] is None


@pytest.mark.parametrize("change", ["drop", "relabel", "false_pass", "energy"])
def test_removing_a_counterexample_or_falsifying_its_receipt_is_rejected(
    change, tmp_path
):
    def mutate(data, rows, row):
        if change == "drop":
            rows.remove(row)
        elif change == "relabel":
            row["expected_strength"] = row["actual_strength"]
        elif change == "false_pass":
            row["matches"] = True
        else:
            row["assessment"]["support_strength"] += 1

    with pytest.raises(ValueError):
        audit(replay(tmp_path, mutate))


def test_resolved_anchor_stays_visible_and_new_counterexample_is_not_discarded(
    tmp_path,
):
    def mutate(data, rows, row):
        row["actual_strength"] = row["expected_strength"]
        row["matches"] = True
        extra = copy.deepcopy(data["distinct_mismatches"][0])
        extra["id"] = "new-failure"
        extra["pillars"] = ["甲子", "丙寅", "戊辰", "庚申"]
        data["distinct_mismatches"].append(extra)

    result = audit(replay(tmp_path, mutate))
    assert len(result["rows"]) == 19
    assert len(result["resolved_under_original_label"]) == 1
    assert len(result["unresolved"]) == 18
    assert any(
        r["id"] == "new-failure" for r in result["additional_current_disagreements"]
    )
    assert not result["classical_acceptance_passed"]


def test_first_case_reading_keeps_paragraph_and_explicit_labels_distinct():
    review = frozen(ROOT / "tests/fixtures/bazi_disagreement_review_v1/review.json")
    readings = {c["source_reading_kind"] for c in review["cases"]}
    assert "paragraph_membership" in readings
    assert len(readings) > 1
    assert all(c["source_label_changed"] is False for c in review["cases"])
    assert all(c["independent_expert_review"] == "pending" for c in review["cases"])
