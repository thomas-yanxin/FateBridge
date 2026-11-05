"""Independent vector-plane replay of Swiss X and Witte's printed cusp table.

The expected-coordinate code imports no FateBridge computation. Geometry grid
comparisons are not independent sky observations. The optional original-table
comparison retains every residual and does not fit a birth time or obliquity.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "tests/fixtures/uranian-meridian-geometry-protocol.json"
PROTOCOL_SHA256 = "5446c655775b60e4ed11c9c468f7ce7ff1d01cf34867db7822f92ef6ecf2fed0"


def _cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def vector_longitude(right_ascension: float, obliquity: float) -> float:
    """Intersect two planes, then inverse-rotate to ecliptic Cartesian axes."""
    alpha, eps = map(math.radians, (right_ascension, obliquity))
    ra_plane_normal = (-math.sin(alpha), math.cos(alpha), 0.0)
    ecliptic_normal = (0.0, -math.sin(eps), math.cos(eps))
    x, y, z = _cross(ra_plane_normal, ecliptic_normal)
    ecliptic_y = math.fsum((y * math.cos(eps), z * math.sin(eps)))
    return math.degrees(math.atan2(ecliptic_y, x)) % 360


def vector_right_ascension(longitude: float, obliquity: float) -> float:
    lam, eps = map(math.radians, (longitude, obliquity))
    x, y = math.cos(lam), math.sin(lam)
    return math.degrees(math.atan2(y * math.cos(eps), x)) % 360


def signed(a: float, b: float) -> float:
    return (a - b + 180) % 360 - 180


def read_protocol() -> dict:
    raw = PROTOCOL.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PROTOCOL_SHA256:
        raise ValueError("Predeclared Meridian geometry protocol checksum mismatch")
    return json.loads(raw)


def geometry_grid(protocol: dict) -> dict:
    import swisseph as swe

    rows = []
    for armc in protocol["reference_armc_degrees"]:
        for epsilon in protocol["reference_obliquity_degrees"]:
            expected = [
                vector_longitude((armc + (house - 10) * 30) % 360, epsilon)
                for house in range(1, 13)
            ]
            for latitude in protocol["reference_latitudes_degrees"]:
                actual, _ = swe.houses_armc(armc, latitude, epsilon, b"X")
                residuals = [signed(a, b) for a, b in zip(actual, expected)]
                rows.append(
                    {
                        "armc": armc,
                        "obliquity": epsilon,
                        "latitude": latitude,
                        "actual_cusps": list(actual),
                        "vector_reference_cusps": expected,
                        "signed_residuals_degrees": residuals,
                        "passed": len(actual) == 12
                        and all(
                            abs(r) <= protocol["geometry_tolerance_degrees"]
                            for r in residuals
                        ),
                    }
                )
    return {
        "backend_version": swe.version,
        "configurations": len(rows),
        "cusp_comparisons": sum(len(row["actual_cusps"]) for row in rows),
        "passed": all(row["passed"] for row in rows),
        "tolerance_degrees": protocol["geometry_tolerance_degrees"],
        "maximum_absolute_residual_degrees": max(
            abs(value) for row in rows for value in row["signed_residuals_degrees"]
        ),
        "rows": rows,
        "independent_sky_observations": 0,
        "physical_or_clock_error_bound": False,
    }


def original_table_comparison(protocol: dict) -> dict:
    import erfa
    import swisseph as swe

    original = ROOT / protocol["printed_source_comparison"]["printed_positions_fixture"]
    data = original.read_bytes()
    if (
        hashlib.sha256(data).hexdigest()
        != protocol["printed_source_comparison"]["printed_values_sha256"]
    ):
        raise ValueError("Frozen Witte printed positions checksum mismatch")
    fixture = json.loads(data)
    # A technical obliquity reference epoch, not an invented birth time.
    d1, d2 = erfa.cal2jd(1859, 1, 27)
    d2 += 0.5
    jd = float(d1 + d2)
    native, native_flags = swe.calc(jd, swe.ECL_NUT, 0)
    if native_flags < 0 or not math.isfinite(native[0]):
        raise ValueError("Independent source comparison has no native true obliquity")
    models = [
        ("IAU2006_mean_ERFA", math.degrees(erfa.obl06(d1, d2))),
        ("Swiss_native_true", float(native[0])),
    ]
    sign, degree, minute = protocol["printed_source_comparison"]["input_MC"]
    mc = sign * 30 + degree + minute / 60
    columns = []
    for model, epsilon in models:
        armc = vector_right_ascension(mc, epsilon)
        rows = []
        for row in fixture["table"][:12]:
            sign, degree, minute = row["natal_cusp"]
            printed = sign * 30 + degree + minute / 60
            calculated = vector_longitude(
                (armc + (row["house"] - 10) * 30) % 360, epsilon
            )
            rows.append(
                {
                    "house": row["house"],
                    "printed_longitude": printed,
                    "calculated_longitude": calculated,
                    "signed_residual_arcminutes": signed(calculated, printed) * 60,
                }
            )
        columns.append(
            {
                "model": model,
                "obliquity": epsilon,
                "derived_armc": armc,
                "rows": rows,
                "maximum_absolute_residual_arcminutes": max(
                    abs(r["signed_residual_arcminutes"]) for r in rows
                ),
            }
        )
    return {
        "scope": "Reconstruct geometry from the printed minute-rounded MC and two predeclared technical obliquity models; not a historical birth-chart calculation",
        "printed_fixture_sha256": hashlib.sha256(data).hexdigest(),
        "source_pdf_sha256": fixture["source_pdf_sha256"],
        "obliquity_reference_julian_day_tt": jd,
        "obliquity_reference_is_assumed_birth_time": False,
        "printed_MC": mc,
        "source_unrounded_MC_and_obliquity_known": False,
        "erfa_version": erfa.__version__,
        "native_true_obliquity_return_flags": native_flags,
        "models": columns,
        "best_model_selected": False,
        "production_obliquity_fitted": False,
        "full_original_acceptance_threshold_defined": False,
        "full_original_numerical_horoscope_accepted": False,
        "original_progression_time_key_accepted": False,
        "empirical_outcomes": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-comparison", action="store_true")
    args = parser.parse_args()
    protocol = read_protocol()
    result = {
        "protocol_sha256": PROTOCOL_SHA256,
        "geometry_grid": geometry_grid(protocol),
    }
    if args.source_comparison:
        result["original_table_comparison"] = original_table_comparison(protocol)
    result.update(authority_certified=False, all_four_objectives_validated=False)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as stream:
        stream.write(
            json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        )
    print(
        json.dumps(
            {
                key: result["geometry_grid"][key]
                for key in (
                    "passed",
                    "configurations",
                    "cusp_comparisons",
                    "maximum_absolute_residual_degrees",
                )
            }
        )
    )
    return 0 if result["geometry_grid"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
