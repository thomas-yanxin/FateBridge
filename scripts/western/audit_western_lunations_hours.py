"""Bounded lunation oracle and planetary-hour counterexample audit.

USNO published UT1 minute values are external answers. Real sunrise boundary
checks are behavioral regressions against a declared horizon policy, not
independent validation of sunrise geometry or empirical predictive power.
"""

import argparse
import hashlib
import json
import platform
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from fatebridge.core.astro.classical import (
    _planetary_hours,
    _prenatal_syzygy,
    _sun_event,
)
from fatebridge.core.astro.geometry import _julian_day
from fatebridge.core.astro.time_scales import ephemeris_time
from fatebridge.core.ephemeris_runtime import (
    configure_ephemeris_path,
    configured_ephemeris_path,
    ephemeris_call,
    ephemeris_model_from_retflag,
    swe,
)

ROOT = Path(__file__).resolve().parents[2]
REFERENCE = ROOT / "tests/fixtures/western-usno-lunations-2026.json"
SEQUENCE = ROOT / "tests/fixtures/western-planetary-hour-sequence-dio-1914.json"


def audit(ephemeris_dir=None):
    reference = json.loads(REFERENCE.read_text())
    cases, dawns = [], []
    observed_models = set()
    previous_path = configured_ephemeris_path()
    try:
        with tempfile.TemporaryDirectory(prefix="fatebridge-lunation-audit-") as empty:
            configure_ephemeris_path(str(ephemeris_dir) if ephemeris_dir else empty)
            for case in reference["cases"]:
                expected = _julian_day(
                    datetime.fromisoformat(case["nominal_ut1"]).replace(
                        tzinfo=timezone.utc
                    )
                )
                actual = _prenatal_syzygy(expected + 0.5)
                if actual is None:
                    raise RuntimeError(f"Lunation unavailable: {case}")
                for body in (swe.SUN, swe.MOON):
                    _, flag = ephemeris_call(
                        "calc",
                        actual["julian_day_tt"],
                        body,
                        swe.FLG_SWIEPH | swe.FLG_SPEED,
                    )
                    observed_models.add(ephemeris_model_from_retflag(flag))
                error = abs(actual["julian_day_ut1"] - expected) * 86400
                cases.append(
                    {
                        "reference": case,
                        "actual": actual,
                        "error_seconds": error,
                        "passed": actual["type"] == case["type"]
                        and error <= reference["tolerance_seconds"],
                    }
                )
            for date, ruler in [
                ("2026-04-15", "Mercury"),
                ("2026-06-01", "Moon"),
                ("2026-09-01", "Mars"),
                ("2026-12-01", "Mars"),
            ]:
                jd = ephemeris_time(
                    datetime.fromisoformat(date).replace(tzinfo=timezone.utc)
                ).jd_ut1
                rise = _sun_event(jd, 0, 51.5, True)
                if rise is None:
                    raise RuntimeError(f"Sunrise unavailable: {date}")
                before = _planetary_hours(rise - 1 / 86400, 0, 51.5, "UTC")
                after = _planetary_hours(rise + 1 / 86400, 0, 51.5, "UTC")
                dawns.append(
                    {
                        "date": date,
                        "location": {"longitude": 0, "latitude": 51.5},
                        "sunrise_jd_ut1": rise,
                        "before": before,
                        "after": after,
                        "passed": before is not None
                        and after is not None
                        and before["is_day"] is False
                        and before["hour_number"] == 12
                        and after["is_day"] is True
                        and after["hour_number"] == 1
                        and after["day_ruler"] == after["hour_ruler"] == ruler,
                    }
                )
    finally:
        configure_ephemeris_path(previous_path)
    sources = [
        "src/fatebridge/core/astro/classical.py",
        "src/fatebridge/core/astro/time_scales.py",
        "src/fatebridge/core/astro/chart.py",
        "src/fatebridge/core/output_charts.py",
        "src/fatebridge/services/astrology.py",
        "tests/western/test_western_lunations_hours.py",
        "tests/astronomy/test_swisseph_runtime_guards.py",
        "scripts/western/audit_western_lunations_hours.py",
    ]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "platform": platform.system() + "-" + platform.machine(),
        "swisseph_version": swe.version,
        "observed_models": sorted(observed_models),
        "ephemeris_files_sha256": (
            {
                path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                for path in sorted(ephemeris_dir.glob("*.se1"))
            }
            if ephemeris_dir
            else {}
        ),
        "reference_kind": reference["reference_kind"],
        "reference_url": reference["source_url"],
        "reference_sha256": hashlib.sha256(REFERENCE.read_bytes()).hexdigest(),
        "lunations": {
            "count": len(cases),
            "passed": sum(case["passed"] for case in cases),
            "time_scale": "UT1",
            "tolerance_seconds": reference["tolerance_seconds"],
            "maximum_error_seconds": max(case["error_seconds"] for case in cases),
            "cases": cases,
        },
        "sunrise_boundary_regressions": {
            "cases": dawns,
            "independent_sunrise_geometry_oracle": False,
        },
        "primary_text": {
            "annotation": json.loads(SEQUENCE.read_text()),
            "reference_sha256": hashlib.sha256(SEQUENCE.read_bytes()).hexdigest(),
            "independent_expert_review": False,
        },
        "code_sha256": {
            name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in sources
        },
        "validation_limits": {
            "all_epochs_validated": False,
            "sunrise_weather_and_horizon_observed": False,
            "free_model_dialogue_evaluated": False,
            "all_three_full_marks_established": False,
        },
    }


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--ephemeris-dir", type=Path)
    args = parser.parse_args()
    if args.ephemeris_dir and not args.ephemeris_dir.is_dir():
        parser.error("ephemeris directory does not exist")
    report = audit(args.ephemeris_dir)
    encoded = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.write_text(encoded, encoding="utf-8")
        print(
            json.dumps(
                {
                    "lunations": report["lunations"]["passed"],
                    "maximum_error_seconds": report["lunations"][
                        "maximum_error_seconds"
                    ],
                    "models": report["observed_models"],
                    "sunrise_regressions": sum(
                        row["passed"]
                        for row in report["sunrise_boundary_regressions"]["cases"]
                    ),
                }
            )
        )
    else:
        print(encoded, end="")
    if not all(
        case["passed"]
        for case in [
            *report["lunations"]["cases"],
            *report["sunrise_boundary_regressions"]["cases"],
        ]
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
