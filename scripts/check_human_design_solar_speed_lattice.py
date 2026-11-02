"""Keep strict root mismatches visible while checking actual local Sun witnesses."""

import argparse
import hashlib
import json
import sys
from fractions import Fraction
from pathlib import Path
from typing import Any, Callable

from fatebridge.core.human_design_time import solve_design_epoch_tt

ROOT = Path(__file__).resolve().parents[1]
FROZEN_REFERENCES = {
    "human-design-solar-speed-lattice.json": (
        "a5f937e6e8df47f094659b5b649bc76523494729b8521daf9cdc30057db1c6f7",
        "8c3477eed7b1389bfdd29525364a1e71ed1dfea99281b06575093d6e2adf9f52",
    ),
    "human-design-solar-speed-lattice-linux.json": (
        "944640a24ce76abc32fa3f69ce976297c6e84ee7cbe1e63214c1721f2b3bb3ea",
        "f942f46c0e4efda0b778f45d8fbf42d3d15100d9ff497f6f2871992b2e53bb14",
    ),
}
FROZEN_CASE_COUNT = 244


def compare_case(c: dict[str, Any], s: dict[str, Any]) -> dict[str, Any]:
    """Keep missing reference observations as failures, not invented residuals."""
    w = s["numerical_precision"]
    lattice = w["local_solar_lattice"]
    observed = {row["jd_tt"]: row for row in lattice["samples"]}

    def residual(tt: float) -> Fraction:
        return (
            Fraction(w["birth_sun_longitude"]) - Fraction(observed[tt]["sun_longitude"])
        ) % 360 - 88

    bracket_observed = c["lower_jd_tt"] in observed and c["upper_jd_tt"] in observed
    selected_observed = c["selected_jd_tt"] in observed
    current_observed = s["design_jd_tt"] in observed
    # This is an internal witness check, never the strict root oracle. If the
    # frozen bracket was not actually observed, its residual cannot be inferred
    # from a different current root or silently treated as zero.
    observed_reference_minimum = (
        min(
            (c["lower_jd_tt"], c["upper_jd_tt"]),
            key=lambda tt: (abs(residual(tt)), tt),
        )
        if bracket_observed
        else None
    )
    reference_residual = residual(c["selected_jd_tt"]) if selected_observed else None
    local_checks = {
        "birth_sun_exact": w["birth_sun_longitude"] == c["birth_sun_longitude"],
        "reference_bracket_inside_observed_lattice": bracket_observed,
        "reference_selected_sun_exact_at_same_TT": selected_observed
        and observed[c["selected_jd_tt"]]["sun_longitude"]
        == c["selected_sun_longitude"],
        "reference_exact_residual_preserved": reference_residual is not None
        and [
            str(reference_residual.numerator),
            str(reference_residual.denominator),
        ]
        == c["exact_residual"],
        "reference_minimum_in_its_own_bracket": observed_reference_minimum is not None
        and observed_reference_minimum == c["selected_jd_tt"],
        "current_exact_residual_matches_its_own_chart": current_observed
        and w["selected"]["residual_degrees"] == float(residual(s["design_jd_tt"])),
    }
    strict = (
        s["design_jd_tt"] == c["selected_jd_tt"]
        and w["selected"]["sun_longitude"] == c["selected_sun_longitude"]
    )
    not_assessed: list[str] = []
    if not selected_observed:
        not_assessed.extend(
            (
                "reference_selected_sun_exact_at_same_TT",
                "reference_exact_residual_preserved",
            )
        )
    if not bracket_observed:
        not_assessed.append("reference_minimum_in_its_own_bracket")
    if not current_observed:
        not_assessed.append("current_exact_residual_matches_its_own_chart")
    return {
        "status": "compared",
        "label": c["label"],
        "backend": c["backend"],
        "reference_selected_jd_tt": c["selected_jd_tt"],
        "current_selected_jd_tt": s["design_jd_tt"],
        "difference_seconds": (s["design_jd_tt"] - c["selected_jd_tt"]) * 86400,
        "strict_root_equal": strict,
        "local_checks": local_checks,
        "not_assessed_local_checks": not_assessed,
        "missing_reference_jd_tt": sorted(
            {
                c[k]
                for k in ("lower_jd_tt", "upper_jd_tt", "selected_jd_tt")
                if c[k] not in observed
            }
        ),
        "reference_birth_sun_longitude": c["birth_sun_longitude"],
        "current_birth_sun_longitude": w["birth_sun_longitude"],
        "observed_decreasing_step_indices": lattice["observed_decreasing_step_indices"],
        "observed_sign_brackets": lattice["observed_sign_brackets"],
        "unique_physical_root_certified": False,
    }


