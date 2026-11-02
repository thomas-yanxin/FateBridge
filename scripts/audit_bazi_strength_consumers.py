"""Verify fixed consumer-arithmetic artifacts without regrading classical failures."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import struct
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from fatebridge.validation.case_capture import inspect_cases

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/bazi_strength_consumers_v1"
FILES = ROOT / "docs/validation/bazi-strength-consumers-files-v1"


def read(path: Path) -> Any:
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == ".gz" else raw)


def capture(name: str) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "capture.jsonl"
        path.write_bytes(gzip.decompress((FILES / (name + ".jsonl.gz")).read_bytes()))
        return inspect_cases(path)


def suite(name: str) -> dict[str, int]:
    value = ET.parse(FILES / (name + ".xml")).getroot().find("testsuite")
    assert value is not None
    return {k: int(value.attrib[k]) for k in ("tests", "failures", "errors", "skipped")}


def audit() -> dict[str, Any]:
    for name in (
        "protocol.json",
        "implementation-plan-first.json",
        "inputs-first.json",
        "public-inputs-first.json",
        "climate-source-first.json",
        "downstream-causality-plan-first.json",
    ):
        path = FIXTURE / name
        if (
            hashlib.sha256(path.read_bytes()).hexdigest()
            != Path(str(path) + ".sha256").read_text().strip()
        ):
            raise ValueError("Frozen protocol/input changed: " + name)
    full = read(FILES / "full-completion-first.json")
    before = struct.Struct(">dddBB")
    after = struct.Struct(">dddBBBB")
    old = gzip.decompress(
        (
            ROOT
            / "docs/validation/bazi-strength-threshold-files-v1/final-all-rows-first.bin.gz"
        ).read_bytes()
    )
    new = gzip.decompress((FILES / "full-all-rows-first.bin.gz").read_bytes())
    if len(old) != before.size * 518400 or len(new) != after.size * 518400:
        raise ValueError("A fixed numerical row was omitted")
    for b, a in zip(before.iter_unpack(old), after.iter_unpack(new), strict=True):
        if b != a[:5]:
            raise ValueError("Old numeric energy, share or grade changed")
    if (
        full["records"] != 518400
        or full["special_changes"] != [171347, 308817, 431014]
        or len(full["body_changes"]) != 187
    ):
        raise ValueError("Arithmetic population or correction set changed")
    if (
        not full["all_exact_energies_and_predicates_match_independent_reference"]
        or not full["all_actual_force_builder_comparisons_match"]
    ):
        raise ValueError("Independent conditional arithmetic verification incomplete")
    baseline, production, wheel = (
        capture("corpus-" + n + "-first") for n in ("baseline", "candidate", "wheel")
    )
    if (
        not baseline["inputs_sha256"]
        == production["inputs_sha256"]
        == wheel["inputs_sha256"]
        or len(production["results"]) != 375
    ):
        raise ValueError("A registered/research case was omitted or substituted")
    if production["results"] != wheel["results"]:
        raise ValueError("Source/wheel corpus results differ")
    inputs = read(FIXTURE / "inputs-first.json")["cases"]
    if (
        len(inputs[:367]) != 367
        or sum(c["expected_strength"] is None for c in inputs) != 252
    ):
        raise ValueError("Unknown source labels were relabelled")
    nineteen = read(FIXTURE / "nineteen-conditions-review-first.json")["rows"]
    for row, (case, result) in zip(
        nineteen,
        (
            (c, r)
            for c, r in zip(inputs, production["results"], strict=True)
            if c["is_original_nineteen"]
        ),
        strict=True,
    ):
        if (
            row["id"] != case["id"]
            or row["expected"] != case["expected_strength"]
            or row["actual"] != result["strength"]["strength_level"]
        ):
            raise ValueError("Original nineteen inputs or labels changed")
        evidence = result["evidence_chain"]
        if (
            evidence["month_command"]["intra_month_duty"]["selected_stem"] is not None
            or evidence["classical_passage"]["summary"]["effective_passage"]
            != "not_adjudicated"
        ):
            raise ValueError("Unknown duty/passage was promoted")
    if len(nineteen) != 19 or sum(not r["matches"] for r in nineteen) != 17:
        raise ValueError("Original disagreements were regraded")
    pub_before, pub_after, pub_wheel = (
        capture("public-" + n + "-first") for n in ("baseline", "candidate", "wheel")
    )
    if (
        not pub_before["inputs_sha256"]
        == pub_after["inputs_sha256"]
        == pub_wheel["inputs_sha256"]
        or len(pub_after["results"]) != 55
        or pub_after["results"] != pub_wheel["results"]
    ):
        raise ValueError("Public source/wheel equivalence incomplete")
    causal = read(FIXTURE / "downstream-causality-verification-first.json")
    if (
        causal["records"] != 55
        or causal[
            "old_business_values_and_types_recovered_except_declared_limitation_text"
        ]
        is not True
    ):
        raise ValueError("Downstream consumer causality control incomplete")
    for side in ("source", "wheel"):
        proof = read(FILES / (side + "-stdio-first-readback-proof.json"))
        if proof["cases"] != 55 or not all(
            r["same_run_delivery_restored"] for r in proof["rows"]
        ):
            raise ValueError("Actual stdio same-run readback incomplete")
    expected = {
        "new-tests-first": (263, 5),
        "new-tests-corrected-first": (363, 0),
        "wheel-tests-first": (363, 0),
        "final-typed-wheel-checks-first": (263, 0),
        "related-tests-first": (23, 11),
    }
    for name, (total, failed) in expected.items():
        actual = suite(name)
        if actual != {"tests": total, "failures": failed, "errors": 0, "skipped": 0}:
            raise ValueError("First test outcome changed: " + name)
    old_model = read(FILES / "old-semantic-exact-replay-first.json.gz")
    if (
        old_model["new_actual_model_executions_this_round"] != 0
        or old_model["replay"]["original_mechanical_score"] != "11/11"
        or old_model["replay"]["all_actual_model_calls_respect8192"] is not False
    ):
        raise ValueError("Historical model failure or scope was relabelled")
    return {
        "synthetic_rows": 518400,
        "special_review_corrections": 3,
        "body_seal_engineering_comparison_corrections": 187,
        "old_numeric_energies_shares_and_grades_unchanged": True,
        "registered_v9_records": 367,
        "separate_complete_climate_research_records": 8,
        "combined_research_records": 375,
        "unknown_labels_retained": 252,
        "original_nineteen_unresolved": 17,
        "source_wheel_full_corpus_and55public_results_equal": True,
        "actual_stdio_scenarios_each_side": 55,
        "stdio_paged_readbacks_each_side": 55,
        "first_new_test_failures_retained": 5,
        "old_related_failed_test_identities_retained": 11,
        "new_actual_model_executions": 0,
        "old_model11_passes_and_budget_failures_both_retained": True,
        "new_classical_accuracy_credit": 0,
        "independent_expert_review": "not_completed",
        "new_fields_actual_model_acceptance": "not_tested",
        "original8192_no_paging_gate_passed": False,
        "real_world_predictive_validity": "not_tested",
        "authority_certified": False,
        "full_goal_complete": False,
        "overall_score": None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Preserve first outputs; choose another path")
    result = audit()
    args.output.write_bytes(
        gzip.compress(
            json.dumps(result, ensure_ascii=False, indent=2).encode(), mtime=0
        )
    )
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
