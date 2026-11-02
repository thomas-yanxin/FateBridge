"""Reproduce the bounded western astronomy audit against frozen NASA data.

This is a numerical audit, not a life-event prediction score. It always
reports untested axes explicitly and never averages them into astronomy.
"""

import argparse
import hashlib
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from fatebridge.core.astro.geometry import _julian_day
from fatebridge.core.ephemeris_runtime import configure_ephemeris_path, swe
from fatebridge.services.astrology import calculate_core_chart_analysis

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "tests/fixtures/western-horizons.json"


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    frozen = json.loads(REFERENCE.read_text())
    cases = []
    maxima = {}
    with tempfile.TemporaryDirectory(prefix="fatebridge-western-empty-") as empty:
        configure_ephemeris_path(empty)
        for reference in frozen["references"]:
            assert (
                hashlib.sha256(reference["response"]["result"].encode()).hexdigest()
                == reference["response_sha256"]
            )
            body = reference["body"]
            summary = {
                "before_longitude_arcsec": 0.0,
                "longitude_arcsec": 0.0,
                "latitude_arcsec": 0.0,
            }
            for row in reference["rows"]:
                moment = datetime.fromisoformat(row["utc"])
                result = calculate_core_chart_analysis(
                    birth_year=moment.year,
                    birth_month=moment.month,
                    birth_day=moment.day,
                    birth_hour=moment.hour,
                    birth_minute=moment.minute,
                    birth_timezone="UTC",
                    birth_longitude=0.0,
                    birth_latitude=51.5,
                    chart_variant="chart",
                )
                if "error" in result:
                    raise RuntimeError(result)
                point = next(p for p in result["planets"] if p["id"] == body)
                # Reproduce the previous UTC-as-UT1 route, with the same four
                # decimal public rounding, without altering the reference.
                old, _ = swe.calc_ut(_julian_day(moment), getattr(swe, body.upper()))

                def error(longitude):
                    return (
                        abs(
                            (longitude - row["apparent_ecliptic_longitude"] + 180) % 360
                            - 180
                        )
                        * 3600
                    )

                errors = {
                    "before_longitude_arcsec": error(round(old[0], 4)),
                    "longitude_arcsec": error(point["longitude"]),
                    "latitude_arcsec": abs(
                        point["latitude"] - row["apparent_ecliptic_latitude"]
                    )
                    * 3600,
                }
                summary = {
                    key: max(summary[key], value) for key, value in errors.items()
                }
                cases.append(
                    {
                        "body": body,
                        "utc": row["utc"],
                        **errors,
                        "passed": max(
                            errors["longitude_arcsec"], errors["latitude_arcsec"]
                        )
                        <= frozen["tolerance_arcseconds"],
                    }
                )
            maxima[body] = summary
    code_paths = [
        "src/fatebridge/core/astro/geometry.py",
        "src/fatebridge/core/astro/time_scales.py",
        "src/fatebridge/core/astro/horizon.py",
        "src/fatebridge/core/astro/ephemeris.py",
        "src/fatebridge/core/astro/chart.py",
        "src/fatebridge/core/astro/classical.py",
        "src/fatebridge/core/astro/layout.py",
        "src/fatebridge/core/astro/birth.py",
        "src/fatebridge/core/classical_western.py",
        "src/fatebridge/core/predictive/_common.py",
        "src/fatebridge/core/output_charts.py",
        "src/fatebridge/core/response_models.py",
        "src/fatebridge/utils/timezones.py",
        "src/fatebridge/core/ptolemy.py",
        "src/fatebridge/services/astrology.py",
        "src/fatebridge/data/knowledge/western-leap-seconds.json",
    ]
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "oracle": frozen["source"],
        "reference_sha256": hashlib.sha256(REFERENCE.read_bytes()).hexdigest(),
        "swisseph_version": swe.version,
        "ephemeris": "Moshier, empty data directory",
        "astronomy": {
            "scope": frozen["scope"],
            "tolerance_arcseconds": frozen["tolerance_arcseconds"],
            "cases": len(cases),
            "passed": sum(case["passed"] for case in cases),
            "maxima": maxima,
        },
        "primary_text": {
            "status": "implemented_and_tested_subset",
            "edition": "Ptolemy, Robbins 1940, I.7, I.13-19 and III.10 Fortune formula only",
            "excluded": "Other chapters, terms variants, full natal judgement, medical or lifespan assertions",
        },
        "interpretation": {
            "status": "deterministic_templates_with_same_run_source_paths",
            "free_text_semantic_accuracy_measured": False,
            "real_model_dialogue_evaluated": False,
        },
        "real_world_prediction": {
            "status": "not_evaluated",
            "independently_observed_cases": 0,
            "score": None,
            "next_requirement": "Frozen outcome definitions, independent cohort, advance forecasts, complete follow-up, fixed baseline and out-of-sample replication",
        },
        "all_four_full_marks_established": False,
        "current_goal_axes": [
            "calendar_and_astronomy",
            "specified_original_text",
            "interpretation_fidelity",
        ],
        "all_three_full_marks_established": False,
        "code_sha256": {
            name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in code_paths
        },
        "cases": cases,
    }
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
        print(
            f"Astronomy: {report['astronomy']['passed']}/{len(cases)} within {frozen['tolerance_arcseconds']} arcsec; report: {args.output}"
        )
    else:
        print(text, end="")
    if not all(case["passed"] for case in cases):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
