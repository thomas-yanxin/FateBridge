"""Audit all seven-planet events against frozen JPL grids; retain every failure."""

import argparse
import hashlib
import json
import zipfile
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

from fatebridge.core.astro.ephemeris import _swisseph_planet_state
from fatebridge.core.astro.geometry import angular_separation_fraction
from fatebridge.core.horary_events import native_planetary_events

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests/fixtures"


def key(event):
    return (
        event["kind"],
        tuple(event["bodies"]),
        event.get("ray_degrees"),
        event["direction"],
    )


def audit():
    protocol_path = FIXTURES / "western-event-paths-protocol.json"
    reference_path = FIXTURES / "western-event-paths-horizons.json"
    plan = json.loads(protocol_path.read_text())
    reference = json.loads(reference_path.read_text())
    assert (
        reference["protocol_sha256"]
        == hashlib.sha256(protocol_path.read_bytes()).hexdigest()
    )
    with zipfile.ZipFile(FIXTURES / "western-event-paths-raw.zip") as archive:
        for c in reference["cases"]:
            for receipt in c["receipts"].values():
                assert (
                    hashlib.sha256(archive.read(receipt["raw_file"])).hexdigest()
                    == receipt["response_sha256"]
                )
    frame_protocol_path = FIXTURES / "western-event-frames-protocol.json"
    target_protocol_path = FIXTURES / "western-event-reference-points-protocol.json"
    body_reference_path = FIXTURES / "western-event-frames-horizons.json"
    aligned_reference_path = FIXTURES / "western-event-reference-points-horizons.json"
    frame_plan = json.loads(frame_protocol_path.read_text())
    target_plan = json.loads(target_protocol_path.read_text())
    body_reference = json.loads(body_reference_path.read_text())
    aligned_reference = json.loads(aligned_reference_path.read_text())
    assert target_plan["station_tolerance_seconds"] == plan["station_tolerance_seconds"]
    assert (
        target_plan["contact_and_ingress_tolerance_seconds"]
        == plan["contact_and_ingress_tolerance_seconds"]
    )
    assert (
        target_plan["prior_common_frame_reference_sha256"]
        == hashlib.sha256(body_reference_path.read_bytes()).hexdigest()
    )
    assert (
        frame_plan["initial_reference_sha256"]
        == hashlib.sha256(reference_path.read_bytes()).hexdigest()
    )
    for controlled_reference in (body_reference, aligned_reference):
        assert (
            controlled_reference["protocol_sha256"]
            == hashlib.sha256(frame_protocol_path.read_bytes()).hexdigest()
        )
        for controlled_case in controlled_reference["cases"]:
            for planet, receipt in controlled_case["receipts"].items():
                assert (
                    hashlib.sha256(receipt["raw_response_utf8"].encode()).hexdigest()
                    == receipt["response_sha256"]
                )
                targets = controlled_reference.get(
                    "native_reference_targets", plan["reference_bodies"]
                )
                assert receipt["parameters"]["COMMAND"] == f"'{targets[planet]}'"
    assert (
        aligned_reference["reference_point_control_protocol_sha256"]
        == hashlib.sha256(target_protocol_path.read_bytes()).hexdigest()
    )
    assert (
        aligned_reference["native_reference_targets"]
        == target_plan["native_reference_targets"]
    )
    frame = frame_plan["primary_frame"]
    diagnostic_frame = "IAU2006/2000B_true_ecliptic_of_date"
    rows, initial, cases, mixed_rows, body_rows, secondary_rows = [], [], [], [], [], []
    identity_failures = []
    longitude_max = 0
    position_count = 0
    for c, body_case, aligned_case in zip(
        reference["cases"],
        body_reference["cases"],
        aligned_reference["cases"],
        strict=True,
    ):
        assert c["case_id"] == body_case["case_id"] == aligned_case["case_id"]
        start = c["start_julian_day_tt"]
        assert (
            start
            == body_case["start_julian_day_tt"]
            == aligned_case["start_julian_day_tt"]
        )
        aligned_frame = aligned_case["frames"][frame]
        native = native_planetary_events(
            SimpleNamespace(julian_day_tt=start + 10.5, zodiac_type="Tropic")
        )
        if native["status"] != "computed":
            cases.append(
                {
                    "case_id": c["case_id"],
                    "status": native["status"],
                    "unavailable_reason": native["unavailable_reason"],
                    "unavailable_code": native.get("unavailable_code"),
                    "failed_sample": native.get("failed_sample"),
                }
            )
            continue
        else:
            pass
        selected = [
            e for e in native["events"] if start < e["julian_day_tt"] <= start + 21
        ]
        for label, expectations, target in (
            ("initial_three_hour", c["expected"], initial),
            ("refined_five_point", c["refined_expected"], mixed_rows),
            (
                "same_frame_body_centers",
                body_case["frames"][frame]["events"],
                body_rows,
            ),
            ("primary_frame_native_reference_points", aligned_frame["events"], rows),
            (
                "secondary_frame_native_reference_points",
                aligned_case["frames"][diagnostic_frame]["events"],
                secondary_rows,
            ),
        ):
            native_identities = Counter(key(event) for event in selected)
            reference_identities = Counter(key(event) for event in expectations)
            if native_identities != reference_identities:
                identity_failures.append(
                    {
                        "case_id": c["case_id"],
                        "reference_method": label,
                        "missing": [
                            {"identity": identity, "count": count}
                            for identity, count in (
                                reference_identities - native_identities
                            ).items()
                        ],
                        "extra": [
                            {"identity": identity, "count": count}
                            for identity, count in (
                                native_identities - reference_identities
                            ).items()
                        ],
                    }
                )
            else:
                pass
            for e in expectations:
                same = [s for s in selected if key(s) == key(e)]
                closest = min(
                    same,
                    key=lambda s: abs(s["julian_day_tt"] - e["julian_day_tt"]),
                    default=None,
                )
                residual = (
                    (closest["julian_day_tt"] - e["julian_day_tt"]) * 86400
                    if closest is not None
                    else None
                )
                tolerance = (
                    plan["station_tolerance_seconds"]
                    if e["kind"] == "station"
                    else plan["contact_and_ingress_tolerance_seconds"]
                )
                target.append(
                    {
                        "case_id": c["case_id"],
                        "kind": e["kind"],
                        "bodies": e["bodies"],
                        "aspect": e.get("aspect"),
                        "reference_julian_day_tt": e["julian_day_tt"],
                        "native_julian_day_tt": (
                            closest["julian_day_tt"] if closest is not None else None
                        ),
                        "signed_residual_seconds": residual,
                        "tolerance_seconds": tolerance,
                        "passed": residual is not None and abs(residual) <= tolerance,
                        "reference_method": label,
                    }
                )
        for planet, samples in aligned_frame["samples"].items():
            for tt, longitude, _ in samples:
                state, model = _swisseph_planet_state(
                    planet, julian_day_tt=tt, correct_motion=False
                )
                error = (
                    float(angular_separation_fraction(longitude, state["longitude"]))
                    * 3600
                )
                longitude_max = max(longitude_max, error)
                position_count += 1
        cases.append(
            {
                "case_id": c["case_id"],
                "status": "computed",
                "event_counts": dict(Counter(e["kind"] for e in selected)),
                "physical_source": native["physical_ephemeris_source"],
                "frame": native["longitude_frame"],
                "ephemeris_reference_points": native["ephemeris_reference_points"],
            }
        )
    return {
        "protocol_sha256": reference["protocol_sha256"],
        "reference_sha256": hashlib.sha256(reference_path.read_bytes()).hexdigest(),
        "cases": cases,
        "position_count": position_count,
        "maximum_longitude_residual_arcseconds": longitude_max,
        "longitude_tolerance_arcseconds": plan["longitude_tolerance_arcseconds"],
        "rows": rows,
        "initial_rows_retained": initial,
        "mixed_definition_diagnostic": {
            "rows": mixed_rows,
            "remaining_failures": [r for r in mixed_rows if not r["passed"]],
        },
        "secondary_frame_diagnostic": {
            "frame": diagnostic_frame,
            "rows": secondary_rows,
            "remaining_failures": [row for row in secondary_rows if not row["passed"]],
        },
        "same_frame_body_center_control": {
            "targets": plan["reference_bodies"],
            "rows": body_rows,
            "remaining_failures": [r for r in body_rows if not r["passed"]],
        },
        "reference_definition": {
            "frame": frame,
            "targets": target_plan["native_reference_targets"],
            "same_observations_not_blind_holdout": True,
            "body_reference_sha256": hashlib.sha256(
                body_reference_path.read_bytes()
            ).hexdigest(),
            "aligned_reference_sha256": hashlib.sha256(
                aligned_reference_path.read_bytes()
            ).hexdigest(),
        },
        "station_target_comparison": [
            {
                "case_id": aligned["case_id"],
                "bodies": aligned["bodies"],
                "body_center_target": target_plan["body_center_targets"][
                    aligned["bodies"][0]
                ],
                "native_target": target_plan["native_reference_targets"][
                    aligned["bodies"][0]
                ],
                "body_minus_native_reference_seconds": (
                    body["reference_julian_day_tt"] - aligned["reference_julian_day_tt"]
                )
                * 86400,
                "native_minus_aligned_reference_seconds": aligned[
                    "signed_residual_seconds"
                ],
                "native_minus_body_reference_seconds": body["signed_residual_seconds"],
            }
            for aligned in rows
            if aligned["kind"] == "station"
            and aligned["bodies"][0] in target_plan["body_center_targets"]
            for body in body_rows
            if body["kind"] == "station"
            and body["bodies"] == aligned["bodies"]
            and body["case_id"] == aligned["case_id"]
        ],
        "identity_failures": identity_failures,
        "all_event_identities_and_counts_match": not identity_failures
        and all(case["status"] == "computed" for case in cases),
        "passed_event_count": sum(r["passed"] for r in rows),
        "event_count": sum(len(case["expected"]) for case in reference["cases"]),
        "compared_event_count": len(rows),
        "all_cases_passed": not identity_failures
        and all(case["status"] == "computed" for case in cases)
        and all(r["passed"] for r in rows)
        and longitude_max <= plan["longitude_tolerance_arcseconds"],
        "remaining_failures": [r for r in rows if not r["passed"]],
        "scope": "Two frozen 21-day windows, all seven traditional planets. Same epochs reused for independent Horizons ICRF direction projection into the frozen protocol's primary IAU2006/2000A frame and reference-point controls, with IAU2006/2000B separately diagnostic; not blind holdout. Initial, refined mixed-definition and same-frame body-center failures retained under the original 120-second station line. Body centers 499/599/699 differ from native system barycenters 4/5/6. No fitted correction, historical-original, complete-interval or outcome certification.",
        "frame_source": "https://www.astro.com/swisseph/swephprg.htm",
        "tolerances_relaxed": False,
        "full_original_text_acceptance": False,
        "authority_certified": False,
        "source_sha256": {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [
                ROOT / "src/fatebridge/core/horary_events.py",
                ROOT / "src/fatebridge/core/horary_event_paths.py",
            ]
        },
    }


