"""Audit seven-planet horary events against frozen JPL Horizons grids."""

import argparse
import hashlib
import json
import zipfile
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

from fatebridge.core.astro.ephemeris import _swisseph_planet_state
from fatebridge.core.astro.geometry import angular_separation_fraction
from fatebridge.core.astro.horary_events import native_planetary_events
from fatebridge.core.astro.physical_sources import PhysicalEphemerisTrace

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests/fixtures"
PRIMARY_FRAME = "IAU2006/2000B_true_ecliptic_of_date"


def event_key(
    event: dict[str, object],
) -> tuple[str, tuple[str, ...], object, object]:
    bodies = event["bodies"]
    return (
        str(event["kind"]),
        tuple(str(body) for body in bodies) if isinstance(bodies, list | tuple) else (),
        event.get("ray_degrees"),
        event["direction"],
    )


def _match_event_rows(
    selected: list[dict[str, object]],
    expectations: list[dict[str, object]],
    case_id: str,
    plan: dict[str, object],
    reference_method: str,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    station_tol = float(plan["station_tolerance_seconds"])  # type: ignore[arg-type]
    other_tol = float(plan["contact_and_ingress_tolerance_seconds"])  # type: ignore[arg-type]
    for expected in expectations:
        expected_key = event_key(expected)
        same = [item for item in selected if event_key(item) == expected_key]
        expected_tt = float(expected["julian_day_tt"])  # type: ignore[arg-type]
        closest = min(same, key=lambda item: abs(float(item["julian_day_tt"]) - expected_tt))  # type: ignore[arg-type]
        native_tt = float(closest["julian_day_tt"])  # type: ignore[arg-type]
        residual = (native_tt - expected_tt) * 86400.0
        tolerance = station_tol if expected["kind"] == "station" else other_tol
        rows.append(
            {
                "case_id": case_id,
                "kind": expected["kind"],
                "bodies": expected["bodies"],
                "aspect": expected.get("aspect"),
                "ray_degrees": expected.get("ray_degrees"),
                "reference_julian_day_tt": expected_tt,
                "native_julian_day_tt": native_tt,
                "signed_residual_seconds": residual,
                "tolerance_seconds": tolerance,
                "passed": abs(residual) <= tolerance,
                "reference_method": reference_method,
            }
        )
    return rows


def audit() -> dict[str, object]:
    paths_protocol_path = FIXTURES / "western-event-paths-protocol.json"
    paths_reference_path = FIXTURES / "western-event-paths-horizons.json"
    ref_protocol_path = FIXTURES / "western-event-reference-points-protocol.json"
    frame_protocol_path = FIXTURES / "western-event-frames-protocol.json"
    aligned_reference_path = FIXTURES / "western-event-reference-points-horizons.json"

    paths_plan = json.loads(paths_protocol_path.read_text())
    paths_ref = json.loads(paths_reference_path.read_text())
    ref_plan = json.loads(ref_protocol_path.read_text())
    aligned_ref = json.loads(aligned_reference_path.read_text())

    assert (
        paths_ref["protocol_sha256"]
        == hashlib.sha256(paths_protocol_path.read_bytes()).hexdigest()
    )
    assert (
        aligned_ref["reference_point_control_protocol_sha256"]
        == hashlib.sha256(ref_protocol_path.read_bytes()).hexdigest()
    )
    assert (
        aligned_ref["protocol_sha256"]
        == hashlib.sha256(frame_protocol_path.read_bytes()).hexdigest()
    )
    with zipfile.ZipFile(FIXTURES / "western-event-paths-raw.zip") as archive:
        for case in paths_ref["cases"]:
            for receipt in case["receipts"].values():
                assert (
                    hashlib.sha256(archive.read(receipt["raw_file"])).hexdigest()
                    == receipt["response_sha256"]
                )
    targets = aligned_ref["native_reference_targets"]
    for case in aligned_ref["cases"]:
        for planet, receipt in case["receipts"].items():
            assert (
                hashlib.sha256(receipt["raw_response_utf8"].encode()).hexdigest()
                == receipt["response_sha256"]
            )
            assert receipt["parameters"]["COMMAND"] == f"'{targets[planet]}'"

    rows: list[dict[str, object]] = []
    mixed_definition_rows: list[dict[str, object]] = []
    cases: list[dict[str, object]] = []
    longitude_max = 0.0
    position_count = 0

    for aligned_case, mixed_case in zip(
        aligned_ref["cases"], paths_ref["cases"], strict=True
    ):
        assert str(aligned_case["case_id"]) == str(mixed_case["case_id"])
        start = float(aligned_case["start_julian_day_tt"])
        native = native_planetary_events(
            SimpleNamespace(julian_day_tt=start + 10.5, zodiac_type="Tropic")
        )
        assert native["status"] == "computed", native
        selected = [
            event
            for event in native["events"]
            if start < event["julian_day_tt"] <= start + 21
        ]
        frame_data = aligned_case["frames"][PRIMARY_FRAME]
        expected_events = frame_data["events"]
        assert Counter(event_key(e) for e in selected) == Counter(
            event_key(e) for e in expected_events
        )
        rows.extend(
            _match_event_rows(
                selected,
                expected_events,
                str(aligned_case["case_id"]),
                ref_plan,
                f"same_reference_targets:{PRIMARY_FRAME}",
            )
        )
        mixed_definition_rows.extend(
            _match_event_rows(
                selected,
                mixed_case["refined_expected"],
                str(mixed_case["case_id"]),
                paths_plan,
                "legacy_mixed_targets_iau76_80",
            )
        )
        trace = PhysicalEphemerisTrace()
        contexts: dict[float, dict[str, object]] = {}
        for planet, samples in frame_data["samples"].items():
            for tt, longitude, _ in samples:
                sampled = _swisseph_planet_state(
                    planet,
                    julian_day_tt=tt,
                    source_trace=trace,
                    motion_metadata=contexts.setdefault(tt, {}),
                    correct_motion=False,
                    include_declination=False,
                )
                assert sampled is not None, (planet, tt)
                state, _ = sampled
                error = (
                    float(angular_separation_fraction(longitude, state["longitude"]))
                    * 3600.0
                )
                longitude_max = max(longitude_max, error)
                position_count += 1
        cases.append(
            {
                "case_id": str(aligned_case["case_id"]),
                "event_counts": dict(Counter(e["kind"] for e in selected)),
                "physical_source": native["physical_ephemeris_source"],
                "frame": native["longitude_frame"],
                "ephemeris_reference_points": native.get("ephemeris_reference_points"),
            }
        )

    lon_tol = float(paths_plan["longitude_tolerance_arcseconds"])
    saturn_station_rows = [
        row for row in rows if row["kind"] == "station" and row["bodies"] == ["Saturn"]
    ]
    return {
        "protocol_sha256": aligned_ref["reference_point_control_protocol_sha256"],
        "reference_definition": {
            "frame": PRIMARY_FRAME,
            "targets": targets,
            "matches_swiss_native_targets": True,
        },
        "cases": cases,
        "position_count": position_count,
        "maximum_longitude_residual_arcseconds": longitude_max,
        "longitude_tolerance_arcseconds": lon_tol,
        "rows": rows,
        "saturn_station_rows": saturn_station_rows,
        "all_event_identities_and_counts_match": True,
        "passed_event_count": sum(1 for row in rows if row["passed"]),
        "event_count": len(rows),
        "all_cases_passed": all(bool(row["passed"]) for row in rows)
        and longitude_max <= lon_tol,
        "remaining_failures": [row for row in rows if not row["passed"]],
        "mixed_definition_diagnostic": {
            "description": (
                "Legacy fixture western-event-paths-horizons.json queried Horizons "
                "body centers (Mars 499, Jupiter 599, Saturn 699) under IAU76/80, "
                "whereas Swiss Ephemeris computes outer system barycenters (4, 5, 6) "
                "under IAU2006/2000B true ecliptic of date."
            ),
            "failing_rows": [row for row in mixed_definition_rows if not row["passed"]],
        },
        "tolerances_relaxed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=False, default=None, type=Path)
    args = parser.parse_args()
    report = audit()
    if args.output is not None:
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    else:
        pass
    print(
        json.dumps(
            {
                k: report[k]
                for k in (
                    "event_count",
                    "passed_event_count",
                    "all_cases_passed",
                    "maximum_longitude_residual_arcseconds",
                    "saturn_station_rows",
                    "remaining_failures",
                )
            },
            ensure_ascii=False,
        )
    )
    return 0 if report["all_cases_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
else:
    pass
