#!/usr/bin/env python3
"""Compare production observations with frozen, source-authored case annotations.

This is an audit, not a classical inference engine. Source labels are never
created from production outputs, and missing adjudication stays unsupported.
Exit 1 means classical acceptance has NOT passed; it is an expected audit result
until the reported gaps are resolved, not permission to replace the oracle.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "tests/data/bazi_classical_v1"
FREEZE = CORPUS / "provenance/reference-freeze.json"
PILLAR_NAMES = ("year", "month", "day", "hour")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_frozen_corpus(corpus: Path = CORPUS, freeze: Path = FREEZE) -> dict[str, Any]:
    manifest = read_json(freeze)
    expected_files = set(manifest["files"])
    if {p.name for p in corpus.glob("*.json")} != expected_files:
        raise ValueError("Reference file set differs from the frozen manifest")
    else:
        pass
    for name, expected_hash in manifest["files"].items():
        if digest(corpus / name) != expected_hash:
            raise ValueError(f"Reference changed after freeze: {name}")
        else:
            pass
    result = {p.stem: read_json(p) for p in sorted(corpus.glob("*.json"))}
    ids = [r["id"] for group in ("cases", "probes") for r in result[group]]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate source record id")
    else:
        pass
    for case in result["cases"]:
        if len(case["pillars"]) != 4 or any(
            not isinstance(p, str) or len(p) != 2 for p in case["pillars"]
        ):
            raise ValueError("Source case must contain four explicit pillars")
        else:
            pass
        if case["adjudication"]["strength"] not in (None, "强", "弱", "中和"):
            raise ValueError("Invalid source strength annotation")
        else:
            pass
    result["freeze"] = manifest
    return result


def observe(chart: list[str]) -> dict[str, Any]:
    # Load production only after independent source labels have been verified.
    from fatebridge.core.classical import determine_monthly_structure
    from fatebridge.core.elements import ElementAnalysis
    from fatebridge.core.rules import BaZiRules

    if len(chart) != 4 or any(not isinstance(p, str) or len(p) != 2 for p in chart):
        raise ValueError("Unknown or incomplete four pillars cannot be observed")
    else:
        pass
    pillars = {key: (p[0], p[1]) for key, p in zip(PILLAR_NAMES, chart)}
    elements = ElementAnalysis.comprehensive_analysis(pillars)
    profile = BaZiRules.build_structure_profile(pillars, elements)
    return {
        "elements": elements,
        "monthly_structure": determine_monthly_structure(pillars, pillars["day"][0]),
        "structure_profile": profile,
    }


def compare(case: dict[str, Any], actual: dict[str, Any]) -> dict[str, Any]:
    from fatebridge.core.month_use import match_month_uses

    reference = case["adjudication"]
    monthly = actual["monthly_structure"]
    source_god = reference["month_pattern"].removeprefix("杂气")
    month_use_match = match_month_uses(monthly["use_resolution"], (source_god,))
    strength = actual["elements"]["day_master"]["strength_level"]
    expected_strength = reference["strength"]
    return {
        "month_pattern": {
            "reference": reference["month_pattern"],
            "actual": monthly,
            "status": (
                "match"
                if monthly["label"].removesuffix("格") == source_god
                else "disagreement"
            ),
            "scope": "取格名称对比，不等于成格验收",
            "downstream": ["格局用神", "成败救应的起点", "喜忌解释"],
        },
        "month_use_identity": {
            "reference_ten_god": source_god,
            **month_use_match,
            "scope": "核对所标注十神是否有合格取用见证。会支正偏未定时保留待裁，成格另审。",
        },
        "strength": {
            "reference": expected_strength,
            "actual": strength,
            "status": (
                "not_adjudicated_by_source"
                if expected_strength is None
                else "match" if strength == expected_strength else "disagreement"
            ),
            "basis": reference["strength_basis"],
            "downstream": ["扶抑五行层", "喜忌冲突分层", "事业行业类比"],
        },
        "formation": {
            "reference": reference["formation"],
            "status": "unsupported",
            "actual_scope": "ten_god_cooccurrence_candidates_only",
            "missing": reference["required_reasoning"],
            "downstream": ["成格与破格解释", "相神识别", "喜忌条件"],
        },
        "useful_roles": {
            "reference": reference["roles"],
            "status": "different_semantic_object_not_accepted",
            "actual_scope": "layered_element_conflict_policy",
            "reason": "月令格局用神、相神与五行扶抑列表不能直接作集合相等比较。",
            "downstream": ["喜用解释", "行业建议依据"],
        },
    }


def audit(split: str = "all") -> dict[str, Any]:
    data = load_frozen_corpus()
    cases = [c for c in data["cases"] if split == "all" or c["split"] == split]
    results = []
    for case in cases:
        actual = observe(case["pillars"])
        variants = []
        if case["variant"]:
            variants.append(
                {
                    "source": case["variant"],
                    "actual": observe(case["variant"]["pillars"]),
                    "status": "secondary_witness_not_independently_verified",
                }
            )
        else:
            pass
        results.append(
            {
                "id": case["id"],
                "source": case["source"],
                "reference": case["adjudication"],
                "actual": actual,
                "comparison": compare(case, actual),
                "variants": variants,
                "disagreements": case["disagreements"],
            }
        )
    from fatebridge.core.classical import twelve_life_stage
    from fatebridge.utils.data import BRANCH_HIDDEN_STEMS, STEM_ELEMENTS

    probes = []
    for probe in data["probes"]:
        if split != "all" and probe["split"] != split:
            continue
        else:
            pass
        inp = probe["input"]
        if "day_stem" in inp:
            day_element = STEM_ELEMENTS[inp["day_stem"]][0]
            hidden_root = any(
                STEM_ELEMENTS[s][0] == day_element
                for s in BRANCH_HIDDEN_STEMS[inp["branch"]]
            )
            probes.append(
                {
                    "reference": probe,
                    "actual_hidden_stem_root": hidden_root,
                    "life_stage": twelve_life_stage(inp["day_stem"], inp["branch"]),
                    "hidden_root_status": (
                        "match"
                        if hidden_root == probe["expected"]["hidden_stem_root"]
                        else "disagreement"
                    ),
                    "text_root_scope": (
                        "same_local_result"
                        if hidden_root == probe["expected"]["text_root"]
                        else "root_definition_difference"
                    ),
                    "production_total_strength_called": False,
                }
            )
        else:
            probes.append(
                {
                    "reference": probe,
                    "status": "insufficient_input_not_called",
                    "production_total_strength_called": False,
                }
            )
    strengths = [r["comparison"]["strength"]["status"] for r in results]
    month_use_statuses = [
        r["comparison"]["month_use_identity"]["status"] for r in results
    ]
    return {
        "profile_id": data["profile"]["profile_id"],
        "split": split,
        "independence": data["profile"]["independence"],
        "reference_hashes": data["freeze"]["files"],
        "source_fingerprints": {
            str(p.relative_to(ROOT)): digest(p)
            for p in (
                ROOT / "src/fatebridge/core/elements.py",
                ROOT / "src/fatebridge/core/rules.py",
                ROOT / "src/fatebridge/core/classical.py",
                ROOT / "src/fatebridge/core/month_use.py",
                ROOT / "src/fatebridge/core/strength.py",
                ROOT / "src/fatebridge/core/storage_movement.py",
                ROOT / "src/fatebridge/core/classical_stages.py",
                ROOT / "src/fatebridge/core/classical_roots.py",
                ROOT / "src/fatebridge/core/classical_force.py",
                ROOT / "src/fatebridge/core/classical_routes.py",
                ROOT / "src/fatebridge/core/classical_seasonal.py",
                ROOT / "src/fatebridge/core/bazi/bazi_evidence.py",
                ROOT / "src/fatebridge/core/useful_elements.py",
                ROOT / "src/fatebridge/utils/data.py",
                ROOT / "uv.lock",
                Path(__file__).resolve(),
            )
        },
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "summary": {
            "full_cases": len(results),
            "month_pattern_matches": sum(
                r["comparison"]["month_pattern"]["status"] == "match" for r in results
            ),
            "month_pattern_disagreements": sum(
                r["comparison"]["month_pattern"]["status"] == "disagreement"
                for r in results
            ),
            "month_use_identity": {
                status: month_use_statuses.count(status)
                for status in (
                    "matched",
                    "requires_identity_adjudication",
                    "not_observed",
                )
            },
            "strength_adjudicated": sum(
                s != "not_adjudicated_by_source" for s in strengths
            ),
            "strength_matches": strengths.count("match"),
            "strength_disagreements": strengths.count("disagreement"),
            "strength_unknown_in_source": strengths.count("not_adjudicated_by_source"),
            "formation_unsupported": len(results),
            "useful_role_semantics_not_accepted": len(results),
            "local_or_unknown_probes": len(probes),
            "classical_acceptance_passed": False,
            "real_world_efficacy": "not_tested",
        },
        "cases": results,
        "probes": probes,
        "disagreements": data["disagreements"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--split", choices=("all", "development", "reserved"), default="all"
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.split)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result["summary"], ensure_ascii=False))
    return 0 if result["summary"]["classical_acceptance_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
else:
    pass
