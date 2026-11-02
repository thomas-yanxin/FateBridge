"""Exact separation of conditional source-clock boxes and preserved references.

This compares models. It cannot revise a historical candidate result, certify
the extrapolated clock or identify the actual Horizons clock implementation.
"""

import argparse
import hashlib
import json
import math
from fractions import Fraction as Q
from pathlib import Path

from scripts.astrodice_interval_reference import replay_interval, tangent_geometry
from scripts.audit_astrodice_clock_budget import bounds
from scripts.diagnose_astrodice_de441_clock import pi_bounds


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def position_certificate(box, direction, radius):
    d = list(map(Q, direction))
    p = list(map(bounds, box))
    squares = Q()
    for i, j in [(1, 2), (2, 0), (0, 1)]:
        a = [p[i][0] * d[j], p[i][1] * d[j]]
        b = [p[j][0] * d[i], p[j][1] * d[i]]
        lo, hi = min(a) - max(b), max(a) - min(b)
        closest = 0 if lo <= 0 <= hi else min(abs(lo), abs(hi))
        squares += closest**2
    sine_squared = squares / sum((v * v for v in d), Q())
    pl, ph = pi_bounds()
    allowed = (Q("0.02") + Q(radius)) * ph / 648000
    return {
        "cross_sine_squared_lower": str(sine_squared),
        "allowed_angle_radians_upper": str(allowed),
        "strict_separation_certificate": sine_squared > allowed**2,
        "approximate_separation_lower_arcsec": max(
            0, math.sqrt(float(sine_squared)) * 648000 / float(ph) - radius
        ),
        "fixed_position_line_arcsec": 0.02,
        "printing_and_arithmetic_radius_arcsec": radius,
    }


def compare(run, fixture, output):
    manifest = fixture / "manifest.json"
    if (
        digest(manifest)
        != "7d69cadeefc9d5621765c0dd509feefb52971afc4f951e93953557cf1e9572a2"
    ):
        raise ValueError("Frozen original printed-reference manifest changed")
    for n, h in json.loads(manifest.read_text())["files"].items():
        if digest(fixture / n) != h:
            raise ValueError("Original printed observation changed")
    source = json.loads((run / "development-first.json").read_text())
    raw = json.loads((fixture / "parent/reference.json").read_text())["rows"]
    qualities = json.loads((fixture / "parent/first-quality.json").read_text())["rows"]
    certificates = json.loads((fixture / "parent/certificates.json").read_text())[
        "rows"
    ]
    records = []
    for row in source["rows"]:
        prior = next(
            r
            for r in raw
            if r["date_tt"] == row["date_nominal_tt"] and r["body"] == row["body"]
        )
        quality = next(r for r in qualities if r["id"] == prior["id"])
        direction, _, _, noise = tangent_geometry(prior)
        printing_radius = math.nextafter(
            noise * math.degrees(1) * 3600 + 1e-9, math.inf
        )
        hypotheses = {}
        for name, item in row["hypotheses"].items():
            if (
                item["status"]
                != "source_interval_enclosed_under_declared_clock_hypothesis"
            ):
                hypotheses[name] = {"status": "source_unqualified"}
                continue
            position = position_certificate(
                item["direction_icrf_intervals"], direction, printing_radius
            )
            rate = {"status": "unqualified_clock_rate_constraint"}
            if "icrf_RA_rate_interval_arcsec_per_TT_day" in item:
                if quality["status"] == "qualified_under_declared_numerical_model":
                    cert = next(r for r in certificates if r["id"] == prior["id"])
                    fit = next(
                        f
                        for f in cert["fits"]
                        if f["window_seconds"] == quality["selected_window_seconds"]
                        and f["odd_order"] == quality["selected_order"]
                    )
                    old_lo, old_hi = replay_interval(prior, fit)[0]
                    lo, hi = bounds(item["icrf_RA_rate_interval_arcsec_per_TT_day"])
                    gap = max(Q(), lo - old_hi, old_lo - hi)
                    rate = {
                        "status": "exact_intervals_replayed",
                        "original_RA_interval_arcsec_per_day": [
                            str(old_lo),
                            str(old_hi),
                        ],
                        "source_RA_interval_arcsec_per_day": [str(lo), str(hi)],
                        "exact_interval_gap_arcsec_per_day": str(gap),
                        "fixed_rate_line_arcsec_per_day": 0.002,
                        "strict_separation_beyond_fixed_rate_line": gap > Q("0.002"),
                    }
                else:
                    rate = {
                        "status": "original_rate_reference_unqualified",
                        "original_quality_status": quality["status"],
                    }
            hypotheses[name] = {"position": position, "ICRF_RA_rate": rate}
        records.append(
            {
                "id": row["id"],
                "original_id": prior["id"],
                "body": row["body"],
                "date_nominal_tt": row["date_nominal_tt"],
                "hypotheses": hypotheses,
            }
        )
    result = {
        "method_id": "exact_conditional_source_clock_vs_preserved_Horizons_model_separation_v1",
        "rows": records,
        "new_candidate_accuracy_acceptances": 0,
        "original_Horizons_results_regraded": False,
        "original_printed_values_or_error_lines_changed": False,
        "actual_Horizons_clock_identified": False,
        "full_goal_complete": False,
        "scope": "Separation between the declared complete DE441/native-solar source model under clock hypotheses and original printed/reference constraints. Long-era clock validity and the original odd-polynomial assumption are not proved; original Swiss-backend failures retain their own source identity.",
    }
    with output.open("x") as f:
        json.dump(result, f, indent=2)
        f.write("\n")
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for n in ["run", "fixture", "output"]:
        p.add_argument("--" + n, type=Path, required=True)
    a = p.parse_args()
    compare(a.run, a.fixture, a.output)
