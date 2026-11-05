"""Compare the full Wujing cohort with its own frozen sixteen-name definition."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from scripts.audit_taiyi_wujing_facsimile import audit as native_audit

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/fixtures/taiyi_wujing_names_v47"
FREEZE_SHA = "050b16b4e2af8f31ebe44d8f59fd9b0c1ef318116f8d205306eb006d2ec299f2"
NAME_FIELDS = {"wenchang_palace", "shiji"}


def verify(corpus: Path = CORPUS) -> dict[str, Any]:
    def sha(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    if sha(corpus / "freeze.json") != FREEZE_SHA:
        raise ValueError("武经同书名位冻结指纹不符")
    frozen = json.loads((corpus / "freeze.json").read_text())
    for name, expected in frozen["files"].items():
        if Path(name).name != name or sha(corpus / name) != expected:
            raise ValueError(f"武经同书名位来源指纹不符：{name}")
    for name, expected in frozen["source_pins"].items():
        if sha(ROOT / name) != expected:
            raise ValueError(f"武经原始比较层指纹不符：{name}")
    profile: dict[str, Any] = json.loads((corpus / "name-profile.json").read_text())
    entries = profile["entries"]
    if (
        len(entries) != 16
        or len({r["name"] for r in entries}) != 16
        or len({r["position"] for r in entries}) != 16
    ):
        raise ValueError("武经十六神名位范围不符")
    return profile


def resolve_name(literal: Any, profile: dict[str, Any]) -> dict[str, Any]:
    """Source-only resolution: no runtime value is accepted as an argument."""
    if not isinstance(literal, str):
        return {"value": None, "reason": "no_literal_name"}
    normalized = literal.translate(str.maketrans(profile["glyph_only_normalization"]))
    candidates = [r for r in profile["entries"] if normalized.startswith(r["name"])]
    if len(candidates) != 1:
        return {
            "value": None,
            "literal": literal,
            "normalized_literal": normalized,
            "reason": "unmapped_or_ambiguous_name",
        }
    entry = candidates[0]
    return {
        "value": entry["position"],
        "literal": literal,
        "normalized_literal": normalized,
        "name_prefix": entry["name"],
        "unadjudicated_suffix": normalized[len(entry["name"]) :],
        "source_clause": entry["literal_clause"],
        "profile": profile["id"],
        "whole_annotation_conformance_assessed": False,
    }


def compare(current: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    # Keep the original evidence and grades independent of future runtime repairs.
    if profile != verify():
        raise ValueError("不能替换冻结的武经同书名位表")
    baseline = native_audit()
    actuals = {
        (r["id"], c["original_comparison"]["actual_field"]): c["actual_value"]
        for r in current["source_rows"]
        for c in r["comparisons"]
    }
    expected_keys = {
        (r["id"], c["original_comparison"]["actual_field"])
        for r in baseline["source_rows"]
        for c in r["comparisons"]
    }
    if (
        len(current["source_rows"]) != 144
        or any(len(r["comparisons"]) != 10 for r in current["source_rows"])
        or len(actuals) != 1440
        or set(actuals) != expected_keys
    ):
        raise ValueError("武经1440字段范围不符")
    totals = {
        key: {"required": 144, "matching": 0, "different": 0, "unknown": 0}
        for key in baseline["field_totals"]
    }
    rows, changes, differences, unknowns = [], [], [], []
    for row in baseline["source_rows"]:
        comparisons = []
        for old in row["comparisons"]:
            original = old["original_comparison"]
            field = original["actual_field"]
            observation = original["source_observation"]
            resolution = {
                "value": old["effective_source_value"],
                "reason": "v46_nonname",
            }
            if field in NAME_FIELDS:
                native = old["native_reading"]
                if native is not None:
                    if native["resolution"] in {
                        "explicit_primary_name",
                        "unresolved_name_identity",
                    }:
                        resolution = resolve_name(native["literal"], profile)
                    else:
                        resolution = {
                            "value": None,
                            "reason": native["resolution"],
                            "literal": native["literal"],
                        }
                elif observation["status"] == "literal_text":
                    resolution = resolve_name(observation["value"], profile)
                else:
                    resolution = {"value": None, "reason": observation["status"]}
            value = resolution["value"]
            actual = actuals[row["id"], field]
            status = (
                "unknown"
                if value is None
                else "matching" if value == actual else "different"
            )
            totals[observation["field"]][status] += 1
            item = {
                "id": row["id"],
                "field": field,
                "v46_source_value": old["effective_source_value"],
                "source_resolution": resolution,
                "actual_value": actual,
                "comparison_status": status,
            }
            comparisons.append(item)
            if value != old["effective_source_value"]:
                changes.append(copy.deepcopy(item))
            if status == "different":
                differences.append(copy.deepcopy(item))
            if status == "unknown":
                unknowns.append(copy.deepcopy(item))
        rows.append({"id": row["id"], "comparisons": comparisons})
    return {
        "completion_claim": False,
        "profile": copy.deepcopy(profile),
        "source_freeze_sha256": FREEZE_SHA,
        "required_rows": 144,
        "required_observations": 1440,
        "name_fields_referenced": 288,
        "current_actual_rule_profile": copy.deepcopy(
            current["current_literal_layer"]["actual_rule_profile"]
        ),
        "original_v46_layer": baseline,
        "old_differences_retained": baseline["old_differences_retained"],
        "source_rows": rows,
        "field_totals": totals,
        "source_reference_changes": changes,
        "differences": differences,
        "unknowns": unknowns,
        "conflict_adjudicated": False,
        "production_arithmetic_changed": False,
        "new_dated_cases": 0,
        "new_model_calls": 0,
        "independent_human_reviews": 0,
        "whole_calendar_acceptance_passed": False,
        "whole_classic_acceptance_passed": False,
        "whole_explanation_fidelity_acceptance_passed": False,
        "real_world_efficacy": "not_tested",
    }


def audit() -> dict[str, Any]:
    profile = verify()
    return compare(native_audit(), profile)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = audit()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "required_observations": 1440,
                "different": len(report["differences"]),
                "unknown": len(report["unknowns"]),
                "whole_classic_acceptance_passed": False,
            }
        )
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
