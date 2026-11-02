"""Audit the causal resolution fix without turning provenance into accuracy."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "tests/fixtures/bazi_punishment_resolution_v1"
D = ROOT / "docs/validation/bazi-punishment-resolution-files-v1"
BEFORE = ROOT / "docs/validation/bazi-branch-inventory-files-v1"
V8, V9 = "season_root_revelation_relations_v8", "season_root_revelation_relations_v9"
POLICY = "completed_combination_punishment_resolution_v1"
SOURCE_ID = "ziping_completed_combination_resolution_primary_v1"


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def normalize_provenance(value, path=(), changes=None):
    changes = [] if changes is None else changes
    if isinstance(value, dict):
        result = {}
        for key, child in value.items():
            if key == "punishment_resolution_policy":
                assert child == POLICY and path[-1] == "assessment"
                changes.append(".".join((*path, key)))
            else:
                result[key] = normalize_provenance(child, (*path, key), changes)
        return result
    if isinstance(value, list):
        result = []
        for i, child in enumerate(value):
            if isinstance(child, dict) and child.get("id") == SOURCE_ID:
                assert path[-1] == "sources"
                changes.append(".".join((*path, str(i))))
            else:
                result.append(normalize_provenance(child, (*path, str(i)), changes))
        return result
    if value == V9:
        assert path[-1] in {"method_id", "strength_method_id"}
        changes.append(".".join(path))
        return V8
    return value


def read_rows(path):
    return [json.loads(line) for line in gzip.open(path, "rt")]


def audit():
    protocol = json.loads((F / "protocol-first.json").read_text())
    assert (
        hashlib.sha256((ROOT / protocol["parent_receipt"]).read_bytes()).hexdigest()
        == protocol["parent_sha256"]
    )
    old = read_rows(BEFORE / "all408-source-final-first.jsonl.gz")
    new = read_rows(D / "all408-current-first.jsonl.gz")
    assert len(old) == len(new) == 408
    changes, original = [], []
    for a, b in zip(old, new):
        assert a["case"] == b["case"]
        assert canonical(a) == canonical(normalize_provenance(b, changes=changes))
        assert (
            a["strength"]["assessment"]["relations"]
            == b["strength"]["assessment"]["relations"]
        )
        assert canonical(a["legacy"]) == canonical(b["legacy"])
        if b["case"]["is_original_nineteen"]:
            original.append(
                {
                    "id": b["case"]["id"],
                    "retained": b["case"]["expected_strength"],
                    "computed": b["strength"]["strength_level"],
                    "pillars": b["case"]["pillars"],
                }
            )
    assert (
        len(original) == 19
        and sum(r["retained"] != r["computed"] for r in original) == 17
    )
    old_public = read_rows(BEFORE / "public-all367-current-first.jsonl.gz")
    new_public = read_rows(D / "public-all367-current-first.jsonl.gz")
    assert len(old_public) == len(new_public) == 367
    for a, b in zip(old_public, new_public):
        assert canonical(a) == canonical(normalize_provenance(b, changes=changes))
        assert a["result"]["source_comparison"] == b["result"]["source_comparison"]
    discovery = json.loads((D / "all20736-discovery-first.json").read_text())
    assert discovery["unsupported"] == 8 and discovery["supported"] == 8
    correction = json.loads(
        (F / "reference-input-order-correction-first.json").read_text()
    )
    assert (
        hashlib.sha256((F / "literal_reference.py").read_bytes()).hexdigest()
        == correction["first_reference_sha256"]
    )
    assert (
        hashlib.sha256((F / "literal_reference_corrected.py").read_bytes()).hexdigest()
        == correction["corrected_reference_sha256"]
    )
    return {
        "research_records": 408,
        "public_records": 367,
        "all408_and367_unchanged_except_declared_provenance": True,
        "all408_default_relations_exactly_unchanged": True,
        "all408_legacy_arithmetic_exactly_unchanged": True,
        "all367_source_comparisons_exactly_unchanged": True,
        "allowed_provenance_paths": sorted(set(changes)),
        "original19": original,
        "original19_retained": 19,
        "original19_unresolved": 17,
        "all20736_geometry_discovery": {
            k: v for k, v in discovery.items() if k != "bad"
        },
        "new_strength_method": V9,
        "punishment_coefficient_unchanged": 0.9,
        "diagnostic_only_punishment_coefficient": 0.8,
        "first_independent_mass_reference_had_input_order_error": True,
        "mass_reference_corrected_after_first_production_edit": True,
        "original_reference_and_raw5000_before_results_retained": True,
        "new_numeric_or_source_label_credit_for_original19": 0,
        "new19_model_semantic_acceptance": "not_tested",
        "independent_expert_review": "not_completed",
        "real_world_predictive_validity": "not_tested",
        "full_goal_complete": False,
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    value = audit()
    args.output.open("x").write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: v
                for k, v in value.items()
                if k not in {"original19", "allowed_provenance_paths"}
            },
            ensure_ascii=False,
        )
    )
