"""Independent Decimal oracle: thresholds are fixed before comparison."""

from __future__ import annotations

import json
import math
import random
from decimal import Decimal, localcontext
from pathlib import Path

import pytest

from fatebridge.core.astro.aspects import (
    _build_aspects,
    _build_directional_relative_antiscia,
    _build_directional_relative_aspects,
    _build_directional_relative_midpoints,
    _get_dynamic_orb,
    _match_cross_aspect,
)
from fatebridge.core.astro.geometry import combine_longitudes
from fatebridge.core.astro.relationship_geometry import unique_midpoint
from fatebridge.core.classical_western import (
    _aspect_is_applying,
    _aspect_phase,
    build_classical_patterns,
    combustion_state,
)
from fatebridge.core.predictive._common import collect_aspect_hits
from fatebridge.services.astrology import _build_classical_patterns_lines

ANGLES = [
    ("conjunction", 0),
    ("sextile", 60),
    ("square", 90),
    ("trine", 120),
    ("opposition", 180),
]
RADII = {
    "Sun": 10.0,
    "Moon": 10.0,
    "Mercury": 7.0,
    "Venus": 7.0,
    "Mars": 7.5,
    "Jupiter": 9.0,
    "Saturn": 9.0,
    "Uranus": 5.0,
    "Neptune": 5.0,
    "Pluto": 5.0,
}


def dec(value):
    return Decimal.from_float(value) if isinstance(value, float) else Decimal(value)


def wrap(value):
    return (value % 360 + 360) % 360


def gap(a, b):
    diff = wrap(dec(a) - dec(b))
    return min(diff, 360 - diff)


def reference_match(a, b, radius, pair=None):
    with localcontext() as ctx:
        ctx.prec = 2048
        separation = gap(a, b)
        matches = []
        for name, angle in ANGLES:
            limit = radius
            if pair:
                limit = (RADII[pair[0]] + RADII[pair[1]]) / 2
                if name in {"sextile", "square"}:
                    limit *= 0.8
            distance = abs(separation - angle)
            if distance <= dec(limit):
                matches.append((distance, name))
        if not matches:
            return None
        distance, name = min(matches, key=lambda row: row[0])
        return {"aspect": name, "delta": float(distance)}


def reference_midpoints(a, b):
    a, b = wrap(dec(a)), wrap(dec(b))
    forward = wrap(b - a)
    if forward == 180:
        axis = ((a + b) / 2) % 180
        return (axis, axis + 180)
    if forward > 180:
        forward -= 360
    return (wrap(a + forward / 2),)


def reference_phase(a, va, b, vb, angle):
    if va is None or vb is None:
        return "unavailable"
    with localcontext() as ctx:
        ctx.prec = 2048
        current = wrap(dec(b) - dec(a))
        distance = min(current, 360 - current)
        current_gap = abs(distance - dec(angle))
        if current_gap == 0:
            return "exact"
        velocity = dec(vb) - dec(va)
        if velocity == 0:
            return "stationary"
        future = wrap(current + velocity * Decimal("1e-1200"))
        future_gap = abs(min(future, 360 - future) - dec(angle))
        assert future_gap != current_gap
        return "applying" if future_gap < current_gap else "separating"


def test_original_wrap_counterexample_is_rejected_without_changing_radius():
    rows = [
        {"id": "Mercury", "longitude": 0.5000000000000001},
        {"id": "Saturn", "longitude": 352.5},
    ]
    assert _get_dynamic_orb("Mercury", "Saturn", "conjunction") == 8
    assert _build_aspects(rows) == []
    assert (
        reference_match(
            rows[0]["longitude"], rows[1]["longitude"], 6, ("Mercury", "Saturn")
        )
        is None
    )


def test_all_dynamic_orbs_keep_the_published_float_policy():
    for a in RADII:
        for b in RADII:
            for name, _ in ANGLES:
                limit = (RADII[a] + RADII[b]) / 2
                if name in {"sextile", "square"}:
                    limit *= 0.8
                assert _get_dynamic_orb(a, b, name) == limit


