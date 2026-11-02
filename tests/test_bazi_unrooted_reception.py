"""An exposed-case gain cannot replace the predeclared fresh-unit gate."""

import gzip
import hashlib
import json
import types
from copy import deepcopy
from pathlib import Path

from fatebridge.utils.data import GENERATION_CYCLE, STEM_ELEMENTS

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "docs/validation/bazi-unrooted-reception-v1"


def frozen(name):
    path = STUDY / name
    assert (
        hashlib.sha256(path.read_bytes()).hexdigest()
        == path.with_suffix(".sha256").read_text().strip()
    )
    return json.loads(
        gzip.decompress(path.read_bytes())
        if path.suffix == ".gz"
        else path.read_bytes()
    )


DEVELOPMENT = frozen("development-first.json.gz")
PROSPECTIVE = frozen("prospective-first.json.gz")
REFERENCE = frozen("reference-first.json")
module = types.ModuleType("_frozen_unrooted_reception_test")
code = STUDY / "candidate.py.txt"
binding = json.loads((STUDY / "implementation-binding.json").read_text())
assert hashlib.sha256(code.read_bytes()).hexdigest() == binding["candidate_sha256"]
exec(compile(code.read_bytes(), str(code), "exec"), module.__dict__)


def changed_case():
    return next(
        r for r in DEVELOPMENT["rows"] if r["reference_id"].endswith(":DTCW1947-JH-02")
    )


def pillars(row):
    return dict(zip(("year", "month", "day", "hour"), map(tuple, row["pillars"])))


def test_every_original_record_label_and_full_baseline_stays_in_development():
    assert DEVELOPMENT["all_records"] == 367
    assert DEVELOPMENT["known"] == 123 and DEVELOPMENT["unknown_retained"] == 244
    assert DEVELOPMENT["full_baseline_mismatch_ids"] == []
    assert DEVELOPMENT["improvement_ids"] == ["stem_conversion_v2:DTCW1947-JH-02"]
    assert DEVELOPMENT["regression_ids"] == []
    assert len(DEVELOPMENT["changed_unknown_ids"]) == 4
    assert all(
        r["expected_strength"] is None
        for r in DEVELOPMENT["rows"]
        if r["reference_id"] in DEVELOPMENT["changed_unknown_ids"]
    )
    assert not any(
        c["baseline_matches"] and not c["candidate_matches"]
        for c in DEVELOPMENT["constraints"]
    )


def test_complete_fixed_unit_has_three_cases_and_no_added_body_labels():
    assert [r["id"] for r in REFERENCE["rows"]] == ["SN01", "SN02", "SN03"]
    assert [r["expected_strength"] for r in REFERENCE["rows"]] == ["强", None, None]
    assert PROSPECTIVE["all_cases"] == 3
    assert PROSPECTIVE["known_exact"] == 1 and PROSPECTIVE["unknown_retained"] == 2
    assert not any(r["candidate"]["changed"] for r in PROSPECTIVE["rows"])
    assert PROSPECTIVE["new_literal_exact_correction_ids"] == []
    assert PROSPECTIVE["new_exact_regression_ids"] == []
    assert PROSPECTIVE["adoption_gate_passed"] is False
    assert (
        PROSPECTIVE["adopted"] is False and PROSPECTIVE["production_changed"] is False
    )


def test_a_positive_actual_body_root_breaks_the_no_reception_predicate():
    row = changed_case()
    baseline = deepcopy(row["baseline"])
    body = STEM_ELEMENTS[row["pillars"][2][0]][0].value
    baseline["hidden_stem_ledger"].append({"element": body, "remaining_mass": 0.01})
    result = module.evaluate(pillars(row), baseline)
    assert result["changed"] is False
    assert result["strength_level"] == row["baseline"]["strength_level"]


def test_synthetic_combination_budget_is_not_a_physical_body_root():
    row = changed_case()
    baseline = deepcopy(row["baseline"])
    baseline["combination_contributions"].append(
        {"element": "木", "mass": 999, "synthetic": True}
    )
    assert module.evaluate(pillars(row), baseline)["changed"] is True


def test_parent_existence_and_dominance_are_separate_necessary_conditions():
    row = changed_case()
    chart = pillars(row)
    body = STEM_ELEMENTS[chart["day"][0]][0]
    parent = next(e for e, child in GENERATION_CYCLE.items() if child == body)
    no_parent = deepcopy(row["baseline"])
    no_parent["hidden_stem_ledger"] = [
        r for r in no_parent["hidden_stem_ledger"] if r["element"] != parent.value
    ]
    assert module.evaluate(chart, no_parent)["changed"] is False
    no_dominance = deepcopy(row["baseline"])
    no_dominance["effective_elements_unrounded"][parent.value] = no_dominance[
        "effective_elements_unrounded"
    ][body.value]
    assert module.evaluate(chart, no_dominance)["changed"] is False


def test_inserting_a_chart_identifier_cannot_change_candidate_result():
    row = changed_case()
    chart, before = pillars(row), deepcopy(row["baseline"])
    expected = module.evaluate(chart, before)
    before["case_id"] = "not-the-source-case"
    before["source_grade"] = "强"
    assert module.evaluate(chart, before) == expected


def test_source_force_subjects_do_not_become_day_master_labels():
    claims = json.loads((STUDY / "retained-mechanism-claims.json").read_text())
    assert claims["claims"][1]["subject"] == "天干兩甲財星"
    assert claims["claims"][2]["subject"] == "壬印與丙傷"
    assert claims["claims"][1]["retained_body_strength"] is None
    assert claims["claims"][2]["retained_body_strength"] is None


def test_original_grade_calculation_and_public_index_have_not_changed():
    protocol = frozen("protocol.json")
    for name in (
        "src/fatebridge/core/strength.py",
        "src/fatebridge/data/reference/bazi-source-annotations-v5.json",
    ):
        assert (
            hashlib.sha256(
                (
                    (
                        ROOT
                        / "docs/validation/bazi-frontmatter-knowledge-v1/before"
                        / name
                    )
                    if name.endswith("strength.py")
                    else (ROOT / name)
                ).read_bytes()
            ).hexdigest()
            == protocol["inputs"][name]
        )
    assert (
        DEVELOPMENT["production_changed"] is PROSPECTIVE["production_changed"] is False
    )
    assert (
        DEVELOPMENT["new_model_executions"] == PROSPECTIVE["new_model_executions"] == 0
    )
