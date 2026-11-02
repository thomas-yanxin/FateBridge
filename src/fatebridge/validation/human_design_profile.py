"""Bounded public profile facts and frozen official lines, not semantic certification."""

import hashlib
import json
from pathlib import Path
from typing import Any

from fatebridge.core.human_design_mechanics import VALID_PROFILES
from fatebridge.core.human_design_profile import (
    profile_evidence,
    profile_reference,
    profile_reference_sha256,
)


def public_profile_checks(root: Path) -> dict[str, Any]:
    reference = profile_reference()
    expected = {r["profile"]: r for r in reference["profiles"]}
    path = root / "src/fatebridge/data/human_design/profile-2026-reference.json"
    if hashlib.sha256(path.read_bytes()).hexdigest() != profile_reference_sha256():
        raise ValueError("Runtime profile facts differ from audited checkout")
    structural = set(expected) == VALID_PROFILES
    rows = []
    for profile, fact in expected.items():
        chart = {
            "profile": profile,
            "activations": {
                side: [{"body": body, "line": fact[key]} for body in ("Sun", "Earth")]
                for side, key in (
                    ("personality", "personality_line"),
                    ("design", "design_line"),
                )
            },
            "incarnation_cross": {"angle": fact["angle"]},
        }
        result = profile_evidence(chart)
        matched = result["status"] == "computed"
        if matched:
            matched = (
                result["geometry"]["angle"] == fact["angle"]
                and [p["line"] for p in result["lines"]]
                == [fact["personality_line"], fact["design_line"]]
                and [p["archetype"] for p in result["lines"]]
                == [
                    reference["line_archetypes"][str(fact[k])]
                    for k in ("personality_line", "design_line")
                ]
                and result["sixth_line_process"]["affected_sides"]
                == [
                    side
                    for side, key in (
                        ("personality", "personality_line"),
                        ("design", "design_line"),
                    )
                    if fact[key] == 6
                ]
                and result["sixth_line_process"]["current_phase"] is None
                and result["sixth_line_process"]["computed_return_dates"] is None
            )
        rows.append(
            {
                "profile": profile,
                "matched": matched,
                "angle": result.get("geometry", {}).get("angle"),
            }
        )
    official = []
    for name in (
        "human-design-official-charts.json",
        "human-design-official-authority-charts.json",
    ):
        cohort = json.loads((root / "tests/fixtures" / name).read_text())
        for case in cohort["cases"]:
            properties = case["properties"]
            displayed = properties["Incarnation Cross"]
            angle = next(
                (
                    a
                    for prefix, a in [
                        ("Right Angle", "right"),
                        ("Juxtaposition", "juxtaposition"),
                        ("Left Angle", "left"),
                    ]
                    if displayed.startswith(prefix)
                ),
                None,
            )
            if angle is None:
                raise ValueError("Unrecognized unchanged official angle label")
            chart = {
                "profile": properties["Profile"],
                "incarnation_cross": {"angle": angle},
                "activations": {
                    side: [
                        {"body": body, "line": int(value.split(".")[1])}
                        for body, value in zip(cohort["planet_order"], column)
                    ]
                    for side, column in case["columns"].items()
                },
            }
            result = profile_evidence(chart)
            matched = (
                result["status"] == "computed" and result["geometry"]["angle"] == angle
            )
            official.append(
                {
                    "id": case["id"],
                    "profile": properties["Profile"],
                    "angle": angle,
                    "matched": matched,
                    "source_pdf_sha256": case["pdf_sha256"],
                }
            )
    passed = (
        structural
        and len(rows) == 12
        and len(official) == 19
        and all(r["matched"] for r in rows + official)
    )
    return {
        "status": "bounded_public_profile_facts_matched" if passed else "failed",
        "reference_sha256": profile_reference_sha256(),
        "source_profiles_equal_legal_calculation_profiles": structural,
        "profiles_checked": len(rows),
        "profiles_matched": sum(r["matched"] for r in rows),
        "angle_profile_counts": {
            a: sum(r["angle"] == a for r in rows)
            for a in ("right", "juxtaposition", "left")
        },
        "official_charts_checked": len(official),
        "official_charts_matched": sum(r["matched"] for r in official),
        "profiles": rows,
        "official_charts": official,
        "scope": "Only12 source-header role/angle combinations, paired-line local derivations and19 frozen official profile/angle observations. Toy paired-line rows are not astronomical or official whole charts. Approximate sixth-line cycle teaching does not compute return dates or present phase. Complete doctrine, psychology and free-text interpretation remain uncertified.",
    }
