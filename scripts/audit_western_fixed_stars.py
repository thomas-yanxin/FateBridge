"""Compare native stars with a frozen independent ERFA numerical reference.

No oracle rewriting. Native runtime and the old linear helper are both
reported; the fixed protocol is checked before accepting any comparison.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path

from fatebridge.core.classical_western import FIXED_STARS, fixed_star_longitude
from fatebridge.core.fixed_stars import DATA, apparent_positions, conjunction_hits

ROOT = Path(__file__).resolve().parents[1]


def audit():
    protocol_path = ROOT / "tests/fixtures/western-fixed-star-protocol.json"
    reference_path = ROOT / "tests/fixtures/western-fixed-stars-erfa.json"
    protocol = json.loads(protocol_path.read_text())
    reference = json.loads(reference_path.read_text())
    assert (
        hashlib.sha256(protocol_path.read_bytes()).hexdigest()
        == reference["protocol_sha256"]
    )
    assert (
        hashlib.sha256((DATA / "sources.json").read_bytes()).hexdigest()
        == reference["source_sha256"]
    )
    assert protocol["tolerance_arcsec"] == 1
    assert len(reference["rows"]) == 120
    rows = []
    profiles = {}
    native_by_epoch = {}
    for epoch in protocol["epochs_tt"]:
        sample = [r for r in reference["rows"] if r["epoch_tt"] == epoch]
        assert len(sample) == 20 and len({r["star"] for r in sample}) == 20
        positions, profile = apparent_positions(sample[0]["julian_day_tt"])
        profiles[epoch] = profile
        assert profile["status"] == "computed"
        assert set(positions) == {r["star"] for r in sample}
        native_by_epoch[epoch] = positions
        for row in sample:
            actual = positions[row["star"]]
            longitude_error = (
                abs((actual["longitude"] - row["longitude"] + 180) % 360 - 180) * 3600
            )
            latitude_error = abs(actual["latitude"] - row["latitude"]) * 3600
            old = fixed_star_longitude(
                FIXED_STARS[row["star"]]["lon2000"], row["julian_day_tt"]
            )
            legacy_error = abs((old - row["longitude"] + 180) % 360 - 180) * 3600
            rows.append(
                {
                    **row,
                    "native_longitude": actual["longitude"],
                    "native_latitude": actual["latitude"],
                    "longitude_residual_arcsec": longitude_error,
                    "latitude_residual_arcsec": latitude_error,
                    "legacy_longitude_residual_arcsec": legacy_error,
                    "passed": max(longitude_error, latitude_error)
                    <= protocol["tolerance_arcsec"],
                }
            )
    assert all(row["passed"] for row in rows)
    assert any(
        row["legacy_longitude_residual_arcsec"] > protocol["tolerance_arcsec"]
        for row in rows
    )
    first = next(r for r in reference["rows"] if r["star"] == "Sirius")
    old = fixed_star_longitude(FIXED_STARS["Sirius"]["lon2000"], first["julian_day_tt"])
    sign = math.copysign(1, old - first["longitude"])
    probes = {
        "legacy_false_positive": old + sign * 0.99,
        "legacy_false_negative": first["longitude"] - sign * 0.99,
    }
    actual = native_by_epoch[first["epoch_tt"]]["Sirius"]
    new_hits = conjunction_hits(probes, {"Sirius": actual}, FIXED_STARS)
    old_hits = conjunction_hits(
        probes, {"Sirius": {**actual, "longitude": old}}, FIXED_STARS
    )
    assert [h["point"] for h in new_hits] == ["legacy_false_negative"]
    assert [h["point"] for h in old_hits] == ["legacy_false_positive"]
    return {
        "status": "bounded_independent_computation_agreement_verified",
        "protocol_sha256": hashlib.sha256(protocol_path.read_bytes()).hexdigest(),
        "reference_sha256": hashlib.sha256(reference_path.read_bytes()).hexdigest(),
        "tolerance_arcsec": protocol["tolerance_arcsec"],
        "cases": 120,
        "passed": sum(r["passed"] for r in rows),
        "max_longitude_residual_arcsec": max(
            r["longitude_residual_arcsec"] for r in rows
        ),
        "max_latitude_residual_arcsec": max(
            r["latitude_residual_arcsec"] for r in rows
        ),
        "legacy_max_longitude_residual_arcsec": max(
            r["legacy_longitude_residual_arcsec"] for r in rows
        ),
        "legacy_over_protocol_tolerance": sum(
            r["legacy_longitude_residual_arcsec"] > protocol["tolerance_arcsec"]
            for r in rows
        ),
        "synthetic_boundary_counterexample": {
            "star": "Sirius",
            "epoch_tt": first["epoch_tt"],
            "point_longitudes": probes,
            "legacy_hits": old_hits,
            "new_hits": new_hits,
            "observed_birth_chart": False,
        },
        "legacy_negative_control_rejected": True,
        "absolute_observational_accuracy_certified": False,
        "limitations": [
            "Same frozen catalogue measurements, independent ERFA and Swiss numerical libraries",
            "Coordinate residuals at six selected 1900-2099 TT epochs only",
            "No binary orbital motion or catalogue covariance validation",
            "No certification of ancient or remote future epochs, traditional prediction, or the complete professional system",
        ],
        "rows": rows,
        "profiles_by_epoch": profiles,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit()
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: v
                for k, v in report.items()
                if k not in {"rows", "synthetic_boundary_counterexample", "limitations"}
            }
        )
    )


if __name__ == "__main__":
    main()
