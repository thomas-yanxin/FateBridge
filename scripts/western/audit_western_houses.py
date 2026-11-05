"""Audit every frozen independent house case; discrepancies make CLI exit 1.

ERFA provides independent Earth rotation and vector sky axes. Astrolog has
separate house algorithms and declared polar/fixed-iteration limitations.
Neither an upstream fallback nor a method discrepancy counts as a numerical
pass. Supplied time pairs do not independently verify UTC/TT/model UT1.
"""

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from fatebridge.core.astro import runtime
from fatebridge.core.astro_models import earth_rotation_policy

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests/fixtures/western-houses-erfa-astrolog.json"


def separation(a, b):
    return abs((a - b + 180) % 360 - 180) * 3600


def audit(reference=None):
    reference = reference or json.loads(FIXTURE.read_text())
    rows = []
    comparisons = []
    limits = reference["protocol"]
    for index, case in enumerate(reference["cases"]):
        p = case["input"]
        # Equal houses return the unflipped upper-meridian sky angle; some
        # polar quadrant systems choose a different MC branch in their ascmc.
        _, angles = runtime.ephemeris_call(
            "houses_ex", p["jd_ut1"], p["latitude"], p["longitude"], b"E"
        )
        errors = {
            name: separation(angles[i], case["erfa_vector_angles"][name])
            for i, name in enumerate(("ascendant", "midheaven"))
        }
        rows.append(
            {
                "index": index,
                "input": p,
                "earth_rotation": earth_rotation_policy(p["jd_tt"], p["jd_ut1"]),
                "axis_error_arcseconds": errors,
                "armc_error_arcseconds": separation(angles[2], case["armc"]),
                "matched": max(errors.values()) <= limits["angle_tolerance_arcseconds"],
            }
        )
        for code, oracle in case["astrolog"].items():
            requested = limits["systems"][code]
            item = {
                "case_index": index,
                "system": code,
                "oracle_effective_system": oracle["effective_system"],
                "oracle_fallback": oracle["effective_system"] != requested,
            }
            try:
                cusps, method_angles = runtime.ephemeris_call(
                    "houses_ex",
                    p["jd_ut1"],
                    p["latitude"],
                    p["longitude"],
                    code.encode(),
                )
            except runtime.swe.Error as error:
                item.update(
                    {
                        "status": (
                            "undefined_requested_method"
                            if item["oracle_fallback"]
                            else "unexpected_runtime_error"
                        ),
                        "runtime_error": str(error),
                        "numeric_match": False,
                    }
                )
            else:
                error = max(separation(a, b) for a, b in zip(cusps, oracle["cusps"]))
                item.update(
                    {
                        "max_cusp_error_arcseconds": error,
                        "house_meridian_branch_error_arcseconds": separation(
                            method_angles[1], case["erfa_vector_angles"]["midheaven"]
                        ),
                        "status": (
                            "oracle_fallback_not_comparable"
                            if item["oracle_fallback"]
                            else (
                                "matched"
                                if error <= limits["cusp_tolerance_arcseconds"]
                                else "unresolved_method_or_numerical_discrepancy"
                            )
                        ),
                        "numeric_match": not item["oracle_fallback"]
                        and error <= limits["cusp_tolerance_arcseconds"],
                    }
                )
            comparisons.append(item)
    counts = {}
    for row in comparisons:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    gaps = [
        row
        for row in comparisons
        if row["status"] not in {"matched", "undefined_requested_method"}
    ]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "fixture_sha256": hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),
        "library_version": runtime.swe.version,
        "earth_rotation": earth_rotation_policy(),
        "angle_count": len(rows),
        "angle_matched_count": sum(row["matched"] for row in rows),
        "maximum_axis_error_arcseconds": {
            key: max(row["axis_error_arcseconds"][key] for row in rows)
            for key in ("ascendant", "midheaven")
        },
        "house_comparison_count": len(comparisons),
        "house_status_counts": counts,
        "angles": rows,
        "houses": comparisons,
        "all_independent_checks_passed": all(row["matched"] for row in rows)
        and not gaps,
        "source_sha256": {
            name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in [
                "src/fatebridge/core/astro/parts.py",
                "src/fatebridge/core/astro/layout.py",
                "src/fatebridge/core/astro/geometry.py",
                "src/fatebridge/core/astro/reference.py",
                "src/fatebridge/core/astro_models.py",
                "src/fatebridge/core/iers2010_series.py",
                "src/fatebridge/core/ephemeris_runtime.py",
                "src/fatebridge/utils/house_systems.py",
                "scripts/western/gen_western_houses_reference.py",
                "scripts/western/build_astrolog_house_oracle.py",
            ]
        },
        "limits": [
            "All collected cases retained; tolerances fixed before collection",
            "No measured EOP, polar motion or independent time conversion",
            "Astrolog's ten-iteration Placidus and polar branches are not assumed authoritative",
            "MC branches differing by half a circle require method and interpretation review",
            "No original-text or empirical prediction certification",
        ],
        "all_three_full_marks_established": False,
        "authority_certified": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit()
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    )
    print(
        f"Axes {result['angle_matched_count']}/{result['angle_count']}; house statuses {result['house_status_counts']}"
    )
    raise SystemExit(0 if result["all_independent_checks_passed"] else 1)