def test_direct_wrapped_swapped_and_random_matches_against_decimal():
    cases = []
    for _, angle in ANGLES:
        for radius in (0.0, 1.5, 3.0, 6.0, 8.0):
            for edge in (angle - radius, angle + radius):
                for point in (
                    math.nextafter(edge, -math.inf),
                    edge,
                    math.nextafter(edge, math.inf),
                ):
                    cases.extend(
                        (
                            (point, 0.0, radius),
                            (0.0, point, radius),
                            (point, 360.0, radius),
                            (360.0, point, radius),
                        )
                    )
    tiny = math.nextafter(0.0, 1.0)
    cases.extend([(tiny, -3.0, 3), (-tiny, 3.0, 3), (0.5000000000000001, 352.5, 8)])
    rng = random.Random(20261022)
    cases.extend(
        (rng.uniform(-720, 720), rng.uniform(-720, 720), rng.choice((0, 1.5, 3, 8)))
        for _ in range(1000)
    )
    for a, b, radius in cases:
        assert _match_cross_aspect(a, b, radius) == reference_match(a, b, radius), (
            a,
            b,
            radius,
        )
        for pair in (("Mercury", "Saturn"), ("Sun", "Mars")):
            assert _match_cross_aspect(a, b, radius, *pair) == reference_match(
                a, b, radius, pair
            )


def test_relationship_midpoints_and_reflections_use_unrounded_coordinates():
    tiny = math.nextafter(0.0, 1.0)
    cases = [
        (0, 180),
        (0, math.nextafter(180.0, 0)),
        (tiny, 60),
        (-tiny, 60),
        (29.99999996, 29.99999998),
        (358.0, 2.0),
    ]
    for first, second in cases:
        targets = [
            {"id": "Moon", "longitude": first},
            {"id": "Saturn", "longitude": second},
        ]
        for source in (0.0, 3.0, -tiny, 33.0, 32.9999999, 177.0, 183.0):
            with localcontext() as ctx:
                ctx.prec = 2048
                candidates = reference_midpoints(first, second)
                expected = [reference_match(dec(source), mid, 3) for mid in candidates]
                expected = sorted(
                    (row for row in expected if row), key=lambda row: row["delta"]
                )
            actual = _build_directional_relative_midpoints(
                [{"id": "Sun", "longitude": source}], targets
            )
            assert [
                {"aspect": row["aspect"], "delta": row["delta"]}
                for row in actual.get("Sun", [])
            ] == expected
        for source in (tiny, -tiny, 3.0, 177.0, 183.0, 357.0):
            for contra in (True, False):
                with localcontext() as ctx:
                    ctx.prec = 2048
                    reflected = -dec(first) if contra else 180 - dec(first)
                    separation = gap(dec(source), reflected)
                    expected = (
                        [{"idA": "Sun", "idB": "Moon", "delta": float(separation)}]
                        if separation <= 3
                        else []
                    )
                actual = _build_directional_relative_antiscia(
                    [{"id": "Sun", "longitude": source}], targets[:1], contra=contra
                )
                assert actual == expected


def test_formula_delivery_preserves_each_half_open_sign_partition():
    tiny = math.nextafter(0.0, 1.0)
    for boundary in range(30, 361, 30):
        result = combine_longitudes(float(boundary), -tiny)
        assert 0 <= result < 360
        assert result // 30 == (boundary - 1) // 30
    assert unique_midpoint(-tiny, 60) < 30


def test_predictive_fixed_orb_and_relationship_dynamic_orb_share_exact_separation():
    for source, target in (
        (0.5000000000000001, 352.5),
        (-math.ulp(0.0), 3.0),
        (0.0, math.nextafter(1.5, math.inf)),
    ):
        expected = reference_match(source, target, 1.5)
        hits = collect_aspect_hits(
            source_longitudes={"Moon": source}, target_longitudes={"Saturn": target}
        )
        assert [(row["aspect"], row["orb"]) for row in hits] == (
            [] if expected is None else [(expected["aspect"], expected["delta"])]
        )
        expected = reference_match(source, target, 4, ("Mercury", "Saturn"))
        actual = _build_directional_relative_aspects(
            [{"id": "Mercury", "longitude": source}],
            [{"id": "Saturn", "longitude": target}],
        )
        assert [row for group in actual for row in group["objects"]] == (
            [] if expected is None else [{"id": "Saturn", **expected}]
        )