def compare(
    reference: dict[str, Any] | None = None,
    solve: Callable[..., dict[str, Any]] = solve_design_epoch_tt,
) -> dict[str, Any]:
    reference_path = ROOT / (
        "tests/fixtures/human-design-solar-speed-lattice-linux.json"
        if sys.platform == "linux"
        else "tests/fixtures/human-design-solar-speed-lattice.json"
    )
    if reference is None:
        reference = json.loads(reference_path.read_text())
        reference_hash = hashlib.sha256(reference_path.read_bytes()).hexdigest()
    else:
        reference_hash = None
    content_hash = hashlib.sha256(
        json.dumps(reference, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    expected_file_hash, expected_content_hash = FROZEN_REFERENCES[reference_path.name]
    reference_bound = (
        len(reference["cases"]) == FROZEN_CASE_COUNT
        and content_hash == expected_content_hash
        and (reference_hash is None or reference_hash == expected_file_hash)
    )
    rows = []
    for c in reference["cases"]:
        try:
            row = compare_case(
                c, solve(c["birth_jd_tt"], backend=c["backend"])["solver"]
            )
        except Exception as error:
            # A failed calculation/check is still one required reference row.
            # The original traceback's type/message remain diagnostic evidence.
            row = {
                "label": c["label"],
                "backend": c["backend"],
                "status": "calculation_or_check_unavailable",
                "reference_selected_jd_tt": c["selected_jd_tt"],
                "strict_root_equal": False,
                "local_checks": {"calculation_available": False},
                "not_assessed_local_checks": ["calculation_available"],
                "error": {"type": type(error).__name__, "message": str(error)},
                "unique_physical_root_certified": False,
            }
        rows.append(row)
    failed = [row for row in rows if not row["strict_root_equal"]]
    local_passed = sum(all(row["local_checks"].values()) for row in rows)
    numeric_passed = bool(rows) and not failed and local_passed == len(rows)
    return {
        "method_id": "human_design_frozen_solar_lattice_comparison_v3",
        "reference_sha256": reference_hash,
        "reference_binding": {
            "frozen_content_bound": reference_bound,
            "content_sha256": content_hash,
            "expected_content_sha256": expected_content_hash,
            "expected_file_sha256": expected_file_hash,
            "expected_case_count": FROZEN_CASE_COUNT,
            "actual_case_count": len(reference["cases"]),
            "scope": "Frozen content identity only, not authentication of the original native generation or its missing Moon-file identity.",
        },
        "strict_selected_root_conformance": {
            "status": "failed" if failed else "passed",
            "total": len(rows),
            "passed": len(rows) - len(failed),
            "failed": len(failed),
        },
        "actual_local_witness_checks_passed": local_passed,
        "unavailable_case_count": sum(row["status"] != "compared" for row in rows),
        "supplied_numeric_checks_passed": numeric_passed,
        "bounded_numeric_conformance_passed": reference_bound and numeric_passed,
        "cases": rows,
        "scope": "All244original integer-search expectations retained unchanged. Different valid adjacent brackets in a nonmonotonic binary64 function are not relabeled exact agreement. Local checks do not authenticate the native sky, physical timing, uniqueness or continuous completeness.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--require-exact", action="store_true")
    args = parser.parse_args()
    r = compare()
    args.output.write_text(json.dumps(r, indent=2) + "\n")
    print(
        json.dumps(
            {
                "strict": r["strict_selected_root_conformance"],
                "local_witness_checks": r["actual_local_witness_checks_passed"],
            }
        )
    )
    if args.require_exact and not r["bounded_numeric_conformance_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
