"""Check actual India physical directions against sealed independent endpoints.

Known failures deliberately exit 1. Reference validation imports no candidate;
the audit imports the selected runtime only after validating frozen material.
"""

import argparse
import hashlib
import json
import math
import platform
from datetime import datetime
from pathlib import Path

REFERENCE_SHA256 = "74d7b76d98bc925d3e09402ad740e22b575cf81658b6a193fe511e99671bf32b"
EXTENDED_REFERENCE_SHA256 = (
    "478bb29f14821c50bfe9ba86bf26a81205a7da89812c63f0c866ef15268da791"
)
ROOT = Path(__file__).resolve().parents[2]


def validate_reference(path):
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    groups = {
        REFERENCE_SHA256: ("Sun", "Mercury", "Venus", "Mars"),
        EXTENDED_REFERENCE_SHA256: ("Moon", "Jupiter", "Saturn"),
    }
    if digest not in groups:
        raise ValueError("Frozen endpoint reference changed")
    value = json.loads(path.read_text())
    if value["candidate_imports"] or value["Swiss_imports"]:
        raise ValueError("Expected directions must not use candidate calculations")
    wanted = {(i, body) for i in (0, 1) for body in groups[digest]}
    directions = value["expected_directions"]
    if (
        len(directions) != len(wanted)
        or {(r["index"], r["body"]) for r in directions} != wanted
    ):
        raise ValueError("Endpoint direction coverage changed")
    for row in value["requests"]:
        if (
            hashlib.sha256(row["raw_response_utf8"].encode()).hexdigest()
            != row["raw_sha256"]
        ):
            raise ValueError("Raw endpoint response changed")
    for row in directions:
        unit = row["true_equatorial_unit_direction"]
        if len(unit) != 3 or not all(math.isfinite(x) for x in unit):
            raise ValueError("Invalid independent direction")
        if abs(math.hypot(*unit) - 1) > 1e-12:
            raise ValueError("Independent direction must be normalized")
    return value


def separation_arcsec(a, b):
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


def audit(reference_path, ephemeris):
    material = validate_reference(reference_path)
    import fatebridge
    from fatebridge.core import ephemeris_runtime as e
    from fatebridge.core import jyotish
    from fatebridge.core.astro.birth import build_astro_birth_info

    e.configure_ephemeris_path(str(ephemeris))
    rows, raw_positions = [], []
    for birth in material["birth_inputs"]:
        moment = datetime.fromisoformat(birth["civil_utc"])
        subject = build_astro_birth_info(
            birth_year=moment.year,
            birth_month=moment.month,
            birth_day=moment.day,
            birth_hour=moment.hour,
            birth_minute=moment.minute,
            birth_second=moment.second,
            birth_microsecond=moment.microsecond,
            birth_timezone="UTC",
            birth_longitude=birth["longitude"],
            birth_latitude=birth["latitude"],
            use_true_solar_time=False,
            preserve_instant=True,
        )
        try:
            actual = jyotish.positions(subject)
            raw_positions.append({"input": birth, "result": actual})
        except Exception as error:
            for expected in material["expected_directions"]:
                if expected["index"] == birth["index"]:
                    rows.append(
                        {
                            "index": birth["index"],
                            "body": expected["body"],
                            "status": "unavailable",
                            "reason": str(error),
                            "passed": False,
                        }
                    )
            continue
        same_epoch = actual["julian_day_tt"] == birth["epoch_jd_tt"]
        for expected in material["expected_directions"]:
            if expected["index"] != birth["index"]:
                continue
            point = actual["equatorial"].get(expected["body"])
            if point is None or point["ephemeris_model"] != "swieph":
                rows.append(
                    {
                        "index": birth["index"],
                        "body": expected["body"],
                        "status": "source_unavailable",
                        "passed": False,
                    }
                )
                continue
            ra, dec = map(
                math.radians, [point["right_ascension"], point["declination"]]
            )
            unit = [
                math.cos(dec) * math.cos(ra),
                math.cos(dec) * math.sin(ra),
                math.sin(dec),
            ]
            error = separation_arcsec(unit, expected["true_equatorial_unit_direction"])
            rows.append(
                {
                    "index": birth["index"],
                    "body": expected["body"],
                    "status": "compared",
                    "same_physical_epoch": same_epoch,
                    "error_arcsec": error,
                    "passed": same_epoch and error <= material["position_line_arcsec"],
                }
            )
    return {
        "status": (
            "passed"
            if len(rows) == len(material["expected_directions"])
            and all(r["passed"] for r in rows)
            else "endpoint_physics_unresolved"
        ),
        "package": fatebridge.__file__,
        "runtime_source_sha256": hashlib.sha256(
            Path(jyotish.__file__).read_bytes()
        ).hexdigest(),
        "reference_sha256": hashlib.sha256(reference_path.read_bytes()).hexdigest(),
        "platform": platform.platform(),
        "expected_rows": len(material["expected_directions"]),
        "passed_rows": sum(row["passed"] for row in rows),
        "position_line_arcsec": material["position_line_arcsec"],
        "rows": rows,
        "raw_positions": raw_positions,
        "scope": "Two exposed synthetic civil/TT endpoint inputs, actual India equatorial directions, independent JPL/ERFA reference. No Lahiri zero-point, future UTC/UT1 observation or reality-prediction certification.",
        "real_event_cases": 0,
        "formally_registered_studies": 0,
        "overall_goal_complete": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reference",
        type=Path,
        default=ROOT / "tests/fixtures/jyotish-endpoint-reference.json",
    )
    parser.add_argument("--ephemeris", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.report.resolve() == args.reference.resolve():
        parser.error("report must not overwrite frozen source material")
    result = audit(args.reference, args.ephemeris)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                key: result[key]
                for key in [
                    "status",
                    "expected_rows",
                    "passed_rows",
                    "position_line_arcsec",
                ]
            }
        )
    )
    raise SystemExit(0 if result["status"] == "passed" else 1)
