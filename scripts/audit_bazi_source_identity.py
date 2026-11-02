"""Replay documentary diffs and actual protocol evidence without model calls."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import tarfile
import xml.etree.ElementTree as ET
from copy import deepcopy
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/bazi_source_identity_v1"
FILES = ROOT / "docs/validation/bazi-source-identity-files-v1"


def read(path: Path) -> Any:
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == ".gz" else raw)


def canonical(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()


def suite(name: str, total: int, failures: int) -> None:
    value = ET.parse(FILES / (name + ".xml")).getroot().find("testsuite")
    assert value is not None
    assert {
        k: int(value.attrib[k]) for k in ["tests", "failures", "errors", "skipped"]
    } == {"tests": total, "failures": failures, "errors": 0, "skipped": 0}


def verify_receipt(path: Path, digest: str) -> int:
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
    data = read(path)
    for name, expected in data["files_sha256"].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected, name
    return len(data["files_sha256"])


def protocols(name: str) -> dict[str, Any]:
    with tarfile.open(FILES / (name + "-raw-first.tar.gz")) as archive:

        def value(relative: str) -> Any:
            handle = archive.extractfile(name + "/" + relative)
            assert handle is not None
            raw = handle.read()
            return json.loads(gzip.decompress(raw) if relative.endswith(".gz") else raw)

        proof = value("proof.json")
        assert proof["responses"] == len(proof["rows"]) == 24
        businesses: dict[str, list[Any]] = {}
        for row in proof["rows"]:
            prefix = row["case"] + "/" + row["transport"]
            first = value(prefix + "-original-response.json")
            assert (
                len(json.dumps(first, ensure_ascii=False, separators=(",", ":")))
                == row["first_chars"]
                <= 8192
            )
            ref = first.get("result_delivery")
            if not ref:
                businesses.setdefault(row["case"], []).append(
                    {k: v for k, v in first.items() if k != "run_metadata"}
                )
                continue
            if row["transport"] == "cli":
                payload = value(row["case"] + "/cli-verified-full-payload.json.gz")
                offset, fragments = 0, []
                while offset is not None:
                    page = value(
                        row["case"] + "/cli-verified-pages/" + str(offset) + ".json"
                    )
                    assert page["offset"] == offset
                    assert page["verification"]["payload_sha256"] == ref["sha256"]
                    assert (
                        page["verification"]["run_id"]
                        == first["run_metadata"]["run_id"]
                    )
                    fragments.append(page["text"])
                    offset = page["next_offset"]
                assert canonical(json.loads("".join(fragments))) == canonical(payload)
            else:
                manifest = value(prefix + "-manifest.json")
                assert (
                    manifest["result_id"] == ref["result_id"]
                    and manifest["sha256"] == ref["sha256"]
                )
                payload = value(prefix + "-same-run-file.json.gz")[
                    manifest["file_payload_path"]
                ]
                assert (
                    manifest["run_metadata"]["run_id"]
                    == first["run_metadata"]["run_id"]
                )
            encoded = json.dumps(
                payload, ensure_ascii=False, separators=(",", ":")
            ).encode()
            assert hashlib.sha256(encoded).hexdigest() == ref["sha256"]
            assert payload["run_metadata"]["run_id"] == first["run_metadata"]["run_id"]
            businesses.setdefault(row["case"], []).append(
                {k: v for k, v in payload.items() if k != "run_metadata"}
            )
        assert len(businesses) == 8
        assert all(
            len(rows) == 3
            and canonical(rows[0]) == canonical(rows[1]) == canonical(rows[2])
            for rows in businesses.values()
        )
        return {
            "responses": 24,
            "largest_first_chars": max(r["first_chars"] for r in proof["rows"]),
            "paged": sum(r["paged"] for r in proof["rows"]),
            "same_run_hashes_verified": True,
            "business_sha256_by_case": {
                case: hashlib.sha256(canonical(rows[0])).hexdigest()
                for case, rows in businesses.items()
            },
        }


def audit() -> dict[str, Any]:
    plan_path = FIXTURE / "patch-plan-first.json"
    assert (
        hashlib.sha256(plan_path.read_bytes()).hexdigest()
        == Path(str(plan_path) + ".sha256").read_text().strip()
    )
    plan = read(plan_path)
    patches = {p["reference_id"]: p for p in plan["patches"]}
    index_path = ROOT / "src/fatebridge/data/reference/bazi-source-annotations-v8.json"
    index_sha = hashlib.sha256(index_path.read_bytes()).hexdigest()
    assert len(patches) == 58
    manifests = read(FIXTURE / "qualified-source-complete-tests-manifest-first.json")
    members = {}
    for filename in [
        "qualified-source-first.tar.gz",
        "test-helper-complete-overlay-first.tar.gz",
    ]:
        with tarfile.open(FILES / filename) as archive:
            for member in archive:
                handle = archive.extractfile(member)
                assert handle is not None
                raw = handle.read()
                assert hashlib.sha256(raw).hexdigest() == manifests[member.name]
                members[member.name] = hashlib.sha256(raw).hexdigest()
    assert members == manifests and len(members) == 1741
    wheel = read(FIXTURE / "wheel-proof-first.json")
    assert (
        hashlib.sha256((ROOT / wheel["wheel"]).read_bytes()).hexdigest()
        == wheel["wheel_sha256"]
    )
    assert wheel["all_package_files_equal_frozen_source"] == 1278
    assert all(manifests["src/" + n] == h for n, h in wheel["files_sha256"].items())
    numerical = read(FIXTURE / "numerical-seven-files-unchanged-first.json")[
        "source_and_live_files_sha256"
    ]
    assert len(numerical) == 7
    assert all(
        manifests[n] == hashlib.sha256((ROOT / n).read_bytes()).hexdigest() == h
        for n, h in numerical.items()
    )
    publisher_note = (
        "出版者标注已按同一书影书名页更正，旧登记另存，命式与强弱标签保持。"
    )
    name_note = "原页所印姓名错配另已更正，旧编号保留；未认定历史人物身份。"
    names = [
        "public-all367-before-first.jsonl.gz",
        "public-all367-source-first.jsonl.gz",
        "public-all367-wheel-first.jsonl.gz",
    ]
    records = [
        [
            json.loads(s)
            for s in gzip.decompress((FILES / n).read_bytes()).decode().splitlines()
        ]
        for n in names
    ]
    assert all(len(group) == 367 for group in records)
    for before, source, installed in zip(*records, strict=True):
        assert canonical(source) == canonical(installed)
        assert before["reference_id"] == source["reference_id"]
        expected = deepcopy(before["result"])
        changed = named = False
        rows = expected["source_comparison"]["records"]
        for i, row in enumerate(rows):
            patch = patches.get(row["reference_id"])
            if patch is None:
                continue
            dynamic = {
                k: row[k]
                for k in ["comparison", "bounded_strength_constraints"]
                if k in row
            }
            assert canonical(
                {k: v for k, v in row.items() if k not in dynamic}
            ) == canonical(patch["before"])
            rows[i] = {**deepcopy(patch["after"]), **dynamic}
            changed = True
            named |= "name_as_printed" in patch["after"]
        expected["source_comparison"]["reference_index"].update(
            index_sha256=index_sha,
            data_revision="source_annotations_v8_witness_identity",
            source_identity_plan_sha256=hashlib.sha256(
                plan_path.read_bytes()
            ).hexdigest(),
            total_registered_source_identity_revisions=58,
            total_registered_printed_name_corrections=2,
        )
        expected["summary"] += (publisher_note if changed else "") + (
            name_note if named else ""
        )
        assert canonical(expected) == canonical(source["result"])
    for name, total, failed in [
        ("baseline-first", 92, 6),
        ("current-first", 92, 14),
        ("new-tests-first", 20, 2),
        ("corrected-retry-first", 112, 6),
        ("new-transport-first", 19, 5),
        ("qualified-source-complete-tests-first", 39, 0),
        ("wheel-complete-tests-first", 39, 0),
    ]:
        suite(name, total, failed)
    parents = read(FIXTURE / "prior2063-bindings-reverified-first.json")
    assert (
        sum(verify_receipt(ROOT / p["receipt"], p["sha256"]) for p in parents) == 2063
    )
    old = read(FIXTURE / "requirements-before-identity-first.json.gz")
    current = read(ROOT / "docs/validation/bazi-three-axis-requirements.json")
    assert len(old) == 102 and all(
        canonical(current[k]) == canonical(v) for k, v in old.items()
    )
    source_protocols = protocols("source-protocols-verified-reader-first")
    wheel_protocols = protocols("wheel-protocols-first")
    assert (
        source_protocols["business_sha256_by_case"]
        == wheel_protocols["business_sha256_by_case"]
    )
    return {
        "publisher_metadata_corrections": 58,
        "printed_name_corrections": 2,
        "all367_complete_public_results_only_declared_documentary_diffs": True,
        "source_and_wheel_business_values_and_types_equal": True,
        "all7_numeric_modules_unchanged": True,
        "source_and_wheel_each_new_tests_passed": 39,
        "baseline_six_failures_retained": True,
        "first_new_type_failures_retained": 2,
        "first_public_type_failures_retained": 5,
        "first_reader_and_snapshot_failures_retained": True,
        "actual_source_protocols": source_protocols,
        "actual_wheel_protocols": wheel_protocols,
        "previous_bindings_verified": 2063,
        "all_previous102_requirement_objects_and_statuses_unchanged": True,
        "original_nineteen_unresolved": 17,
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
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    result = audit()
    if args.receipt:
        result["current_receipt_bindings_verified"] = verify_receipt(
            args.receipt, Path(str(args.receipt) + ".sha256").read_text().strip()
        )
    raw = json.dumps(result, ensure_ascii=False, indent=2).encode() + b"\n"
    args.output.open("xb").write(
        gzip.compress(raw, mtime=0) if args.output.suffix == ".gz" else raw
    )
    print(json.dumps(result, ensure_ascii=False))
