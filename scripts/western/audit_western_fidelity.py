"""Reproduce bounded coordinate, source and deterministic-prose evidence.

This emits inspectable counterexamples and source hashes, not a universal
semantic score, expert certification or a redefinition of the three-axis goal.
"""

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from fatebridge.core.astro.aspects import _build_aspects
from fatebridge.core.astro.parts import _build_houses, _build_planet_record
from fatebridge.core.ptolemy import sign_relationship
from fatebridge.services.astrology import (
    _build_angle_lines,
    _build_dominant_energy,
    _build_house_lines,
    _build_social_style,
)

ROOT = Path(__file__).resolve().parents[2]
REFERENCE = ROOT / "tests/fixtures/western-ptolemy-sign-relations-robbins-1940.json"


def audit():
    reference = json.loads(REFERENCE.read_text())
    signs = [row["sign"] for row in reference["signs"]]
    boundaries = []
    for index in range(12):
        for direction in (-1, 0, 1):
            cusp = index * 30.0
            longitude = (
                cusp
                if direction == 0
                else math.nextafter(cusp, math.inf if direction > 0 else -math.inf)
            )
            point = _build_planet_record("Sun", longitude, 0, 0, "whole_sign")
            expected_sign = signs[(index - (direction < 0)) % 12]
            boundaries.append(
                {
                    "input": longitude,
                    "expected_sign": expected_sign,
                    "actual": point,
                    "passed": point["sign"] == expected_sign
                    and 0 <= point["longitude"] < 360
                    and 0 <= point["degree_in_sign"] < 30,
                }
            )
    relationships = []
    for row in reference["signs"]:
        for other in signs:
            actual = sign_relationship(row["sign"], other)
            expected_command_pair = other == row["command_obey_partner"]
            expected_beholding = other == row["beholding_partner"]
            relationships.append(
                {
                    "sign_a": row["sign"],
                    "sign_b": other,
                    "actual": actual,
                    "passed": bool(actual["commanding_sign"]) == expected_command_pair
                    and actual["beholding_equal_power"] == expected_beholding,
                }
            )
    disjunct_cases = [
        {**case, "actual": sign_relationship(case["a"], case["b"])["disjunct"]}
        for case in reference["disjunct_cases"]
    ]
    for case in disjunct_cases:
        case["passed"] = case["actual"] == case["expected"]
    outside = [
        _build_planet_record("Mercury", 0, 0, 0, "whole_sign"),
        _build_planet_record("Saturn", 8.00000001, 0, 0, "whole_sign"),
    ]
    houses = _build_houses(75.1234567, "equal")
    rendering = {
        "houses": _build_house_lines(houses),
        "angles": _build_angle_lines(
            {
                "ascendant": {"longitude": 75.1234567, "sign_zh": "双子"},
                "midheaven": {"longitude": 359.9999999, "sign_zh": "双鱼"},
            }
        ),
        "ties": _build_dominant_energy(
            {"Fire": 2, "Air": 2, "Earth": 1}, {"Cardinal": 2, "Fixed": 2, "Mutable": 1}
        ),
        "separate_mc": _build_social_style(
            [],
            {
                "ascendant": {"sign": "Aries", "sign_zh": "白羊"},
                "midheaven": {"sign": "Capricorn", "sign_zh": "摩羯"},
            },
        ),
    }
    rendering["passed"] = (
        "第1宫：双子 15.12°" in rendering["houses"]
        and "Asc：双子 15.12°" in rendering["angles"]
        and "30.00°" not in rendering["angles"]
        and "并列最多（各2颗）" in rendering["ties"]
        and "偏强" not in rendering["ties"]
        and "重视结果、责任与长期结构的建立" in rendering["separate_mc"]
    )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "method_id": "western_boundary_and_template_counterfactual_audit_v1",
        "goal_axes": [
            "calendar_and_astronomy",
            "specified_original_text",
            "interpretation_fidelity",
        ],
        "reference": {
            "source_url": reference["source_url"],
            "annotation": reference["annotation"],
            "file_sha256": hashlib.sha256(REFERENCE.read_bytes()).hexdigest(),
        },
        "coordinate_boundaries": {
            "cases": boundaries,
            "scope": "36 representable values at the 12 sign boundaries; not full astronomical accuracy validation",
        },
        "source_sign_relationships": {
            "cases": relationships,
            "disjunct_cases": disjunct_cases,
            "scope": "I.14/I.15 manually annotated partner matrix plus I.16 exclusion cases; degree-orb aspects remain separate",
        },
        "modern_orb_boundary": {
            "input_longitudes": [p["longitude"] for p in outside],
            "declared_orb_limit": 8.0,
            "actual": _build_aspects(outside),
            "passed": _build_aspects(outside) == [],
        },
        "rendering_examples": rendering,
        "validation_limits": {
            "all_generated_prose_independently_reviewed": False,
            "real_model_dialogue_evaluated": False,
            "full_original_treatise_implemented": False,
            "authority_certified": False,
            "all_three_full_marks_established": False,
        },
    }


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = audit()
    encoded = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.write_text(encoded)
        print(
            json.dumps(
                {
                    "boundary_cases": len(report["coordinate_boundaries"]["cases"]),
                    "sign_pair_checks": len(
                        report["source_sign_relationships"]["cases"]
                    ),
                    "report": str(args.output),
                },
                ensure_ascii=False,
            )
        )
    else:
        print(encoded, end="")
    checks = [
        *report["coordinate_boundaries"]["cases"],
        *report["source_sign_relationships"]["cases"],
        *report["source_sign_relationships"]["disjunct_cases"],
        report["modern_orb_boundary"],
        report["rendering_examples"],
    ]
    if not all(case["passed"] for case in checks):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