def test_instantaneous_phase_does_not_step_past_perfection():
    tiny = math.ulp(0.0)
    cases = [
        (0, 13, 0.1, 0, 0),
        (11, 13, 132, 0.08, 120),
        (11, 13, 10, 0.03, 0),
        (0, -13, 359.9, 0, 0),
        (0, 0, 60, 1, 60),
        (0, 1, 59, 1, 60),
        (0, None, 59, 1, 60),
        (tiny, 0, 0, tiny, 0),
        (0, 1e308, 1, -1e308, 0),
    ]
    rng = random.Random(20261022)
    cases.extend(
        (
            rng.uniform(-720, 720),
            rng.uniform(-15, 15),
            rng.uniform(-720, 720),
            rng.uniform(-15, 15),
            angle,
        )
        for _, angle in ANGLES
        for _ in range(200)
    )
    for a, va, b, vb, angle in cases:
        expected = reference_phase(a, va, b, vb, angle)
        assert _aspect_phase(a, va, b, vb, angle) == expected, (a, va, b, vb, angle)
        assert _aspect_phase(b, vb, a, va, angle) == expected
        assert _aspect_is_applying(a, va, b, vb, angle) is {
            "applying": True,
            "separating": False,
        }.get(expected)
    assert _aspect_is_applying(0, 13, 0.1, 0, 0) is True


@pytest.mark.parametrize("angle", [0.0, 60.0, 90.0, 120.0, 180.0])
def test_phase_at_each_exact_angle_and_adjacent_double(angle):
    for target in (
        math.nextafter(angle, -math.inf),
        angle,
        math.nextafter(angle, math.inf),
    ):
        for first_speed, second_speed in ((13.0, 0.0), (-13.0, 0.0), (1.0, 1.0)):
            expected = reference_phase(0.0, first_speed, target, second_speed, angle)
            assert (
                _aspect_phase(0.0, first_speed, target, second_speed, angle) == expected
            )


def test_classical_motion_evidence_and_delivery_keep_exact_and_unknown_distinct():
    positions = [
        {"id": "Moon", "sign": "Aries", "longitude": 0.0},
        {"id": "Saturn", "sign": "Aries", "longitude": 0.1},
    ]
    aspects = [{"planet_a": "Moon", "planet_b": "Saturn", "aspect": "conjunction"}]
    for speeds, expected in (
        ({"Moon": 13, "Saturn": 0}, "applying"),
        ({"Moon": 1, "Saturn": 1}, "stationary"),
        ({}, "unavailable"),
    ):
        patterns = build_classical_patterns(positions, aspects, "day", speeds=speeds)
        assert patterns["aspect_motion"][0]["phase"] == expected
        assert (
            patterns["application_policy"]["rule_id"]
            == "instantaneous_longitude_phase_v1"
        )
        json.dumps(patterns, allow_nan=False)
        rendered = _build_classical_patterns_lines({"classical_patterns": patterns})
        assert {
            "applying": "入相",
            "stationary": "相对黄经同速",
            "unavailable": "速度未知",
        }[expected] in rendered
        assert "合相黄纬同侧条件在逐项证据中单列（可为缺项）" in rendered
        assert "未检验未来成相及完整原典条件" in rendered


def test_combustion_and_nodal_thresholds_reject_the_wrap_counterexample():
    tiny = math.ulp(0.0)
    assert combustion_state(-tiny, 8.5) == "under_beams"
    positions = [{"id": "Moon", "sign": "Aries", "longitude": -tiny}]
    # north bending at 3 degrees is just farther than 3 degrees from -tiny.
    result = build_classical_patterns(positions, [], "day", node_longitude=-87.0)
    assert result["nodal_bending"] == []


@pytest.mark.parametrize("radius", [float("nan"), float("inf"), -1, 181])
def test_invalid_thresholds_are_rejected_even_for_empty_inputs(radius):
    for call in (
        lambda: _build_aspects([], radius),
        lambda: _build_directional_relative_aspects([], [], radius),
        lambda: _build_directional_relative_midpoints([], [], radius),
        lambda: _build_directional_relative_antiscia([], [], orb=radius),
        lambda: collect_aspect_hits(
            source_longitudes={}, target_longitudes={}, orb_limit=radius
        ),
    ):
        with pytest.raises(ValueError):
            call()


def test_protocol_is_present_and_explicitly_preserves_the_historical_failure():
    data = json.loads(
        (
            Path(__file__).parents[1]
            / "fixtures/western-angular-predicates-protocol.json"
        ).read_text()
    )
    assert data["protocol_id"] == "western_angular_predicates_decimal_v1"
    assert Path(data["preserved_failure"]).is_file()
