"""Independent literal angular-strength rules; no FateBridge or Swiss imports."""

import argparse
import hashlib
import json
import math
import random
import sys
from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument("--output", type=Path, required=True)
a = p.parse_args()
assert not a.output.exists()
PEAKS = {
    "Sun": 10,
    "Moon": 33,
    "Mars": 298,
    "Mercury": 165,
    "Jupiter": 95,
    "Venus": 357,
    "Saturn": 200,
}
WEAK = {
    "Sun": "mc_opposite",
    "Moon": "mc",
    "Mars": "mc_opposite",
    "Mercury": "asc_opposite",
    "Jupiter": "asc_opposite",
    "Venus": "mc",
    "Saturn": "asc",
}


def exact(v):
    return Fraction.from_float(float(v))


def dist(lon, point):
    left = exact(lon) % 360
    right = point % 360
    return min(abs(left - right + turn * 360) for turn in [-1, 0, 1])


def decimal_check(lon, point, value):
    with localcontext() as c:
        c.prec = 1500
        # Separate high-precision decimal evaluation, from original binary operands.
        dl = Decimal.from_float(float(lon)) % 360
        if dl < 0:
            dl += 360
        dp = Decimal(point.numerator) / Decimal(point.denominator) % 360
        if dp < 0:
            dp += 360
        angular = min(abs(dl - dp + Decimal(turn) * 360) for turn in [-1, 0, 1])
        assert float(angular / 3) == value


rng = random.Random(27012607)
uchcha = []
for planet, peak in PEAKS.items():
    angles = (
        {float(x) for x in range(360)}
        | {rng.uniform(-720, 1080) for _ in range(100)}
        | {-720.0, -360.0, -0.0, 360.0, 720.0, 1080.0}
    )
    for centre in [
        0,
        peak,
        (peak + 90) % 360,
        (peak + 180) % 360,
        (peak + 270) % 360,
        360,
    ]:
        angles.update(
            [
                float(centre),
                math.nextafter(float(centre), -math.inf),
                math.nextafter(float(centre), math.inf),
            ]
        )
    for longitude in sorted(angles):
        point = Fraction((peak + 180) % 360)
        arc = dist(longitude, point)
        value = float(arc / 3)
        decimal_check(longitude, point, value)
        uchcha.append(
            dict(
                planet=planet,
                longitude=longitude,
                longitude_hex=longitude.hex(),
                deep_fall_degrees=int(point),
                shortest_arc_exact=str(arc),
                expected_virupa=value,
                expected_hex=value.hex(),
            )
        )
anchors = [
    0.0,
    math.nextafter(0.0, math.inf),
    10.0,
    math.nextafter(10.0, math.inf),
    33.0,
    math.nextafter(33.0, -math.inf),
    95.0,
    math.nextafter(95.0, math.inf),
    118.0,
    179.99,
    180.0,
    math.nextafter(180.0, math.inf),
    200.0,
    275.0,
    math.nextafter(359.99, math.inf),
]
frames = [
    (asc, anchors[(i * 7 + 3) % len(anchors)]) for i, asc in enumerate(anchors)
] + [(rng.uniform(0, 360), rng.uniform(0, 360)) for _ in range(100)]
dig = []
for index, (asc, mc) in enumerate(frames):
    points = {
        "asc": exact(asc),
        "mc": exact(mc),
        "asc_opposite": (exact(asc) + 180) % 360,
        "mc_opposite": (exact(mc) + 180) % 360,
    }
    for side in ["lower", "nearest", "higher", "random"]:
        longitudes = {}
        expected = {}
        arcs = {}
        weak = {}
        for planet, kind in WEAK.items():
            point = points[kind]
            nearest = float(point)
            if nearest >= 360:
                nearest = 0.0
            if side == "random":
                longitude = rng.uniform(0, 360)
            else:
                longitude = (
                    math.nextafter(nearest, -math.inf if side == "lower" else math.inf)
                    if side != "nearest"
                    else nearest
                )
                if longitude < 0:
                    longitude = math.nextafter(360.0, 0.0)
                if longitude >= 360:
                    longitude = 0.0
            arc = dist(longitude, point)
            value = float(arc / 3)
            decimal_check(longitude, point, value)
            longitudes[planet] = longitude
            expected[planet] = value
            arcs[planet] = str(arc)
            weak[planet] = str(point)
        dig.append(
            dict(
                frame=index,
                side=side,
                raw=dict(ascendant=asc, midheaven=mc, longitudes=longitudes),
                expected_virupa=expected,
                expected_shortest_arcs_exact=arcs,
                exact_weak_points=weak,
            )
        )
assert not any(
    n == "fatebridge" or n.startswith("fatebridge.") or n in ["swisseph", "pyswisseph"]
    for n in sys.modules
)
record = dict(
    provenance=dict(
        source_sha256="13609f1af89541e070c798b8c70c6bfd74a8b9a71a71388913bf898e9f9ddf3f",
        sections=[
            "3.49-50 printed38-39/PDF37-38",
            "27.1 printed263-264/PDF262-263",
            "27.7 printed267/PDF266",
        ],
        reference="Independent standard-library Fraction three-image distance plus Decimal1500 cross-check. Literal source coefficients, no production or Swiss imports.",
        scope="Mathematical binary-input evaluation; not astronomical/clock accuracy, independent persons or events",
    ),
    protocol=dict(
        random_seed=27012607,
        all_seven_physical_grahas=True,
        weak_points_from_unrounded_original_cardinal_inputs=True,
        final_once_float_rounding=True,
        comparison_tolerance=0,
        original_existing_tolerances_not_rewritten=True,
    ),
    uchcha_cases=uchcha,
    dig_cases=dig,
    counts=dict(uchcha=len(uchcha), dig_packets=len(dig), dig_values=7 * len(dig)),
    real_events=0,
    independent_model_blind_reviews=0,
    whole_goal_complete=False,
)
a.output.write_text(
    json.dumps(record, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
)
print(
    json.dumps(
        dict(
            counts=record["counts"],
            sha256=hashlib.sha256(a.output.read_bytes()).hexdigest(),
        )
    ),
    flush=True,
)
