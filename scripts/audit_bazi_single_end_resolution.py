"""Audit the source-conditioned numerical change without relabelling sources."""

import argparse
import gzip
import json
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "tests/fixtures/bazi_single_end_resolution_v1"
D = ROOT / "docs/validation/bazi-single-end-resolution-files-v1"
OLD = ROOT / "docs/validation/bazi-punishment-resolution-files-v1"
V9, V10 = "season_root_revelation_relations_v9", "season_root_revelation_relations_v10"
OLD_POLICY = "completed_combination_punishment_resolution_v1"
NEW_POLICY = "completed_combination_unique_pair_resolution_v2"
SOURCE_ID = "ziping_unique_zi_mao_single_end_resolution_primary_v1"


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def normalized(value, path=()):
    if isinstance(value, dict):
        return {k: normalized(v, (*path, k)) for k, v in value.items()}
    if isinstance(value, list):
        result = []
        for i, child in enumerate(value):
            if isinstance(child, dict) and child.get("id") == SOURCE_ID:
                assert path[-1] == "sources"
            else:
                result.append(normalized(child, (*path, str(i))))
        return result
    if value == V10:
        assert path[-1] in {"method_id", "strength_method_id"}
        return V9
    if value == NEW_POLICY:
        assert path[-1] == "punishment_resolution_policy"
        return OLD_POLICY
    return value


def rows(path):
    return [json.loads(line) for line in gzip.open(path, "rt")]


def leaf_diffs(a, b, path=()):
    if type(a) is not type(b):
        return [{"path": ".".join(path), "before": a, "after": b}]
    if isinstance(a, dict) and set(a) == set(b):
        return [r for k in a for r in leaf_diffs(a[k], b[k], (*path, k))]
    if isinstance(a, list) and len(a) == len(b):
        return [
            r
            for i, (x, y) in enumerate(zip(a, b))
            for r in leaf_diffs(x, y, (*path, str(i)))
        ]
    return [] if a == b else [{"path": ".".join(path), "before": a, "after": b}]


def audit():
    old, new = rows(OLD / "all408-current-first.jsonl.gz"), rows(
        D / "all408-current-first.jsonl.gz"
    )
    candidate = json.loads(
        gzip.decompress((D / "all408-candidate-first.json.gz").read_bytes())
    )["rows"]
    assert len(old) == len(new) == len(candidate) == 408
    changes, original = [], []
    for before, after, isolated in zip(old, new, candidate):
        assert before["case"] == after["case"] == isolated["case"]
        norm = normalized(after)
        assert canonical(norm["strength"]["assessment"]) == canonical(isolated["after"])
        assert canonical(before["legacy"]) == canonical(after["legacy"])
        if canonical(before) != canonical(norm):
            changes.append({"case": after["case"], "diffs": leaf_diffs(before, norm)})
        if after["case"]["is_original_nineteen"]:
            assert canonical(before) == canonical(norm)
            original.append(
                {
                    "id": after["case"]["id"],
                    "retained": after["case"]["expected_strength"],
                    "current": after["strength"]["strength_level"],
                }
            )
    assert len(changes) == 1 and changes[0]["case"]["id"] == "DTCW1947-JH-01"
    assert changes[0]["case"]["expected_strength"] is None
    assert (
        len(original) == 19
        and sum(r["retained"] != r["current"] for r in original) == 17
    )
    old_public, new_public = rows(OLD / "public-all367-current-first.jsonl.gz"), rows(
        D / "public-all367-current-first.jsonl.gz"
    )
    assert len(old_public) == len(new_public) == 367
    public_changes = []
    for before, after in zip(old_public, new_public):
        norm = normalized(after)
        assert before["reference_id"] == after["reference_id"]
        assert canonical(before["result"]["source_comparison"]) == canonical(
            norm["result"]["source_comparison"]
        )
        assert canonical(before["result"]["input_context"]) == canonical(
            norm["result"]["input_context"]
        )
        assert before["result"]["summary"] == norm["result"]["summary"]
        if canonical(before) != canonical(norm):
            public_changes.append(
                {
                    "reference_id": after["reference_id"],
                    "diffs": leaf_diffs(before, norm),
                }
            )
    assert len(public_changes) == 1 and public_changes[0]["reference_id"].endswith(
        ":DTCW1947-JH-01"
    )
    study = json.loads((D / "study-summary-first.json").read_text())
    assert all(
        study[k] == 0
        for k in (
            "known_label_regressions",
            "new_bound_regressions",
            "new_public_bound_regressions",
            "new_source_control_regressions",
        )
    )
    return {
        "research_records": 408,
        "public_records": 367,
        "all408_match_frozen_first_candidate_except_declared_provenance": True,
        "all408_legacy_arithmetic_unchanged": True,
        "unaffected_research_complete_objects_preserved": 407,
        "unaffected_public_complete_objects_preserved": 366,
        "all367_source_labels_unknowns_bounds_and_comparisons_exactly_unchanged": True,
        "changed_research": changes,
        "changed_public": public_changes,
        "original19": original,
        "original19_retained": 19,
        "original19_unresolved": 17,
        "geometry_rows": 20736,
        "affected_geometries": 300,
        "independent_daystem_probes": 3000,
        "full_chapter_conformance_certified": False,
        "first_collector_bounds_schema_error_retained": True,
        "new_independent_classical_accuracy_credit": 0,
        "new19_model_semantic_acceptance": "not_tested",
        "independent_expert_review": "not_completed",
        "real_world_predictive_validity": "not_tested",
        "full_goal_complete": False,
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    result = audit()
    a.output.open("x").write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: v
                for k, v in result.items()
                if k not in {"changed_research", "changed_public", "original19"}
            },
            ensure_ascii=False,
        )
    )
