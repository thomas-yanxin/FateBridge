"""Frozen artificial curve sampler; never a physical complete-run reader."""

import json
from copy import deepcopy
from fractions import Fraction
from pathlib import Path

from fatebridge.core.human_design import longitude_activation
from fatebridge.core.human_design_root_interpretations import candidate_chart

ROOT = Path(__file__).resolve().parents[1]
E = ROOT / "docs/validation/human-design-interval-coordinate-extrema-v1/evidence"


def model(case_id):
    reference = json.loads((E / "rational-reference.json").read_text())
    case = next(r for r in reference["cases"] if r["id"] == case_id)
    source = json.loads(
        (ROOT / "tests/fixtures/human-design-transition-case.json").read_text()
    )["physical_samples"]["nominal"]
    origin = reference["origin_jd_tt"]
    cache = {}
    calls = []

    def at(tt):
        if tt not in cache:
            calls.append(tt)
            chart = deepcopy(source)
            x = (Fraction(tt) - Fraction(origin)) * 86400
            phase = case["boundary_degrees"] + case["sign"] * (
                Fraction(1, 2**44) - (x - 5) ** 2 / 10**12
            )
            target = next(
                a for a in chart["activations"]["personality"] if a["body"] == "Mercury"
            )
            target.update(
                longitude_activation(float(phase % 360) % 360),
                longitude_speed=float(
                    case["sign"]
                    * (-2 * (x - case["reported_velocity_zero_seconds"]) / 10**12)
                    * 86400
                ),
            )
            chart.update(
                candidate_chart(
                    chart["activations"]["personality"], chart["activations"]["design"]
                )
            )
            for side in ("personality", "design"):
                for key in ("jd_tt", "jd_ut1"):
                    chart["time_scales"][side][key] += tt - origin
            # These inherited clock/root records are scaffolding, deliberately
            # not offered to the physical complete-result verifier.
            cache[tt] = chart
        return cache[tt]

    peak = next(
        p["birth_jd_tt"] for p in case["points"] if p["requested_offset_seconds"] == 5
    )
    return at, origin, peak, calls
