"""Independent scanned structures, unresolved rules and actual use conditions."""

import importlib.util
import json
import shutil
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core.metaphysics.jinkou_patterns import structural_patterns
from fatebridge.core.output_ren_patterns import JinkouPatternEvaluation
from tests.ren.test_ren_classical_depth import AUDIT as V1

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "audit_jinkou_patterns", ROOT / "scripts/ren/audit_jinkou_patterns.py"
)
assert SPEC and SPEC.loader
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


def literal(index):
    case = AUDIT.load_reference()["cases"][index - 1]
    old = V1.load_frozen_corpus()
    return AUDIT.literal_rows(case, old["rules"]["inherent"]), case


def recognize(index):
    rows, case = literal(index)
    return structural_patterns(rows, day_ganzhi=case["day"] or "甲子")


def ids(result):
    return {p["id"] for p in result["matched"]}


def test_all_64_scanned_entries_are_kept_including_disagreements_and_missing_days():
    report = AUDIT.audit()
    assert report["corpus_case_count"] == 64
    assert report["matched_semantic_cases"] == 54
    assert report["unevaluated_definitions"] == 6
    assert {c["id"] for c in report["semantic_failures"]} == {
        "P03",
        "P04",
        "P05",
        "P25",
    }
    assert len(report["source_day_reconstructions"]) == 64
    assert (
        sum(
            c["status"] == "missing_source_day"
            for c in report["source_day_reconstructions"]
        )
        == 2
    )
    assert report["matched_source_day_cases"] == 46
    assert report["semantic_status_counts"] == {
        "matched": 54,
        "not_matched": 4,
        "unresolved": 6,
    }
    assert report["reconstruction_status_counts"] == {
        "matched": 46,
        "not_matched": 16,
        "unavailable": 2,
    }
    assert all(
        c["matched"] is None
        for c in report["semantic_checks"]
        if c["status"] == "unevaluated_definition"
    )
    assert all(
        c["matched"] is None
        for c in report["source_day_reconstructions"]
        if c["status"] == "missing_source_day"
    )
    assert not report["classical_acceptance_passed"] and not report["goal_complete"]


@pytest.mark.parametrize(
    "index",
    [
        1,
        2,
        12,
        19,
        20,
        21,
        27,
        29,
        30,
        31,
        32,
        34,
        35,
        36,
        37,
        40,
        41,
        42,
        43,
        44,
        45,
        46,
        47,
        48,
        49,
        50,
        51,
        54,
        55,
        60,
        61,
        62,
        63,
        64,
    ],
)
def test_source_structure_has_its_named_predicate_with_a_locator(index):
    result = recognize(index)
    match = next(p for p in result["matched"] if p["id"] == f"P{index:02}")
    assert match["condition"] and match["basis"]
    assert (
        match["original_pdf_page"]
        == AUDIT.load_reference()["cases"][index - 1]["original_pdf_page"]
    )
    assert result["evaluated_rule_count"] == 58
    assert result["catalog_count"] == 64


def test_equal_earth_elements_are_not_three_identical_house_branches():
    result = recognize(6)
    assert "P06" in ids(result) and "P05" not in ids(result)


def test_complete_ledger_distinguishes_a_false_definition_from_an_unresolved_one():
    # The independently frozen 俱比 example has equal earth elements but
    # different house branches. P05 is false; P52 is still undecided.
    result = recognize(6)
    records = {p["id"]: p for p in result["evaluations"]}
    assert list(records) == [f"P{i:02}" for i in range(1, 65)]
    assert records["P06"]["matched"] is True
    assert records["P06"]["status"] == "matched"
    assert records["P05"]["matched"] is False
    assert records["P05"]["status"] == "not_matched"
    assert records["P05"]["condition"] and records["P05"]["reason"] is None
    assert {k for k, p in records.items() if p["matched"] is None} == {
        "P52",
        "P53",
        "P56",
        "P57",
        "P58",
        "P59",
    }
    assert records["P52"]["status"] == "unresolved_definition"
    assert records["P52"]["condition"] is None and records["P52"]["reason"]
    assert records["P52"]["original_pdf_page"] == 118
    assert sum(result["evaluation_counts"].values()) == 64
    assert result["evaluation_counts"]["unresolved"] == 6
    assert result["evaluation_counts"]["matched"] == len(result["matched"])
    assert {k for k, p in records.items() if p["matched"] is True} == ids(result)


@pytest.mark.parametrize(
    "status,matched",
    [
        ("unresolved_definition", False),
        ("unresolved_definition", True),
        ("matched", False),
        ("matched", None),
        ("not_matched", True),
        ("not_matched", None),
    ],
)
def test_public_contract_rejects_a_changed_three_state_verdict(status, matched):
    with pytest.raises(ValidationError, match="三态"):
        JinkouPatternEvaluation.model_validate(dict(status=status, matched=matched))


def test_three_state_contract_accepts_actual_values_and_partial_projection():
    for record in recognize(6)["evaluations"]:
        JinkouPatternEvaluation.model_validate(record)
    for partial in (
        {"matched": None},
        {"matched": False},
        {"status": "matched"},
        {"status": "unresolved_definition"},
    ):
        JinkouPatternEvaluation.model_validate(partial)
    with pytest.raises(ValidationError):
        JinkouPatternEvaluation.model_validate({"matched": "false"})


def test_same_phase_does_not_make_same_branch_fuyin():
    result = recognize(13)
    assert {"P10", "P13"} <= ids(result)
    assert "P11" not in ids(result)


def test_transformed_trine_control_and_noble_control_are_different_conditions():
    result = recognize(2)
    assert "P02" in ids(result) and "P01" not in ids(result)


def test_upward_and_downward_generation_remain_distinct():
    assert "P34" in ids(recognize(34)) and "P36" not in ids(recognize(34))
    assert "P36" in ids(recognize(36)) and "P34" not in ids(recognize(36))


def test_no_control_guideline_and_empty_use_do_not_invent_a_final_adjudication():
    # An entirely symbolic source-style board, never an asserted real date.
    result = V1.observe_jinkou(dict(day="癸巳", hour="申", ground="子", general="戌"))
    evidence = result["use_evidence"]
    assert evidence["no_control_principle_applies"] is True
    assert evidence["status"] == "no_control_strength_priority_unresolved"
    assert evidence["comprehensive_position"] is None
    assert result["overview"]["use_position"] == evidence["polarity_position"]
    assert evidence["subject_position"] == "贵神"
    result = V1.observe_jinkou(dict(day="丙申", hour="丑", ground="巳", general="子"))
    selected = next(r for r in result["rows"] if r["is_use"])
    evidence = result["use_evidence"]
    assert evidence["xun_kong"] == selected["xun_kong"]
    assert evidence["si_da_kong"] == selected["si_da_kong"]
    assert evidence["comprehensive_position"] is None


def test_reference_manifest_rejects_tampered_independent_labels(tmp_path):
    target = tmp_path / "source"
    shutil.copytree(AUDIT.CORPUS, target)
    file = target / "cases.json"
    data = json.loads(file.read_text())
    data["cases"][2]["positions"][1] = "玄武"
    file.write_text(json.dumps(data, ensure_ascii=False))
    with pytest.raises(ValueError, match="reference changed"):
        AUDIT.load_reference(target)
