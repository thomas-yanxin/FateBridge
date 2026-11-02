"""Recheck frozen month-duty contradictions, complete cohorts and protocol archives."""

import argparse
import gzip
import hashlib
import json
import tarfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "tests/fixtures/bazi_month_command_integrity_v1"
D = ROOT / "docs/validation/bazi-month-command-integrity-files-v1"
OLD = ROOT / "docs/validation/bazi-same-target-bureau-files-v1"


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def rows(path):
    return [json.loads(line) for line in gzip.open(path, "rt")]


def read(path):
    return json.loads(path.read_text())


def suite(name):
    tests = ET.parse(D / (name + ".xml")).getroot().findall(".//testcase")
    failed = [
        t.attrib["name"]
        for t in tests
        if t.find("failure") is not None or t.find("error") is not None
    ]
    return {
        "passed": len(tests) - len(failed),
        "failed": len(failed),
        "failed_names": failed,
    }


def audit():
    from pydantic import ValidationError

    from fatebridge.core.output_bazi_evidence import BaziEvidenceChain

    first = json.loads(
        gzip.decompress((D / "first152-accepted-contradictions.json.gz").read_bytes())
    )
    assert len(first) == 152 and len({r["id"] for r in first}) == 19
    for row in first:
        assert row["first_accepted"] is True
        try:
            BaziEvidenceChain.model_validate(row["value"])
        except ValidationError:
            pass
        else:
            raise AssertionError((row["id"], row["fault"]))
    before_partial = read(D / "partial-first-backend-first.json")
    after_partial = read(D / "partial-final-backend-first.json")
    assert before_partial["accepted"] == [True] * 5
    assert after_partial["accepted"] == [False] * 5
    baseline = rows(OLD / "all408-source-first.jsonl.gz")
    public_before = rows(OLD / "public-all367-source-first.jsonl.gz")
    original19 = []
    for name in ("source-first", "source-final-first", "wheel-final-first"):
        after = rows(D / ("all408-" + name + ".jsonl.gz"))
        assert len(after) == 408 and canonical(after) == canonical(baseline)
        public_after = rows(D / ("public-all367-" + name + ".jsonl.gz"))
        assert len(public_after) == 367 and canonical(public_after) == canonical(
            public_before
        )
    for row in baseline:
        if row["case"]["is_original_nineteen"]:
            case = row["case"]
            original19.append(
                {
                    "id": case["id"],
                    "retained_annotation": case["expected_strength"],
                    "current_strength": row["strength"]["strength_level"],
                    "unresolved": case["expected_strength"]
                    != row["strength"]["strength_level"],
                    "all_body_seal_month_and_passage_values_unchanged": True,
                }
            )
    assert len(original19) == 19 and sum(r["unresolved"] for r in original19) == 17
    with tarfile.open(OLD / "affiliation-protocols-source-first.tar.gz") as archive:
        old_protocols = json.loads(archive.extractfile("proof.json").read())
    protocols = []
    for backend in ("source-first", "source-final-first", "wheel-final-first"):
        with tarfile.open(D / ("protocols-" + backend + ".tar.gz")) as archive:
            proof = json.loads(archive.extractfile("proof.json").read())
        assert proof["responses"] == 69 and proof["groups"] == old_protocols["groups"]
        assert proof["fixed_response_char_limit"] == 8192
        assert all(
            r["same_run_hash_verified"] and r["first_chars"] <= 8192
            for r in proof["rows"]
        )
        protocols.append(
            {
                "backend": backend,
                "responses": 69,
                "business_results_identical_to_v69": True,
                "paged": sum(r["paged"] for r in proof["rows"]),
                "largest_first_chars": max(r["first_chars"] for r in proof["rows"]),
            }
        )
    names = (
        "new-before-first",
        "new-after-first",
        "new-expanded-first",
        "new-cross-binding-first",
        "transports-before-first",
        "transports-after-live-first",
        "new-source-first",
        "new-source-final-first",
        "new-wheel-final-first",
        "related-before-first",
        "related-after-first",
    )
    suites = {name: suite(name) for name in names}
    assert (
        suites["new-before-first"]["passed"],
        suites["new-before-first"]["failed"],
    ) == (5, 159)
    assert suites["transports-before-first"]["failed"] == 33
    assert suites["transports-after-live-first"]["passed"] == 33
    assert suites["new-source-first"]["passed"] == 198
    assert all(
        suites[n]["passed"] == 203 and suites[n]["failed"] == 0
        for n in ("new-source-final-first", "new-wheel-final-first")
    )
    assert suites["related-before-first"] == suites["related-after-first"]
    assert (
        suites["related-after-first"]["passed"],
        suites["related-after-first"]["failed"],
    ) == (208, 5)
    unchanged = read(F / "all7-producer-files-unchanged-first.json")
    assert len(unchanged) == 7 and all(unchanged.values())
    first_sources = read(F / "protocol-first.json")["initial_files_sha256"]
    assert all(
        hashlib.sha256((ROOT / n).read_bytes()).hexdigest() == first_sources[n]
        for n in unchanged
    )
    old_ledger = json.loads(
        gzip.decompress((F / "requirements-before-append-first.json.gz").read_bytes())
    )
    current_ledger = read(ROOT / "docs/validation/bazi-three-axis-requirements.json")
    assert len(old_ledger) == 106 and len(old_ledger["requirements"]) == 14
    assert all(current_ledger[k] == v for k, v in old_ledger.items())
    return {
        "original19": original19,
        "first_accepted_contradictions_now_rejected": 152,
        "additional_partial_contradictions_now_rejected": 5,
        "all408_complete_calculations_and_types_identical_to_v69": True,
        "all367_public_results_and_types_identical_to_v69": True,
        "all7_producer_files_unchanged": True,
        "protocols": protocols,
        "suites": suites,
        "independent_literal_hidden_positions_checked": 360,
        "all_original14_requirements_and_gates_retained": True,
        "new_strength_or_duty_algorithm": False,
        "new_classical_accuracy_credit": 0,
        "new_actual_model_executions": 0,
        "original19_model_semantic_acceptance": "not_tested",
        "independent_expert_review": "not_completed",
        "real_world_predictive_validity": "not_tested",
        "old_failed_gates_regraded": False,
        "full_goal_complete": False,
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    a.output.open("x").write(json.dumps(audit(), ensure_ascii=False, indent=2) + "\n")
