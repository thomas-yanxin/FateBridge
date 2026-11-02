"""New primary witnesses cannot turn diagnostic agreement into source truth."""

import copy
import json
from pathlib import Path

import pytest

from scripts.audit_liuren_jingwei_harmony import CORPUS, audit, reference

REVIEW = reference()


def test_same_work_editions_and_anonymous_annotations_keep_their_identities():
    witnesses = REVIEW["witnesses"]
    assert witnesses["red_annotations_attributed_to_mao_zhidao"] is False
    assert witnesses["reader_count"] == 1 and witnesses["blind"] is False
    assert all(
        not w["exact_copy_used_by_yuan_shushan_proven"] for w in witnesses["witnesses"]
    )
    inference = REVIEW["readings"]["inference"]
    assert inference["preferred_candidate"] == "H1"
    assert inference["status"] == "supported_not_exclusive"
    assert inference["production_adoption"] is False
    assert inference["adjudicated_original_tanyuan_ids"] == []


def test_same_hit_totals_can_conceal_disjoint_rule_answers():
    data = REVIEW["reference"]
    assert data["candidate_true_counts"]["H1"] == data["candidate_true_counts"]["H2"]
    days1 = {r["day_ganzhi"] for r in data["days"] if r["candidates"]["H1"]}
    days2 = {r["day_ganzhi"] for r in data["days"] if r["candidates"]["H2"]}
    assert days1 == {"乙酉", "丙申", "戊申", "辛卯", "壬寅"}
    assert days2 == {"丙戌", "丁亥", "庚辰", "辛巳", "癸巳"}
    assert not days1 & days2
    assert len(data["disagreements"][0]["contexts"]) == 20
    assert data["new_adjudicated_rules"] == data["new_empirical_events"] == 0


def test_consensus_and_disagreement_both_leave_original_source_unknown():
    rows = REVIEW["reference"]["contexts"]
    assert len(rows) == 720
    assert any(
        len({json.dumps(v) for v in r["hypothetical"].values()}) > 1 for r in rows
    )
    assert any(
        len({json.dumps(v) for v in r["hypothetical"].values()}) == 1 for r in rows
    )
    assert all(
        r["adjudicated_source_truth"] == {"D11": None, "D12": None} for r in rows
    )
    assert all(r["selected_production_model"] is None for r in rows)


def test_full_original_cohort_stays_unchanged():
    result = audit()
    assert result["engineering_guard_passed"] is True
    assert len(result["rows"]) == 720 and result["failures"] == []
    assert all(row["actual"] == [None, None] for row in result["rows"])
    assert result["classical_conformance"] == "not_completed"
    assert result["calendar_validation"] == "not_reassessed"
    assert result["free_text_fidelity"] == "not_reassessed"
    assert result["goal_complete"] is False


@pytest.mark.parametrize("invented", [False, True])
def test_audit_detects_turning_unknown_into_candidate_answer(monkeypatch, invented):
    import fatebridge.core.metaphysics.liureng_day_placements as production

    actual = production.day_placement_patterns

    def substituted(*args):
        value = copy.deepcopy(actual(*args))
        for row in value["evaluations"][-2:]:
            row["matched"] = invented
        return value

    monkeypatch.setattr(production, "day_placement_patterns", substituted)
    result = audit()
    assert result["engineering_guard_passed"] is False
    assert len(result["failures"]) == 720
    assert result["goal_complete"] is False


def test_modified_manifest_cannot_redefine_frozen_review(tmp_path: Path):
    # Failure precedes loading the large source files; no PDF copies required.
    (tmp_path / "freeze.json").write_bytes((CORPUS / "freeze.json").read_bytes() + b" ")
    with pytest.raises(ValueError, match="identity changed"):
        reference(tmp_path)
