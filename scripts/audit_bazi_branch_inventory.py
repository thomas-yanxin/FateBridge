"""Audit additive branch facts against complete, retained pre-change outputs."""

import argparse
import gzip
import hashlib
import json
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "docs/validation/bazi-branch-inventory-files-v1"
F = ROOT / "tests/fixtures/bazi_branch_inventory_v1"
BEFORE = ROOT / "docs/validation/bazi-month-command-integrity-files-v1"


def rows(path):
    return [json.loads(line) for line in gzip.open(path, "rt")]


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def audit():
    protocol = json.loads((F / "protocol-first.json").read_text())
    assert (
        hashlib.sha256((ROOT / protocol["parent_receipt"]).read_bytes()).hexdigest()
        == protocol["parent_sha256"]
    )
    assert (
        hashlib.sha256(
            (ROOT / "src/fatebridge/core/strength.py").read_bytes()
        ).hexdigest()
        == protocol["initial_files_sha256"]["src/fatebridge/core/strength.py"]
    )
    old = rows(BEFORE / "all408-source-final-first.jsonl.gz")
    new = rows(D / "all408-current-first.jsonl.gz")
    assert len(old) == len(new) == 408
    inventory_count, node_refs, original = 0, 0, []
    for a, b in zip(old, new):
        assert a["case"] == b["case"]
        assert canonical(a["strength"]) == canonical(b["strength"])
        assert canonical(a["legacy"]) == canonical(b["legacy"])
        natal = deepcopy(b["natal"])
        context = natal["classical_passage_relations"]
        inventory = context.pop("branch_combination_candidates")
        assert (
            inventory["calculation_effect"] == "none"
            and inventory["effective_combination"] == "not_adjudicated"
        )
        inventory_count += len(inventory["candidates"])
        for node in context["nodes"]:
            refs = node.pop("potential_branch_candidate_refs")
            node_refs += len(refs or [])
        assert canonical(a["natal"]) == canonical(natal)
        if b["case"]["is_original_nineteen"]:
            original.append(
                {
                    "id": b["case"]["id"],
                    "pillars": b["case"]["pillars"],
                    "retained_expected": b["case"]["expected_strength"],
                    "computed": b["strength"]["strength_level"],
                    "agrees": b["case"]["expected_strength"]
                    == b["strength"]["strength_level"],
                }
            )
    assert len(original) == 19 and sum(not r["agrees"] for r in original) == 17
    old_public = rows(BEFORE / "public-all367-source-final-first.jsonl.gz")
    new_public = rows(D / "public-all367-current-first.jsonl.gz")
    assert len(old_public) == len(new_public) == 367
    for a, b in zip(old_public, new_public):
        clean = deepcopy(b)
        assert (
            clean["result"]["current_calculation"].pop("branch_combination_candidates")[
                "calculation_effect"
            ]
            == "none"
        )
        assert canonical(a) == canonical(clean)
    return {
        "all408_strength_and_legacy_exact_values_and_types_unchanged": True,
        "all408_natal_changes_only_declared_inventory_and_refs": True,
        "all367_public_changes_only_declared_sidecar": True,
        "research_records": len(new),
        "public_records": len(new_public),
        "research_candidate_occurrences": inventory_count,
        "research_node_candidate_refs": node_refs,
        "original19": original,
        "original19_retained": 19,
        "original19_unresolved": 17,
        "new_numeric_or_source_label_changes": 0,
        "new_classical_accuracy_credit": 0,
        "new19_model_semantic_acceptance": "not_tested",
        "real_world_predictive_validity": "not_tested",
        "full_goal_complete": False,
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    result = audit()
    args.output.open("x").write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {k: v for k, v in result.items() if k != "original19"}, ensure_ascii=False
        )
    )
