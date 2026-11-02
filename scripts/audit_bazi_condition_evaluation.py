"""Verify frozen original19 evaluation readiness, without running a model."""

from __future__ import annotations

import argparse
import ast
import gzip
import hashlib
import json
import tarfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/bazi_condition_evaluation_v1"
FILES = ROOT / "docs/validation/bazi-condition-evaluation-files-v1"


def read(path: Path) -> Any:
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == ".gz" else raw)


def same_json(a: Any, b: Any) -> bool:
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(same_json(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(
            same_json(x, y) for x, y in zip(a, b, strict=True)
        )
    return bool(a == b)


def verify_receipt(path: Path, expected_sha256: str | None = None) -> int:
    expected = expected_sha256
    if expected is None:
        expected = Path(str(path) + ".sha256").read_text().strip()
    assert hashlib.sha256(path.read_bytes()).hexdigest() == expected
    receipt = read(path)
    for relative, digest in receipt["files_sha256"].items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == digest
    return len(receipt["files_sha256"])


def suite(name: str, total: int) -> dict[str, int]:
    node = ET.parse(FILES / (name + ".xml")).getroot().find("testsuite")
    assert node is not None
    counts = {
        key: int(node.attrib[key]) for key in ["tests", "failures", "errors", "skipped"]
    }
    assert counts == {"tests": total, "failures": 0, "errors": 0, "skipped": 0}
    return counts


def audit() -> dict[str, Any]:
    for name in [
        "protocol.json",
        "primary-page-selection-first.json",
        "cases-neutral-first.json",
        "requested-execution-neutral-first.json",
    ]:
        path = FIXTURE / name
        assert (
            hashlib.sha256(path.read_bytes()).hexdigest()
            == Path(str(path) + ".sha256").read_text().strip()
        )
    protocol = read(FIXTURE / "protocol.json")
    for relative, digest in protocol["initial_files_sha256"].items():
        if relative not in {"scripts/evaluate_agent.py", "scripts/evaluate_agent.pyi"}:
            assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == digest
    previous = read(FIXTURE / "prior1838-bindings-reverified-first.json")
    assert (
        sum(verify_receipt(ROOT / r["receipt"], r["sha256"]) for r in previous) == 1838
    )
    for row in previous:
        assert (
            hashlib.sha256((ROOT / row["receipt"]).read_bytes()).hexdigest()
            == row["sha256"]
        )
    cases_file = FILES / "neutral-prepared-case-dataset.json"
    cases = read(cases_file)["cases"]
    assert len(cases) == len({c["id"] for c in cases}) == 19
    assert (
        cases_file.read_bytes() == (FIXTURE / "cases-neutral-first.json").read_bytes()
    )
    manifest_path = FILES / "neutral-prepared-source-manifest.json"
    manifest = read(manifest_path)
    request = read(FIXTURE / "requested-execution-neutral-first.json")
    assert request["cases"] == 19 and request["one_first_execution_per_case"]
    assert (
        request["dataset_sha256"] == hashlib.sha256(cases_file.read_bytes()).hexdigest()
    )
    assert (
        request["source_manifest_sha256"]
        == hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    )
    assert request["command"][:6] == [
        "uv",
        "run",
        "--locked",
        "--extra",
        "dev",
        "python",
    ]
    assert request["command"][6].endswith("/source/scripts/evaluate_agent.py")
    assert "--model" not in request["command"] and "--case" not in request["command"]
    identity = read(FIXTURE / "private-neutral-identity-map-first.json")
    workspace_proof = read(FIXTURE / "all19-neutral-workspace-preflight-first.json")
    assert (
        workspace_proof["cases"] == 19 and workspace_proof["extra_source_files"] == 72
    )
    images, documents = set(), set()
    with tarfile.open(FILES / "prepared-source-neutral-first.tar.gz") as archive:
        assert set(archive.getnames()) == set(manifest)

        def value(relative: str) -> bytes:
            handle = archive.extractfile(relative)
            assert handle is not None
            raw = handle.read()
            assert hashlib.sha256(raw).hexdigest() == manifest[relative]
            return raw

        for member in archive:
            value(member.name)
        tree = ast.parse(value("scripts/evaluate_agent.py").decode())
        functions = {
            n.name: hashlib.sha256(
                ast.dump(n, include_attributes=False).encode()
            ).hexdigest()
            for n in tree.body
            if isinstance(n, ast.FunctionDef)
            and n.name in protocol["legacy_function_asts_sha256"]
        }
        assert functions == protocol["legacy_function_asts_sha256"]
        previous_workbook = read(
            ROOT
            / "tests/fixtures/bazi_hidden_rank_review_v1/all19-supplemental-explanation-workbook-first.json"
        )
        originals = {r["id"]: r for r in previous_workbook["cases"]}
        for case, binding, staged in zip(
            cases, identity, workspace_proof["rows"], strict=True
        ):
            assert case["source_case_id"] == binding["private_source_case_id"]
            assert case["id"] == binding["model_case_id"] == staged["id"]
            assert case["evidence_only_workspace"] is True
            assert case["source_case_id"] not in case["prompt"]
            expected = {
                "AGENTS.md",
                *[e["workspace_path"] for e in case["evidence_files"]],
            }
            assert set(staged["workspace_files_sha256"]) == expected
            for evidence in case["evidence_files"]:
                data = value(evidence["source_path"])
                assert hashlib.sha256(data).hexdigest() == evidence["sha256"]
                assert (
                    staged["workspace_files_sha256"][evidence["workspace_path"]]
                    == evidence["sha256"]
                )
                if evidence["source_path"].endswith(".png"):
                    images.add(evidence["source_path"])
                else:
                    documents.add(evidence["source_path"])
            model_input = json.loads(value(case["evidence_files"][0]["source_path"]))
            assert model_input["case_id"] == binding["public_case_id"]
            assert not any(
                s in model_input["case_id"] for s in ["HEAVY", "LIGHT", "MAO", "-MA-"]
            )
            assert "source_record" not in model_input
            assert "expected_strength" not in model_input["source_statement"]
            full = originals[case["source_case_id"]]
            raw_original = (ROOT / full["input_file"]).read_bytes()
            assert hashlib.sha256(raw_original).hexdigest() == full["input_sha256"]
            original = json.loads(gzip.decompress(raw_original))
            for key in [
                "actual_frozen_strength",
                "force_components",
                "month_command",
                "classical_passage",
                "classical_passage_relations",
            ]:
                assert same_json(model_input[key], original[key])
            assert case["manual_review"] == full["manual_review_criteria"]
    assert len(images) == 51 and len(documents) == 21
    review_path = FILES / "reviewer-only-all19-source-conditions-first.json"
    assert (
        hashlib.sha256(review_path.read_bytes()).hexdigest()
        == Path(str(review_path) + ".sha256").read_text().strip()
    )
    review = read(review_path)
    assert len(review["rows"]) == 19
    assert review["original_unresolved_cases_retained"] == 17
    for row, binding in zip(review["rows"], identity, strict=True):
        assert row["private_source_case_id"] == binding["private_source_case_id"]
        assert row["neutral_case_id"] == binding["model_case_id"]
        assert row["intra_month_duty_status"] == "not_adjudicated"
        assert row["intra_month_selected_stem"] is None
        assert row["effective_passage_states"] == ["not_adjudicated"]
        assert row["source_accuracy_credit"] == 0
        assert row["manual_original_labels_overwritten"] is False
        assert row["actual_model_semantic_acceptance"] == "pending"
        for anchor in row["source_anchor_images"]:
            assert (
                hashlib.sha256((ROOT / anchor["path"]).read_bytes()).hexdigest()
                == anchor["sha256"]
            )
    assert sum(r["path_occurrences_in_supplied_views"] for r in review["rows"]) == 1797
    preparation = read(FILES / "neutral-prepared-preparation.json")
    assert (
        preparation["selected_case_count"] == 19
        and preparation["model_invocations"] == 0
    )
    assert all(
        r["reference_status"] == "frozen_evidence_files_verified"
        for r in preparation["references"]
    )
    backend = read(FILES / "neutral-backend-reference-proof.json")
    assert (
        backend["actual_stdio_knowledge_call_passed"]
        and backend["same_run_readback_verified"]
    )
    assert (
        backend["first_structured_reply_chars"]
        <= backend["fixed_response_char_limit"]
        == 8192
    )
    assert backend["new_models"] == 0
    wheel = read(FIXTURE / "wheel-package-proof-first.json")
    assert (
        hashlib.sha256((ROOT / wheel["wheel"]).read_bytes()).hexdigest()
        == wheel["wheel_sha256"]
    )
    assert (
        wheel["package_files_all_equal_frozen_source"]
        == len(wheel["files_sha256"])
        == 1272
    )
    assert all(
        manifest["src/" + name] == digest
        for name, digest in wheel["files_sha256"].items()
    )
    old_ledger = read(
        FIXTURE / "requirements-before-condition-evaluation-first.json.gz"
    )
    ledger = read(ROOT / "docs/validation/bazi-three-axis-requirements.json")
    assert len(old_ledger) == 101 and len(ledger) == 102
    assert all(same_json(ledger[k], v) for k, v in old_ledger.items())
    return {
        "original_cases_prepared": 19,
        "distinct_original_page_images": 51,
        "explicit_json_documents": 21,
        "frozen_runtime_files": len(manifest),
        "all19_workspace_inventory_and_input_hashes_verified": True,
        "neutral_identifiers_do_not_expose_original_label_names": True,
        "all_calculation_facts_original_labels_and_criteria_retained": True,
        "legacy7_scorer_prompt_function_asts_unchanged": True,
        "first_tests": suite("tests-first", 71),
        "evidence_mode_tests": suite("tests-evidence-mode-first", 72),
        "wheel_tests": suite("wheel-tests-first", 72),
        "wheel_package_files_equal_frozen_source": 1272,
        "previous_receipt_bindings_reverified": 1838,
        "all_previous101_requirement_objects_and_statuses_unchanged": True,
        "strict_runner_type_errors": read(
            FIXTURE / "current-mode-type-retention-first.json"
        ),
        "actual_separate_backend_stdio_check": backend,
        "model_calls_during_preparation": 0,
        "actual_model_results": "not_evaluated_by_this_readiness_audit",
        "actual_model_reading_or_semantic_acceptance_proven": False,
        "original_nineteen_unresolved": 17,
        "primary_source_condition_reviews_by_same_developer": 19,
        "source_reviews_are_independent_expert_adjudication": False,
        "source_review_labels_or_frozen_model_inputs_changed": False,
        "new_classical_accuracy_credit": 0,
        "real_world_predictive_validity": "not_tested",
        "full_goal_complete": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    result = audit()
    if args.receipt is not None:
        result["sealed_current_receipt_bindings_verified"] = verify_receipt(
            args.receipt
        )
    raw = json.dumps(result, ensure_ascii=False, indent=2).encode() + b"\n"
    with args.output.open("xb") as handle:
        handle.write(
            gzip.compress(raw, mtime=0) if args.output.suffix == ".gz" else raw
        )
    print(json.dumps(result, ensure_ascii=False))
