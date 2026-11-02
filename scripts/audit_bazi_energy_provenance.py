"""Check all retained records and native parts without relabelling source cases."""

import argparse
import gzip
import json
from fractions import Fraction
from pathlib import Path

from fatebridge.core.output_source_annotations import SourceCurrentCalculation

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "docs/validation/bazi-energy-provenance-files-v1"
OLD = ROOT / "docs/validation/bazi-single-end-resolution-files-v1"
PARTS = ("physical_hidden", "synthetic_branch", "non_day_visible")


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def rows(path):
    return [json.loads(line) for line in gzip.open(path, "rt")]


def strip_additions(value, path=()):
    if isinstance(value, dict):
        result = {}
        for key, child in value.items():
            if (
                key == "energy_unrounded"
                and len(path) >= 2
                and path[-2] == "combination_contributions"
            ):
                assert (
                    path[:2]
                    in {("strength", "assessment"), ("result", "current_calculation")}
                    or path[0] == "legacy"
                )
                continue
            if key == "energy_provenance":
                assert path in {
                    ("natal", "force_components"),
                    ("result", "current_calculation"),
                }
                continue
            result[key] = strip_additions(child, (*path, key))
        return result
    if isinstance(value, list):
        return [
            strip_additions(child, (*path, str(i))) for i, child in enumerate(value)
        ]
    return value


def audit():
    before, after = rows(OLD / "all408-current-first.jsonl.gz"), rows(
        D / "all408-current-first.jsonl.gz"
    )
    independent = json.loads(
        gzip.decompress((D / "independent-all408-parts-first.json.gz").read_bytes())
    )
    assert len(before) == len(after) == len(independent) == 408
    originals, max_residual, max_reference_error, native_rows = [], 0.0, 0.0, 0
    for old, new, reference in zip(before, after, independent):
        assert canonical(old) == canonical(strip_additions(new))
        assert old["case"] == new["case"] == reference["case"]
        p = new["natal"]["force_components"]["energy_provenance"]
        assert (
            p["status"] == "complete"
            and p["strength_method_id"] == "season_root_revelation_relations_v10"
        )
        for front in p["fronts"].values():
            max_residual = max(max_residual, abs(front["residual"]))
            assert abs(front["residual"]) <= 1e-12
            for part in PARTS:
                expected = float(Fraction(reference["parts"][front["element"]][part]))
                error = abs(expected - front[part]["energy_unrounded"])
                max_reference_error = max(max_reference_error, error)
                assert error <= 1e-12
        for row in new["strength"]["assessment"]["combination_contributions"]:
            native_rows += 1
            assert row["energy"] == round(row["energy_unrounded"], 6)
        if new["case"]["is_original_nineteen"]:
            originals.append(
                {
                    "id": new["case"]["id"],
                    "pillars": new["case"]["pillars"],
                    "source_label": new["case"]["expected_strength"],
                    "current_grade": new["strength"]["strength_level"],
                    "source_label_authority": "retained_developer_annotation_not_second_expert",
                    "fronts": p["fronts"],
                    "month_duty_status": new["natal"]["month_command"][
                        "intra_month_duty"
                    ]["status"],
                    "classical_adjudication": new["natal"]["force_components"][
                        "classical_adjudication"
                    ],
                    "passage": new["natal"]["classical_passage"],
                    "passage_relations": new["natal"]["classical_passage_relations"],
                    "new_classical_accuracy_credit": 0,
                }
            )
    assert (
        len(originals) == 19
        and sum(r["source_label"] != r["current_grade"] for r in originals) == 17
    )
    old_public, new_public = rows(OLD / "public-all367-current-first.jsonl.gz"), rows(
        D / "public-all367-current-first.jsonl.gz"
    )
    assert len(old_public) == len(new_public) == 367
    for old, new in zip(old_public, new_public):
        assert canonical(old) == canonical(strip_additions(new))
        assert (
            new["result"]["current_calculation"]["energy_provenance"]["status"]
            == "complete"
        )
        SourceCurrentCalculation.model_validate(new["result"]["current_calculation"])
    return {
        "research_records": 408,
        "public_records": 367,
        "all_previous_values_and_types_preserved_except_declared_additions": True,
        "native_synthetic_rows": native_rows,
        "all2040_fronts_independently_checked": True,
        "maximum_native_closure_residual": max_residual,
        "maximum_independent_part_error": max_reference_error,
        "original19": originals,
        "original19_count": 19,
        "original19_unresolved": 17,
        "new_classical_accuracy_credit": 0,
        "new_model_executions": 0,
        "new19_explanation_acceptance": "not_tested",
        "real_world_predictive_validity": "not_tested",
        "whole_goal_complete": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit()
    args.output.open("x").write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {k: v for k, v in result.items() if k != "original19"}, ensure_ascii=False
        )
    )
