"""Reproduce primary-text direction and policy sensitivity checks without services."""

import argparse
import hashlib
import json
from dataclasses import asdict, fields, replace
from pathlib import Path

from fatebridge.core.elements import ElementAnalysis
from fatebridge.core.strength import DEFAULT_POLICY, _evaluate

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/bazi-strength-reference.json"


def build_report():
    fixture = json.loads(FIXTURE.read_text())
    rows = []
    for case in fixture["cases"] + fixture["additional_cases"]:
        pillars = {k: tuple(v) for k, v in case["pillars"].items()}
        phases = ElementAnalysis.seasonal_phases(pillars["month"][1])
        result = ElementAnalysis.analyze_day_master_strength(pillars)
        assessment = result["assessment"]
        flips, trials = [], 0
        for parameter in fields(DEFAULT_POLICY):
            for scale in (0.85, 1.15):
                value = getattr(DEFAULT_POLICY, parameter.name) * scale
                if parameter.name in {
                    "clash_winner",
                    "clash_loser",
                    "clash_equal",
                    "punishment",
                    "binding",
                    "transformation_transfer",
                    "partial_transfer",
                }:
                    value = min(1.0, value)
                trial = _evaluate(
                    pillars, phases, replace(DEFAULT_POLICY, **{parameter.name: value})
                )
                trials += 1
                if trial["strength_level"] != assessment["strength_level"]:
                    flips.append(
                        {
                            "parameter": parameter.name,
                            "scale": scale,
                            "strength": trial["strength_level"],
                        }
                    )
        rows.append(
            {
                "id": case["id"],
                "pillars": case["pillars"],
                "reference_strength": case["expected_strength"],
                "computed_strength": result["strength_level"],
                "direction_matches": result["strength_level"]
                == case["expected_strength"],
                "support_share": round(assessment["support_share"], 6),
                "decision_rule": assessment["structural_decision"]["rule"],
                "requires_special_structure_review": assessment[
                    "requires_special_structure_review"
                ],
                "stress_trials": trials,
                "stress_label_changes": flips,
            }
        )
    return {
        "method_id": "season_root_revelation_relations_v2",
        "reference_fixture_sha256": hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),
        "protocol": fixture["protocol"],
        "parameters": asdict(DEFAULT_POLICY),
        "scope": "原文规则和方向对照；并非独立统计盲测或现实预测效度验证。极旺极弱样例偏多，不代表全部命局。",
        "summary": {
            "reference_cases": len(rows),
            "direction_matches": sum(r["direction_matches"] for r in rows),
            "stress_trials": sum(r["stress_trials"] for r in rows),
            "stress_label_changes": sum(len(r["stress_label_changes"]) for r in rows),
        },
        "cases": rows,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Optional report destination")
    args = parser.parse_args()
    text = json.dumps(build_report(), ensure_ascii=False, indent=2) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
    print(json.dumps(json.loads(text)["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
