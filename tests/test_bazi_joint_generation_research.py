"""Audit negative research evidence without adopting or rescoring the candidate."""

import gzip
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "tests/fixtures/bazi_joint_generation_v1"
D = ROOT / "docs/validation/bazi-joint-generation-files-v1"


def read(path):
    return json.loads(gzip.decompress(path.read_bytes()))


def test_candidate_and_first_outcomes_remain_bound_to_the_frozen_implementation():
    binding = json.loads((F / "implementation-before-outcomes-first.json").read_text())
    candidate = ROOT / "tests/fixtures/bazi_joint_generation_v1/candidate.py"
    assert (
        hashlib.sha256(candidate.read_bytes()).hexdigest()
        == binding["code_sha256"][str(candidate.relative_to(ROOT))]
    )
    first = read(D / "full408-first.json.gz")
    assert (
        first["candidate_sha256"] == hashlib.sha256(candidate.read_bytes()).hexdigest()
    )
    assert first["adopted"] is False and first["production_changed"] is False


def test_all408_and_original19_keep_unknown_labels_and_published_baselines():
    study = read(D / "full408-first.json.gz")
    original = [
        json.loads(line)
        for line in gzip.open(
            ROOT
            / "docs/validation/bazi-month-command-integrity-files-v1/all408-source-final-first.jsonl.gz",
            "rt",
        )
    ]
    assert len(study["records"]) == len(original) == 408
    for result, row in zip(study["records"], original):
        assert result["case"] == row["case"]
        assert json.dumps(result["baseline"], sort_keys=True) == json.dumps(
            row["strength"]["assessment"], sort_keys=True
        )
    eligible = [r for r in study["records"] if r["joint_predicates"]["eligible"]]
    assert (
        len(eligible) == 2 and len({tuple(r["case"]["pillars"]) for r in eligible}) == 1
    )
    assert sum(r["case"]["expected_strength"] is None for r in study["records"]) == 281
    nineteen = [r for r in study["records"] if r["case"]["is_original_nineteen"]]
    assert len(nineteen) == 19
    assert (
        sum(
            r["baseline"]["strength_level"] != r["case"]["expected_strength"]
            for r in nineteen
        )
        == 17
    )


def test_root_loss_removal_does_not_by_itself_reproduce_tongguan_source_grade():
    rows = read(D / "full408-first.json.gz")["records"]
    case = next(r for r in rows if r["case"]["id"] == "DTCW1947-TG-01")
    assert (
        case["baseline"]["strength_level"]
        == case["root_protection_only"]["strength_level"]
        == "弱"
    )
    assert case["original19_no_clash_punishment_diagnostic"]["strength_level"] == "弱"
    assert case["joint_candidate"]["strength_level"] == "强"
    assert (
        case["root_protection_only"]["threshold_arithmetic"]["numerical_label"] == "弱"
    )
    assert (
        case["root_protection_only"]["support_share"]
        > case["baseline"]["support_share"]
    )


def test_full_scope_keeps_all_four_postcondition_counterexamples_and_no_new_labels():
    scope = read(D / "all518400-scope-first.json.gz")
    assert scope["enumerated_formula_inputs"] == 518400
    assert scope["preliminary_joint_branch_body_shapes"] == 1120
    assert scope["joint_candidate_eligible"] == scope["distinct_eligible_inputs"] == 5
    assert scope["postcondition_failures"] == 4
    failures = [
        r
        for r in scope["eligible_records"]
        if r["broken_other_prerequisites_after_recompute"]
    ]
    assert len(failures) == 4
    assert all(r["known_classical_label"] is None for r in scope["eligible_records"])
    crosswalk = json.loads((F / "scope-source-label-crosswalk-first.json").read_text())
    assert len(crosswalk) == 5
    registered = [r for r in crosswalk if r["retained_registered_observations"]]
    assert len(registered) == 1
    assert [
        r["expected_strength"]
        for r in registered[0]["retained_registered_observations"]
    ] == ["强", "强"]
    assert all(
        r["new_label_assigned"] is False
        and "not_assessed" in r["first_probe_field_meaning"]
        for r in crosswalk
    )
    assert all(
        r["broken_other_prerequisites_after_recompute"]
        == ["no_branch_combination_or_contest"]
        for r in failures
    )
    assert all(any(e["kind"] == "半合" for e in r["after_relations"]) for r in failures)
    assert not any(e["kind"] == "半合" for r in failures for e in r["before_relations"])


def test_independent_input_enumeration_is_complete_and_modern_consistency_is_not_birth_evidence():
    spec = importlib.util.spec_from_file_location(
        "_v71_literal_enumeration", F / "independent_scope.py"
    )
    oracle = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(oracle)
    from fatebridge.validation.bazi_source_corpus import input_consistency

    count = 0
    for values in oracle.inputs():
        facts = input_consistency(values)
        assert facts["all_three_modern_checks_match"]
        assert facts["historical_birth_datetime_verified"] is False
        count += 1
    assert count == 518400


def test_all_six_original_owned_source_files_remain_sealed():
    plan = json.loads((F / "protocol-first.json").read_text())
    source = {
        n: h for n, h in plan["initial_files_sha256"].items() if n.startswith("src/")
    }
    assert len(source) == 6
    originals = read(F / "before-first.json.gz")
    assert all(
        hashlib.sha256(originals[n].encode()).hexdigest() == h
        for n, h in source.items()
    )
