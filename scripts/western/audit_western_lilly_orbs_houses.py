"""Compare named Lilly facts with manually frozen pages, not predictive efficacy."""

import argparse
import hashlib
import json
import zipfile
from fractions import Fraction
from pathlib import Path

from fatebridge.core.astrology_horary import _applying_aspect
from fatebridge.core.lilly_houses import house_condition
from fatebridge.core.lilly_orbs import full_orbs, pair_radius

ROOT = Path(__file__).resolve().parents[2]


def audit():
    fixture = ROOT / "tests/fixtures/western-lilly-orbs-houses-1647.json"
    reference = json.loads(fixture.read_text())
    archive = fixture.with_name("western-lilly-orbs-houses-sources.zip")
    failures, source_checks, pair_checks = [], [], []
    with zipfile.ZipFile(archive) as z:
        for row in reference["source_receipts"]:
            actual = hashlib.sha256(z.read(f"{row['page']}.{row['type']}")).hexdigest()
            passed = actual == row["sha256"]
            source_checks.append({**row, "passed": passed})
            if not passed:
                failures.append(f"source:{row['page']}.{row['type']}")
    for profile, table in reference["orb_tables"].items():
        if full_orbs(profile) != table:
            failures.append(f"table:{profile}")
        for a in table:
            for b in table:
                expected = (Fraction(str(table[a])) + Fraction(str(table[b]))) / 2
                actual = pair_radius(a, b, profile)
                pair_checks.append(
                    dict(
                        profile=profile,
                        planets=[a, b],
                        expected=str(expected),
                        actual=str(actual),
                        passed=actual == expected,
                    )
                )
                if actual != expected:
                    failures.append(f"pair:{profile}:{a}:{b}")
    counterexamples = []
    for row in reference["counterexamples"]:
        states = [
            dict(planet=p, longitude=lon, speed=1.0)
            for p, lon in zip(row["planets"], row["longitudes"])
        ]
        results = {
            key: _applying_aspect(*states, orb_profile=profile) is not None
            for key, profile in zip(("first", "second"), reference["orb_tables"])
        }
        passed = all(results[key] is row[key] for key in results)
        counterexamples.append({**row, "observed_after": results, "passed": passed})
        if not passed:
            failures.append(f"counterexample:{row['kind']}")
    house_checks = []
    for rank, house in enumerate(reference["p48_house_strength_order"], 1):
        actual = house_condition(house, "R", "Tropic")
        passed = (
            actual["p48_strength_rank"] == rank
            and actual["p115_house_points"]
            == reference["p115_house_points"][str(house)]
            and house in reference["house_classes"][actual["house_class"]]
        )
        house_checks.append({"actual": actual, "passed": passed})
        if not passed:
            failures.append(f"house:{house}")
    return {
        "scope": "Named manually transcribed p107 tables, arithmetic and pp48/115 house rows only. Shared rows are not independent astronomical observations; not a whole-method acceptance audit.",
        "fixture_sha256": hashlib.sha256(fixture.read_bytes()).hexdigest(),
        "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "production_generated_expected": False,
        "source_checks": source_checks,
        "pair_checks": pair_checks,
        "counterexamples": counterexamples,
        "house_checks": house_checks,
        "failures": failures,
        "named_frozen_facts_passed": not failures,
        "full_original_text_acceptance": False,
        "expert_reviewed": False,
        "real_world_efficacy": "not_tested",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "named_frozen_facts_passed": result["named_frozen_facts_passed"],
                "failures": result["failures"],
                "full_original_text_acceptance": False,
            }
        )
    )
    return 0 if result["named_frozen_facts_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
