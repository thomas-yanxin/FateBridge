"""Replay strict DE441 India positives against a sealed J2000 reference.

The kernel can be the declared small coefficient fixture or a complete DE441.
Neither a missing kernel nor a native refusal counts as a positive pass.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
from typing import TypedDict

REFERENCE_SHA256 = "d94a2f582520a0a330a46342c0dad5a316cb3ac1609e80161fd8a38197b7df0e"


class BirthPayload(TypedDict):
    birth_year: int
    birth_month: int
    birth_day: int
    birth_hour: int
    birth_minute: int
    birth_timezone: str
    birth_longitude: float
    birth_latitude: float


class ReferenceBirthPayload(BirthPayload):
    birth_second: int
    birth_microsecond: int


class IndiaOptions(TypedDict):
    ephemeris_policy: str
    cheshta_model: str


def direction_error(longitude: float, latitude: float, reference: list[float]) -> float:
    lon, lat = map(math.radians, (longitude, latitude))
    actual = (
        math.cos(lat) * math.cos(lon),
        math.cos(lat) * math.sin(lon),
        math.sin(lat),
    )
    a, b = actual, reference
    cross = (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )
    return (
        math.degrees(
            math.atan2(
                math.sqrt(sum(x * x for x in cross)), sum(x * y for x, y in zip(a, b))
            )
        )
        * 3600
    )


def audit(kernel: Path, reference_path: Path) -> dict:
    from fatebridge.core import ephemeris_runtime as e
    from fatebridge.core.astro.birth import build_astro_birth_info
    from fatebridge.core.execution_context import call_clock
    from fatebridge.core.jyotish import build_india, positions
    from fatebridge.services.jyotish import calculate_vimshottari

    reference_raw = reference_path.read_bytes()
    if hashlib.sha256(reference_raw).hexdigest() != REFERENCE_SHA256:
        raise ValueError("The sealed J2000 reference changed")
    reference = json.loads(reference_raw)
    os.environ["SE_EPHE_PATH"] = str(kernel.parent)
    os.environ["FATEBRIDGE_JPL_FILE"] = kernel.name
    e.configure_ephemeris_path()
    payload: BirthPayload = dict(
        birth_year=2000,
        birth_month=1,
        birth_day=1,
        birth_hour=12,
        birth_minute=0,
        birth_timezone="UTC",
        birth_longitude=0.0,
        birth_latitude=0.0,
    )
    options: IndiaOptions = dict(
        ephemeris_policy="require_data_files", cheshta_model="simon1994_j2000"
    )
    aligned: ReferenceBirthPayload = {
        **payload,
        "birth_hour": 11,
        "birth_minute": 58,
        "birth_second": 55,
        "birth_microsecond": 816000,
    }
    raw = positions(build_astro_birth_info(**aligned, preserve_instant=True), **options)
    if raw["julian_day_tt"] != 2451545.0:
        raise ValueError("The declared recorded birth did not retain its reference TT")
    rows = []
    for row in reference["rows"]:
        point = raw["motion_true_j2000"][row["body"]]
        error = direction_error(
            point["longitude"], point["latitude"], row["ecliptic_unit_vector"]
        )
        rows.append(
            {
                "body": row["body"],
                "epoch_jd_tt": raw["julian_day_tt"],
                "model": point["ephemeris_model"],
                "error_arcsec": error,
                "passed": point["ephemeris_model"] == "jpl"
                and error <= reference["position_line_arcsec"],
            }
        )
    with call_clock("2026-10-23T00:00:00Z"):
        india = build_india(
            build_astro_birth_info(**payload, preserve_instant=True),
            divisions=[9, 10],
            birth_time_uncertainty_minutes=1,
            **options,
        )
        service = calculate_vimshottari(
            **payload,
            analysis_year=2001,
            divisions=[9, 10],
            birth_time_uncertainty_minutes=1,
            **options,
        )
    if "error" in service:
        raise ValueError("Vimshottari did not return its strict positive result")
    profiles = {}
    for name, result in [("india", india), ("vimshottari", service["india"])]:
        profile = result["profile"]
        source = profile["physical_ephemeris_source"]
        if (
            profile["physical_backend_policy"] != "strict_jpl"
            or profile["ephemeris_models"] != ["jpl"]
            or len(source["files"]) != 1
            or not all(r["model"] == "jpl" for r in source["by_factor"].values())
            or result["birth_time_sensitivity"]["sample_count"] != 5
        ):
            raise ValueError("Strict positive frame/source/grid requirements failed")
        profiles[name] = {
            "sample_count": 5,
            "physical_source": source,
            "original_utc": profile["clock_context"]["calculation_utc_datetime"],
        }
    passed = len(rows) == 5 and all(row["passed"] for row in rows)
    return {
        "status": "passed" if passed else "failed",
        "rows": rows,
        "position_line_arcsec": reference["position_line_arcsec"],
        "profiles": profiles,
        "reference_sha256": REFERENCE_SHA256,
        "runtime_source": str(Path(e.__file__).resolve()),
        "independent_epochs": 1,
        "new_independent_epochs": 0,
        "real_event_cases": 0,
        "scope": "Five existing JPL/ERFA geometric references and two strict India operations; shared DE441 dynamics, not independent observations, full chronology, Lahiri, original-text or prediction certification.",
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--kernel", required=True, type=Path)
    p.add_argument("--report", required=True, type=Path)
    p.add_argument(
        "--reference",
        type=Path,
        default=Path(__file__).resolve().parents[2]
        / "tests/fixtures/jyotish-jpl-j2000-reference.json",
    )
    a = p.parse_args()
    if a.report.resolve() in {a.kernel.resolve(), a.reference.resolve()}:
        p.error("report must not overwrite the kernel or reference")
    try:
        result = audit(a.kernel.resolve(), a.reference)
    except Exception as error:
        result = {
            "status": "failed",
            "error_type": type(error).__name__,
            "reason": getattr(error, "reason", None),
            "message": str(error),
            "positive_pass": False,
            "real_event_cases": 0,
        }
    a.report.parent.mkdir(parents=True, exist_ok=True)
    a.report.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "rows": len(result.get("rows", []))}))
    return int(result["status"] != "passed")


if __name__ == "__main__":
    raise SystemExit(main())
