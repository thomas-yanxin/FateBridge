"""Replay all frozen unit-root rows and transports without model execution."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib.util
import json
import struct
import tarfile
import tempfile
import xml.etree.ElementTree as ET
from fractions import Fraction
from pathlib import Path
from typing import Any

from fatebridge.validation.case_capture import inspect_cases

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/bazi_root_predicate_v1"
FILES = ROOT / "docs/validation/bazi-root-predicate-files-v1"


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


def capture(name: str) -> list[Any]:
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "capture.jsonl"
        path.write_bytes(gzip.decompress((FILES / (name + ".jsonl.gz")).read_bytes()))
        result = inspect_cases(path)
        assert result["status"] == "complete"
        return result["results"]


def without_new_receipt(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            k: (
                {
                    n: without_new_receipt(v)
                    for n, v in item.items()
                    if n not in {"scope", "physical_root_unit_comparison"}
                }
                if k == "threshold_arithmetic" and isinstance(item, dict)
                else without_new_receipt(item)
            )
            for k, item in value.items()
        }
    if isinstance(value, list):
        return [without_new_receipt(item) for item in value]
    return value


def suite(name: str, total: int, failures: int) -> dict[str, Any]:
    root = ET.parse(FILES / (name + ".xml")).getroot()
    item = root.find("testsuite")
    assert item is not None
    counts = {
        k: int(item.attrib[k]) for k in ("tests", "failures", "errors", "skipped")
    }
    assert counts == {"tests": total, "failures": failures, "errors": 0, "skipped": 0}
    failed = [
        c.attrib["name"] for c in root.iter("testcase") if c.find("failure") is not None
    ]
    return {**counts, "failed_test_names": failed}


def stdio(name: str) -> dict[str, Any]:
    proof = read(FILES / (name + "-readback-proof.json"))
    assert proof["cases"] == 66 and proof["all_requests_response_char_limit"] == 8192
    assert len(proof["rows"]) == 66
    with tarfile.open(FILES / (name + "-payloads.tar.gz")) as archive:

        def value(path: str) -> Any:
            handle = archive.extractfile(path)
            assert handle is not None
            raw = handle.read()
            return json.loads(gzip.decompress(raw) if path.endswith(".gz") else raw)

        for i, row in enumerate(proof["rows"]):
            first = value(f"{i}-original-response.json")
            manifest = value(f"{i}-manifest.json")
            wrapper = value(f"{i}-same-run-file.json.gz")
            ref = first["result_delivery"]
            assert row["index"] == i and row["paged"] and row["same_run_verified"]
            assert (
                len(json.dumps(first, ensure_ascii=False, separators=(",", ":")))
                == row["first_reply_chars"]
                <= 8192
            )
            assert (
                manifest["result_id"] == ref["result_id"]
                and manifest["sha256"] == ref["sha256"]
            )
            payload = wrapper[manifest["file_payload_path"]]
            encoded = json.dumps(
                payload, ensure_ascii=False, separators=(",", ":")
            ).encode()
            assert hashlib.sha256(encoded).hexdigest() == ref["sha256"]
            assert (
                payload["run_metadata"]["run_id"]
                == manifest["run_metadata"]["run_id"]
                == first["run_metadata"]["run_id"]
            )
    assert all(row["inline_reference_has_file_path"] for row in proof["rows"])
    return {
        "cases": 66,
        "same_run_verified": 66,
        "paged": 66,
        "largest_structured_reply_chars": max(
            r["first_reply_chars"] for r in proof["rows"]
        ),
    }


def audit() -> dict[str, Any]:
    for name in (
        "protocol.json",
        "baseline-source-manifest.json",
        "candidate-source-manifest.json",
        "current-source-manifest-first.json",
        "independent_root_reference.py",
        "implementation-plan-first.json",
        "inputs-first.json",
        "public-inputs-first.json",
    ):
        path = FIXTURE / name
        assert (
            hashlib.sha256(path.read_bytes()).hexdigest()
            == Path(str(path) + ".sha256").read_text().strip()
        )
    module_spec = importlib.util.spec_from_file_location(
        "root_audit_population",
        ROOT / "tests/fixtures/bazi_strength_threshold_v1/scan.py",
    )
    assert module_spec is not None and module_spec.loader is not None
    queue = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(queue)
    before = read(FILES / "baseline-completion-first.json")
    after = read(FILES / "candidate-completion-first.json")
    fmt = struct.Struct(before["row_format"])
    data = gzip.decompress((FILES / "baseline-all-rows-first.bin.gz").read_bytes())
    newer = gzip.decompress((FILES / "candidate-all-rows-first.bin.gz").read_bytes())
    assert len(data) == fmt.size * 518400 and data == newer
    elements = "木火土金水"
    stem_element = dict(zip("甲乙丙丁戊己庚辛壬癸", "木木火火土土金金水水"))
    generates = dict(zip(elements, elements[1:] + elements[:1]))
    controls = dict(zip(elements, "土金水木火"))
    changed, counts, finals, unit_boundaries = [], [], [], []
    controller_changes = wealth_changes = 0
    ih = hashlib.sha256()
    with gzip.open(FILES / "baseline-all-exact-roots-first.jsonl.gz", "rt") as stream:
        for i, pillars in enumerate(queue.inputs()):
            exact = json.loads(next(stream))
            assert exact["index"] == i
            row = fmt.unpack_from(data, i * fmt.size)
            q = dict(zip(elements, map(Fraction, exact["root_masses"])))
            old_flags = [v >= 1 for v in row[:5]]
            new_flags = [q[e] >= 1 for e in elements]
            assert list(map(bool, row[5:10])) == old_flags
            assert list(map(bool, row[10:15])) == new_flags
            assert row[15:19] == row[19:23]
            if any(v == 1 for v in q.values()):
                unit_boundaries.append(i)
            if old_flags != new_flags:
                changed.append(i)
                assert all(
                    not a and b and q[e] == 1
                    for e, a, b in zip(elements, old_flags, new_flags)
                    if a != b
                )
            body = stem_element[pillars[2][0]]
            seal = next(e for e in elements if generates[e] == body)
            controller = next(e for e in elements if controls[e] == body)
            wealth = controls[body]
            visible = [stem_element[pillars[k][0]] for k in (0, 1, 3)]
            new_count = sum(e == controller and q[e] >= 1 for e in visible)
            new_wealth = any(e == wealth and q[e] >= 1 for e in visible)
            assert row[24] == new_count and row[26] == new_wealth
            assert row[23] == sum(
                e == controller and old_flags[elements.index(e)] for e in visible
            )
            assert row[25] == any(
                e == wealth and old_flags[elements.index(e)] for e in visible
            )
            new_front = (
                new_count >= 2
                and new_wealth
                and all(e not in {body, seal} for e in visible)
                and sum(row[19:23]) <= 1
            )
            assert row[28] == (0 if new_front else row[27])
            controller_changes += row[23] != row[24]
            wealth_changes += row[25] != row[26]
            if row[23] != row[24] or row[25] != row[26]:
                counts.append(i)
            if row[27] != row[28]:
                finals.append(i)
            ih.update(
                json.dumps(
                    pillars, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                ).encode()
                + b"\n"
            )
        assert next(stream, None) is None
    assert (
        i + 1 == 518400
        and ih.hexdigest() == before["inputs_sha256"] == after["inputs_sha256"]
    )
    assert len(changed) == 1141 and changed == after["root_predicate_corrected_inputs"]
    assert (
        len(counts) == 215
        and counts == after["consumed_structure_field_changed_inputs"]
    )
    assert (controller_changes, wealth_changes, finals) == (
        109,
        106,
        [399737, 408365, 494165],
    )
    assert (
        finals == after["final_grade_changed_inputs"]
        and unit_boundaries == before["unit_boundary_inputs"]
    )
    assert len(unit_boundaries) == 24891
    for family, total in (("corpus", 408), ("public", 66)):
        old_values = capture(family + "-baseline-first")
        new_values = capture(family + "-candidate-first")
        assert len(old_values) == len(new_values) == total
        other = capture(family + "-wheel-first")
        assert equal(new_values, other)
        del other
        other = capture(family + "-current-first")
        assert equal(new_values, other)
        del other
        other = capture(family + "-causal-first")
        assert equal(old_values, other)
        del other
        if family == "corpus":
            assert equal(
                without_new_receipt(old_values), without_new_receipt(new_values)
            )
        del old_values, new_values
    differences = read(FIXTURE / "all-business-differences-first.json.gz")
    assert (
        differences["corpus"]["changed_fields"] == 5712
        and differences["public"]["changed_fields"] == 1285
    )
    research = differences["source_results"]
    assert [
        research[k]
        for k in (
            "records",
            "different_inputs",
            "known_records",
            "unknown_records",
            "different_known_input_disagreements",
        )
    ] == [408, 357, 127, 281, 25]
    assert sum(not r["matches"] for r in research["original_nineteen"]) == 17
    suites = {
        "source_new_first": suite("source-new-tests-first", 96, 3),
        "source_corrected_brackets": suite("source-corrected-brackets-first", 9, 0),
        "wheel_new": suite("wheel-new-tests-first", 96, 0),
        "baseline_related": suite("baseline-related-first", 372, 1),
        "source_related": suite("source-related-first", 372, 1),
    }
    assert (
        suites["baseline_related"]["failed_test_names"]
        == suites["source_related"]["failed_test_names"]
    )
    failure_kind = read(FIXTURE / "old-related-failure-kind-correction-first.json")
    assert failure_kind["corrected_kind"] == "stale_v6_method_id_assertion"
    assert not failure_kind["first_suite_scores_or_old_assertions_changed"]
    assert all("494165" in n for n in suites["source_new_first"]["failed_test_names"])
    stdios = {
        name: stdio(name)
        for name in ("source-stdio-first", "wheel-stdio-first", "current-stdio-first")
    }
    receipt = ROOT / "docs/validation/bazi-root-unit-arithmetic-local-v1.json"
    if receipt.exists():
        for path, expected in read(receipt)["files_sha256"].items():
            assert (
                hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == expected
            ), path
    return {
        "scope": "Fixed conditional budget arithmetic, source records and local transports; no model or prediction calls.",
        "synthetic_inputs": 518400,
        "exact_unit_boundary_inputs": 24891,
        "corrected_root_predicate_inputs": 1141,
        "controller_count_changed_inputs": 109,
        "wealth_flag_changed_inputs": 106,
        "final_grade_changed_indices": finals,
        "all_old_float_energies_relations_and_rootqualifications_retained": True,
        "source_records": 408,
        "known_records": 127,
        "unknown_records": 281,
        "different_known_input_disagreements": 25,
        "original_nineteen_unresolved": 17,
        "all_source_old_nonreceipt_values_and_sensitivity_equal": True,
        "public_scenarios": 66,
        "source_wheel_all_business_values_and_types_equal": True,
        "current_runtime_files": len(
            read(FIXTURE / "current-source-manifest-first.json")
        ),
        "current408_and66_all_business_values_and_types_equal_to_qualified_wheel": True,
        "causal_old_three_modules_restore_all_old_values_and_types": True,
        "test_runs": suites,
        "stdio": stdios,
        "first_source_test_score_regraded": False,
        "old_related_failure_kind": "stale_v6_method_id_assertion",
        "original_full_view8192_no_paging_gate_passed": False,
        "old_lost_first_objects_gate_passed": False,
        "classical_effective_body_seal_root_force": "not_adjudicated",
        "intra_month_duty_and_effective_passage": "not_adjudicated",
        "month_clause_author_attribution": "not_completed",
        "new_classical_accuracy_credit": 0,
        "new_actual_model_executions": 0,
        "new_fields_actual_model_semantic_acceptance": "not_tested",
        "independent_expert_review": "not_completed",
        "real_world_predictive_validity": "not_tested",
        "full_goal_complete": False,
        "overall_score": None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit()
    raw = json.dumps(result, ensure_ascii=False, indent=2).encode() + b"\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("xb") as handle:
        handle.write(
            gzip.compress(raw, mtime=0) if args.output.suffix == ".gz" else raw
        )
    print(
        json.dumps(
            {k: v for k, v in result.items() if k not in ("test_runs", "stdio")},
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
