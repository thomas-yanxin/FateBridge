"""Common-frame comparisons retain every old coordinate, threshold and failure."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from scripts.gen_human_design_icrf_horizons import (
    ROOT,
    parameters,
    parse_response,
    plan,
)

BASE = ROOT / "docs/validation/human-design-icrf-horizons-v1"
E = BASE / "evidence"
BINDINGS = {
    "nasa-attempt1/reference.json": "d783a6e8cb436b3ca808938165f3ad7a1ec337d99aee166d9458b15d9ad17249",
    "de440-icrf-reference.json": "2a018b02c5e627646fc4eeeaf29f3b4e16218b62e1a20445397c4c9466168f2f",
}
# Inspected swi_bias(FALSE), IAU2006, applies rb transpose to the input.
# This is a declared source formula, never a fit to NASA residuals.
BIAS = (
    (0.99999999999999412, -0.00000007078368961, 0.00000008056213978),
    (0.00000007078368695, 0.99999999999999700, 0.00000003306428553),
    (-0.00000008056214212, -0.00000003306427981, 0.99999999999999634),
)


def references() -> dict:
    result = {}
    for name, digest in BINDINGS.items():
        raw = (E / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError("Independent reference changed: " + name)
        result[name] = json.loads(raw)
    for record in result["nasa-attempt1/reference.json"]["records"]:
        folder = E / "nasa-attempt1"
        request = json.loads((folder / f"{record['body']}.request.json").read_bytes())
        if (
            request["parameters"] != parameters(record["body"])
            or parse_response(
                (folder / f"{record['body']}.response.json").read_bytes(),
                record["body"],
            )
            != record
        ):
            raise ValueError("NASA reference detached from raw request/response")
    fixed = plan()
    for value in result.values():
        if [r["body"] for r in value["records"]] != list(fixed["bodies"]):
            raise ValueError("Wrong reference target order")
        for record in value["records"]:
            if record["target_id"] != fixed["bodies"][record["body"]] or [
                (r["id"], r["jd_tt"]) for r in record["rows"]
            ] != [(r["id"], r["jd_tt"]) for r in fixed["epochs"]]:
                raise ValueError("Missing/rebound original target or TT")
    return result


def mv(matrix: list | tuple, vector: list | tuple) -> list[float]:
    return [math.fsum(a * b for a, b in zip(row, vector)) for row in matrix]


def mm(a: list | tuple, b: list | tuple) -> list[list[float]]:
    return [
        [math.fsum(x * y for x, y in zip(row, column)) for column in zip(*b)]
        for row in a
    ]


def vector(lon: float, lat: float) -> list[float]:
    a, b = math.radians(lon), math.radians(lat)
    return [math.cos(b) * math.cos(a), math.cos(b) * math.sin(a), math.sin(b)]


def spherical(v: list | tuple) -> dict[str, float]:
    return {
        "longitude": math.degrees(math.atan2(v[1], v[0])) % 360,
        "latitude": math.degrees(math.atan2(v[2], math.hypot(v[0], v[1]))),
    }


def signed(a: float, b: float) -> float:
    return math.remainder(a - b, 360) * 3600


def separation(a: dict[str, float], b: dict[str, float]) -> float:
    x, y = vector(a["right_ascension"], a["declination"]), vector(
        b["right_ascension"], b["declination"]
    )
    cross = [
        x[1] * y[2] - x[2] * y[1],
        x[2] * y[0] - x[0] * y[2],
        x[0] * y[1] - x[1] * y[0],
    ]
    return (
        math.degrees(
            math.atan2(math.hypot(*cross), math.fsum(u * v for u, v in zip(x, y)))
        )
        * 3600
    )


def rotation(
    tt: float, mean_obliquity: float, nutation_longitude: float
) -> list[list[float]]:
    from fatebridge.core.astro.continuous_lahiri import ecliptic_rotation, precession

    p, _ = precession(tt)
    e, _ = ecliptic_rotation(math.radians(mean_obliquity))
    psi = math.radians(nutation_longitude)
    z = (
        (math.cos(psi), -math.sin(psi), 0),
        (math.sin(psi), math.cos(psi), 0),
        (0, 0, 1),
    )
    return mm(z, mm(e, mm(p, BIAS)))


def validate_rotation(matrix: list | tuple) -> None:
    if (
        len(matrix) != 3
        or any(len(row) != 3 for row in matrix)
        or any(
            type(value) not in (int, float) or not math.isfinite(value)
            for row in matrix
            for value in row
        )
    ):
        raise ValueError("Malformed source rotation")
    product = mm(matrix, tuple(zip(*matrix)))
    if any(
        abs(product[i][j] - int(i == j)) > 1e-12 for i in range(3) for j in range(3)
    ):
        raise ValueError("Source matrix is not orthonormal")
    cross = [
        matrix[0][1] * matrix[1][2] - matrix[0][2] * matrix[1][1],
        matrix[0][2] * matrix[1][0] - matrix[0][0] * matrix[1][2],
        matrix[0][0] * matrix[1][1] - matrix[0][1] * matrix[1][0],
    ]
    if abs(math.fsum(a * b for a, b in zip(cross, matrix[2])) - 1) > 1e-12:
        raise ValueError("Source matrix is not a proper rotation")


def spherical_separation(a: dict[str, float], b: dict[str, float]) -> float:
    return separation(
        {"right_ascension": a["longitude"], "declination": a["latitude"]},
        {"right_ascension": b["longitude"], "declination": b["latitude"]},
    )


def capture() -> dict:
    from fatebridge.core.astro import runtime
    from fatebridge.core.human_design import BODY_IDS, positions_at_tt
    from fatebridge.core.human_design_natal_sources import guard_natal_sources

    @guard_natal_sources
    def actual() -> dict:
        swe = runtime.swe
        if swe is None:
            raise RuntimeError("Swiss unavailable")
        rows = []
        for epoch in plan()["epochs"]:
            tt = epoch["jd_tt"]
            original = positions_at_tt(tt, "true", require_swiss_files=True)
            eps, eps_flags = runtime.ephemeris_call("calc", tt, swe.ECL_NUT, 0)
            matrix = rotation(tt, eps[1], eps[2])
            for body in plan()["bodies"]:
                default, default_flags = runtime.ephemeris_call(
                    "calc", tt, BODY_IDS[body], swe.FLG_SWIEPH | swe.FLG_SPEED
                )
                requested = (
                    swe.FLG_SWIEPH
                    | swe.FLG_SPEED
                    | swe.FLG_EQUATORIAL
                    | swe.FLG_J2000
                    | swe.FLG_ICRS
                )
                icrf, icrf_flags = runtime.ephemeris_call(
                    "calc", tt, BODY_IDS[body], requested
                )
                if (
                    default_flags != 258
                    or icrf_flags != requested | swe.FLG_NONUT
                    or not all(math.isfinite(v) for v in (*default, *icrf))
                ):
                    raise ValueError(
                        "Unexpected diagnostic native flags or nonfinite state"
                    )
                if (default[0], default[3], default_flags) != (
                    original[body]["longitude"],
                    original[body]["longitude_speed"],
                    original[body]["return_flags"],
                ):
                    raise ValueError(
                        "Default diagnostic is not the actual producer value"
                    )
                rows.append(
                    {
                        **epoch,
                        "body": body,
                        "position": original[body],
                        "default_native_coordinates": list(default),
                        "default_return_flags": default_flags,
                        "icrf_requested_flags": requested,
                        "icrf_return_flags": icrf_flags,
                        "icrf_native_coordinates": list(icrf),
                        "native_ecliptic_nutation": {
                            "values": list(eps),
                            "returned_flags": eps_flags,
                        },
                        "declared_icrf_to_default_ecliptic_matrix": matrix,
                    }
                )
        return {
            "rows": rows,
            "native_version": str(swe.version),
            "matrix_formula": "Rz(nutation_longitude) @ Rx(mean_obliquity) @ Vondrak2011_precession @ IAU2006_bias_transpose",
            "matrix_is_fitted_to_observed_residuals": False,
            "native_execution_authenticated": False,
            "scope": "Actual current default producer and separate raw ICRF diagnostics in a fresh Python process. Declared source rotation is checked for closure, not assumed as a new astronomical oracle.",
        }

    return actual()


def compare(production: dict, sources: dict) -> dict:
    fixed = plan()
    keys = [
        (r["id"], body, r["jd_tt"]) for r in fixed["epochs"] for body in fixed["bodies"]
    ]
    if [(r["id"], r["body"], r["jd_tt"]) for r in production["rows"]] != keys:
        raise ValueError("Producer lost or rebound an original row")
    lookups = {
        name: {
            (r["id"], record["body"]): r
            for record in value["records"]
            for r in record["rows"]
        }
        for name, value in sources.items()
    }
    rows = []
    for p in production["rows"]:
        key = p["id"], p["body"]
        nasa = lookups["nasa-attempt1/reference.json"][key]
        sky = lookups["de440-icrf-reference.json"][key]
        validate_rotation(sky["icrf_to_ecliptic_of_date_rotation"])
        validate_rotation(p["declared_icrf_to_default_ecliptic_matrix"])
        if (
            p["default_return_flags"] != 258
            or p["icrf_requested_flags"] != 133410
            or p["icrf_return_flags"] != 133474
        ):
            raise ValueError("Wrong actual native frame flags")
        if (
            p["default_native_coordinates"][0],
            p["default_native_coordinates"][3],
            258,
        ) != (
            p["position"]["longitude"],
            p["position"]["longitude_speed"],
            p["position"]["return_flags"],
        ):
            raise ValueError("Producer detached from raw native default state")
        icrf = {
            "horizons": nasa["icrf_apparent_quantity45"],
            "skyfield": sky["icrf_apparent"],
            "swiss": {
                "right_ascension": p["icrf_native_coordinates"][0],
                "declination": p["icrf_native_coordinates"][1],
            },
        }
        for c in icrf.values():
            if not all(math.isfinite(v) for v in c.values()) or not (
                0 <= c["right_ascension"] < 360 and -90 <= c["declination"] <= 90
            ):
                raise ValueError("Invalid ICRF coordinate")
        sky_frame = {
            label: spherical(
                mv(
                    sky["icrf_to_ecliptic_of_date_rotation"],
                    vector(c["right_ascension"], c["declination"]),
                )
            )
            for label, c in icrf.items()
        }
        swiss_frame = {
            label: spherical(
                mv(
                    p["declared_icrf_to_default_ecliptic_matrix"],
                    vector(c["right_ascension"], c["declination"]),
                )
            )
            for label, c in icrf.items()
        }
        metrics = {}
        for name, a, b in (
            ("horizons_minus_swiss", "horizons", "swiss"),
            ("horizons_minus_skyfield", "horizons", "skyfield"),
            ("swiss_minus_skyfield", "swiss", "skyfield"),
        ):
            angle = separation(icrf[a], icrf[b])
            longitude = signed(sky_frame[a]["longitude"], sky_frame[b]["longitude"])
            metrics[name] = {
                "icrf_angular_separation_arcseconds": angle,
                "common_skyfield_frame_longitude_difference_arcseconds": longitude,
                "angular_within_unchanged2arcsec_diagnostic_threshold": angle
                <= fixed["angular_tolerance_arcseconds"],
                "longitude_within_unchanged2arcsec_diagnostic_threshold": abs(longitude)
                <= fixed["angular_tolerance_arcseconds"],
            }
        rows.append(
            {
                "id": p["id"],
                "body": p["body"],
                "jd_tt": p["jd_tt"],
                "offset_days": p["offset_days"],
                "icrf_apparent": icrf,
                "skyfield_frame_projections": sky_frame,
                "declared_swiss_frame_projections": swiss_frame,
                "comparisons": metrics,
                "frame_closure_angular_arcseconds": {
                    "swiss": spherical_separation(
                        {
                            "longitude": p["position"]["longitude"],
                            "latitude": p["default_native_coordinates"][1],
                        },
                        swiss_frame["swiss"],
                    ),
                    "skyfield": spherical_separation(
                        sky["of_date_apparent"], sky_frame["skyfield"]
                    ),
                },
                "frame_diagnostics_arcseconds": {
                    "swiss_default_minus_source_rotation_closure": signed(
                        p["position"]["longitude"], swiss_frame["swiss"]["longitude"]
                    ),
                    "skyfield_default_minus_saved_rotation_closure": signed(
                        sky["of_date_apparent"]["longitude"],
                        sky_frame["skyfield"]["longitude"],
                    ),
                    "horizons31_minus_horizons45_in_skyfield_frame": signed(
                        nasa["ecliptic_of_date_quantity31"]["longitude"],
                        sky_frame["horizons"]["longitude"],
                    ),
                    "horizons31_minus_horizons45_in_declared_swiss_frame": signed(
                        nasa["ecliptic_of_date_quantity31"]["longitude"],
                        swiss_frame["horizons"]["longitude"],
                    ),
                },
                "production_coordinate_replaced": False,
                "original_failure_regraded": False,
            }
        )
    names = list(rows[0]["comparisons"])
    counts = {
        name: {
            "positions": len(rows),
            "angular_failed": sum(
                not r["comparisons"][name][
                    "angular_within_unchanged2arcsec_diagnostic_threshold"
                ]
                for r in rows
            ),
            "longitude_failed": sum(
                not r["comparisons"][name][
                    "longitude_within_unchanged2arcsec_diagnostic_threshold"
                ]
                for r in rows
            ),
        }
        for name in names
    }
    longitude_closures = {
        name: max(abs(r["frame_diagnostics_arcseconds"][name]) for r in rows)
        for name in (
            "swiss_default_minus_source_rotation_closure",
            "skyfield_default_minus_saved_rotation_closure",
        )
    }
    closures = {
        name: max(row["frame_closure_angular_arcseconds"][name] for row in rows)
        for name in ("swiss", "skyfield")
    }
    return {
        "method_id": "human_design_common_icrf_near_conjunction_comparison_v2",
        "position_count": len(rows),
        "rows": rows,
        "counts": counts,
        "rotation_closure_maximum_arcseconds": closures,
        "rotation_longitude_closure_maximum_arcseconds": longitude_closures,
        "source_rotation_closure_accepted": all(v <= 0.0001 for v in closures.values()),
        "status": (
            "disagreements_remain"
            if any(
                c["angular_failed"] or c["longitude_failed"] for c in counts.values()
            )
            else "bounded_common_frame_agreement_only"
        ),
        "old_calendar_failure_regraded": False,
        "physical_model_or_original_software_certified": False,
        "all_original_reference_rows_retained": True,
        "scope": "ICRF45 removes the mixed of-date frame from this investigative comparison; all old31 values and original failures remain. Rotation closure is an engineering consistency check, not independent physical evidence. No model selected by closeness, no full-range or predictive acceptance.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--production", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.production.exists():
        raise FileExistsError("Never replace diagnostic captures")
    independent = references()
    production = capture()
    args.production.write_text(json.dumps(production, indent=2) + "\n")
    value = compare(production, independent)
    args.output.write_text(json.dumps(value, indent=2) + "\n")
    print(
        json.dumps(
            {
                "status": value["status"],
                "counts": value["counts"],
                "rotation_closure": value["rotation_closure_maximum_arcseconds"],
            }
        )
    )
    return int(
        value["status"] == "disagreements_remain"
        or not value["source_rotation_closure_accepted"]
    )


if __name__ == "__main__":
    raise SystemExit(main())
