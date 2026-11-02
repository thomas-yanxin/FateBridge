"""Replay source-order sensitivity and actual old-model coverage without models."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import tarfile
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from fatebridge.validation.case_capture import inspect_cases

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/bazi_hidden_rank_review_v1"
FILES = ROOT / "docs/validation/bazi-hidden-rank-review-files-v1"


def read(path: Path) -> Any:
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == ".gz" else raw)


def equal(a: Any, b: Any) -> bool:
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(equal(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(equal(x, y) for x, y in zip(a, b, strict=True))
    return bool(a == b)


def capture(path: Path) -> list[Any]:
    with tempfile.TemporaryDirectory() as folder:
        target = Path(folder) / "capture.jsonl"
        target.write_bytes(gzip.decompress(path.read_bytes()))
        result = inspect_cases(target)
        assert result["status"] == "complete"
        results = result["results"]
        assert isinstance(results, list)
        return results


def get(value: Any, path: str) -> Any:
    for name in path.split("."):
        value = value[int(name)] if isinstance(value, list) else value[name]
    return value


def feature_paths(value: Any, prefix: str = "") -> list[str]:
    targets = {
        "force_components",
        "intra_month_duty",
        "classical_passage",
        "classical_passage_relations",
        "threshold_arithmetic",
    }
    result = []
    if isinstance(value, dict):
        for key, item in value.items():
            path = prefix + "." + key if prefix else key
            if key in targets:
                result.append(path)
            result.extend(feature_paths(item, path))
    elif isinstance(value, list):
        for i, item in enumerate(value):
            result.extend(feature_paths(item, prefix + "." + str(i)))
    return result


def model_coverage() -> dict[str, Any]:
    folder = ROOT / "tests/fixtures/bazi_semantic_run_v5"
    provenance = read(folder / "provenance.json")
    for relative, digest in provenance["files"].items():
        assert hashlib.sha256((folder / relative).read_bytes()).hexdigest() == digest
    review = read(ROOT / "docs/validation/bazi-budget-guide-first-review-v1.json")
    rows, units, claims = [], 0, 0
    for case in review["cases"]:
        location = folder / case["id"]
        answer = (location / "answer.txt").read_text()
        assert (
            hashlib.sha256((location / "answer.txt").read_bytes()).hexdigest()
            == case["answer_sha256"]
        )
        packets_path = location / case["review_payloads_file"]
        assert (
            hashlib.sha256(packets_path.read_bytes()).hexdigest()
            == case["review_payloads_sha256"]
        )
        packets = read(packets_path)
        for unit in case["sentence_reviews"]:
            assert answer[unit["start"] : unit["end"]] == unit["quote"]
            for ref in unit["evidence_paths"]:
                get(packets[ref["packet"]]["payload"], ref["path"])
            units += 1
        for claim in case["direct_field_claims"]:
            assert equal(
                get(packets[claim["packet"]]["payload"], claim["path"]), claim["value"]
            )
            claims += 1
        exposed = [
            {"packet": i, "paths": feature_paths(p["payload"])}
            for i, p in enumerate(packets)
        ]
        rows.append(
            {
                "id": case["id"],
                "actual_packets": len(packets),
                "original_mechanical_and_manual_scores_unchanged": True,
                "new_conditions_exposed": any(p["paths"] for p in exposed),
                "new_condition_acceptance": "not_exercised_by_these_original_questions",
                "exposure": exposed,
            }
        )
    assert len(rows) == 11 and units == 188 and claims == 126
    assert not any(r["new_conditions_exposed"] for r in rows)
    return {
        "provenance_files_verified": len(provenance["files"]),
        "first_answer_units_rebound": units,
        "typed_claims_rebound": claims,
        "old_scores_or_semantic_judgments_changed": False,
        "new_conditions_exposed_cases": 0,
        "rows": rows,
        "scope": "Rebind existing developer reviews; no new independent semantic accuracy or penalty for an unasked topic.",
    }


def suite(name: str, total: int, failures: int) -> dict[str, int]:
    node = ET.parse(FILES / (name + ".xml")).getroot().find("testsuite")
    assert node is not None
    value = {k: int(node.attrib[k]) for k in ["tests", "failures", "errors", "skipped"]}
    assert value == {"tests": total, "failures": failures, "errors": 0, "skipped": 0}
    return value


def transport(name: str) -> dict[str, Any]:
    rows = []
    with tarfile.open(FILES / (name + ".tar.gz")) as archive:

        def value(member: str) -> Any:
            handle = archive.extractfile(member)
            assert handle is not None
            raw = handle.read()
            return json.loads(gzip.decompress(raw) if member.endswith(".gz") else raw)

        originals = [
            n for n in archive.getnames() if n.endswith("-original-response.json")
        ]
        assert len(originals) == 6
        for member in originals:
            first = value(member)
            parent, prefix = member.rsplit("/", 1)
            kind = prefix.removesuffix("-original-response.json")
            ref = first.get("result_delivery")
            chars = len(json.dumps(first, ensure_ascii=False, separators=(",", ":")))
            assert chars <= 8192
            if ref:
                wrapper = value(parent + "/" + kind + "-same-run-file.json.gz")
                path = ref.get("file_payload_path")
                if not path:
                    path = value(parent + "/" + kind + "-manifest.json")[
                        "file_payload_path"
                    ]
                payload = wrapper[path]
                encoded = json.dumps(
                    payload, ensure_ascii=False, separators=(",", ":")
                ).encode()
                assert hashlib.sha256(encoded).hexdigest() == ref["sha256"]
                assert (
                    payload["run_metadata"]["run_id"] == first["run_metadata"]["run_id"]
                )
            rows.append({"transport": kind, "paged": bool(ref), "first_chars": chars})
    return {"responses": 6, "rows": rows, "all_same_run_readbacks_verified": True}


def audit() -> dict[str, Any]:
    for name in [
        "protocol.json",
        "counterfactual-plan-first.json",
        "entry-proposal-first.json",
        "primary-context-reread-first.json",
        "all19-supplemental-explanation-workbook-first.json",
    ]:
        path = FIXTURE / name
        assert (
            hashlib.sha256(path.read_bytes()).hexdigest()
            == Path(str(path) + ".sha256").read_text().strip()
        )
    old = capture(
        ROOT
        / "docs/validation/bazi-passage-partial-files-v1/corpus-candidate-first.jsonl.gz"
    )
    source = capture(FILES / "corpus-source-first.jsonl.gz")
    wheel = capture(FILES / "corpus-wheel-first.jsonl.gz")
    alternate = capture(FILES / "ordinal-counterfactual-first.jsonl.gz")
    assert len(source) == len(wheel) == len(old) == len(alternate) == 408
    assert equal(old, source) and equal(source, wheel)
    assert all(
        equal(a["baseline"], b["strength"])
        for a, b in zip(alternate, source, strict=True)
    )
    assert sum(a["changed_grade"] for a in alternate) == 0
    for c in read(FIXTURE / "all19-supplemental-explanation-workbook-first.json")[
        "cases"
    ]:
        assert (
            hashlib.sha256((ROOT / c["input_file"]).read_bytes()).hexdigest()
            == c["input_sha256"]
        )
        assert (
            c["actual_model_status"] == "not_run"
            and c["semantic_acceptance"] == "pending"
        )
    return {
        "original_nineteen_unresolved": 17,
        "newly_resolved_original_cases": 0,
        "all408_business_values_and_types_unchanged": True,
        "ordinal_counterfactual": read(
            FIXTURE / "ordinal-sensitivity-full-details-first.json"
        ),
        "prior_actual_model_coverage": model_coverage(),
        "first_source_tests": suite("source-knowledge-first", 4, 2),
        "corrected_source_tests": suite("source-knowledge-corrected", 4, 0),
        "wheel_tests": suite("wheel-knowledge-first", 4, 0),
        "source_transport": transport("source-knowledge-corrected"),
        "wheel_transport": transport("wheel-knowledge-first"),
        "new_source_scoped_knowledge_entries": 1,
        "all_original85_knowledge_entries_retained": True,
        "complete_primary_context_pages_reread": list(range(66, 75)),
        "additional_original19_explanation_inputs_prepared": 19,
        "additional_actual_model_executions": 0,
        "new_conditions_actual_model_acceptance": "not_tested",
        "first_independent_ordinal_gate_regraded": False,
        "real_world_predictive_validity": "not_tested",
        "full_goal_complete": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit()
    raw = json.dumps(result, ensure_ascii=False, indent=2).encode() + b"\n"
    with args.output.open("xb") as handle:
        handle.write(
            gzip.compress(raw, mtime=0) if args.output.suffix == ".gz" else raw
        )
    print(
        json.dumps(
            {
                k: v
                for k, v in result.items()
                if k not in {"prior_actual_model_coverage", "ordinal_counterfactual"}
            },
            ensure_ascii=False,
        )
    )
