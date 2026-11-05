"""Check geometric arithmetic without promoting it to astronomical accuracy."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path

from fatebridge.core.human_design_solar_projection import nominal_solar_projection

ROOT = Path(__file__).resolve().parents[1]
BINDINGS = {
    "tests/fixtures/human-design-solar-projection-plan.json": "ec98cd33f17fc8bd837263df58eec684121c23398028f9bcb178d9c3a7ab93d5",
    "tests/fixtures/human-design-solar-projection-reference.json.gz": "8c11e2821c9dd64312d8dce2398cbb5d4466426d5876c1b86742bc47e2925a7a",
}


def checks(root: Path = ROOT) -> dict:
    for name, sha in BINDINGS.items():
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != sha:
            raise ValueError("Frozen solar-projection oracle changed")
    plan = json.loads(
        (root / "tests/fixtures/human-design-solar-projection-plan.json").read_text()
    )
    reference = json.loads(
        gzip.decompress(
            (
                root / "tests/fixtures/human-design-solar-projection-reference.json.gz"
            ).read_bytes()
        )
    )
    if len(reference["rows"]) != plan["case_count"]:
        raise ValueError("Independent geometry case omitted")
    maximum = {
        key: 0.0
        for key in (
            "separation_radians",
            "nominal_solar_radius_radians",
            "projection_margin_radians",
        )
    }
    failures, inside = [], []
    for row in reference["rows"]:
        result = nominal_solar_projection(
            row["sun_longitude_latitude_distance_au"],
            row["target_longitude_latitude_distance_au"],
        )
        errors = {key: abs(result[key] - float(row[key])) for key in maximum}
        for key, error in errors.items():
            maximum[key] = max(maximum[key], error)
        matches = (
            all(error <= plan["oracle_tolerance_radians"] for error in errors.values())
            and result["inside_nominal_solar_disk_projection"]
            is row["inside_nominal_solar_disk_projection"]
            and result["more_distant_than_sun_in_supplied_coordinates"]
            is row["more_distant_than_sun_in_supplied_coordinates"]
        )
        if not matches:
            failures.append({"reference": row, "computed": result, "errors": errors})
        if row["inside_nominal_solar_disk_projection"]:
            inside.append({"reference": row, "computed": result})
    return {
        "method_id": plan["method_id"],
        "status": "failed" if failures else "bounded_geometry_arithmetic_matched",
        "case_count": len(reference["rows"]),
        "cases_matched": len(reference["rows"]) - len(failures),
        "maximum_scalar_errors_radians": maximum,
        "inside_nominal_projection_cases": inside,
        "failures": failures,
        "bindings": BINDINGS,
        "native_astronomy_accuracy_certified": False,
        "physical_occultation_certified": False,
        "visibility_certified": False,
        "scope": reference["scope"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = checks()
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered)
    else:
        print(rendered, end="")
    return int(result["status"] == "failed")


if __name__ == "__main__":
    raise SystemExit(main())
