"""Audit the frozen Lilly cells and printed examples, not empirical predictions."""

import argparse
import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal, localcontext
from math import inf, nextafter
from pathlib import Path

from fatebridge.core.lilly import dignity_at, pair_reception

ROOT = Path(__file__).resolve().parents[2]


def audit():
    reference_path = ROOT / "tests/fixtures/western-lilly-reception-1647.json"
    reference = json.loads(reference_path.read_text())
    failures = []
    comparisons = 0
    with localcontext() as context:
        context.prec = 1200
        for index, cells in enumerate(reference["term_endpoints"]):
            for _, endpoint in cells[1:]:
                boundary = float(index * 30 + endpoint)
                for value in (
                    nextafter(boundary, -inf),
                    boundary,
                    nextafter(boundary, inf),
                ):
                    longitude = Decimal.from_float(value) % 360
                    sign_index, degree = int(longitude // 30), longitude % 30
                    sign = reference["term_endpoints"][sign_index][0]
                    bound = next(
                        lord
                        for lord, end in reference["term_endpoints"][sign_index][1:]
                        if degree < end
                    )
                    exaltation = next(
                        (
                            p
                            for p, (s, _) in reference["exaltations"].items()
                            if s == sign
                        ),
                        None,
                    )
                    for sect in ("day", "night"):
                        triplicity = next(
                            row[sect]
                            for row in reference["triplicity"]
                            if sign in row["signs"]
                        )
                        expected = {
                            "rulership": reference["domicile"][sign_index],
                            "exaltation": exaltation,
                            "triplicity": triplicity,
                            "bound": bound,
                            "face": reference["faces"][sign_index][
                                int(degree // 10) + 1
                            ],
                        }
                        for planet in reference["exaltations"]:
                            actual = dignity_at(planet, value, sect)
                            held = [
                                kind
                                for kind, lord in expected.items()
                                if lord == planet
                            ]
                            comparisons += 1
                            if (
                                actual["lords"] != expected
                                or actual["dignities"] != held
                                or actual["peregrine"] != (not held)
                            ):
                                failures.append(
                                    {
                                        "planet": planet,
                                        "longitude": value,
                                        "sect": sect,
                                        "expected_lords": expected,
                                        "expected_dignities": held,
                                        "actual": actual,
                                    }
                                )
    printed_examples = []
    for row in reference["p112_examples"]:
        (first, first_lon), (second, second_lon) = row["bodies"].items()
        actual = pair_reception(
            first, first_lon, second, second_lon, row.get("sect", "day")
        )
        printed_examples.append(
            {
                "input": row,
                "actual": actual,
                "passed": actual["mutual"] is True
                and actual["mutual_same_kind"] == row["mutual_same_kind"],
            }
        )
    peregrine = []
    for row in reference["peregrine_examples"]:
        actual = dignity_at(row["planet"], row["longitude"], row["sect"])
        peregrine.append(
            {
                "input": row,
                "actual": actual,
                "passed": actual["peregrine"] == row["peregrine"],
            }
        )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "reference_sha256": hashlib.sha256(reference_path.read_bytes()).hexdigest(),
        "reference_method": reference["annotation_method"],
        "comparisons": comparisons,
        "term_cells": 60,
        "face_cells": 36,
        "sect_variants": 2,
        "boundary_comparison": "Independent Decimal over each supplied double and frozen manual cells; no epsilon or re-fitted radius",
        "failures": failures,
        "printed_reception_examples": printed_examples,
        "printed_peregrine_examples": peregrine,
        "passed": not failures
        and all(row["passed"] for row in printed_examples + peregrine),
        "full_original_text_acceptance": False,
        "independent_expert_review": False,
        "independent_astronomy_oracle": False,
        "scope": "Seven-planet selected table and printed p112 examples only; not critical-edition, full-book judgement, actual-model behaviour or outcome certification",
        "source_sha256": {
            rel: hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()
            for rel in [
                "src/fatebridge/core/lilly.py",
                "src/fatebridge/core/horary_conditions.py",
                "src/fatebridge/core/classical_western.py",
                "scripts/western/audit_western_lilly_reception.py",
            ]
        },
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(
        f"{report['comparisons']} boundary/planet/sect comparisons; selected examples passed={report['passed']}"
    )
    raise SystemExit(0 if report["passed"] else 1)
