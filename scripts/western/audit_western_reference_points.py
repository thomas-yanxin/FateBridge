"""Separate reference-frame and target-center errors against independent fixed observations."""

import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from fatebridge.core.astro.ephemeris import _swisseph_planet_state
from fatebridge.core.astro.geometry import angular_separation_fraction
from fatebridge.core.astro.opaque_solar import opaque_solar_positions
from fatebridge.core.astro.physical_sources import PhysicalEphemerisTrace
from fatebridge.core.astro.time_scales import ut1_from_tt
from fatebridge.core.horary_events import native_planetary_events

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests/fixtures"


def event_key(e: dict[str, Any]) -> tuple[str, tuple[str, ...], int | None, int]:
    return e["kind"], tuple(e["bodies"]), e.get("ray_degrees"), e["direction"]


def compare_events(
    native: list[dict[str, Any]],
    reference: list[dict[str, Any]],
    case_id: str,
    frame: str,
    point_kind: str,
    plan: dict[str, Any],
) -> list[dict[str, Any]]:
    assert Counter(map(event_key, native)) == Counter(map(event_key, reference))
    rows = []
    for key in sorted(set(map(event_key, reference)), key=str):
        expected = sorted(
            (e for e in reference if event_key(e) == key),
            key=lambda e: e["julian_day_tt"],
        )
        actual = sorted(
            (e for e in native if event_key(e) == key), key=lambda e: e["julian_day_tt"]
        )
        for a, b in zip(actual, expected, strict=True):
            difference = (a["julian_day_tt"] - b["julian_day_tt"]) * 86400
            tolerance = (
                plan["station_tolerance_seconds"]
                if key[0] == "station"
                else plan["contact_and_ingress_tolerance_seconds"]
            )
            rows.append(
                dict(
                    case_id=case_id,
                    frame=frame,
                    reference_points=point_kind,
                    kind=key[0],
                    bodies=key[1],
                    ray_degrees=key[2],
                    reference_julian_day_tt=b["julian_day_tt"],
                    native_julian_day_tt=a["julian_day_tt"],
                    signed_residual_seconds=difference,
                    tolerance_seconds=tolerance,
                    passed=abs(difference) <= tolerance,
                )
            )
    return rows


def audit_opaque_solar_positions() -> dict[str, Any]:
    """Sample the named position model against every unchanged source row.

    Frame B is projected from the computed ICRS direction, not relabelled
    frame-A coordinates. The two frames reuse the same observations.
    """
    import erfa

    corpus = json.loads(
        (FIXTURES / "western-event-reference-points-horizons.json").read_text()
    )
    plan = json.loads(
        (FIXTURES / "western-event-reference-points-protocol.json").read_text()
    )
    trace = PhysicalEphemerisTrace()
    maxima: dict[str, dict[str, Any]] = {}
    failures = []
    count = 0
    intercepted_count = 0
    for case in corpus["cases"]:
        names = list(case["rows"])
        for i, epoch in enumerate(case["rows"][names[0]]):
            tt = epoch["julian_day_tt"]
            sampled = opaque_solar_positions(tt, names, source_trace=trace)
            for state in sampled["positions"]:
                row = case["rows"][state["body"]][i]
                assert row["julian_day_tt"] == tt
                for frame, expected in row["projections"].items():
                    if frame.endswith("2000A_true_ecliptic_of_date"):
                        lon, lat = state["longitude"], state["latitude"]
                    else:
                        delta = tt - 2451545.0
                        dpsi, deps = erfa.nut00b(2451545.0, delta)
                        eps, *_, matrix = erfa.pn06(2451545.0, delta, dpsi, deps)
                        eps += deps
                        equator = matrix @ state["apparent_icrs_unit_direction"]
                        x = equator[0]
                        y = math.cos(eps) * equator[1] + math.sin(eps) * equator[2]
                        z = -math.sin(eps) * equator[1] + math.cos(eps) * equator[2]
                        lon = math.degrees(math.atan2(y, x)) % 360
                        lat = math.degrees(math.atan2(z, math.hypot(x, y)))
                    residual = (
                        float(angular_separation_fraction(lon, expected[0])) * 3600
                    )
                    lat_residual = abs(lat - expected[1]) * 3600
                    key = state["body"] + ":" + frame
                    previous = maxima.get(key)
                    if previous is None or residual > previous["longitude_arcseconds"]:
                        maxima[key] = dict(
                            longitude_arcseconds=residual,
                            julian_day_tt=tt,
                            case_id=case["case_id"],
                            solar_disc_intercepted=state["solar_disc_intercepted"],
                        )
                    if (
                        residual > plan["position_diagnostic_arcseconds"]
                        or lat_residual > plan["position_diagnostic_arcseconds"]
                    ):
                        failures.append(
                            dict(
                                body=state["body"],
                                frame=frame,
                                julian_day_tt=tt,
                                longitude_arcseconds=residual,
                                latitude_arcseconds=lat_residual,
                            )
                        )
                count += 1
                intercepted_count += state["solar_disc_intercepted"]
    expected_count = sum(
        len(rows) for case in corpus["cases"] for rows in case["rows"].values()
    )
    return dict(
        method_id="finite_source_opaque_solar_apparent_positions_v1",
        apparent_model="opaque_solar",
        scope="standalone_positions_only",
        body_epoch_pairs=count,
        expected_body_epoch_pairs=expected_count,
        solar_disc_intercepted_body_epoch_pairs=intercepted_count,
        frame_comparisons=2 * count,
        frames_are_not_independent_samples=True,
        original_tolerance_arcseconds=plan["position_diagnostic_arcseconds"],
        maximum_longitude_error_arcseconds=maxima,
        failures=failures,
        passed=count == expected_count == 7070 and not failures,
        physical_ephemeris_source=trace.finish(),
        natal_chart_recomputed=False,
        native_mismatch_overridden=False,
    )


