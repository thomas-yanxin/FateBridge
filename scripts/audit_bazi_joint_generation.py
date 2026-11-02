"""Keep the joint-generation candidate rejected by its full frozen scope gate."""

import argparse
import gzip
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "tests/fixtures/bazi_joint_generation_v1"
D = ROOT / "docs/validation/bazi-joint-generation-files-v1"


def read(path):
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == ".gz" else raw)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def audit():
    protocol = read(F / "protocol-first.json")
    implementation = read(F / "implementation-before-outcomes-first.json")
    digest = hashlib.sha256((F / "candidate.py").read_bytes()).hexdigest()
    assert (
        digest
        == implementation["code_sha256"][
            "tests/fixtures/bazi_joint_generation_v1/candidate.py"
        ]
    )
    assert (
        hashlib.sha256((F / "run-study-before-package-fix.py").read_bytes()).hexdigest()
        == implementation["code_sha256"][
            "tests/fixtures/bazi_joint_generation_v1/run_study.py"
        ]
    )
    assert (F / "run-study-before-package-fix.py").read_text().replace(
        'load_module("_v71_shadow_arithmetic", arithmetic_path)',
        'load_module("fatebridge.core._v71_shadow_arithmetic", arithmetic_path)',
    ) == (F / "run_study.py").read_text()
    study, scope = read(D / "full408-first.json.gz"), read(
        D / "all518400-scope-first.json.gz"
    )
    assert study["candidate_sha256"] == scope["candidate_sha256"] == digest
    assert study["adopted"] is False and study["production_changed"] is False
    assert len(study["records"]) == 408
    prior = [
        json.loads(line)
        for line in gzip.open(
            ROOT
            / "docs/validation/bazi-month-command-integrity-files-v1/all408-source-final-first.jsonl.gz",
            "rt",
        )
    ]
    improvements, regressions, original19, effects = [], [], [], []
    candidates = {}
    for result, old in zip(study["records"], prior):
        assert canonical(result["case"]) == canonical(old["case"])
        assert canonical(result["baseline"]) == canonical(old["strength"]["assessment"])
        case = result["case"]
        before, after = (
            result["baseline"]["strength_level"],
            result["joint_candidate"]["strength_level"],
        )
        candidates[tuple(case["pillars"])] = result
        expected = case["expected_strength"]
        if expected is not None and before != expected and after == expected:
            improvements.append(case["group"] + ":" + case["id"])
        if expected is not None and before == expected and after != expected:
            regressions.append(case["group"] + ":" + case["id"])
        if result["joint_predicates"]["eligible"]:
            effects.append(
                {
                    "id": case["id"],
                    "pillars": case["pillars"],
                    "published_grade": before,
                    "root_only_grade": result["root_protection_only"]["strength_level"],
                    "root_only_share": result["root_protection_only"]["support_share"],
                    "experimental_structural_grade": after,
                }
            )
        if case["is_original_nineteen"]:
            original19.append(
                {
                    "id": case["id"],
                    "source_annotation": expected,
                    "published_grade": before,
                    "no_clash_punishment_diagnostic_grade": result[
                        "original19_no_clash_punishment_diagnostic"
                    ]["strength_level"],
                    "published_unresolved": before != expected,
                    "candidate_not_adopted": True,
                }
            )
    assert len(improvements) == 2 and not regressions
    assert len(effects) == 2 and len({tuple(x["pillars"]) for x in effects}) == 1
    assert (
        len(original19) == 19
        and sum(r["published_unresolved"] for r in original19) == 17
    )
    assert (
        sum(r["case"]["expected_strength"] is not None for r in study["records"]) == 127
    )
    assert (
        scope["enumerated_formula_inputs"] == 518400
        and scope["preliminary_joint_branch_body_shapes"] == 1120
    )
    assert (
        scope["joint_candidate_eligible"] == scope["distinct_eligible_inputs"] == 5
        and scope["postcondition_failures"] == 4
    )
    failures = [
        r
        for r in scope["eligible_records"]
        if r["broken_other_prerequisites_after_recompute"]
    ]
    assert len(failures) == 4
    assert all(r["known_classical_label"] is None for r in scope["eligible_records"])
    crosswalk = read(F / "scope-source-label-crosswalk-first.json")
    assert len(crosswalk) == 5
    source_matches = [r for r in crosswalk if r["retained_registered_observations"]]
    assert (
        len(source_matches) == 1
        and len(source_matches[0]["retained_registered_observations"]) == 2
    )
    assert all(
        r["expected_strength"] == "强"
        for r in source_matches[0]["retained_registered_observations"]
    )
    assert all(
        "not_assessed" in r["first_probe_field_meaning"]
        and r["new_label_assigned"] is False
        for r in crosswalk
    )
    assert all(
        r["broken_other_prerequisites_after_recompute"]
        == ["no_branch_combination_or_contest"]
        for r in failures
    )
    # Public forbidden-grade boundaries remain in their original denominator.
    index = read(ROOT / "src/fatebridge/data/reference/bazi-source-annotations-v8.json")
    public = [
        json.loads(line)
        for line in gzip.open(
            ROOT
            / "docs/validation/bazi-month-command-integrity-files-v1/public-all367-source-final-first.jsonl.gz",
            "rt",
        )
    ]
    by_reference = {r["reference_id"]: r for r in public}
    bounds = []
    for bound in index["strength_constraints"]:
        old = by_reference[bound["reference_id"]]
        result = candidates[tuple(old["pillars"])]
        before = (
            result["baseline"]["strength_level"] not in bound["forbidden_strengths"]
        )
        after = (
            result["joint_candidate"]["strength_level"]
            not in bound["forbidden_strengths"]
        )
        assert not (before and not after)
        bounds.append(
            {
                "constraint": bound,
                "baseline_satisfied": before,
                "experimental_satisfied": after,
            }
        )
    assert len(bounds) == 3
    suites = {}
    for name in (
        "candidate-gate-first",
        "candidate-gate-explicit-fixture-first",
        "research-audit-first",
        "research-audit-final-first",
    ):
        rows = ET.parse(D / (name + ".xml")).getroot().findall(".//testcase")
        failed = [
            r.attrib["name"]
            for r in rows
            if r.find("failure") is not None or r.find("error") is not None
        ]
        suites[name] = {
            "passed": len(rows) - len(failed),
            "failed": len(failed),
            "failed_names": failed,
        }
    assert (
        suites["candidate-gate-first"]["failed"] == 4
        and suites["candidate-gate-first"]["passed"] == 1
    )
    assert (
        suites["candidate-gate-explicit-fixture-first"]
        == suites["candidate-gate-first"]
    )
    assert (
        suites["research-audit-first"]["passed"] == 6
        and suites["research-audit-first"]["failed"] == 0
    )
    assert (
        suites["research-audit-final-first"]["passed"] == 6
        and suites["research-audit-final-first"]["failed"] == 0
    )
    sources = {
        p: h
        for p, h in protocol["initial_files_sha256"].items()
        if p.startswith("src/")
    }
    assert len(sources) == 6 and all(
        hashlib.sha256((ROOT / p).read_bytes()).hexdigest() == h
        for p, h in sources.items()
    )
    review = read(F / "complete-source-review-first.json")
    assert len(review["cases"]) == 4
    assert all(
        hashlib.sha256((ROOT / p).read_bytes()).hexdigest() == h
        for p, h in review["page_files_sha256"].items()
    )
    previous = read(F / "requirements-before-append-first.json.gz")
    current = read(ROOT / "docs/validation/bazi-three-axis-requirements.json")
    assert len(previous) == 107 and len(previous["requirements"]) == 14
    assert all(current[k] == v for k, v in previous.items())
    return {
        "all408_current_baselines_identical": True,
        "source_known_unknown_counts": [127, 281],
        "first_development_improvement_records": improvements,
        "first_development_improvement_distinct_inputs": 1,
        "first_development_regressions": regressions,
        "development_effects": effects,
        "original19": original19,
        "scope_formula_inputs": 518400,
        "scope_inputs_are_not_verified_birth_datetimes": True,
        "scope_eligible_inputs": 5,
        "postcondition_counterexamples": failures,
        "postcondition_failure_count": 4,
        "all_original3_forbidden_grade_bounds": bounds,
        "suites": suites,
        "adoption_gate_passed": False,
        "candidate_adopted": False,
        "candidate_unchanged_after_outcomes": True,
        "failed_cases_not_filtered_to_rescue_candidate": True,
        "production_changed": False,
        "new_transport_wheel_or_deployment_validation_claimed": False,
        "old_visible_only_candidate_gate_regraded": False,
        "new_classical_accuracy_credit": 0,
        "new_models": 0,
        "new19_model_semantic_acceptance": "not_tested",
        "independent_expert_review": "not_completed",
        "real_world_predictive_validity": "not_tested",
        "full_goal_complete": False,
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    a.output.open("x").write(json.dumps(audit(), ensure_ascii=False, indent=2) + "\n")
