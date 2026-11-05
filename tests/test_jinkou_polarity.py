"""A finite mathematical scope must not replace unresolved classical gates."""

import ast
import copy
import json
import shutil

import pytest

from scripts.audit_jinkou_polarity import (
    CORPUS,
    audit,
    compare_case,
    observe,
    reference,
)


@pytest.fixture(scope="module")
def data():
    return reference()


def test_formal_truth_table_retains_unreachable_masks_and_explicit_source_scope(data):
    answers = data["reference"]
    assert len(data["readings"]["formal_truth_table"]) == 16
    assert len(answers["cases"]) == 17280
    assert len(answers["mask_counts"]) == len(answers["unreachable_masks"]) == 8
    assert set(answers["mask_counts"].values()) == {2160}
    assert answers["use_counts"] == {"将神": 10800, "贵神": 6480}
    assert all(c["mask"][0] == c["mask"][3] for c in answers["cases"])
    assert data["readings"]["source_pages"] == list(range(41, 47))
    assert data["readings"]["annotation"]["reader_count"] == 1
    assert data["readings"]["annotation"]["blinded"] is False
    assert answers["scope"]["new_independent_real_events"] == 0


def test_entire_symbolic_cohort_passes_only_the_named_finite_gate():
    result = audit()
    assert result["formal_mask_count"] == 16
    assert all(r["matched"] for r in result["formal_rules"])
    assert result["symbolic_case_count"] == 17280
    assert result["polarity_scope_passed"] is True
    assert result["failures"] == []
    assert result["god_dun_polarity_difference_count"] == 0
    assert result["god_dun_phase_different_but_polarity_same"] == 13824
    assert result["implementation_unchanged"] is True
    assert result["calendar_validation"] == "not_assessed_symbolic_inputs"
    assert result["final_use_void_predicate_adjudicated"] is False
    assert result["comprehensive_use_adjudicated"] is False
    assert result["classical_acceptance_passed"] is False
    assert result["goal_complete"] is False
    old = result["original_scan_audit"]
    assert (old["scan_matched_count"], old["scan_case_count"]) == (11, 12)
    assert [r["id"] for r in old["scan_failures"]] == ["S01"]
    assert old["older_online_matched_count"] == 12


@pytest.mark.parametrize("change", ["readings", "reference", "source_image", "joint"])
def test_reference_labels_and_joint_manifest_rewrites_cannot_improve_score(
    tmp_path, change
):
    import hashlib

    target = tmp_path / "corpus"
    shutil.copytree(CORPUS, target, ignore=shutil.ignore_patterns("__pycache__"))
    name = {
        "readings": "readings.json",
        "reference": "reference.json",
        "source_image": "page-045.jpg",
        "joint": "reference.json",
    }[change]
    path = target / name
    path.write_bytes(path.read_bytes() + b" ")
    if change == "joint":
        manifest = json.loads((target / "freeze.json").read_text())
        manifest["files"][name] = hashlib.sha256(path.read_bytes()).hexdigest()
        (target / "freeze.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="Frozen polarity"):
        reference(target)


@pytest.mark.parametrize(
    "fault",
    [
        "dun_phase_as_god_phase",
        "wrong_polarity",
        "invented_use",
        "wrong_selected_empty",
        "invented_comprehensive",
        "integer_as_boolean",
        "duplicate_trace",
    ],
)
def test_independent_reference_catches_identity_use_and_evidence_faults(data, fault):
    case = next(
        c
        for c in data["reference"]["cases"]
        if c["use"] == "贵神"
        and data["readings"]["stem_elements"][c["dun_stems"][1]]
        != data["readings"]["branch_elements"][c["contents"][1]]
    )
    board = observe(case)
    assert compare_case(case, board, readings=data["readings"])["matched"]
    bad = copy.deepcopy(board)
    if fault == "dun_phase_as_god_phase":
        bad["rows"][1]["element"] = data["readings"]["stem_elements"][
            case["dun_stems"][1]
        ]
    elif fault == "wrong_polarity":
        bad["rows"][1]["polarity"] = "阴" if case["mask"][1] == "阳" else "阳"
    elif fault == "invented_use":
        bad["overview"]["use_position"] = "人元"
    elif fault == "wrong_selected_empty":
        bad["use_evidence"]["xun_kong"] = not bad["use_evidence"]["xun_kong"]
    elif fault == "invented_comprehensive":
        bad["use_evidence"]["comprehensive_position"] = "贵神"
    elif fault == "integer_as_boolean":
        bad["rows"][0]["is_use"] = int(bad["rows"][0]["is_use"])
    else:
        trace = next(
            t for t in bad["rule_trace"] if t["rule_id"] == "jinkou.polarity_use"
        )
        bad["rule_trace"].append(copy.deepcopy(trace))
    assert compare_case(case, bad, readings=data["readings"])["matched"] is False