def main():
    parser = argparse.ArgumentParser(__doc__)
    outputs = parser.add_mutually_exclusive_group(required=True)
    outputs.add_argument("--output", type=Path)
    outputs.add_argument(
        "--controls-output",
        type=Path,
        help="Extract small station controls from the existing frozen local archives",
    )
    args = parser.parse_args()
    if args.controls_output is not None:
        frame_plan = json.loads(
            (FIXTURES / "western-event-frames-protocol.json").read_text()
        )
        target_plan = json.loads(
            (FIXTURES / "western-event-reference-points-protocol.json").read_text()
        )
        original_plan = json.loads(
            (FIXTURES / "western-event-paths-protocol.json").read_text()
        )
        stations = []
        source_hashes = {}
        for filename, identity, targets in (
            (
                "western-event-frames-horizons.json",
                "body_center",
                original_plan["reference_bodies"],
            ),
            (
                "western-event-reference-points-horizons.json",
                "native_reference_point",
                target_plan["native_reference_targets"],
            ),
        ):
            reference_path = FIXTURES / filename
            source_hashes[filename] = hashlib.sha256(
                reference_path.read_bytes()
            ).hexdigest()
            reference = json.loads(reference_path.read_text())
            for case in reference["cases"]:
                for frame, observations in case["frames"].items():
                    for event in observations["events"]:
                        if event["kind"] == "station":
                            planet = event["bodies"][0]
                            receipt = case["receipts"][planet]
                            assert (
                                receipt["parameters"]["COMMAND"]
                                == f"'{targets[planet]}'"
                            )
                            assert (
                                hashlib.sha256(
                                    receipt["raw_response_utf8"].encode()
                                ).hexdigest()
                                == receipt["response_sha256"]
                            )
                            stations.append(
                                {
                                    "case_id": case["case_id"],
                                    "frame": frame,
                                    "reference_point": identity,
                                    "target": targets[planet],
                                    "response_sha256": receipt["response_sha256"],
                                    **event,
                                }
                            )
                        else:
                            pass
        controls = {
            "source": "https://ssd.jpl.nasa.gov/api/horizons.api",
            "source_sha256": source_hashes,
            "primary_frame": frame_plan["primary_frame"],
            "station_tolerance_seconds": original_plan["station_tolerance_seconds"],
            "native_reference_targets": target_plan["native_reference_targets"],
            "body_center_targets": target_plan["body_center_targets"],
            "stations": stations,
            "scope": "Small extracted controls from reused development observations; full raw archives remain required by the original 106-event audit. No fitted offsets or blind holdout.",
        }
        args.controls_output.write_text(
            json.dumps(controls, ensure_ascii=False, indent=2) + "\n"
        )
        return 0
    else:
        pass
    report = audit()
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: report[k]
                for k in (
                    "event_count",
                    "passed_event_count",
                    "all_cases_passed",
                    "maximum_longitude_residual_arcseconds",
                    "remaining_failures",
                )
            },
            ensure_ascii=False,
        )
    )
    return 0 if report["all_cases_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
