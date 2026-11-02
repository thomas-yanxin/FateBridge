"""Keep exposed gains, whole-unit evidence and rejected adoption distinct."""

import gzip
import hashlib
import json
import types
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.utils.data import GENERATION_CYCLE, STEM_ELEMENTS

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "docs/validation/bazi-visible-seal-path-v1"
ORDER = ("year", "month", "day", "hour")


def read(name):
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


def operator():
    binding = json.loads((STUDY / "implementation-binding.json").read_text())
    path = STUDY / "candidate.py.txt"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == binding["candidate_sha256"]
    module = types.ModuleType("_test_frozen_visible_seal_path")
    exec(compile(path.read_bytes(), str(path), "exec"), module.__dict__)
    return module


def example():
    data = read("development-first.json.gz")
    return next(
        r for r in data["rows"] if r["reference_id"].endswith(":DTCW1947-QQ-01")
    )


def test_every_old_record_is_replayed_without_numerical_or_source_label_mutation():
    data = read("development-first.json.gz")
    assert data["all_records"] == len(data["rows"]) == 367
    assert data["known"] == 123 and data["unknown_retained"] == 244
    assert not data["full_baseline_mismatch_ids"]
    assert not data["regression_ids"]
    assert len(data["improvement_ids"]) == 2
    assert len(data["changed_unknown_ids"]) == 5
    assert all(
        r["baseline_matches"] is None and r["candidate_matches"] is None
        for r in data["rows"]
        if r["expected_strength"] is None
    )
    assert not any(
        c["baseline_matches"] and not c["candidate_matches"]
        for c in data["constraints"]
    )
    assert data["development_gate_passed"]
    assert not data["adopted"] and not data["production_changed"]


def test_paths_use_actual_adjacent_positions_and_do_not_mutate_inputs():
    row = example()
    baseline = deepcopy(row["baseline"])
    pillars = dict(zip(ORDER, map(tuple, row["pillars"])))
    before = deepcopy(pillars)
    result = operator().evaluate(pillars, baseline)
    assert baseline == row["baseline"] and pillars == before
    assert result == row["candidate"]
    for position, paths in result["all_paths_to_day"].items():
        for path in paths:
            assert path[0] == position and path[-1] == "day"
            assert len(path) == len(set(path))
            for left, right in zip(path, path[1:]):
                assert abs(ORDER.index(left) - ORDER.index(right)) == 1
                a, b = (
                    STEM_ELEMENTS[pillars[left][0]][0],
                    STEM_ELEMENTS[pillars[right][0]][0],
                )
                assert a == b or GENERATION_CYCLE[a] == b


@pytest.mark.parametrize(
    "remove", ["body_qualification", "seal_roots", "officer_roots"]
)
def test_missing_real_prerequisite_cannot_be_replaced_by_synthetic_mass(remove):
    row = example()
    baseline = deepcopy(row["baseline"])
    pillars = dict(zip(ORDER, map(tuple, row["pillars"])))
    if remove == "body_qualification":
        for root in baseline["root_qualifications"]:
            root["qualified_for_structural_rule"] = False
    else:
        element = "木" if remove == "seal_roots" else "水"
        for root in baseline["hidden_stem_ledger"]:
            if root["element"] == element:
                root["remaining_mass"] = 0
        baseline["combination_contributions"].append(
            {"element": element, "mass": 10**12}
        )
    result = operator().evaluate(pillars, baseline)
    assert result["strength_level"] == baseline["strength_level"] == "弱"
    assert result["changed"] is False


def test_column_permutation_does_not_preserve_a_missing_generation_path():
    row = example()
    pillars = dict(zip(ORDER, map(tuple, row["pillars"])))
    pillars["year"], pillars["month"] = pillars["month"], pillars["year"]
    result = operator().evaluate(pillars, deepcopy(row["baseline"]))
    assert result["all_paths_to_day"]["month"] == []
    assert not result["changed"]


@pytest.mark.parametrize("rotation", range(5))
def test_all_five_elements_use_the_same_relational_operator(rotation):
    row = example()
    baseline = deepcopy(row["baseline"])
    module = operator()
    cycle = list(GENERATION_CYCLE)
    # Build the actual generation order, independent of enum/dictionary ordering.
    cycle = [cycle[0]]
    for _ in range(4):
        cycle.append(GENERATION_CYCLE[cycle[-1]])
    rotate = {e: cycle[(cycle.index(e) + rotation) % 5] for e in cycle}
    module.STEM_ELEMENTS = {
        s: (rotate[e], polarity) for s, (e, polarity) in STEM_ELEMENTS.items()
    }
    for root in baseline["hidden_stem_ledger"]:
        root["element"] = next(
            rotate[e].value for e in cycle if e.value == root["element"]
        )
    pillars = dict(zip(ORDER, map(tuple, row["pillars"])))
    result = module.evaluate(pillars, baseline)
    assert result["strength_level"] == row["candidate"]["strength_level"]
    assert result["predicates"] == row["candidate"]["predicates"]
    assert result["all_paths_to_day"] == row["candidate"]["all_paths_to_day"]


def test_whole_source_units_and_day_master_column_are_not_selected_by_outcome():
    reference = read("reference.json")
    data = read("prospective-first.json.gz")
    assert len(reference["cases"]) == data["all_cases"] == 6
    assert data["known_exact"] == 1 and data["unknown_retained"] == 5
    assert [r["source_case"] for r in data["rows"]] == reference["cases"]
    assert all(r["input_not_registered_in_old321"] for r in data["rows"])
    final = reference["cases"][-1]
    assert final["pillars"] == ["丙子", "己亥", "辛酉", "己亥"]
    assert final["pages"] == [248, 249]
    assert reference["cases"][3]["source_claims"][0]["ordinal_day"] == 22
    assert reference["cases"][4]["source_claims"][0]["ordinal_day"] == 26
    assert all(c["duty_day_after_term"] is None for c in reference["cases"])
    assert reference["cases"][2]["expected_strength"] is None
    assert data["constraints"][0]["source_claim"]["forbidden_strengths"] == ["弱"]


def test_exposed_gain_does_not_close_the_failed_new_source_adoption_gate():
    development = read("development-first.json.gz")
    data = read("prospective-first.json.gz")
    assert development["development_gate_passed"]
    assert data["adoption_conditions"]["development_gate_passed"]
    assert data["new_literal_exact_correction_ids"] == []
    assert not data["adoption_conditions"][
        "at_least_one_new_literal_input_exact_correction"
    ]
    assert not data["adoption_gate_passed"]
    assert not data["adopted"] and not data["production_changed"]
    assert (
        data["new_independent_validation_credit"] == data["new_model_executions"] == 0
    )
