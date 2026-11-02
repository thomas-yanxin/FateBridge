"""Two-factor Hamburg geometry; hand-built cases are not original birth cases."""

import math
import random
from itertools import combinations

import pytest

from fatebridge.core.astro import runtime
from fatebridge.core.astro.midpoints import midpoint_geometry
from fatebridge.services.astrology import calculate_germany_chart_analysis
from tests.fixtures.surface_payloads import astro_payload


@pytest.mark.parametrize("separation", range(0, 360, 45))
def test_hard_angles_keep_full_circle_identity(separation):
    # Rudolph 1979 laws 13/16 specify the angle classes, not these numerical
    # examples or our one-degree inclusive tolerance.
    result = midpoint_geometry({"A": 0.0, "B": float(separation)}, orb_degrees=0)
    for period in (90, 45):
        contacts = result["dials"][str(period)]["two_factor_contacts"]
        assert len(contacts) == int(separation % period == 0)
        if contacts:
            row = contacts[0]
            assert row["equation"] == "A=B"
            assert row["orb"] == row["signed_orb"] == 0
            assert row["factor_offset_degrees"] == (-separation) % 360
            assert row["aspect_degrees"] == min(separation, 360 - separation)
            assert row["separation_degrees"] == min(separation, 360 - separation)
            assert row["rule_id"] == "hamburg.two_factor_hard_contacts.v1"
    # The same pair in two dials is still one pair, not two independent facts.
    assert result["unique_two_factor_pair_count"] == 1


@pytest.mark.parametrize("period", [90, 45])
def test_two_factor_orb_boundaries_use_unrounded_inputs(period):
    for center in range(0, 361, 45):
        for sign in (-1, 1):
            boundary = float(center + sign)
            for value, expected in (
                (math.nextafter(boundary, float(center)), True),
                (boundary, True),
                (math.nextafter(boundary, boundary + sign), False),
            ):
                contacts = midpoint_geometry({"A": 0.0, "B": value})["dials"][
                    str(period)
                ]["two_factor_contacts"]
                assert bool(contacts) == (expected and center % period == 0), (
                    period,
                    center,
                    sign,
                    value,
                )
                if contacts:
                    assert contacts[0]["aspect_degrees"] == min(
                        center % 360, (-center) % 360
                    )
                    assert contacts[0]["orb"] <= 1


@pytest.mark.parametrize("seed,size", [(13981, 9), (68219, 22)])
def test_two_factor_set_against_independent_trigonometry(seed, size):
    rng = random.Random(seed)
    points = {f"P{i:02}": rng.uniform(-400, 700) for i in range(size)}
    result = midpoint_geometry(points)
    union = set()
    for period in (90, 45):
        expected = {}
        for a, b in combinations(sorted(points), 2):
            phi = 2 * math.pi * (points[a] - points[b]) / period
            signed = math.atan2(math.sin(phi), math.cos(phi)) * period / (2 * math.pi)
            if abs(signed) <= 1:
                expected[a, b] = signed
        rows = result["dials"][str(period)]["two_factor_contacts"]
        actual = {(row["id_a"], row["id_b"]): row for row in rows}
        assert len(actual) == len(rows)  # No reversed pairs or self-pair hits.
        assert set(actual) == set(expected)
        union.update(actual)
        for pair, signed in expected.items():
            assert actual[pair]["signed_orb"] == pytest.approx(signed, abs=2e-12)
            theta = math.radians(points[pair[0]] - points[pair[1]])
            separation = abs(math.degrees(math.atan2(math.sin(theta), math.cos(theta))))
            assert actual[pair]["separation_degrees"] == pytest.approx(
                separation, abs=2e-12
            )
    assert result["unique_two_factor_pair_count"] == len(union)


def test_two_factor_pairs_are_order_and_common_rotation_invariant():
    points = {"Sun": 350.0, "Cupido": 35.125, "Midheaven": 80.5, "Aries Point": 0.0}
    first = midpoint_geometry(points)
    reordered = midpoint_geometry(dict(reversed(list(points.items()))))
    rotated = midpoint_geometry({name: value + 17.25 for name, value in points.items()})
    for period in ("90", "45"):
        contacts = first["dials"][period]["two_factor_contacts"]
        assert contacts
        assert contacts == reordered["dials"][period]["two_factor_contacts"]
        assert contacts == rotated["dials"][period]["two_factor_contacts"]


def test_empty_and_single_factor_catalogues_cannot_inflate_contact_counts():
    for points in ({}, {"A": 0.0}):
        result = midpoint_geometry(points)
        assert result["unique_two_factor_pair_count"] == 0
        for dial in result["dials"].values():
            assert not dial["two_factor_contacts"]
            assert not dial["three_factor_contacts"]
            assert not dial["four_factor_contacts"]


@pytest.mark.skipif(runtime.swe is None, reason="Swiss Ephemeris required")
def test_native_two_factor_layer_covers_all_factors_without_invented_readings():
    layer = calculate_germany_chart_analysis(**astro_payload())["midpoint_analysis"]
    assert layer["ruleset_id"] == "hamburg_midpoint_geometry_v3"
    assert layer["version"] == "3"
    factors = {row["id"]: row for row in layer["factors"]}
    assert len(factors) == 22
    hypotheticals = {
        name for name, row in factors.items() if row["kind"] == "hypothetical"
    }
    union = set()
    all_contacts = []
    for period, dial in layer["dials"].items():
        rows = dial["two_factor_contacts"]
        assert layer["contact_counts"][period]["two_factor"] == len(rows)
        assert rows
        for row in rows:
            union.add((row["id_a"], row["id_b"]))
            assert row["contains_hypothetical"] == bool(
                {row["id_a"], row["id_b"]} & hypotheticals
            )
            assert "source_interpretation" not in row
        all_contacts.extend(rows)
    assert layer["unique_two_factor_pair_count"] == len(union)
    assert any(row["contains_hypothetical"] for row in all_contacts)
    assert any("Midheaven" in (row["id_a"], row["id_b"]) for row in all_contacts)
    trace = next(
        row
        for row in layer["rule_trace"]
        if row["rule_id"] == "hamburg.two_factor_hard_contacts.v1"
    )
    assert trace["source_id"] == "rudolph_1979_17laws"
    assert trace["source_sections"] == ["13", "16"]
    assert layer["original_text_conformance"] == "not_assessed"
    assert layer["real_world_efficacy"] == "not_tested"
