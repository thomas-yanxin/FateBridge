"""Reproduce the cutoff counterexample without treating a score as validity."""

import argparse
import json
import random
from datetime import datetime, timezone
from pathlib import Path

from fatebridge.core.astro.aspects import (
    _build_directional_relative_aspects,
    _flatten_directional_relative_aspects,
)
from fatebridge.core.astro.parts import _build_planet_record
from fatebridge.core.astro.relationship_scoring import (
    compatibility_with_evidence,
    relationship_scoring_policy,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = "tests/fixtures/western-relationship-score-boundaries.json"


def audit():
    fixture = json.loads((ROOT / FIXTURE).read_text())
    names = fixture["body_order"]
    charts = [
        [
            _build_planet_record(name, angle, 0, 0, "whole_sign")
            for name, angle in zip(names, fixture[role + "_longitudes"])
        ]
        for role in ("inner", "outer")
    ]
    steps = [
        min((a - b) % 360, (b - a) % 360) // 30
        for a in fixture["inner_longitudes"]
        for b in fixture["outer_longitudes"]
    ]
    counts = {
        "positive": sum(step in {0, 2, 4} for step in steps),
        "negative": sum(step in {3, 6} for step in steps),
    }
    if counts != fixture["independent_integer_step_counts"]:
        raise RuntimeError("Frozen integer-step enumeration differs")
    rng = random.Random(39183)
    rows = []
    for inner, outer in (charts, list(reversed(charts))):
        contacts = _flatten_directional_relative_aspects(
            _build_directional_relative_aspects(inner, outer),
            source_key="inner",
            target_key="outer",
        )
        contacts.sort(key=lambda row: (row["orb"], row["inner"], row["outer"]))
        score, evidence = compatibility_with_evidence(inner, outer, contacts)
        if score != fixture["expected_scores"]:
            raise RuntimeError("Version 2 differs from frozen arithmetic")
        for _ in range(30):
            rng.shuffle(contacts)
            if compatibility_with_evidence(inner, outer, contacts)[0] != score:
                raise RuntimeError("Contact ordering changed the version 2 score")
        rows.append(
            {
                "current_scores": score,
                "evidence": evidence,
            }
        )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": fixture["kind"],
        "policy": relationship_scoring_policy(),
        "independent_integer_step_counts": counts,
        "rows": rows,
        "interpretation_limits": [
            "Exact-boundary and permutation regressions are unit invariants, not an external astronomy oracle",
            "24 contacts, positive conjunctions, equal weights and baseline 50 remain uncalibrated conventions",
            "Ptolemy IV.7 prioritizes Sun, Moon, Ascendant and Fortune and is not implemented by this heuristic",
            "Full original-text conformity, actual model interpretation and real-world prediction are not established",
        ],
        "original_text_scope_reviewed": {
            "edition": "Ptolemy, Tetrabiblos, F. E. Robbins, Loeb 1940",
            "section": "IV.7",
            "url": "https://penelope.uchicago.edu/Thayer/E/Roman/Texts/Ptolemy/Tetrabiblos/4B%2A.html#7",
            "independent_expert_collation": False,
            "complete_method_implemented": False,
        },
        "all_three_full_marks_established": False,
        "empirical_relationship_validation": False,
        "authority_certified": False,
    }


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit()
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    )
    print("Current role symmetry, exact ties and permutation checks passed")


if __name__ == "__main__":
    main()
