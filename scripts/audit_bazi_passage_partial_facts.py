"""Replay retained physical-fact evidence; never execute models or regrade gates."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import runpy
import tarfile
import tempfile
import xml.etree.ElementTree as ET
from fractions import Fraction
from pathlib import Path
from typing import Any

from fatebridge.validation.case_capture import inspect_cases

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/bazi_month_passage_next_v1"
FILES = ROOT / "docs/validation/bazi-passage-partial-files-v1"


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


def suite(name: str, total: int, failures: int) -> dict[str, int]:
    root = ET.parse(FILES / (name + ".xml")).getroot()
    item = root.find("testsuite")
    assert item is not None
    counts = {
        k: int(item.attrib[k]) for k in ("tests", "failures", "errors", "skipped")
    }
    assert counts == {"tests": total, "failures": failures, "errors": 0, "skipped": 0}
    return counts


def stdio(name: str) -> dict[str, Any]:
    proof = read(FILES / (name + "-readback-proof.json"))
    assert proof["cases"] == 66 and proof["fixed_response_char_limit"] == 8192
    with tarfile.open(FILES / (name + "-payloads.tar.gz")) as archive:

        def value(path):
            handle = archive.extractfile(path)
            assert handle is not None
            raw = handle.read()
            return json.loads(gzip.decompress(raw) if path.endswith(".gz") else raw)

        for index, row in enumerate(proof["rows"]):
            first = value(f"{index}-original-response.json")
            manifest = value(f"{index}-manifest.json")
            wrapper = value(f"{index}-same-run-file.json.gz")
            ref = first["result_delivery"]
            assert (
                ref["result_id"] == manifest["result_id"]
                and ref["sha256"] == manifest["sha256"]
            )
            payload = wrapper[manifest["file_payload_path"]]
            encoded = json.dumps(
                payload, ensure_ascii=False, separators=(",", ":")
            ).encode()
            assert hashlib.sha256(encoded).hexdigest() == ref["sha256"]
            assert (
                payload["run_metadata"]["run_id"]
                == first["run_metadata"]["run_id"]
                == manifest["run_metadata"]["run_id"]
            )
            assert (
                len(json.dumps(first, ensure_ascii=False, separators=(",", ":")))
                == row["first_reply_chars"]
                <= 8192
            )
            assert row["index"] == index and row["paged"] and row["same_run_verified"]
    return {
        "cases": 66,
        "paged": 66,
        "same_run_verified": 66,
        "largest_structured_reply_chars": max(
            r["first_reply_chars"] for r in proof["rows"]
        ),
    }


def audit() -> dict[str, Any]:
    for name in (
        "protocol.json",
        "first-independent-counterexamples.json",
        "independent_reference.py",
        "baseline-source-manifest-first.json",
        "candidate-source-manifest-first.json",
    ):
        path = FIXTURE / name
        assert (
            hashlib.sha256(path.read_bytes()).hexdigest()
            == Path(str(path) + ".sha256").read_text().strip()
        )
    reference = runpy.run_path(str(FIXTURE / "independent_reference.py"))
    manifest = read(FIXTURE / "candidate-source-manifest-first.json")
    with tarfile.open(FILES / "qualified-source-first.tar.gz") as archive:
        assert set(archive.getnames()) == set(manifest)
        for member in archive:
            handle = archive.extractfile(member)
            assert (
                handle is not None
                and hashlib.sha256(handle.read()).hexdigest() == manifest[member.name]
            )
    ordinal_contract = read(FIXTURE / "pre-edit-hidden-catalog-contract.json")[
        "hidden_stems"
    ]
    independent_ordinal_differences = []
    inputs = read(ROOT / "tests/fixtures/bazi_root_predicate_v1/inputs-first.json")[
        "cases"
    ]
    prior = read(
        ROOT
        / "tests/fixtures/bazi_seasonal_bing_v1/nineteen-current-conditions-review-first.json"
    )["rows"]
    current = capture("corpus-candidate-first")
    assert len(current) == 408
    for family, count in (("corpus", 408), ("public", 66)):
        before = capture(family + "-baseline-first")
        after = current if family == "corpus" else capture(family + "-candidate-first")
        wheel = capture(family + "-wheel-first")
        assert len(before) == len(after) == len(wheel) == count
        assert equal(before, after) and equal(after, wheel), family
    byid = {c["id"]: r for c, r in zip(inputs, current, strict=True)}
    rows = []
    for old in prior:
        result = byid[old["id"]]
        chain, strength = result["evidence_chain"], result["strength"]
        pillars = dict(zip(reference["PILLARS"], old["pillars"]))
        force = chain["force_components"]
        energy = strength["assessment"]["threshold_arithmetic"]["energies_exact"]
        body = reference["STEMS"][pillars["day"][0]]
        seal = reference["ELEMENTS"][(reference["ELEMENTS"].index(body) - 1) % 5]
        assert body != seal
        for role, element in (("body", body), ("seal", seal)):
            actual = force["components"][role]
            expected = [
                {"pillar": p, "branch": glyphs[1], "stem": s, "hidden_rank": rank}
                for p, glyphs in pillars.items()
                for rank, s in enumerate(reference["HIDDEN"][glyphs[1]])
                if reference["STEMS"][s] == element
            ]
            assert actual["element"] == element

            def membership(entries):
                return sorted((n["pillar"], n["branch"], n["stem"]) for n in entries)

            assert membership(actual["physical_hidden_roots"]) == membership(expected)
            if not equal(actual["physical_hidden_roots"], expected):
                independent_ordinal_differences.append(
                    {
                        "id": old["id"],
                        "role": role,
                        "first_literal_reference": expected,
                        "actual": actual["physical_hidden_roots"],
                        "external_ordinal_accuracy": "not_adjudicated",
                    }
                )
            assert all(
                ordinal_contract[n["branch"]][n["hidden_rank"]] == n["stem"]
                for n in actual["physical_hidden_roots"]
            )
            assert actual["revealed_positions"] == [
                p
                for p, glyphs in pillars.items()
                if p != "day" and reference["STEMS"][glyphs[0]] == element
            ]
            assert Fraction(
                force["engineering_composition"][role + "_energy_exact"]
            ) == Fraction(energy[element])
            assert Fraction(old[role + "_exact"]) == Fraction(energy[element])
        assert set(force["classical_adjudication"].values()) == {"not_adjudicated"}
        duty = chain["month_command"]["intra_month_duty"]
        assert duty["selected_stem"] is None and duty["status"] == "not_adjudicated"
        assert duty["source_reference"]["effective_command_status"] == "not_adjudicated"
        passage = chain["classical_passage"]
        nodes = {n["id"]: n for n in passage["nodes"]}
        for n in nodes.values():
            p, plane, s = n["id"].split(":")
            assert n["pillar"] == p and n["plane"] == plane and n["stem"] == s
            assert n["element"] == reference["STEMS"][s]
            if plane == "stem":
                assert (
                    s == pillars[p][0]
                    and n["branch"] is None
                    and n["hidden_rank"] is None
                )
            else:
                assert n["branch"] == pillars[p][1]
                assert s in reference["HIDDEN"][n["branch"]]
                assert ordinal_contract[n["branch"]][n["hidden_rank"]] == s
                assert (n["hidden_rank"] == 0) == (
                    reference["HIDDEN"][n["branch"]][0] == s
                )
        paths = []
        for name in (
            "visible_paths",
            "principal_hidden_paths",
            "all_hidden_paths",
            "mixed_paths",
        ):
            for path in passage[name]:
                assert reference["possible_path"](path)
                actual = [nodes[path[k]] for k in ("from_node", "via_node", "to_node")]
                assert path["elements"] == [n["element"] for n in actual]
                assert path["binding_states"] == [n["binding_state"] for n in actual]
                roots = [n["remaining_root_state"] for n in actual]
                expected_roots = (
                    None
                    if "not_supplied" in roots
                    else all(r == "positive_remaining_budget" for r in roots)
                )
                assert path["all_nodes_have_remaining_roots"] is expected_roots
                assert path["principal_hidden_only"] == all(
                    n["plane"] == "hidden" and n["hidden_rank"] == 0 for n in actual
                )
                assert path["effective_passage"] == "not_adjudicated"
                paths.append(path)
        assert passage["summary"]["effective_passage"] == "not_adjudicated"
        assert strength["strength_level"] == old["actual"]
        rows.append(
            {
                "id": old["id"],
                "pillars": old["pillars"],
                "expected": old["expected"],
                "actual": strength["strength_level"],
                "matches": old["matches"],
                "body_exact": old["body_exact"],
                "seal_exact": old["seal_exact"],
                "body_and_seal_physical_facts_separate_and_consistent": True,
                "source_condition_review_retained": old["developer_condition_review"],
                "source_record_sha256": hashlib.sha256(
                    json.dumps(
                        old["source_record"], ensure_ascii=False, sort_keys=True
                    ).encode()
                ).hexdigest(),
                "month_duty": {
                    "selected_stem": None,
                    "status": "not_adjudicated",
                    "civil_birth_instant_supplied": False,
                    "nominal_schedule_adopted": False,
                },
                "physical_nodes_checked": len(nodes),
                "path_occurrences_checked": len(paths),
                "effective_passage": "not_adjudicated",
                "new_classical_correct_credit": 0,
            }
        )
    assert len(rows) == 19 and sum(not r["matches"] for r in rows) == 17
    before = read(FILES / "baseline-probes-first.json")
    after = read(FILES / "candidate-probes-first.json")
    assert before["match_count"] == 3 and after["match_count"] == 22
    assert equal(
        before["unknown_relation_probe"]["relation_context"],
        after["unknown_relation_probe"]["relation_context"],
    )
    assert before["unknown_relation_probe"]["relation_context"][
        "unclassified_event_refs"
    ] == ["assessment.relations:0"]
    for node in after["unknown_relation_probe"]["passage"]["nodes"]:
        assert node["binding_state"] == "no_binding_recorded"
    return {
        "source_records": 408,
        "different_inputs": len({tuple(c["pillars"]) for c in inputs}),
        "known_records": sum(c.get("expected_strength") is not None for c in inputs),
        "source_and_wheel_all_408_and_66_business_values_and_types_unchanged": True,
        "original_nineteen": rows,
        "original_nineteen_unresolved": 17,
        "newly_resolved_original_cases": 0,
        "synthetic_wrongly_accepted_contracts_fixed": 19,
        "actual_invalid_natal_passage_observed": False,
        "first_independent_hidden_ordinal_gate_passed": False,
        "independent_hidden_ordinal_differences_retained": independent_ordinal_differences,
        "hidden_ordinal_accuracy": "not_adjudicated",
        "unknown_relation_context_retained": True,
        "first_related_tests": suite("related-first", 93, 3),
        "first_new_tests": suite("new-first", 29, 0),
        "source_qualified_tests": suite("source-tests-first", 188, 0),
        "wheel_qualified_tests": suite("wheel-tests-first", 188, 0),
        "source_stdio": stdio("source-stdio-first"),
        "wheel_stdio": stdio("wheel-stdio-first"),
        "all408_guard": read(FILES / "all408-guard-first.json")["cases"],
        "new_actual_model_executions": 0,
        "new_fields_model_semantic_acceptance": "not_tested",
        "original_no_paging_gate_regraded": False,
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
            {k: v for k, v in result.items() if k != "original_nineteen"},
            ensure_ascii=False,
        )
    )
