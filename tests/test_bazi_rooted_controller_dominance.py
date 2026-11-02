"""Research rule guards do not turn an exposed development gain into adoption."""

import copy
import gzip
import hashlib
import json
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "docs/validation/bazi-rooted-controller-dominance-v1"


def frozen(name, compressed=False):
    path = STUDY / name
    assert (
        hashlib.sha256(path.read_bytes()).hexdigest()
        == path.with_suffix(".sha256").read_text().strip()
    )
    return json.loads(
        gzip.decompress(path.read_bytes()) if compressed else path.read_bytes()
    )


DEV = frozen("development-first.json.gz", True)
NEW = frozen("prospective-first.json.gz", True)
REFERENCE = frozen("reference-corrected-second.json")
XQ = next(r for r in DEV["rows"] if r["reference_id"].endswith(":DTCW1947-XQ-30"))


def candidate():
    module = types.ModuleType("_rooted_controller_test")
    path = STUDY / "candidate.py.txt"
    binding = json.loads((STUDY / "implementation-binding.json").read_text())
    assert hashlib.sha256(path.read_bytes()).hexdigest() == binding["candidate_sha256"]
    exec(compile(path.read_bytes(), str(path), "exec"), module.__dict__)
    return module


def pillars():
    return dict(zip(("year", "month", "day", "hour"), map(tuple, XQ["pillars"])))


def test_all_original_records_unknowns_and_bound_claims_are_preserved():
    assert (
        DEV["all_records"] == 367
        and DEV["known"] == 123
        and DEV["unknown_retained"] == 244
    )
    assert (
        DEV["full_baseline_mismatch_ids"]
        == DEV["regression_ids"]
        == DEV["changed_unknown_ids"]
        == []
    )
    assert DEV["improvement_ids"] == [XQ["reference_id"]]
    assert len(DEV["constraints"]) == 3
    assert sum(not c["baseline_matches"] for c in DEV["constraints"]) == 2
    assert all(
        c["baseline_matches"] == c["candidate_matches"] for c in DEV["constraints"]
    )
    assert DEV["adopted"] is DEV["production_changed"] is False


def test_complete_preselected_unit_fails_the_unchanged_adoption_gate():
    assert (
        NEW["all_cases"] == 4
        and NEW["known_exact"] == 3
        and NEW["unknown_retained"] == 1
    )
    assert (
        NEW["new_literal_exact_correction_ids"] == NEW["new_exact_regression_ids"] == []
    )
    assert (
        NEW["adoption_conditions"]["at_least_one_new_literal_input_exact_correction"]
        is False
    )
    assert (
        NEW["adoption_gate_passed"]
        is NEW["adopted"]
        is NEW["production_changed"]
        is False
    )
    assert all(
        r["baseline"]["strength_level"] == r["candidate"]["strength_level"]
        for r in NEW["rows"]
    )


def test_high_resolution_transcription_repair_does_not_change_any_pillar_or_label():
    first = frozen("reference-first.json")
    assert [(r["id"], r["pillars"], r["expected_strength"]) for r in first["rows"]] == [
        (r["id"], r["pillars"], r["expected_strength"]) for r in REFERENCE["rows"]
    ]
    assert "支拱寅戌" in REFERENCE["rows"][1]["context"][1]
    assert "干透兩丁" in REFERENCE["rows"][2]["anchor"]
    assert REFERENCE["rows"][2]["expected_strength"] is None


def test_source_year_month_conflict_remains_literal_and_not_a_birth_reconstruction():
    row = next(r for r in NEW["rows"] if r["source_case"]["id"] == "GR04")
    assert row["source_case"]["pillars"] == ["戊辰", "己酉", "乙亥", "甲申"]
    assert row["input_context"]["month_stem_matches_recorded_year"] is False
    assert row["input_context"]["expected_month_stem_under_modern_rule"] == "辛"
    assert row["input_context"]["literal_source_changed"] is False
    assert row["input_context"]["historical_birth_datetime_verified"] is False


@pytest.mark.parametrize("remaining", [0.0, 0.749999, 0.75])
def test_controller_retention_uses_actual_ledger_and_the_existing_threshold(remaining):
    baseline = copy.deepcopy(XQ["baseline"])
    root = next(
        r
        for r in baseline["hidden_stem_ledger"]
        if r["pillar"] == "year" and r["element"] == "火"
    )
    root["remaining_mass"] = root["initial_mass"] * remaining
    result = candidate().evaluate(pillars(), baseline)
    assert result["changed"] is (remaining >= 0.75)


def test_real_rooted_output_disables_the_hypothesized_unmediated_condition():
    baseline = copy.deepcopy(XQ["baseline"])
    baseline["hidden_stem_ledger"].append(
        dict(
            pillar="hour", stem="壬", element="水", initial_mass=1.0, remaining_mass=1.0
        )
    )
    assert candidate().evaluate(pillars(), baseline)["changed"] is False


def test_visible_parent_disables_the_hypothesis_without_changing_the_chart_lookup_key():
    original = pillars()
    modified = dict(original, year=("戊", original["year"][1]))
    result = candidate().evaluate(modified, copy.deepcopy(XQ["baseline"]))
    assert result["predicates"]["no_visible_parent"] is False
    assert result["changed"] is False


def test_candidate_is_element_cycle_symmetric_on_synthetic_operator_inputs():
    module = candidate()
    elements = list(module.GENERATION_CYCLE)
    body = module.STEM_ELEMENTS[pillars()["day"][0]][0]
    order = [body]
    for _ in range(4):
        order.append(module.GENERATION_CYCLE[order[-1]])
    assert set(order) == set(elements)
    for shift in range(5):
        rename = {element: order[(i + shift) % 5] for i, element in enumerate(order)}
        actual = candidate()
        actual.STEM_ELEMENTS = {
            stem: (rename[value[0]], *value[1:])
            for stem, value in module.STEM_ELEMENTS.items()
        }
        actual.BRANCH_ELEMENTS = {
            branch: (rename[value[0]], *value[1:])
            for branch, value in module.BRANCH_ELEMENTS.items()
        }
        actual.GENERATION_CYCLE = {
            rename[a]: rename[b] for a, b in module.GENERATION_CYCLE.items()
        }
        actual.DESTRUCTION_CYCLE = {
            rename[a]: rename[b] for a, b in module.DESTRUCTION_CYCLE.items()
        }
        baseline = copy.deepcopy(XQ["baseline"])
        lookup = {element.value: rename[element].value for element in elements}
        for row in baseline["hidden_stem_ledger"]:
            row["element"] = lookup[row["element"]]
        assert actual.evaluate(pillars(), baseline)["strength_level"] == "弱"
