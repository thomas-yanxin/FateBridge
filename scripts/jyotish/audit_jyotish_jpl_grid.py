"""Audit original-TT domain geometry on the sealed 1900-2050 DE441 grid.

The shifted argument is a supplementary time-scale diagnostic. It can never
replace an original-TT result or determine acceptance. No birth clock is moved.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any

PROTOCOL_SHA256 = "8bc70e8c3796696c889572197b4da02833dd84f9e32fffbebb40cfa11bbb694a"
REFERENCE_SHA256 = "b4cad1dde5f89713fbe14a09229a601d49e4131662812b6bedbdac2b75e7a202"
KERNEL_SHA256 = "476096486def4e41bfceb29aa27f50784da0bce318902bcf7b88caad058cd4da"


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(8 * 1024 * 1024):
            result.update(chunk)
    return result.hexdigest()


def unit(point: dict[str, Any]) -> tuple[float, float, float]:
    lon, lat = map(math.radians, (point["longitude"], point["latitude"]))
    return math.cos(lat) * math.cos(lon), math.cos(lat) * math.sin(lon), math.sin(lat)


def error_arcsec(
    a: list[float] | tuple[float, ...], b: list[float] | tuple[float, ...]
) -> float:
    cross = (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )
    return (
        math.degrees(
            math.atan2(math.hypot(*cross), math.fsum(x * y for x, y in zip(a, b)))
        )
        * 3600
    )


def load_reference(protocol_path: Path, reference_path: Path) -> tuple[dict, dict]:
    if (
        digest(protocol_path) != PROTOCOL_SHA256
        or digest(reference_path) != REFERENCE_SHA256
    ):
        raise ValueError("Sealed protocol or independent reference changed")
    protocol, reference = json.loads(protocol_path.read_text()), json.loads(
        reference_path.read_text()
    )
    wanted = {
        (body, r["jd_tt"]) for body in protocol["targets"] for r in protocol["epochs"]
    }
    seen = [(r["body"], r["jd_tt"]) for r in reference["rows"]]
    if (
        reference["protocol_sha256"] != PROTOCOL_SHA256
        or reference["forbidden_candidate_imports"] is not False
        or len(seen) != protocol["expected_rows"]
        or len(set(seen)) != len(seen)
        or set(seen) != wanted
    ):
        raise ValueError("Reference separation or frozen cohort incomplete")
    return protocol, reference


def audit(kernel: Path, protocol_path: Path, reference_path: Path) -> dict[str, Any]:
    protocol, reference = load_reference(protocol_path, reference_path)
    if digest(kernel) != KERNEL_SHA256:
        raise ValueError("The admitted complete DE441 kernel changed")
    os.environ["SE_EPHE_PATH"], os.environ["FATEBRIDGE_JPL_FILE"] = (
        str(kernel.parent),
        kernel.name,
    )
    from fatebridge.core import ephemeris_runtime as e
    from fatebridge.core.jyotish_mean import admitted, geometric_points

    e.configure_ephemeris_path()
    rows: list[dict[str, Any]] = []
    by_epoch: dict[float, dict[str, Any]] = {}
    for epoch in protocol["epochs"]:
        jd = epoch["jd_tt"]
        same_epoch = [r for r in reference["rows"] if r["jd_tt"] == jd]
        delta = same_epoch[0]["geocentric_tdb_minus_tt_seconds"]
        if any(r["geocentric_tdb_minus_tt_seconds"] != delta for r in same_epoch):
            raise ValueError("Inconsistent independent time offset")
        shifted = jd + delta / 86400
        by_epoch[jd] = {"original": {}, "supplementary": {}}
        try:
            by_epoch[jd]["original"] = geometric_points(jd, "require_data_files")
        except Exception as exc:
            by_epoch[jd]["original_error"] = repr(exc)
        if admitted(shifted):
            try:
                by_epoch[jd]["supplementary"] = geometric_points(
                    shifted, "require_data_files"
                )
            except Exception as exc:
                by_epoch[jd]["supplementary_error"] = repr(exc)
        else:
            by_epoch[jd]["supplementary_error"] = "outside_admitted_model_window"
        print(f"evaluated original TT {epoch['tt_calendar']}", flush=True)
    for ref in reference["rows"]:
        epoch, body = ref["jd_tt"], ref["body"]
        data = by_epoch[epoch]
        row: dict[str, Any] = {
            "body": body,
            "jd_tt": epoch,
            "tt_calendar": ref["tt_calendar"],
            "original_error": data.get("original_error"),
        }
        point = data["original"].get(body)
        if point is not None:
            row["original_point"] = point
            row["original_error_arcsec"] = error_arcsec(
                unit(point), ref["ecliptic_unit_vector"]
            )
            row["passed"] = (
                point["ephemeris_model"] == "jpl"
                and point["frame"] == protocol["frame"]
                and row["original_error_arcsec"] <= protocol["position_line_arcsec"]
            )
        else:
            row["passed"] = False
        delta = ref["geocentric_tdb_minus_tt_seconds"]
        diagnostic: dict[str, Any] = {
            "tdb_minus_tt_seconds": delta,
            "argument_jd": epoch + delta / 86400,
            "representable_offset_seconds": ((epoch + delta / 86400) - epoch) * 86400,
            "argument_shift_rounding_seconds": ((epoch + delta / 86400) - epoch) * 86400
            - delta,
            "error": data.get("supplementary_error"),
            "used_for_acceptance": False,
        }
        alternate = data["supplementary"].get(body)
        if alternate is not None:
            diagnostic["point"] = alternate
            diagnostic["residual_arcsec"] = error_arcsec(
                unit(alternate), ref["ecliptic_unit_vector"]
            )
            if point is not None:
                diagnostic["change_from_original_arcsec"] = error_arcsec(
                    unit(alternate), unit(point)
                )
        row["supplementary_time_argument"] = diagnostic
        rows.append(row)
    if digest(kernel) != KERNEL_SHA256:
        raise ValueError("DE441 kernel changed during audit")
    return {
        "status": (
            "passed_original_TT_grid"
            if all(r["passed"] for r in rows)
            else "failed_original_TT_grid"
        ),
        "protocol_sha256": PROTOCOL_SHA256,
        "reference_sha256": REFERENCE_SHA256,
        "kernel_sha256": KERNEL_SHA256,
        "auditor_sha256": digest(Path(__file__)),
        "original_position_line_arcsec": protocol["position_line_arcsec"],
        "rows": rows,
        "scope": protocol["scope"],
        "runtime_math_changed": False,
        "real_event_cases": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    fixtures = Path(__file__).resolve().parents[2] / "tests/fixtures"
    parser.add_argument("--kernel", type=Path, required=True)
    parser.add_argument(
        "--protocol", type=Path, default=fixtures / "jyotish-jpl-grid-protocol.json"
    )
    parser.add_argument(
        "--reference", type=Path, default=fixtures / "jyotish-jpl-grid-reference.json"
    )
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists() or args.report.resolve() in {
        p.resolve() for p in (args.kernel, args.protocol, args.reference)
    }:
        parser.error("report must be new and must not overwrite an input")
    try:
        result = audit(args.kernel.resolve(), args.protocol, args.reference)
    except Exception as exc:
        result = {
            "status": "audit_error",
            "error": repr(exc),
            "rows": [],
            "real_event_cases": 0,
        }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x") as stream:
        stream.write(json.dumps(result, indent=2) + "\n")
    print(result["status"])
    raise SystemExit(0 if result["status"] == "passed_original_TT_grid" else 1)


if __name__ == "__main__":
    main()
