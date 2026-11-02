"""Verify the full rejected multiplicity candidate, including its counterexample."""

import argparse
import gzip
import hashlib
import importlib.util
import json
import xml.etree.ElementTree as ET
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "tests/fixtures/bazi_zi_mao_multiplicity_v1"
D = ROOT / "docs/validation/bazi-zi-mao-multiplicity-files-v1"


def read(path):
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == ".gz" else raw)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def audit():
    binding = read(F / "candidate-reference-binding-first.json")["files_sha256"]
    assert all(
        hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest
        for name, digest in binding.items()
    )
    protocol = read(F / "protocol-first.json")
    originals = read(F / "before-first.json.gz")
    assert all(
        hashlib.sha256(originals[name].encode()).hexdigest() == digest
        for name, digest in protocol["initial_files_sha256"].items()
        if name.startswith("src/")
    )
    summary = read(D / "study-summary-first.json")
    assert (
        summary["geometry_rows"],
        summary["affected_geometries"],
        summary["daystem_probes"],
    ) == (20736, 120, 1200)
    assert (
        summary["known_label_regressions"]
        == summary["new_bound_regressions"]
        == summary["new_public_bound_regressions"]
        == 0
    )
    assert summary["new_source_control_regressions"] == 1
    study = read(D / "all408-candidate-first.json.gz")["rows"]
    baseline = [
        json.loads(line)
        for line in gzip.open(
            ROOT
            / "docs/validation/bazi-energy-provenance-files-v1/all408-current-first.jsonl.gz",
            "rt",
        )
    ]
    assert len(study) == len(baseline) == 408
    original, changed = [], []
    for row, old in zip(study, baseline):
        assert canonical(row["case"]) == canonical(old["case"])
        assert canonical(row["before"]) == canonical(old["strength"]["assessment"])
        assert row["before"]["strength_level"] == row["after"]["strength_level"]
        if row["changed"]:
            changed.append(row["case"]["id"])
        if row["case"]["is_original_nineteen"]:
            assert canonical(row["before"]) == canonical(row["after"])
            original.append(
                {
                    "id": row["case"]["id"],
                    "source_label": row["case"]["expected_strength"],
                    "current_grade": row["before"]["strength_level"],
                }
            )
    assert changed == ["YL-03", "DTCW1947-YX-01", "DTCW1947-SJ09"]
    assert (
        len(original) == 19
        and sum(r["source_label"] != r["current_grade"] for r in original) == 17
    )
    assert sum(r["case"]["expected_strength"] is not None for r in study) == 127
    reference = load("multiplicity_literal_reference", F / "reference.py")
    geometries = [
        json.loads(line)
        for line in gzip.open(D / "all20736-geometry-first.jsonl.gz", "rt")
    ]
    old_geometry = [
        json.loads(line)
        for line in gzip.open(
            ROOT
            / "docs/validation/bazi-single-end-resolution-files-v1/all20736-geometry-first.jsonl.gz",
            "rt",
        )
    ]
    assert len(geometries) == len(old_geometry) == 20736
    assert len({tuple(row["branches"]) for row in geometries}) == 20736
    for row, old in zip(geometries, old_geometry):
        assert row["branches"] == old["branches"] and row["before"] == old["after"]
        assert row["after"] == reference.expected_relations(
            row["branches"], row["before"]
        )
    assert sum(row["changed"] for row in geometries) == 120
    arithmetic = load(
        "frozen_independent_arithmetic",
        ROOT / "tests/fixtures/bazi_strength_threshold_v1/independent_reference_v2.py",
    )
    probes = read(D / "all-affected-daystems-first.json.gz")["rows"]
    assert len(probes) == 1200
    for row in probes:
        expected = arithmetic.reconstruct(row["pillars"], row["after"]["relations"])
        assert {
            e: Fraction(q) for e, q in row["independent_energies_exact"].items()
        } == expected["energies"]
        assert {
            e: Fraction(q)
            for e, q in row["after"]["threshold_arithmetic"]["energies_exact"].items()
        } == expected["energies"]
        assert all(
            abs(row["after"]["effective_elements_unrounded"][e] - float(q)) <= 1e-12
            for e, q in expected["energies"].items()
        )
    controls = read(D / "original14clause-and9controls-first.json.gz")
    first_controls = read(
        ROOT
        / "tests/fixtures/bazi_single_end_resolution_v1/source-condition-controls-first.json"
    )
    assert (
        controls["all_clauses"] == first_controls["all_clauses"]
        and len(controls["all_clauses"]) == 14
    )
    assert [row["control"] for row in controls["controls"]] == first_controls[
        "synthetic_controls"
    ]
    regression = [
        row
        for row in controls["controls"]
        if row["before_matches"] and not row["after_matches"]
    ]
    assert (
        len(regression) == 1
        and regression[0]["control"]["id"] == "two_mao_after_binding_gap"
    )
    assert all(e["kind"] != "六合" for e in regression[0]["before"]["relations"])
    parity = read(D / "all25-source-parity-diagnostics-first.json.gz")
    assert len(parity["rows"]) == 25 and all(
        row["mechanism_matches"] for row in parity["rows"]
    )
    sexagenary = {
        "甲乙丙丁戊己庚辛壬癸"[i % 10] + "子丑寅卯辰巳午未申酉戌亥"[i % 12]
        for i in range(60)
    }
    month_stems = {"乙": "戊", "丁": "壬", "己": "丙", "辛": "庚", "癸": "甲"}
    assert len({tuple(row["pillars"]) for row in parity["rows"]}) == 25
    for row in parity["rows"]:
        y, m, d, h = row["pillars"]
        assert all(p in sexagenary for p in row["pillars"])
        assert y[1] == "卯" and m == month_stems[y[0]] + "子"
        assert d[0] == "甲" and d[1] in "寅辰午申戌" and h == "丁卯"
        assert [i for i, p in enumerate(row["pillars"]) if p[1] == "卯"] == [0, 3]
    assert sum(row["source_clause"] == "C09" for row in parity["rows"]) == 20
    assert (
        parity["does_not_override_failed_original_control"] is True
        and parity["candidate_adopted"] is False
    )
    suites = {}
    for name in ("pre-edit-adoption-first", "candidate-gate-first"):
        cases = list(ET.parse(D / (name + ".xml")).getroot().iter("testcase"))
        failures = [
            t.attrib["name"]
            for t in cases
            if t.find("failure") is not None or t.find("error") is not None
        ]
        suites[name] = {
            "passed": len(cases) - len(failures),
            "failed": len(failures),
            "failed_names": failures,
        }
    assert (
        suites["pre-edit-adoption-first"]["passed"] == 1
        and suites["pre-edit-adoption-first"]["failed"] == 3
    )
    assert (
        suites["candidate-gate-first"]["passed"] == 10
        and suites["candidate-gate-first"]["failed"] == 3
    )
    assert any(
        "two_mao_after_binding_gap" in name
        for name in suites["candidate-gate-first"]["failed_names"]
    )
    decision = read(F / "rejected-candidate-decision-first.json")
    assert (
        decision["decision"] == "reject_current_multiplicity_candidate"
        and decision["production_changed"] is False
    )
    return {
        "geometry_rows": 20736,
        "changed_geometries": 120,
        "independent_daystem_probes": 1200,
        "maximum_independent_float_error": summary["max_independent_float_error"],
        "research_records": 408,
        "public_records": 367,
        "known_unknown_counts": [127, 281],
        "changed_experimental_records": changed,
        "all408_grades_unchanged_even_in_candidate": True,
        "all19_original_assessments_unchanged_even_in_candidate": True,
        "original19": original,
        "original19_unresolved": 17,
        "known_label_regressions": 0,
        "new_bound_regressions": 0,
        "new_public_bound_regressions": 0,
        "new_source_control_regressions": 1,
        "failed_source_control": "two_mao_after_binding_gap",
        "original14clauses_and9controls_retained": True,
        "post_discovery_parity_diagnostics": {
            "C09": 20,
            "C10": 5,
            "not_new_independent_accuracy_credit": True,
        },
        "suites": suites,
        "candidate_adopted": False,
        "candidate_unchanged_after_outcomes": True,
        "production_changed": False,
        "new_transport_wheel_or_deployment_acceptance_claimed": False,
        "new_classical_accuracy_credit": 0,
        "new_models": 0,
        "new19_model_semantic_acceptance": "not_tested",
        "independent_expert_review": "not_completed",
        "real_world_predictive_validity": "not_tested",
        "full_goal_complete": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    value = audit()
    args.output.open("x").write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {k: v for k, v in value.items() if k != "original19"}, ensure_ascii=False
        )
    )