def audit(*, apparent_model: str = "native") -> dict[str, Any]:
    point_plan_path = FIXTURES / "western-event-reference-points-protocol.json"
    frame_plan_path = FIXTURES / "western-event-frames-protocol.json"
    plan = json.loads(point_plan_path.read_text())
    frame_plan = json.loads(frame_plan_path.read_text())
    body_path = FIXTURES / "western-event-frames-horizons.json"
    bary_path = FIXTURES / "western-event-reference-points-horizons.json"
    bodies = json.loads(body_path.read_text())
    bary = json.loads(bary_path.read_text())
    assert (
        hashlib.sha256(body_path.read_bytes()).hexdigest()
        == plan["prior_common_frame_reference_sha256"]
    )
    assert (
        bary["reference_point_control_protocol_sha256"]
        == hashlib.sha256(point_plan_path.read_bytes()).hexdigest()
    )
    assert (
        bodies["protocol_sha256"]
        == bary["protocol_sha256"]
        == hashlib.sha256(frame_plan_path.read_bytes()).hexdigest()
    )
    for corpus, targets in (
        (bary, plan["native_reference_targets"]),
        (bodies, {**plan["native_reference_targets"], **plan["body_center_targets"]}),
    ):
        assert corpus["production_imports"] is corpus["swiss_imports"] is False
        for case in corpus["cases"]:
            for planet, receipt in case["receipts"].items():
                assert (
                    hashlib.sha256(receipt["raw_response_utf8"].encode()).hexdigest()
                    == receipt["response_sha256"]
                )
                assert receipt["parameters"]["COMMAND"] == f"'{targets[planet]}'"
    event_rows = []
    unavailable_event_cases = []
    positions = []
    sources = []
    trace = PhysicalEphemerisTrace()
    contexts: dict[float, dict[str, Any]] = {}
    for bc, pc in zip(bodies["cases"], bary["cases"], strict=True):
        assert bc["case_id"] == pc["case_id"]
        start = pc["start_julian_day_tt"]
        native = native_planetary_events(
            SimpleNamespace(julian_day_tt=start + 10.5, zodiac_type="Tropic")
        )
        sources.append(native.get("physical_ephemeris_source"))
        if native["status"] == "computed":
            selected = [
                e for e in native["events"] if start < e["julian_day_tt"] <= start + 21
            ]
            for label, corpus in (("body_centers", bc), ("native_system_points", pc)):
                for frame, data in corpus["frames"].items():
                    event_rows += compare_events(
                        selected, data["events"], pc["case_id"], frame, label, plan
                    )
        else:
            unavailable_event_cases.append(
                dict(
                    case_id=pc["case_id"],
                    status=native["status"],
                    unavailable_reason=native.get("unavailable_reason"),
                    unavailable_code=native.get("unavailable_code"),
                    failed_sample=native.get("failed_sample"),
                    independent_events_not_compared=len(
                        pc["frames"][next(iter(pc["frames"]))]["events"]
                    ),
                )
            )
        for planet, rows in pc["rows"].items():
            maximum = {f: 0.0 for f in frame_plan["frame_models"]}
            worst = {}
            body_difference = 0.0
            for i, row in enumerate(rows):
                tt = row["julian_day_tt"]
                sampled = _swisseph_planet_state(
                    planet,
                    ut1_from_tt(tt),
                    julian_day_tt=tt,
                    source_trace=trace,
                    motion_metadata=contexts.setdefault(tt, {}),
                    correct_motion=False,
                )
                if sampled is None:
                    raise RuntimeError("Physical coordinate comparison unavailable")
                state, model = sampled
                for frame in maximum:
                    delta = (
                        float(
                            angular_separation_fraction(
                                state["longitude"], row["projections"][frame][0]
                            )
                        )
                        * 3600
                    )
                    if delta >= maximum[frame]:
                        maximum[frame] = delta
                        ra, dec = map(math.radians, row["icrf_ra_dec"])
                        sun_ra, sun_dec = map(
                            math.radians, pc["rows"]["Sun"][i]["icrf_ra_dec"]
                        )
                        cosine = math.sin(dec) * math.sin(sun_dec) + math.cos(
                            dec
                        ) * math.cos(sun_dec) * math.cos(ra - sun_ra)
                        worst[frame] = {
                            "julian_day_tt": tt,
                            "longitude_error_arcseconds": delta,
                            "independent_solar_separation_degrees": math.degrees(
                                math.acos(max(-1, min(1, cosine)))
                            ),
                        }
                body_difference = max(
                    body_difference,
                    float(
                        angular_separation_fraction(
                            row["jpl_date_ecliptic"][0],
                            bc["rows"][planet][i]["jpl_date_ecliptic"][0],
                        )
                    )
                    * 3600,
                )
            positions.append(
                dict(
                    case_id=pc["case_id"],
                    planet=planet,
                    body_epoch_count=len(rows),
                    native_target=plan["native_reference_targets"][planet],
                    physical_model=model,
                    maximum_same_point_longitude_error_arcseconds=maximum,
                    worst_position_samples=worst,
                    maximum_body_center_vs_system_point_longitude_difference_arcseconds=body_difference,
                )
            )
    same = [e for e in event_rows if e["reference_points"] == "native_system_points"]
    other = [e for e in event_rows if e["reference_points"] == "body_centers"]
    expected_event_comparisons = sum(
        len(data["events"])
        for case in bary["cases"]
        for data in case["frames"].values()
    )
    complete_events = (
        not unavailable_event_cases
        and len(same) == expected_event_comparisons
        and expected_event_comparisons > 0
    )
    pos_pass = all(
        v <= plan["position_diagnostic_arcseconds"]
        for p in positions
        for v in p["maximum_same_point_longitude_error_arcseconds"].values()
    )
    return dict(
        opaque_solar_positions=(
            audit_opaque_solar_positions() if apparent_model == "opaque_solar" else None
        ),
        protocol_sha256=hashlib.sha256(point_plan_path.read_bytes()).hexdigest(),
        frame_protocol_sha256=hashlib.sha256(frame_plan_path.read_bytes()).hexdigest(),
        current_native_physical_sources=sources,
        position_source=trace.finish(),
        positions=positions,
        event_rows=event_rows,
        same_point_event_times_passed=sum(e["passed"] for e in same),
        same_point_event_times_compared=len(same),
        same_point_event_times_expected=expected_event_comparisons,
        unavailable_event_cases=unavailable_event_cases,
        complete_event_comparison=complete_events,
        reference_body_epoch_pairs=sum(p["body_epoch_count"] for p in positions),
        frame_variants_are_not_extra_independent_samples=True,
        same_point_positions_passed=pos_pass,
        same_point_numerical_acceptance=pos_pass
        and complete_events
        and all(e["passed"] for e in same),
        body_center_comparison_passed=complete_events
        and all(e["passed"] for e in other),
        body_center_remaining_failures=[e for e in other if not e["passed"]],
        maximum_station_residual_seconds_by_point_and_frame={
            str((label, frame)): max(
                (
                    abs(e["signed_residual_seconds"])
                    for e in event_rows
                    if e["kind"] == "station"
                    and e["reference_points"] == label
                    and e["frame"] == frame
                ),
                default=None,
            )
            for label in ("native_system_points", "body_centers")
            for frame in frame_plan["frame_models"]
        },
        original_tolerances_changed=False,
        production_default_target_changed=False,
        post_discovery_diagnostic=True,
        scope="Same 7070 body/epoch pairs with added quantities and target-center controls. Both frame variants reuse the same observations. Default native system-point numerical agreement is separate from the retained failed physical-body-center comparison. No COB mode is silently claimed, no fitted offset, no full-epoch, original-text or outcome certification.",
        primary_source="https://www.astro.com/swisseph/swisseph.htm",
        primary_source_section="2.4 and AppendixC Test6",
        full_original_text_acceptance=False,
        all_three_full_marks_established=False,
        authority_certified=False,
    )


def main() -> int:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--apparent-model",
        choices=("native", "opaque_solar"),
        default="native",
        help="Select the acceptance gate. Native chart/event gates remain separate and unchanged.",
    )
    args = parser.parse_args()
    result = audit(apparent_model=args.apparent_model)
    selected_gate = (
        result["opaque_solar_positions"]["passed"]
        if args.apparent_model == "opaque_solar"
        else result["same_point_numerical_acceptance"]
    )
    result["selected_apparent_model"] = args.apparent_model
    result["selected_model_scope"] = (
        "standalone_positions_only"
        if args.apparent_model == "opaque_solar"
        else "native_chart_and_events"
    )
    result["selected_model_numerical_acceptance"] = selected_gate
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "same_point_numerical_acceptance",
                    "selected_apparent_model",
                    "selected_model_scope",
                    "selected_model_numerical_acceptance",
                    "same_point_event_times_passed",
                    "same_point_event_times_compared",
                    "same_point_positions_passed",
                    "body_center_comparison_passed",
                    "maximum_station_residual_seconds_by_point_and_frame",
                )
            },
            ensure_ascii=False,
        )
    )
    return 0 if selected_gate else 1


if __name__ == "__main__":
    raise SystemExit(main())
