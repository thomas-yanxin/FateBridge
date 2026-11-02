"""Audit saved same-receipt controls and same-run local protocol delivery."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import tarfile
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/bazi_force_coherence_v1"
FILES = ROOT / "docs/validation/bazi-force-coherence-files-v1"


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
    } == {
        "tests": total,
        "failures": failures,
        "errors": 0,
        "skipped": 0,
    }


def protocols(name: str) -> dict[str, Any]:
    with tarfile.open(FILES / (name + "-raw-first.tar.gz")) as archive:

        def value(relative: str) -> Any:
            handle = archive.extractfile(name + "/" + relative)
            assert handle is not None
            raw = handle.read()
            return json.loads(gzip.decompress(raw) if relative.endswith(".gz") else raw)

        calls = []
        for journal in ["capture.jsonl", "capture-resume.jsonl"]:
            handle = archive.extractfile(name + "/" + journal)
            assert handle is not None
            previous = None
            for sequence, line in enumerate(handle.read().decode().splitlines(), 1):
                record = json.loads(line)
                digest = record.pop("sha256")
                assert (
                    record["sequence"] == sequence
                    and record["previous_sha256"] == previous
                )
                assert hashlib.sha256(canonical(record)).hexdigest() == digest
                previous = digest
                if record["event"] == "tool_call":
                    assert record["arguments"]["response_char_limit"] == 8192
                    assert record["arguments"]["include_snapshot_text"] is False
                    assert (
                        record["outcome"] == "returned"
                        and not record["result"]["is_error"]
                    )
                    calls.append(record)
        assert len(calls) == 22
        actual_mcp = {
            r["result"]["structured_content"]["run_metadata"]["run_id"]: r["result"][
                "structured_content"
            ]
            for r in calls
        }
        prefetch = value("prefetch-proof.json")
        assert (
            prefetch["same_cli_parser_each_page"]
            and prefetch["page_size_or_response_budget_overrides"] == 0
        )
        for record in prefetch["records"]:
            assert (
                record["actual_entrypoint"] == "fatebridge.cli.run"
                and record["chart_recalculations"] == 0
            )
            folder = str(Path(record["first_response"]).parent)
            for page in record["pages"]:
                handle = archive.extractfile(
                    name
                    + "/"
                    + folder
                    + "/cli-verified-pages/"
                    + str(page["offset"])
                    + ".json"
                )
                assert (
                    handle is not None
                    and hashlib.sha256(handle.read()).hexdigest()
                    == page["stdout_sha256"]
                )
        proof = value("proof.json")
        assert proof["responses"] == len(proof["rows"]) == 64
        assert proof["fixed_response_char_limit"] == 8192 and proof["new_models"] == 0
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
                    assert manifest["result_id"] == ref["result_id"]
                    assert manifest["sha256"] == ref["sha256"]
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
                assert (
                    payload["run_metadata"]["run_id"] == first["run_metadata"]["run_id"]
                )
            businesses.setdefault(row["case"], []).append(
                {k: v for k, v in payload.items() if k != "run_metadata"}
            )
        assert len(businesses) == 22
        before = read(FILES / "public11-before-first.json.gz")
        for row in before["rows"]:
            for view in ["full", "projected"]:
                case = row["tool"] + "-" + view
                values = businesses[case]
                assert len(values) == (2 if row["tool"] == "analyze_destiny" else 3)
                assert len({canonical(v) for v in values}) == 1
                if view == "full":
                    expected = dict(row["result"])
                    expected.pop("snapshot_text", None)
                    assert canonical(values[0]) == canonical(expected)
        return {
            "responses": 64,
            "largest_first_chars": max(r["first_chars"] for r in proof["rows"]),
            "paged": sum(r["paged"] for r in proof["rows"]),
            "business_sha256_by_case": {
                k: hashlib.sha256(canonical(v[0])).hexdigest()
                for k, v in businesses.items()
            },
        }


def audit() -> dict[str, Any]:
    protocol = FIXTURE / "protocol-first.json"
    assert (
        hashlib.sha256(protocol.read_bytes()).hexdigest()
        == Path(str(protocol) + ".sha256").read_text().strip()
    )
    first = read(FIXTURE / "source-manifest-first.json")
    final = read(FIXTURE / "source-manifest-final.json")
    members = {}
    for filename in [
        "qualified-source-first.tar.gz",
        "helper-style-overlay-first.tar.gz",
    ]:
        with tarfile.open(FILES / filename) as archive:
            for member in archive:
                handle = archive.extractfile(member)
                assert handle is not None
                digest = hashlib.sha256(handle.read()).hexdigest()
                assert (
                    digest
                    == (first if filename.startswith("qualified") else final)[
                        member.name
                    ]
                )
                members[member.name] = digest
    assert members == final and len(final) == 1759
    wheel = read(FIXTURE / "wheel-proof-first.json")
    wheel_path = ROOT / wheel["wheel"]
    assert hashlib.sha256(wheel_path.read_bytes()).hexdigest() == wheel["wheel_sha256"]
    with zipfile.ZipFile(wheel_path) as archive:
        observed = {
            n: hashlib.sha256(archive.read(n)).hexdigest()
            for n in archive.namelist()
            if n.startswith("fatebridge/")
        }
    assert (
        observed == wheel["files_sha256"]
        and len(observed) == wheel["all_package_files_equal_frozen_source"] == 1283
    )
    assert all(final["src/" + n] == h for n, h in observed.items())
    for name in [
        "src/fatebridge/core/output_classical_force.py",
        "src/fatebridge/core/output_bazi_evidence.py",
        "tests/test_bazi_force_coherence.py",
        "tests/test_bazi_force_coherence_transports.py",
    ]:
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == final[name]
    numerical = read(FIXTURE / "calculation-eight-files-unchanged-first.json")
    assert len(numerical) == 8
    assert all(
        final[n] == hashlib.sha256((ROOT / n).read_bytes()).hexdigest() == h
        for n, h in numerical.items()
    )
    suites = [
        ("new-tests-first", 30, 27),
        ("new-transport-first", 33, 23),
        ("new-transport-route-corrected-before-first", 33, 22),
        ("corrected-tests-first", 63, 0),
        ("frozen-source-tests-first", 63, 0),
        ("installed-wheel-tests-first", 63, 0),
        ("related-baseline-first", 336, 0),
        ("related-corrected-first", 336, 0),
    ]
    for name, total, failed in suites:
        suite(name, total, failed)
    # Correcting nonexistent REST exposure did not alter the final passing test assertions.
    assert (
        hashlib.sha256((FIXTURE / "new-tests-first-source.py").read_bytes()).hexdigest()
        == final["tests/test_bazi_force_coherence.py"]
    )
    assert (
        hashlib.sha256(
            (FIXTURE / "new-transport-route-corrected-before-source.py").read_bytes()
        ).hexdigest()
        == final["tests/test_bazi_force_coherence_transports.py"]
    )
    for name, expected_count, expect_error in [
        ("new-transport-first", 60, False),
        ("new-transport-route-corrected-before-first", 64, False),
        ("corrected-tests-first", 64, True),
        ("frozen-source-tests-first", 64, True),
        ("installed-wheel-tests-first", 64, True),
    ]:
        with tarfile.open(FILES / (name + "-raw-first.tar.gz")) as archive:
            packets = []
            for member in archive:
                if member.isfile() and member.name.endswith("-actual-response.json"):
                    handle = archive.extractfile(member)
                    assert handle is not None
                    packets.append(json.loads(handle.read()))
        assert len(packets) == expected_count
        assert all(
            (packet.get("error_code") == "internal_error") == expect_error
            for packet in packets
        )
    first_diff = read(FIXTURE / "protocol-first-direct-baseline-diff.json")
    assert (
        len(first_diff) == 1
        and first_diff[0]["path"] == ".snapshot_text"
        and first_diff[0]["kind"] == "missing"
    )
    assert (
        hashlib.sha256(
            (FIXTURE / "snapshot-option-producer-source-first.py").read_bytes()
        ).hexdigest()
        == final["src/fatebridge/utils/formatting.py"]
    )
    groups = []
    for name in ["before", "source", "wheel"]:
        with gzip.open(FILES / ("all408-" + name + "-first.jsonl.gz"), "rt") as lines:
            groups.append([json.loads(line) for line in lines])
    assert all(len(group) == 408 for group in groups)
    assert canonical(groups[0]) == canonical(groups[1]) == canonical(groups[2])
    original = [r for r in groups[0] if r["case"]["is_original_nineteen"]]
    assert len(original) == 19
    unresolved = sum(
        r["case"]["expected_strength"] != r["strength"]["strength_level"]
        for r in original
    )
    assert unresolved == 17
    zeros = [
        r
        for r in groups[0]
        if r["natal"]["force_components"]["engineering_composition"][
            "body_energy_exact"
        ]
        == r["natal"]["force_components"]["engineering_composition"][
            "seal_energy_exact"
        ]
        == "0"
    ]
    assert len(zeros) == 3 and len({tuple(r["case"]["pillars"]) for r in zeros}) == 2
    for row in zeros:
        comp = row["natal"]["force_components"]["engineering_composition"]
        assert (
            comp["body_within_support_exact"] is None
            and comp["body_within_support_share"] is None
        )
    review = read(FIXTURE / "original19-condition-followup-first.json")
    assert (
        hashlib.sha256((ROOT / review["parent_review"]).read_bytes()).hexdigest()
        == review["parent_review_sha256"]
    )
    assert (
        len(review["rows"]) == 19
        and review["unresolved"] == 17
        and review["models_invoked"] == 0
    )
    assert all(
        r["intra_month_selected_stem"] is None
        and r["effective_passage_states"] == ["not_adjudicated"]
        for r in review["rows"]
    )
    assert sum(r["path_occurrences_in_supplied_views"] for r in review["rows"]) == 1797
    parents = read(FIXTURE / "prior2179-bindings-reverified-first.json")
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
    assert count == 2179
    old = read(FIXTURE / "requirements-before-append-first.json.gz")
    current = read(ROOT / "docs/validation/bazi-three-axis-requirements.json")
    assert len(old) == 103 and all(
        canonical(current[k]) == canonical(v) for k, v in old.items()
    )
    source = protocols("source-protocols-first")
    installed = protocols("wheel-protocols-first")
    assert source["business_sha256_by_case"] == installed["business_sha256_by_case"]
    return {
        "complete_records_equal_without_value_or_type_changes": 408,
        "original19_unresolved": unresolved,
        "existing_zero_total_records": 3,
        "existing_zero_total_distinct_inputs": 2,
        "source_and_wheel_each_new_tests": 63,
        "related_before_and_after_each": 336,
        "all_prior2179_bindings_verified": True,
        "source_protocols": source,
        "wheel_protocols": installed,
        "original8192_full_view_no_paging_gate_regraded": False,
        "new_classical_accuracy_credit": 0,
        "new_actual_model_executions": 0,
        "new19_model_semantic_acceptance": "not_tested",
        "independent_expert_review": "not_completed",
        "real_world_predictive_validity": "not_tested",
        "full_goal_complete": False,
        "overall_score": None,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    result = audit()
    arguments.output.open("x").write(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(result, ensure_ascii=False))
