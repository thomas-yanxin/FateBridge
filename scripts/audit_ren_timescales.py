"""Primary solar coordinates and complete PMO minutes after TT/civil repair."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/fixtures/ren_timescale_v1"
IMPLEMENTATION = (
    "src/fatebridge/core/almanac.py",
    "src/fatebridge/core/astro/time_scales.py",
    "src/fatebridge/core/astro/historical_utc.py",
    "src/fatebridge/core/metaphysics/ren_calendar.py",
    "src/fatebridge/services/metaphysics.py",
    "src/fatebridge/core/output_chinese.py",
    "scripts/audit_ren_timescales.py",
    "scripts/audit_ren_calendar_pmo.py",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reference(corpus: Path = CORPUS) -> dict[str, Any]:
    manifest = json.loads((corpus / "freeze.json").read_text())
    names = {"reference.json", "iers-history.txt"}
    if set(manifest["files"]) != names or {
        p.name for p in corpus.iterdir()
    } != names | {"freeze.json"}:
        raise ValueError("Frozen time-scale inventory changed")
    for name, expected in manifest["files"].items():
        if sha(corpus / name) != expected:
            raise ValueError(f"Frozen time-scale source changed: {name}")
    ref = json.loads((corpus / "reference.json").read_text())
    for name, expected in ref["references"].items():
        if sha(ROOT / name) != expected:
            raise ValueError(f"Referenced time-scale source changed: {name}")
    return ref


def audit() -> tuple[dict[str, Any], dict[str, Any]]:
    ref = reference()
    data = json.loads((ROOT / "tests/fixtures/western-horizons.json").read_text())
    sun = next(row for row in data["references"] if row["body"] == "Sun")
    raw = sun["response"]["result"]
    if hashlib.sha256(raw.encode()).hexdigest() != sun["response_sha256"]:
        raise ValueError("JPL raw solar response changed")
    rows = list(
        csv.reader(raw.split("$$SOE")[1].split("$$EOE")[0].strip().splitlines())
    )
    if len(rows) != 12:
        raise ValueError("All twelve independent JPL solar epochs are required")
    before = {name: sha(ROOT / name) for name in IMPLEMENTATION}
    from fatebridge.core.astro.time_scales import ephemeris_time
    from fatebridge.core.ephemeris_runtime import (
        ephemeris_call,
        ephemeris_model_from_retflag,
        swe,
    )

    coordinates = []
    for row in rows:
        instant = datetime.strptime(row[0].strip(), "%Y-%b-%d %H:%M:%S.%f").replace(
            tzinfo=timezone.utc
        )
        epoch = ephemeris_time(instant)
        position, flags = ephemeris_call("calc", epoch.jd_tt, swe.SUN, swe.FLG_SWIEPH)
        expected_longitude, expected_latitude = float(row[3]), float(row[4])
        longitude_error = ((position[0] - expected_longitude + 180) % 360 - 180) * 3600
        latitude_error = (position[1] - expected_latitude) * 3600
        coordinates.append(
            dict(
                published_clock=instant.isoformat(),
                published_time_scale="UT1" if instant.year < 1962 else "UTC",
                civil_policy=epoch.method,
                future_leap_seconds_assumed_unchanged=epoch.future_leap_seconds_assumed_unchanged,
                actual_model=ephemeris_model_from_retflag(flags),
                jd_tt=epoch.jd_tt,
                expected_longitude=expected_longitude,
                expected_latitude=expected_latitude,
                actual_longitude=position[0],
                actual_latitude=position[1],
                longitude_error_arcseconds=longitude_error,
                latitude_error_arcseconds=latitude_error,
                matched=max(abs(longitude_error), abs(latitude_error))
                <= ref["criteria"]["sun_coordinate_absolute_arcseconds"],
            )
        )
    spec = importlib.util.spec_from_file_location(
        "pmo_timescale", ROOT / "scripts/audit_ren_calendar_pmo.py"
    )
    assert spec and spec.loader
    pmo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pmo)
    minutes = pmo.audit()
    if (
        minutes["minute_criterion"]["max_absolute_difference_seconds"]
        != ref["criteria"]["printed_minute_absolute_seconds"]
    ):
        raise ValueError("The independent printed-minute criterion must not change")
    unchanged = before == {name: sha(ROOT / name) for name in IMPLEMENTATION}
    summary = {key: value for key, value in minutes.items() if key != "comparisons"}
    return (
        dict(
            audit_id="ren_timescale_v1",
            criteria=ref["criteria"],
            jpl_source=sun["request_url"],
            jpl_response_sha256=sun["response_sha256"],
            solar_coordinate_checks=coordinates,
            solar_coordinate_check_count=len(coordinates),
            solar_coordinate_failure_count=sum(
                not row["matched"] for row in coordinates
            ),
            pmo_minute_summary=summary,
            implementation_sha256=before,
            implementation_unchanged_during_audit=unchanged,
            all_performed_comparisons_passed=(
                unchanged
                and all(row["matched"] for row in coordinates)
                and minutes["all_performed_comparisons_passed"]
            ),
            full_supported_calendar_domain_certified=False,
            goal_complete=False,
            source_sha256=sha(CORPUS / "reference.json"),
            limits=ref["limits"],
        ),
        minutes,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report, minutes = audit()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    companion = args.output.with_name(args.output.stem + "-pmo.json")
    companion.write_text(json.dumps(minutes, ensure_ascii=False, indent=2) + "\n")
    report["complete_pmo_comparisons"] = {
        "file": companion.name,
        "sha256": sha(companion),
    }
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "solar_coordinate_checks": report["solar_coordinate_check_count"],
                "solar_coordinate_failures": report["solar_coordinate_failure_count"],
                "minute_compared": minutes["compared_count"],
                "minute_failures": minutes["minute_failure_count"],
                "max_minute_difference_seconds": minutes[
                    "max_absolute_difference_seconds"
                ],
                "boundary_pairs": minutes["boundary_pair_count"],
                "all_performed_comparisons_passed": report[
                    "all_performed_comparisons_passed"
                ],
            }
        )
    )
    return 0 if report["all_performed_comparisons_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
