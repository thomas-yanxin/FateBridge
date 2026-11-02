"""Independent direction rotation, all registered X placements and Witte1924 table.

Geometric reference calculations use no FateBridge or Swiss house solver.
The backend is an additional comparator, not an independent sky ephemeris.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "tests/fixtures/uranian-meridian-placement-protocol.json"
PROTOCOL_SHA256 = "f1509ffe77831170052d299eb5a0736c06bc0fd6ec87facf8e52acc53e46b850"
RECORD = ROOT / "tests/fixtures/uranian-witte1924-meridian-placement.json"
RECORD_SHA256 = "8b9fb026df196fa9d5742c3cedffbb1d60b7d9748854a2cce33ad85987c9c9b7"


def pinned(path: Path, expected: str) -> dict:
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError("Frozen meridian placement reference checksum mismatch")
    return json.loads(raw)


def signed(a: float, b: float, period: int = 360) -> float:
    return float(
        (Fraction(a) - Fraction(b) + Fraction(period, 2)) % period - Fraction(period, 2)
    )


def reference_rotation(lon: float, lat: float, eps: float) -> tuple[float, float]:
    """Rodrigues rotation about the equinoctial x-axis, with no solver calls."""
    l, b, e = map(math.radians, (lon, lat, eps))
    v = [math.cos(b) * math.cos(l), math.cos(b) * math.sin(l), math.sin(b)]
    k = [1.0, 0.0, 0.0]
    cross = [0.0, -v[2], v[1]]
    dot = sum(a * b for a, b in zip(k, v))
    rotated = [
        v[i] * math.cos(e) + cross[i] * math.sin(e) + k[i] * dot * (1 - math.cos(e))
        for i in range(3)
    ]
    ra = math.degrees(math.atan2(rotated[1], rotated[0]))
    de = math.degrees(math.atan2(rotated[2], math.hypot(*rotated[:2])))
    return ra, de


def reference_house(ra: float, armc: float) -> tuple[int, float, float]:
    # Search the twelve oriented sectors rather than using a floor index.
    a = Fraction(ra)
    for h in range(1, 13):
        start = Fraction(armc) + (h - 10) * 30
        offset = (a - start) % 360
        if offset < 30:
            return h, float(Fraction(h) + offset / 30), float(min(offset, 30 - offset))
    raise AssertionError("Every finite RA belongs to a sector")


def grid(protocol: dict) -> dict:
    from fatebridge.core.astro import runtime
    from fatebridge.core.astro.meridian_placement import factor_position

    swe = runtime.swe
    if swe is None:
        raise RuntimeError("Actual Swiss house_pos comparator required")
    tol = protocol["geometry_tolerance_degrees"]
    checks = []
    with runtime.preserve_ephemeris_path():
        for armc in protocol["armc_degrees"]:
            for eps in protocol["obliquities_degrees"]:
                for lon in protocol["ecliptic_longitudes_degrees"]:
                    for lat in protocol["ecliptic_latitudes_degrees"]:
                        ra, de = reference_rotation(lon, lat, eps)
                        house, pos, distance = reference_house(ra, armc)
                        actual = factor_position(
                            longitude=lon, latitude=lat, obliquity=eps, armc=armc
                        )
                        assert actual["status"] == "computed"
                        controls = [
                            float(
                                runtime.ephemeris_call(
                                    "house_pos", armc, geolat, eps, (lon, lat), b"X"
                                )
                            )
                            for geolat in protocol["geographic_latitudes_degrees"]
                        ]
                        ra_error = signed(actual["right_ascension"], ra)
                        pos_error = signed(actual["house_position"], pos, 12) * 30
                        backend_errors = [
                            signed(actual["house_position"], value, 12) * 30
                            for value in controls
                        ]
                        boundary = distance <= tol
                        expected_control, _, control_distance = reference_house(
                            reference_rotation(lon, 0.0, eps)[0], armc
                        )
                        matched = (
                            abs(ra_error) <= tol
                            and abs(pos_error) <= tol
                            and abs(actual["declination"] - de) <= tol
                            and all(abs(v) <= tol for v in backend_errors)
                        )
                        integer_matched = (
                            None
                            if boundary
                            else actual["house"] == house
                            and all(math.floor(v) == house for v in controls)
                        )
                        checks.append(
                            {
                                "armc": armc,
                                "obliquity": eps,
                                "longitude": lon,
                                "latitude": lat,
                                "reference_ra": ra,
                                "runtime_ra": actual["right_ascension"],
                                "reference_house": house,
                                "runtime_house": actual["house"],
                                "reference_position": pos,
                                "runtime_position": actual["house_position"],
                                "ra_error_degrees": ra_error,
                                "position_error_degrees": pos_error,
                                "backend_positions_in_declared_geolat_order": controls,
                                "backend_errors_degrees": backend_errors,
                                "boundary_band_integer_comparison": boundary,
                                "integer_house_matched": integer_matched,
                                "matched": matched,
                                "zero_latitude_control_house": expected_control,
                                "zero_latitude_control_boundary_band": control_distance
                                <= tol,
                                "runtime_zero_latitude_control_house": actual[
                                    "longitude_only_control_house"
                                ],
                                "latitude_changes_house": house != expected_control,
                            }
                        )
    n = len(checks)
    return {
        "unique_direction_and_armc_configurations": n,
        "backend_comparisons": n * len(protocol["geographic_latitudes_degrees"]),
        "numeric_checks_matched": all(c["matched"] for c in checks),
        "interior_integer_checks_matched": all(
            c["integer_house_matched"]
            for c in checks
            if not c["boundary_band_integer_comparison"]
        ),
        "integer_boundary_comparisons_unresolved": sum(
            c["boundary_band_integer_comparison"] for c in checks
        ),
        "latitude_changes_house_unique_configurations": sum(
            c["latitude_changes_house"]
            for c in checks
            if not c["boundary_band_integer_comparison"]
        ),
        "maximum_ra_error_degrees": max(abs(c["ra_error_degrees"]) for c in checks),
        "latitude_changes_house_outside_both_boundary_bands": sum(
            c["latitude_changes_house"]
            for c in checks
            if not c["boundary_band_integer_comparison"]
            and not c["zero_latitude_control_boundary_band"]
        ),
        "maximum_backend_error_degrees": max(
            abs(v) for c in checks for v in c["backend_errors_degrees"]
        ),
        "checks": checks,
        "independent_sky_observations": 0,
        "physical_or_clock_error_bound": False,
        "scope": "4320 unique synthetic direction/ARMC configurations each checked at5 geographic latitudes; boundary-band integers remain unresolved, not counted as proven house placements",
    }


def source_cusps(record: dict) -> dict:
    from fatebridge.core.astro import runtime

    def angle(raw):
        return raw[0] * 30 + raw[1] + raw[2] / 60

    def cusp(mc, house, eps):
        l, e = math.radians(mc), math.radians(eps)
        a = math.atan2(math.sin(l) * math.cos(e), math.cos(l)) + math.radians(
            (house - 10) * 30
        )
        return math.degrees(math.atan2(math.sin(a) / math.cos(e), math.cos(a))) % 360

    # A technical TT label for choosing obliquity, not a birth instant or UTC.
    jd = datetime(1849, 1, 22).toordinal() + 1721424.5 + 0.5
    t = (jd - 2451545) / 36525
    mean = (
        84381.406
        + t
        * (
            -46.836769
            + t
            * (-0.0001831 + t * (0.00200340 + t * (-0.000000576 - 0.0000000434 * t)))
        )
    ) / 3600
    with runtime.preserve_ephemeris_path():
        values, flag = runtime.ephemeris_call("calc", jd, runtime.swe.ECL_NUT, 0)
        assert flag >= 0
        true = values[0]
    mc = angle(record["rows"][0]["meridian"])
    columns = []
    for name, eps in [("IAU2006_mean", mean), ("Swiss_true", true)]:
        rows = []
        for row in record["rows"]:
            house = row["house"]
            printed = angle(row["meridian"])
            computed = cusp(mc, house, eps)
            lo, hi = sorted(
                signed(cusp(mc + delta, house, eps), computed)
                for delta in [-0.5 / 60, 0.5 / 60]
            )
            center = signed(printed, computed)
            overlap = lo <= center + 0.5 / 60 and hi >= center - 0.5 / 60
            rows.append(
                {
                    "house": house,
                    "printed_meridian_longitude": printed,
                    "computed_longitude": computed,
                    "printed_minus_computed_arcminutes": center * 60,
                    "computed_mc_rounding_interval_offsets_degrees": [lo, hi],
                    "source_and_mc_rounding_intervals_overlap": overlap,
                    "printed_placidus_longitude": angle(row["placidus"]),
                }
            )
        columns.append(
            {
                "model": name,
                "obliquity": eps,
                "rows": rows,
                "all_six_meridian_intervals_overlap": all(
                    r["source_and_mc_rounding_intervals_overlap"] for r in rows
                ),
            }
        )
    return {
        "source": record["source"],
        "source_record_sha256": RECORD_SHA256,
        "printed_rows": 6,
        "independent_historical_examples": 1,
        "technical_obliquity_epoch_jd_tt": jd,
        "columns": columns,
        "historical_birth_clock_adopted": False,
        "full_original_method_accepted": False,
        "empirical_outcomes": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--source-pdf", type=Path)
    args = parser.parse_args()
    protocol = pinned(PROTOCOL, PROTOCOL_SHA256)
    record = pinned(RECORD, RECORD_SHA256)
    if (
        args.source_pdf
        and hashlib.sha256(args.source_pdf.read_bytes()).hexdigest()
        != record["source"]["pdf_sha256"]
    ):
        raise ValueError("Original PDF checksum mismatch")
    g = grid(protocol)
    s = source_cusps(record)
    report = {
        "audit_version": "meridian_placement_v1",
        "protocol": protocol,
        "protocol_sha256": PROTOCOL_SHA256,
        "source_pdf_bytes_checked": bool(args.source_pdf),
        "geometry": g,
        "source_table": s,
        "source_table_reconciled_with_all_predeclared_models": all(
            c["all_six_meridian_intervals_overlap"] for c in s["columns"]
        ),
        "all_four_objectives_validated": False,
        "authority_certified": False,
    }
    with args.output.open("x") as output:
        json.dump(report, output, ensure_ascii=False, indent=2, allow_nan=False)
        output.write("\n")
    print(json.dumps({k: v for k, v in g.items() if k != "checks"}))
    return (
        0
        if g["numeric_checks_matched"]
        and g["interior_integer_checks_matched"]
        and report["source_table_reconciled_with_all_predeclared_models"]
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
