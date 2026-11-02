"""Replay complete source-condition joins without model calls or regrading."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import tarfile
import xml.etree.ElementTree as ET
import zipfile
from contextlib import ExitStack
from copy import deepcopy
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/bazi_source_conditions_public_v1"
FILES = ROOT / "docs/validation/bazi-source-conditions-public-files-v1"


def read(path: Path) -> Any:
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == ".gz" else raw)


def canonical(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()


def suite(name: str, total: int, failed: int, deselected: int = 0) -> None:
    value = ET.parse(FILES / (name + ".xml")).getroot().find("testsuite")
    assert value is not None
    assert {
        k: int(value.attrib[k]) for k in ["tests", "failures", "errors", "skipped"]
    } == {"tests": total, "failures": failed, "errors": 0, "skipped": 0}


def protocols(name: str) -> dict[str, Any]:
    with tarfile.open(FILES / (name + "-raw-first.tar.gz")) as archive:

        def value(relative: str) -> Any:
            handle = archive.extractfile(name + "/" + relative)
            assert handle is not None
            raw = handle.read()
            return json.loads(gzip.decompress(raw) if relative.endswith(".gz") else raw)

        proof = value("proof.json")
        assert proof["responses"] == len(proof["rows"]) == 126
        assert proof["fixed_response_char_limit"] == 8192 and proof["new_models"] == 0
        calls = []
        for journal_name in [
            "capture.jsonl",
            "capture-resume.jsonl",
            "capture-resume2.jsonl",
        ]:
            journal = archive.extractfile(name + "/" + journal_name)
            assert journal is not None
            previous = None
            for sequence, line in enumerate(journal.read().decode().splitlines(), 1):
                record = json.loads(line)
                digest = record.pop("sha256")
                assert (
                    record["sequence"] == sequence
                    and record["previous_sha256"] == previous
                )
                assert hashlib.sha256(canonical(record)).hexdigest() == digest
                previous = digest
                if record["event"] == "tool_call":
                    assert record["tool"] == "bazi_source_compare"
                    assert record["arguments"]["response_char_limit"] == 8192
                    assert not record["result"]["is_error"]
                    text = "".join(
                        c.get("text", "")
                        for c in record["result"]["content"]
                        if c["type"] == "text"
                    )
                    assert len(text) <= 8192 and canonical(
                        json.loads(text)
                    ) == canonical(record["result"]["structured_content"])
                    calls.append(record["result"]["structured_content"])
        assert len(calls) == 42
        actual_mcp = {r["run_metadata"]["run_id"]: r for r in calls}
        businesses: dict[str, list[Any]] = {}
        for row in proof["rows"]:
            prefix = row["case"] + "/" + row["transport"]
            first = value(prefix + "-original-response.json")
            assert (
                len(json.dumps(first, ensure_ascii=False, separators=(",", ":")))
                == row["first_chars"]
                <= 8192
            )
            if row["transport"] == "cli":
                assert canonical(value(row["case"] + "/cli-stdout.json")) == canonical(
                    first
                )
            elif row["transport"] == "mcp":
                assert canonical(
                    actual_mcp[first["run_metadata"]["run_id"]]
                ) == canonical(first)
            ref = first.get("result_delivery")
            payload = first
            if ref:
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
                        next_offset = page["next_offset"]
                        assert next_offset is None or next_offset > offset
                        offset = next_offset
                    raw = "".join(fragments).encode()
                    assert hashlib.sha256(raw).hexdigest() == ref["sha256"]
                    assert canonical(json.loads(raw)) == canonical(payload)
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
                    hashlib.sha256(
                        json.dumps(
                            payload, ensure_ascii=False, separators=(",", ":")
                        ).encode()
                    ).hexdigest()
                    == ref["sha256"]
                )
                assert (
                    payload["run_metadata"]["run_id"] == first["run_metadata"]["run_id"]
                )
            businesses.setdefault(row["case"], []).append(
                {k: v for k, v in payload.items() if k != "run_metadata"}
            )
        assert len(businesses) == 42 and all(
            len(v) == 3 and len({canonical(p) for p in v}) == 1
            for v in businesses.values()
        )
        return {
            "responses": 126,
            "largest_first_chars": max(r["first_chars"] for r in proof["rows"]),
            "paged": sum(r["paged"] for r in proof["rows"]),
            "business_sha256_by_case": {
                k: hashlib.sha256(canonical(v[0])).hexdigest()
                for k, v in businesses.items()
            },
        }


def audit() -> dict[str, Any]:
    plan_path = FIXTURE / "publication-plan-first.json"
    raw = plan_path.read_bytes()
    plan = json.loads(raw)
    plan_sha = hashlib.sha256(raw).hexdigest()
    assert plan_sha == Path(str(plan_path) + ".sha256").read_text().strip()
    assert (
        raw
        == (
            ROOT / "src/fatebridge/data/reference/bazi-source-condition-reviews-v1.json"
        ).read_bytes()
    )
    assert (
        len(plan["reviews"]) == 19
        and sum(len(r["reference_bindings"]) for r in plan["reviews"]) == 21
    )
    manifest = read(FIXTURE / "source-manifest-first.json")
    with tarfile.open(FILES / "qualified-source-first.tar.gz") as archive:
        members = {}
        for member in archive:
            handle = archive.extractfile(member)
            assert handle is not None
            members[member.name] = hashlib.sha256(handle.read()).hexdigest()
    assert members == manifest
    wheel = read(FIXTURE / "wheel-proof-first.json")
    path = ROOT / wheel["wheel"]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == wheel["wheel_sha256"]
    with zipfile.ZipFile(path) as archive:
        package = {
            n: hashlib.sha256(archive.read(n)).hexdigest()
            for n in archive.namelist()
            if n.startswith("fatebridge/")
        }
    assert package == wheel["files_sha256"]
    assert all(manifest["src/" + n] == h for n, h in package.items())
    parent_index = ROOT / plan["parent_index_path"]
    assert (
        hashlib.sha256(parent_index.read_bytes()).hexdigest()
        == plan["parent_index_sha256"]
        == manifest[str(parent_index.relative_to(ROOT))]
    )
    parent = ROOT / plan["registered_developer_review_path"]
    assert (
        hashlib.sha256(parent.read_bytes()).hexdigest()
        == plan["registered_developer_review_sha256"]
    )
    old_reviews = {r["private_source_case_id"]: r for r in read(parent)["rows"]}
    for row in plan["reviews"]:
        old = old_reviews[row["case_id"]]
        assert (
            hashlib.sha256(canonical(old)).hexdigest()
            == row["parent_review_row_sha256"]
        )
        content = row["review"]
        for new_key, old_key in [
            ("pillars", "pillars"),
            ("claim_shape", "source_claim_shape"),
            ("reading_excerpt", "source_quote_transcribed_for_scope"),
            ("source_pdf_sha256", "source_pdf_sha256"),
            ("body_seal_conditions", "body_seal_conditions_review"),
            ("passage_conditions", "passage_conditions_review"),
        ]:
            assert content[new_key] == old[old_key]
        anchors = [
            {
                "pdf_page": int(Path(a["path"]).stem.rsplit("-p", 1)[1]),
                "image_sha256": a["sha256"],
            }
            for a in old["source_anchor_images"]
        ]
        assert content["source_page_anchors"] == anchors
        for relative in content["relative_timing_statements"]:
            assert (
                row["case_id"] == "ML-02"
                and relative["reading_excerpt"]
                in old["source_quote_transcribed_for_scope"]
            )
            assert (
                relative["source_term"],
                relative["source_elapsed_days"],
                relative["source_duty_stem"],
            ) == ("立春", 6, "戊")
            assert (
                relative["calendar_instant_reconstructed"] is False
                and relative["effective_duty_assigned"] is False
            )
    by_reference = {}
    for row in plan["reviews"]:
        for binding in row["reference_bindings"]:
            by_reference[binding["reference_id"]] = {
                **deepcopy(row["review"]),
                "provenance": {
                    "method_id": plan["method_id"],
                    "condition_layer_sha256": plan_sha,
                    "registered_review_sha256": plan[
                        "registered_developer_review_sha256"
                    ],
                    "registered_review_row_sha256": row["parent_review_row_sha256"],
                    "parent_index_record_sha256": binding["parent_record_sha256"],
                },
            }
    with ExitStack() as stack:
        handles = [
            stack.enter_context(
                gzip.open(FILES / ("public-all367-" + name + "-first.jsonl.gz"), "rt")
            )
            for name in ["before", "source", "wheel"]
        ]
        count = 0
        for lines in zip(*handles, strict=True):
            before, source, installed = [json.loads(line) for line in lines]
            assert canonical(source) == canonical(installed)
            expected = deepcopy(before["result"])
            for row in expected["source_comparison"]["records"]:
                if row["reference_id"] in by_reference:
                    row["source_condition_review"] = by_reference[row["reference_id"]]
            expected["source_comparison"]["reference_index"].update(
                source_condition_review_method_id=plan["method_id"],
                source_condition_review_sha256=plan_sha,
                total_registered_source_condition_reviews=19,
                total_records_with_source_condition_review=21,
            )
            assert canonical(source["result"]) == canonical(expected), before[
                "reference_id"
            ]
            count += 1
        assert count == 367
    for name in ["source", "wheel"]:
        original = (
            ROOT
            / "docs/validation/bazi-force-coherence-files-v1/all408-before-first.jsonl.gz"
        )
        count = original19 = unresolved = 0
        with (
            gzip.open(original, "rt") as old_lines,
            gzip.open(
                FILES / ("all408-" + name + "-first.jsonl.gz"), "rt"
            ) as new_lines,
        ):
            for old_line, new_line in zip(old_lines, new_lines, strict=True):
                before, after = json.loads(old_line), json.loads(new_line)
                assert canonical(before) == canonical(after)
                if after["case"]["is_original_nineteen"]:
                    original19 += 1
                    unresolved += (
                        after["case"]["expected_strength"]
                        != after["strength"]["strength_level"]
                    )
                    assert (
                        after["natal"]["month_command"]["intra_month_duty"][
                            "selected_stem"
                        ]
                        is None
                    )
                count += 1
        assert (count, original19, unresolved) == (408, 19, 17)
    for name, total, failed in [
        ("new-public-before-first", 19, 19),
        ("new-tests-first", 20, 0),
        ("complete-tests-first", 50, 0),
        ("new-transport-first", 25, 19),
        ("corrected-tests-first", 75, 0),
        ("related-baseline-first", 39, 0),
        ("related-after-first", 39, 1),
        ("frozen-source-tests-first", 75, 0),
        ("installed-wheel-tests-first", 75, 0),
    ]:
        suite(name, total, failed)
    failure = ET.parse(FILES / "related-after-first.xml").getroot().find("testsuite")
    assert failure is not None
    assert [
        t.attrib["name"]
        for t in failure.findall("testcase")
        if t.find("failure") is not None
    ] == ["test_all367_complete_public_results_have_only_declared_documentary_diffs"]
    old = read(FIXTURE / "requirements-before-append-first.json.gz")
    current = read(ROOT / "docs/validation/bazi-three-axis-requirements.json")
    assert len(old) == 104 and all(
        canonical(current[k]) == canonical(v) for k, v in old.items()
    )
    parents = read(FIXTURE / "prior2305-bindings-reverified-first.json")
    count = 0
    for parent in parents:
        path = ROOT / parent["receipt"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == parent["sha256"]
        entries = read(path)["files_sha256"]
        assert len(entries) == parent["bindings_verified"]
        assert all(
            hashlib.sha256((ROOT / n).read_bytes()).hexdigest() == h
            for n, h in entries.items()
        )
        count += len(entries)
    assert count == 2305
    source = protocols("source-protocols-first")
    installed = protocols("wheel-protocols-first")
    assert source["business_sha256_by_case"] == installed["business_sha256_by_case"]
    return {
        "source_cases": 19,
        "existing_records_with_conditions": 21,
        "unknown_duplicate_annotations_retained": 2,
        "all367_complete_results_only_declared_condition_additions": True,
        "all408_complete_calculations_unchanged": True,
        "source_and_wheel_each_new_tests": 75,
        "related_before_passed": 39,
        "related_after_passed": 38,
        "old_full_v66_output_gate_still_failed": True,
        "source_protocols": source,
        "wheel_protocols": installed,
        "prior2305_bindings_verified": True,
        "original19_unresolved": 17,
        "new_classical_accuracy_credit": 0,
        "new_actual_model_executions": 0,
        "new19_model_semantic_acceptance": "not_tested",
        "real_world_predictive_validity": "not_tested",
        "full_goal_complete": False,
        "overall_score": None,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit()
    args.output.open("x").write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False))
