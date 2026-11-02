"""Refine station timing from frozen JPL positions; retain the initial failed oracle."""

import hashlib
import json
from pathlib import Path

from gen_western_event_paths_reference import unwrap

ROOT = Path(__file__).resolve().parents[1]


def vertex(values, i, stride):
    a, b, c, d, e = (values[i + j * stride] for j in (-2, -1, 0, 1, 2))
    h = stride / 24
    first = (a - 8 * b + 8 * d - e) / (12 * h)
    second = (-a + 16 * b - 30 * c + 16 * d - e) / (12 * h * h)
    third = (-a + 2 * b - 2 * d + e) / (2 * h**3)
    fourth = (a - 4 * b + 6 * c - 4 * d + e) / h**4
    x = 0.0
    for _ in range(8):
        slope = first + second * x + third * x * x / 2 + fourth * x**3 / 6
        curvature = second + third * x + fourth * x * x / 2
        x -= slope / curvature
    assert abs(x) <= 1 / 48
    # L1 derivative weights propagate each printed coordinate's half-unit
    # rounding; this does not bound polynomial truncation or JPL systematics.
    derivative_rounding = 5e-8 * 18 / (12 * h)
    return x, derivative_rounding / abs(curvature) * 86400


def main():
    reference = ROOT / "tests/fixtures/western-event-paths-horizons.json"
    refinement = ROOT / "tests/fixtures/western-event-station-reference-refinement.json"
    plan = json.loads(refinement.read_text())
    original = reference.read_bytes()
    existing = json.loads(original)
    if existing.get("initial_expected_retained"):
        existing.pop("initial_expected_retained")
        existing.pop("station_refinement_protocol_sha256")
        for case in existing["cases"]:
            case.pop("refined_expected")
        original = (json.dumps(existing, indent=2, allow_nan=False) + "\n").encode()
    assert hashlib.sha256(original).hexdigest() == plan["original_reference_sha256"]
    data = json.loads(original)
    for case in data["cases"]:
        updated = []
        for event in case["expected"]:
            row = dict(event)
            if event["kind"] == "station":
                samples = case["samples"][event["bodies"][0]]
                values = unwrap(samples)
                index = min(
                    range(len(samples)),
                    key=lambda i: abs(samples[i][0] - event["julian_day_tt"]),
                )
                offset, uncertainty = vertex(values, index, 12)
                short_offset, _ = vertex(values, index, 6)
                stability = abs(offset - short_offset) * 86400
                assert stability <= plan["maximum_between_spacing_station_seconds"]
                assert (
                    uncertainty
                    <= plan["maximum_rounding_station_time_uncertainty_seconds"]
                )
                row.update(
                    julian_day_tt=samples[index][0] + offset,
                    initial_three_hour_julian_day_tt=event["julian_day_tt"],
                    spacing_stability_seconds=stability,
                    coordinate_rounding_time_bound_seconds=uncertainty,
                )
            updated.append(row)
        case["refined_expected"] = updated
    data["station_refinement_protocol_sha256"] = hashlib.sha256(
        refinement.read_bytes()
    ).hexdigest()
    data["initial_expected_retained"] = True
    reference.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")
    print(
        "Refined stationary longitudes using both frozen spacings; original expected rows retained"
    )


if __name__ == "__main__":
    main()
