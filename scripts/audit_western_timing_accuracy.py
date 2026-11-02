"""Audit native timing against frozen independent astronomy, with no outcome proxy."""

import argparse
import hashlib
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from fatebridge.core.astro.geometry import _julian_day
from fatebridge.core.astrology_events import find_cardinal_ingress_utc
from fatebridge.core.ephemeris_runtime import configure_ephemeris_path, swe
from fatebridge.core.predictive._common import build_subject
from fatebridge.core.predictive.returns import build_return_payload

ROOT = Path(__file__).resolve().parents[1]


def subject(moment):
    return build_subject(
        name="fictional-audit",
        local_datetime=moment,
        longitude=0.0,
        latitude=51.5,
        timezone_name="UTC",
        house_system="P",
    )


def angle_error(a, b):
    return abs((a - b + 180) % 360 - 180) * 3600


def audit(ephemeris_dir=None):
    positions_path = ROOT / "tests/fixtures/western-horizons.json"
    returns_path = ROOT / "tests/fixtures/western-returns-horizons.json"
    hko_path = ROOT / "tests/fixtures/bazi-timing-hko-2026.json"
    fortune_path = ROOT / "tests/fixtures/western-ptolemy-fortune-robbins-1940.json"
    positions = json.loads(positions_path.read_text())
    returns = json.loads(returns_path.read_text())
    hko = json.loads(hko_path.read_text())
    for recording in [*positions["references"], *returns["recordings"]]:
        if (
            hashlib.sha256(recording["response"]["result"].encode()).hexdigest()
            != recording["response_sha256"]
        ):
            raise ValueError("Independent source recording hash mismatch")
    position_rows, return_rows, ingress_rows = [], [], []
    observed_models = set()
    with tempfile.TemporaryDirectory(prefix="fatebridge-western-timing-") as empty:
        configure_ephemeris_path(str(ephemeris_dir) if ephemeris_dir else empty)
        for reference in positions["references"]:
            for row in reference["rows"]:
                moment = datetime.fromisoformat(row["utc"])
                chart = subject(moment)
                observed_models.add(chart.calculation_basis["ephemeris_model"])
                native = getattr(chart, reference["body"].lower())
                previous, _ = swe.calc_ut(
                    _julian_day(moment), getattr(swe, reference["body"].upper())
                )
                error = angle_error(native.abs_pos, row["apparent_ecliptic_longitude"])
                latitude_error = (
                    abs(native.latitude - row["apparent_ecliptic_latitude"]) * 3600
                )
                position_rows.append(
                    {
                        "body": reference["body"],
                        "utc": row["utc"],
                        "previous_utc_as_ut1_longitude_error_arcsec": angle_error(
                            previous[0], row["apparent_ecliptic_longitude"]
                        ),
                        "longitude_error_arcsec": error,
                        "latitude_error_arcsec": latitude_error,
                        "passed": max(error, latitude_error)
                        <= positions["tolerance_arcseconds"],
                    }
                )
        for case in returns["cases"]:
            key = "solar_return" if case["planet"] == "Sun" else "lunar_return"
            result = build_return_payload(
                subject(datetime.fromisoformat(case["birth_utc"])),
                analysis_datetime=datetime.fromisoformat(case["analysis_utc"]),
                return_longitude=85.32,
                return_latitude=27.72,
                return_timezone="+05:45",
                include=[key],
            )[key]
            actual = datetime.fromisoformat(result["return_datetime_utc"])
            error = abs(
                (
                    actual - datetime.fromisoformat(case["expected_return_utc"])
                ).total_seconds()
            )
            return_rows.append(
                {
                    "case_id": case["case_id"],
                    "body": case["planet"],
                    "expected_return_utc": case["expected_return_utc"],
                    "actual_return_utc": actual.isoformat(),
                    "error_seconds": error,
                    "tolerance_seconds": returns["tolerances_seconds"][case["planet"]],
                    "solver_residual_arcseconds": result["solver"][
                        "residual_arcseconds"
                    ],
                    "not_after_analysis": result["solver"]["event_not_after_analysis"],
                    "passed": error <= returns["tolerances_seconds"][case["planet"]]
                    and result["solver"]["event_not_after_analysis"],
                }
            )
        for case in hko["cases"]:
            if case["term"] not in {"春分", "夏至", "秋分", "冬至"}:
                continue
            actual = find_cardinal_ingress_utc(2026, case["term"])
            error = abs((actual - datetime.fromisoformat(case["at"])).total_seconds())
            ingress_rows.append(
                {
                    "term": case["term"],
                    "expected": case["at"],
                    "actual_utc": actual.isoformat(),
                    "error_seconds": error,
                    "passed": error <= hko["tolerance_seconds"],
                }
            )
    code_paths = [
        "src/fatebridge/core/predictive/native_chart.py",
        "src/fatebridge/core/predictive/_common.py",
        "src/fatebridge/core/predictive/returns.py",
        "src/fatebridge/core/predictive/primary_directions.py",
        "src/fatebridge/core/astro/time_scales.py",
        "src/fatebridge/core/astro/geometry.py",
        "src/fatebridge/core/astro/ephemeris.py",
        "src/fatebridge/core/astro/horizon.py",
        "src/fatebridge/core/ephemeris_runtime.py",
        "src/fatebridge/core/astro/birth.py",
        "src/fatebridge/utils/timezones.py",
        "src/fatebridge/data/knowledge/western-leap-seconds.json",
        "src/fatebridge/core/astrology_events.py",
        "src/fatebridge/core/output_western.py",
        "src/fatebridge/core/output_charts.py",
        "src/fatebridge/services/western_timing_tools.py",
        "src/fatebridge/api.py",
        "src/fatebridge/core/ptolemy.py",
        "tests/test_western_timing_accuracy.py",
        "tests/test_western_accuracy_transports.py",
        "scripts/gen_western_returns_reference.py",
        "scripts/audit_western_timing_accuracy.py",
    ]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "method_id": "western_native_timing_independent_astronomy_v1",
        "ephemeris": f"Swiss {swe.version}; "
        + (
            "operator-supplied files"
            if ephemeris_dir
            else "Moshier, empty data directory"
        ),
        "observed_ephemeris_models": sorted(observed_models),
        "ephemeris_file_sha256": (
            {
                path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                for path in sorted(ephemeris_dir.glob("*.se1"))
            }
            if ephemeris_dir
            else {}
        ),
        "scope": "Tropical geocentric apparent positions, solar/lunar preceding returns and cardinal ingresses; no life-event inference",
        "sources": [positions["source"], returns["source"], *hko["sources"]],
        "reference_sha256": {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (positions_path, returns_path, hko_path, fortune_path)
        },
        "positions": {
            "count": len(position_rows),
            "passed": sum(c["passed"] for c in position_rows),
            "tolerance_arcseconds": positions["tolerance_arcseconds"],
            "maximum_longitude_error_arcsec": max(
                c["longitude_error_arcsec"] for c in position_rows
            ),
            "maximum_latitude_error_arcsec": max(
                c["latitude_error_arcsec"] for c in position_rows
            ),
            "moon_previous_maximum_error_arcsec": max(
                c["previous_utc_as_ut1_longitude_error_arcsec"]
                for c in position_rows
                if c["body"] == "Moon"
            ),
            "moon_native_maximum_error_arcsec": max(
                c["longitude_error_arcsec"]
                for c in position_rows
                if c["body"] == "Moon"
            ),
            "cases": position_rows,
        },
        "returns": {
            "count": len(return_rows),
            "passed": sum(c["passed"] for c in return_rows),
            "tolerances_seconds": returns["tolerances_seconds"],
            "cases": return_rows,
        },
        "cardinal_ingresses": {
            "count": len(ingress_rows),
            "passed": sum(c["passed"] for c in ingress_rows),
            "tolerance_seconds": hko["tolerance_seconds"],
            "cases": ingress_rows,
        },
        "primary_text": {
            "status": "implemented_subset_requires_independent_expert_review",
            "edition": "Ptolemy, Tetrabiblos, Robbins 1940",
            "chapters": ["I.7", "I.13-19", "III.10 Fortune formula only"],
            "full_primary_directions_validated": False,
            "fortune_source_url": json.loads(fortune_path.read_text())["source_url"],
            "fortune_reference_kind": "manual_primary_text_annotation_and_arithmetic_examples",
        },
        "interpretation": {
            "structured_fact_transport_parity": "covered_by_native_MCP_REST_CLI_tests",
            "free_text_semantic_accuracy_measured": False,
            "real_model_dialogue_evaluated": False,
        },
        "real_world_prediction": {
            "independently_observed_cases": 0,
            "score": None,
            "status": "not_evaluated",
            "astronomical_event_accuracy_is_not_life_event_accuracy": True,
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
    }


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--ephemeris-dir",
        type=Path,
        help="Audit operator-supplied Swiss files; default audits an empty directory / Moshier",
    )
    args = parser.parse_args()
    if args.ephemeris_dir and not args.ephemeris_dir.is_dir():
        parser.error("ephemeris directory does not exist")
    report = audit(args.ephemeris_dir)
    encoded = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(encoded)
        print(
            json.dumps(
                {
                    key: {k: v for k, v in report[key].items() if k != "cases"}
                    for key in ["positions", "returns", "cardinal_ingresses"]
                }
            )
        )
    else:
        print(encoded, end="")
    if not all(
        c["passed"]
        for key in ["positions", "returns", "cardinal_ingresses"]
        for c in report[key]["cases"]
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
