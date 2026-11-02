"""Compare the author diagrams and literal table with the served derivation."""

import hashlib
import json
from pathlib import Path
from typing import Any

from fatebridge.core.fengshui.mutual_geometry import (
    geometry_provenance,
    validate_author_phase,
    validate_mutual_geometry,
)
from fatebridge.core.fengshui.timeliness import classify_timeliness
from fatebridge.utils.errors import FengshuiCalculationError

HASHES = {
    "page-019.png": "558fc9148f25ff71a54cb80735d3e8c182be72eab23275db9a9c5807aaba96b0",
    "reference.json": "b66c7bc9ceb9c498c2f05a8da4e6e0a28d4d8edd0b8e219e6b328fa3c3fd3081",
}


def load_mutual_geometry_reference(folder: Path) -> dict[str, Any]:
    if json.loads((folder / "hashes.json").read_text()) != HASHES:
        raise ValueError("Retain the independently frozen diagram capture")
    for name, digest in HASHES.items():
        if hashlib.sha256((folder / name).read_bytes()).hexdigest() != digest:
            raise ValueError("Frozen Wang diagram capture changed")
    value = json.loads((folder / "reference.json").read_text())
    if not isinstance(value, dict):
        raise ValueError("Source diagram reference must be an object")
    return value


def audit_mutual_geometry_reference(reference: dict[str, Any]) -> dict[str, Any]:
    directions = {"N", "NE", "E", "SE", "S", "SW", "W", "NW"}
    for layout in ("earlier_heaven", "later_heaven"):
        if set(reference[layout]) != directions or set(
            reference[layout].values()
        ) != set(reference["star_trigrams"].values()):
            raise ValueError("Retain both complete eight-position source diagrams")
    if set(reference["printed_mutual_numbers"]) != set(map(str, range(1, 10))):
        raise ValueError("Retain all nine printed table rows, including five")
    provenance = geometry_provenance()
    position_differences = [
        {
            "layout": layout,
            "direction": direction,
            "expected": trigram,
            "actual": provenance["source_diagrams"][layout].get(direction),
        }
        for layout in ("earlier_heaven", "later_heaven")
        for direction, trigram in reference[layout].items()
        if provenance["source_diagrams"][layout].get(direction) != trigram
    ]
    differences = []
    rows = []
    star_for_trigram = {
        value: int(key) for key, value in reference["star_trigrams"].items()
    }
    for current in range(1, 10):
        expected_paths = []
        if current != 5:
            trigram = reference["star_trigrams"][str(current)]
            for origin, other in (
                ("later_heaven", "earlier_heaven"),
                ("earlier_heaven", "later_heaven"),
            ):
                direction = next(
                    d for d, t in reference[origin].items() if t == trigram
                )
                expected_paths.append(
                    {
                        "current_layout": origin,
                        "current_trigram": trigram,
                        "diagram_direction": direction,
                        "coincident_layout": other,
                        "coincident_trigram": reference[other][direction],
                        "coincident_star_number": star_for_trigram[
                            reference[other][direction]
                        ],
                    }
                )
        for number in range(1, 10):
            actual = classify_timeliness(number, current)
            geometry = actual["mutual_use_reference"]["geometry"]
            matched = (
                geometry["paths"] == expected_paths
                and geometry["printed_period_numbers"]
                == reference["printed_mutual_numbers"][str(current)]
                and geometry["site_eligibility_established"] is False
            )
            try:
                validate_author_phase(actual, number=number, current=current)
                validate_mutual_geometry(geometry, number=number, current=current)
            except FengshuiCalculationError:
                matched = False
            row = {
                "current_period_number": current,
                "star_number": number,
                "matches_source_geometry": matched,
                "actual": geometry,
            }
            rows.append(row)
            if not matched:
                differences.append(row)
    return {
        "reference_id": reference["reference_id"],
        "source_position_count": 16,
        "position_differences": position_differences,
        "ordered_overlap_paths": 16,
        "source_conditioned_star_cases": 81,
        "differences": differences,
        "scoped_geometry_acceptance_passed": not differences
        and not position_differences,
        "five_period_geometric_derivation_verified": False,
        "five_period_policy": "literal_printed_row_only_no_invented_fifth_trigram",
        "rows": rows,
        "scope": reference["scope"],
        "whole_book_conformity_established": False,
        "real_world_prediction_established": False,
    }
