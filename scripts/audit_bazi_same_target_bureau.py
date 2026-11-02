"""Audit preserved source boundaries, full cohorts and actual transport receipts."""

import argparse
import gzip
import hashlib
import importlib.util
import json
import tarfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "tests/fixtures/bazi_same_target_bureau_v1"
D = ROOT / "docs/validation/bazi-same-target-bureau-files-v1"


def read(path):
    return json.loads(path.read_text())


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def cohort(name):
    return [json.loads(line) for line in gzip.open(D / name, "rt")]


def normalize(value):
    """Only predeclared documentary changes; preserve JSON types and all numbers."""
    if isinstance(value, dict):
        return {k: normalize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [
            normalize(v)
            for v in value
            if not (
                isinstance(v, dict)
                and v.get("id") == "complete_same_target_affiliation_primary_v1"
            )
        ]
    if isinstance(value, str):
        return value.replace(
            "season_root_revelation_relations_v7", "season_root_revelation_relations_v8"
        ).replace("已识别v5/v6/v7的", "已识别v5/v6/v7/v8的")
    return value


def differences(before, after, path=""):
    if type(before) is not type(after):
        return [{"path": path, "before": before, "after": after}]
    if isinstance(before, dict):
        result = []
        for key in sorted(before.keys() | after.keys()):
            if key not in before or key not in after:
                result.append(
                    {
                        "path": path + "." + key,
                        "before": before.get(key),
                        "after": after.get(key),
                        "key_presence_changed": True,
                    }
                )
            else:
                result.extend(differences(before[key], after[key], path + "." + key))
        return result
    if isinstance(before, list):
        if len(before) != len(after):
            return [{"path": path, "before": before, "after": after}]
        return [
            d
            for i, (a, b) in enumerate(zip(before, after))
            for d in differences(a, b, path + ":" + str(i))
        ]
    return [] if before == after else [{"path": path, "before": before, "after": after}]


def audit():
    spec = importlib.util.spec_from_file_location(
        "independent_geometry", F / "reference_geometry.py"
    )
    oracle = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(oracle)
    plan = read(F / "source-review-and-adoption-first.json")
    assert (
        hashlib.sha256((F / "reference_geometry.py").read_bytes()).hexdigest()
        == plan["independent_geometry_sha256"]
    )
    groups = [
        cohort("all408-" + label + "-first.jsonl.gz")
        for label in ("before", "source", "wheel")
    ]
    assert all(len(g) == 408 for g in groups)
    assert canonical(groups[1]) == canonical(
        cohort("all408-qualified-source-first.jsonl.gz")
    )
    changed, original19, leaf_diffs, legacy_equal = [], [], [], 0
    inputs = {}
    for before, source, wheel in zip(*groups):
        assert canonical(source) == canonical(wheel)
        assert canonical(before["case"]) == canonical(source["case"])
        assert canonical(before["legacy"]) == canonical(source["legacy"])
        legacy_equal += 1
        case = before["case"]
        inputs[tuple(case["pillars"])] = (
            source,
            bool(oracle.affiliations([p[1] for p in case["pillars"]])),
        )
        eligible = inputs[tuple(case["pillars"])][1]
        if not eligible:
            assert canonical(normalize(before)) == canonical(normalize(source)), case[
                "id"
            ]
        else:
            delta = differences(normalize(before), normalize(source))
            assert delta, case["id"]
            changed.append(
                {
                    "id": case["id"],
                    "before_grade": before["strength"]["strength_level"],
                    "after_grade": source["strength"]["strength_level"],
                    "retained_annotation": case["expected_strength"],
                    "label_status": case["label_status"],
                    "new_classical_accuracy_credit": 0,
                }
            )
            leaf_diffs.append({"id": case["id"], "differences": delta})
        if case["is_original_nineteen"]:
            assert not eligible
            original19.append(
                {
                    "id": case["id"],
                    "expected_strength": case["expected_strength"],
                    "current_strength": source["strength"]["strength_level"],
                    "unresolved": case["expected_strength"]
                    != source["strength"]["strength_level"],
                    "numeric_and_condition_facts_unchanged": True,
                }
            )
    assert len(changed) == 4 and len(original19) == 19
    assert sum(r["unresolved"] for r in original19) == 17
    public = [
        cohort("public-all367-" + label + "-first.jsonl.gz")
        for label in ("before", "source", "wheel")
    ]
    assert all(len(g) == 367 for g in public)
    assert canonical(public[1]) == canonical(
        cohort("public-all367-qualified-source-first.jsonl.gz")
    )
    public_affected = []
    for before, source, wheel in zip(*public):
        assert canonical(source) == canonical(wheel)
        assert before["pillars"] == source["pillars"]
        research, eligible = inputs[tuple(source["pillars"])]
        assert canonical(
            source["result"]["current_calculation"]["assessment"]
        ) == canonical(research["strength"]["assessment"])
        if not eligible:
            assert canonical(normalize(before)) == canonical(normalize(source)), before[
                "reference_id"
            ]
        else:
            public_affected.append(before["reference_id"])

            # Annotation, source identity and unknown status stay intact. Only
            # calculated-strength observations may reflect the new default.
            def annotations(rows):
                return [
                    {
                        k: v
                        for k, v in r.items()
                        if k
                        not in {
                            "current_model_strength",
                            "comparison_with_current_model",
                        }
                    }
                    for r in rows
                ]

            assert canonical(
                annotations(before["result"]["source_comparison"]["records"])
            ) == canonical(
                annotations(source["result"]["source_comparison"]["records"])
            )
        assert (
            source["result"]["source_comparison"][
                "full_original_text_conformance_certified"
            ]
            is False
        )
    assert len(public_affected) == 4
    evidence = []
    for backend in ("live", "source", "wheel"):
        with tarfile.open(D / ("protocols-" + backend + "-first.tar.gz")) as archive:
            proof = json.loads(archive.extractfile("proof.json").read())
        assert proof["responses"] == len(proof["rows"]) == 105
        assert proof["fixed_response_char_limit"] == 8192
        assert all(
            r["same_run_hash_verified"] and r["first_chars"] <= 8192
            for r in proof["rows"]
        )
        evidence.append(
            {
                "backend": backend,
                "actual_responses": 105,
                "paged": sum(r["paged"] for r in proof["rows"]),
                "largest_first_chars": max(r["first_chars"] for r in proof["rows"]),
                "new_models": 0,
            }
        )
    suites = {}
    for name in (
        "new-before",
        "new-after",
        "new-after-enum-correction",
        "new-qualified-source",
        "new-qualified-source-path-corrected",
        "new-wheel",
        "related-before",
        "related-after",
    ):
        root = ET.parse(D / (name + "-first.xml")).getroot()
        tests = root.findall(".//testcase")
        failed = [
            t.attrib["name"]
            for t in tests
            if t.find("failure") is not None or t.find("error") is not None
        ]
        suites[name] = {
            "total": len(tests),
            "failed": len(failed),
            "passed": len(tests) - len(failed),
            "failed_names": failed,
        }
    assert suites["new-before"]["failed"] == 6
    assert suites["new-after"]["failed"] == 4
    assert suites["new-qualified-source"]["failed"] == 1
    assert all(
        suites[n]["passed"] == 11 and suites[n]["failed"] == 0
        for n in (
            "new-after-enum-correction",
            "new-qualified-source-path-corrected",
            "new-wheel",
        )
    )
    assert (
        suites["related-before"]["failed"] == 3
        and suites["related-after"]["failed"] == 16
    )
    synthetic = [
        read(D / ("all600-" + backend + "-first.json"))
        for backend in ("source", "wheel")
    ]
    assert synthetic[0] == synthetic[1] and synthetic[0]["synthetic_cases"] == 600
    positive_protocols = []
    for backend in ("source", "wheel"):
        with tarfile.open(
            D / ("affiliation-protocols-" + backend + "-first.tar.gz")
        ) as archive:
            proof = json.loads(archive.extractfile("proof.json").read())
            assert proof["responses"] == 69 and len(proof["groups"]) == 24
            for row in proof["rows"]:
                assert row["first_chars"] <= 8192 and row["same_run_hash_verified"]
                payload = json.loads(
                    gzip.decompress(
                        archive.extractfile(
                            row["case"] + "/" + row["transport"] + "-full.json.gz"
                        ).read()
                    )
                )
                tool = row["case"].split("-synthetic-affiliation")[0]
                if tool == "analyze_destiny":
                    chain = payload["structure_profile"]["evidence_chain"]
                elif tool == "bazi_birth":
                    chain = payload["bazi_birth"]["structure_profile"]["evidence_chain"]
                else:
                    chain = payload[tool.removeprefix("bazi_") + "_analysis"][
                        "evidence_chain"
                    ]
                context = chain["classical_passage_relations"]
                assert context["effective_passage"] == "not_adjudicated"
                assert (
                    chain["force_components"]["engineering_composition"][
                        "strength_method_id"
                    ]
                    == "season_root_revelation_relations_v8"
                )
                (affiliated,) = [
                    r["receipt"]
                    for r in context["events"]
                    if r["receipt"]["status"] == "same_target_affiliation_only"
                ]
                assert affiliated["positions"] == ["day", "hour"]
                assert affiliated["outside_positions"] == ["hour"]
                assert affiliated["primary_formation"] == {
                    "kind": "三会",
                    "positions": ["year", "month", "day"],
                    "target": "木",
                }
                assert (
                    affiliated["additional_budget"] == 0.0
                    and affiliated["calculation_effect"] == "none"
                )
                if tool == "bazi_birth" and row["case"].endswith("-snapshot"):
                    assert all(
                        s in payload["snapshot_text"]
                        for s in (
                            "同目标附合",
                            "局外支不据此转化",
                            "不裁定全局成格或有效通关",
                        )
                    )
            positive_protocols.append(
                {
                    "backend": backend,
                    "actual_responses": 69,
                    "all11_tools_actual_affiliation_present": True,
                    "paged": sum(r["paged"] for r in proof["rows"]),
                    "largest_first_chars": max(r["first_chars"] for r in proof["rows"]),
                    "groups": proof["groups"],
                }
            )
    assert positive_protocols[0]["groups"] == positive_protocols[1]["groups"]
    return {
        "four_supported_geometry_corrections": changed,
        "all408_historical_defaults_identical": legacy_equal,
        "all404_unaffected_current_records_only_declared_metadata": True,
        "all367_source_wheel_complete_results_equal": True,
        "public_affected_rows": public_affected,
        "original19": original19,
        "leaf_differences": leaf_diffs,
        "protocols": evidence,
        "positive_affiliation_protocols": positive_protocols,
        "suites": suites,
        "new_classical_accuracy_credit": 0,
        "new_actual_model_executions": 0,
        "original19_model_semantic_acceptance": "not_tested",
        "independent_expert_review": "not_completed",
        "real_world_predictive_validity": "not_tested",
        "old_failed_gates_regraded": False,
        "full_goal_complete": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.open("x").write(
        json.dumps(audit(), ensure_ascii=False, indent=2) + "\n"
    )
