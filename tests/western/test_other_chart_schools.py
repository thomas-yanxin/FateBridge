"""Independent mathematical and publisher-reference checks for specialty charts."""

import json
import math
import random
from bisect import bisect_right
from datetime import datetime
from fractions import Fraction
from itertools import combinations
from pathlib import Path

import pytest

from fatebridge.core.astro import runtime
from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.astro.geometry import _sector13_for_longitude
from fatebridge.core.astro.midpoints import (
    _native_factors,
    build_midpoint_analysis,
    midpoint_axis,
    midpoint_geometry,
)
from fatebridge.core.astro.sectors import thirteen_sectors
from fatebridge.services.astrology import (
    calculate_core_chart_analysis,
    calculate_germany_chart_analysis,
)
from tests.fixtures.surface_payloads import astro_payload

FIXTURE = json.loads(
    (Path(__file__).parents[1] / "fixtures/uranian-witte-2026.json").read_text()
)
HAS_SWE = pytest.mark.skipif(runtime.swe is None, reason="Swiss Ephemeris required")


@pytest.mark.parametrize(
    "case",
    json.loads(
        (Path(__file__).parents[1] / "fixtures/uranian-rudolph-1979.json").read_text()
    )["cases"],
    ids=lambda case: case["id"],
)
def test_cited_rudolph_propositions_with_hand_constructed_exact_examples(case):
    geometry = midpoint_geometry(case["positions"], orb_degrees=0.0)
    for dial in (90, 45):
        rows = [
            row
            for row in geometry["dials"][str(dial)][case["kind"]]
            if row["equation"] == case["equation"]
        ]
        assert bool(rows) == (dial in case["expected_dials"])
        if rows:
            assert rows[0]["orb"] == 0
            assert rows[0]["axis_offset_degrees"] == case["axis_offset_degrees"]


def test_midpoint_axes_are_unordered_and_handle_antipodal_factors():
    for a, b, axis in [(350.0, 10.0, 0.0), (0.0, 180.0, 90.0), (90.0, 270.0, 0.0)]:
        first = midpoint_axis(a, b)
        assert first == midpoint_axis(b, a)
        assert first["axis_longitude"] == axis
        assert first["opposite_longitude"] == axis + 180
    assert midpoint_axis(0, 180)["antipodal_inputs"] is True
    axis = midpoint_axis(-math.ulp(0.0), -math.ulp(0.0))
    assert 0 <= axis["axis_longitude"] < 180
    assert 0 <= axis["opposite_longitude"] < 360
    assert 0 <= axis["dial_90"] < 90
    assert 0 <= axis["dial_45"] < 45


@pytest.mark.parametrize("dial", [90, 45])
def test_three_and_four_factor_contacts_against_independent_doubled_angle_equations(
    dial,
):
    rng = random.Random(13981)
    points = {str(i): rng.uniform(-400, 700) for i in range(9)}
    result = midpoint_geometry(points)["dials"][str(dial)]

    # Work with doubled equations directly, not midpoint_axis or its constants.
    def error(doubled):
        phi = math.pi * doubled / dial
        return abs(math.atan2(math.sin(phi), math.cos(phi))) * dial / (2 * math.pi)

    triples = set()
    quads = set()
    pairs = list(combinations(points, 2))
    for a, b in pairs:
        for p in points:
            if p not in (a, b) and error(2 * points[p] - points[a] - points[b]) <= 1:
                triples.add((p, a, b))
    for (a, b), (c, d) in combinations(pairs, 2):
        if (
            len({a, b, c, d}) == 4
            and error(points[a] + points[b] - points[c] - points[d]) <= 1
        ):
            quads.add((a, b, c, d))
    assert {
        (r["point"], r["id_a"], r["id_b"]) for r in result["three_factor_contacts"]
    } == triples
    assert {
        (r["id_a"], r["id_b"], r["id_c"], r["id_d"])
        for r in result["four_factor_contacts"]
    } == quads
    for row in result["three_factor_contacts"]:
        expected = error(
            2 * points[row["point"]] - points[row["id_a"]] - points[row["id_b"]]
        )
        assert row["orb"] == pytest.approx(expected, abs=1e-12)


def test_midpoint_orb_is_inclusive_without_rounding_or_algebraic_self_hits():
    for coordinate, expected in [
        (math.nextafter(1.0, -math.inf), True),
        (1.0, True),
        (math.nextafter(1.0, math.inf), False),
    ]:
        result = midpoint_geometry({"A": 0.0, "B": 0.0, "C": coordinate})
        for dial in result["dials"].values():
            hits = [
                r
                for r in dial["three_factor_contacts"]
                if r["point"] == "C" and r["id_a"] == "A" and r["id_b"] == "B"
            ]
            assert bool(hits) == expected
            assert all(
                len({r["point"], r["id_a"], r["id_b"]}) == 3
                for r in dial["three_factor_contacts"]
            )
            assert not dial["four_factor_contacts"]


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -1.0, 6.0])
def test_invalid_midpoint_orbs_rejected(bad):
    with pytest.raises(ValueError):
        midpoint_geometry({"A": 0.0}, orb_degrees=bad)


def test_all_thirteen_sector_edges_against_exact_independent_interval_search():
    edges = [Fraction(360 * n, 13) for n in range(14)]
    rng = random.Random(430231)
    for anchor in (0.0, 17.25, 121.4667, math.nextafter(360.0, 0.0), -180.0):
        probes = [rng.uniform(-720, 720) for _ in range(500)]
        for n in range(14):
            cusp = float(Fraction(anchor) + edges[n])
            probes.extend(
                [math.nextafter(cusp, -math.inf), cusp, math.nextafter(cusp, math.inf)]
            )
        for value in probes:
            relative = (Fraction(value) - Fraction(anchor)) % 360
            expected = bisect_right(edges, relative)
            assert _sector13_for_longitude(value, anchor) == expected
        assert len(thirteen_sectors(anchor)) == 13
    assert _sector13_for_longitude(-math.ulp(0.0), 0.0) == 13
    sectors = thirteen_sectors(-math.ulp(0.0))
    assert sectors[0]["sign"] == "Pisces"
    assert all(0 <= row["cusp_longitude"] < 360 for row in sectors)


@HAS_SWE
@pytest.mark.parametrize("row", FIXTURE["rows"], ids=lambda row: row["utc"])
def test_nineteen_factors_against_independent_witte_publisher_ephemeris(row):
    assert (
        FIXTURE["source_pdf_sha256"]
        == "61e973148b74711196d5ec3b4a03e202cb3d1f1cfce8e6827bc51347f769bc57"
    )
    moment = datetime.fromisoformat(row["utc"])
    birth = build_astro_birth_info(
        birth_year=moment.year,
        birth_month=moment.month,
        birth_day=moment.day,
        birth_hour=0,
        birth_timezone="UTC",
        birth_longitude=0,
        birth_latitude=0,
    )
    actual = {p["id"]: p for p in _native_factors(birth, False)["factors"]}
    assert len(actual) == 22
    for name, position in row["positions"].items():
        # Only the frozen publisher's sign/degree/minute/second table generates
        # expected coordinates. Production code never supplies expected values.
        expected = (
            position["sign_index"] * 30
            + position["degree"]
            + position["minute"] / 60
            + position["second"] / 3600
        )
        error_arcseconds = (
            abs((actual[name]["longitude"] - expected + 180) % 360 - 180) * 3600
        )
        assert error_arcseconds <= position["tolerance_arcseconds"], (
            name,
            error_arcseconds,
        )
    assert {p["kind"] for p in actual.values()} == {
        "physical_body",
        "hypothetical",
        "reference_point",
        "lunar_node",
    }


@HAS_SWE
def test_native_coordinates_use_one_physical_time_and_covariant_aries_point():
    birth = build_astro_birth_info(
        **{k: v for k, v in astro_payload().items() if k != "chart_variant"}
    )
    tropical = {
        p["id"]: p["longitude"] for p in _native_factors(birth, False)["factors"]
    }
    sidereal = {
        p["id"]: p["longitude"] for p in _native_factors(birth, True)["factors"]
    }
    offset = (tropical["Sun"] - sidereal["Sun"]) % 360
    for name in tropical:
        assert (tropical[name] - sidereal[name]) % 360 == pytest.approx(
            offset, abs=1e-10
        ), name
    assert sidereal["Aries Point"] != 0.0
    # Rotation preserves all the midpoint equations, including Aries contacts.
    first = midpoint_geometry(tropical)
    second = midpoint_geometry(sidereal)
    for dial in ("90", "45"):
        for field in (
            "two_factor_contacts",
            "three_factor_contacts",
            "four_factor_contacts",
        ):
            assert {r["equation"] for r in first["dials"][dial][field]} == {
                r["equation"] for r in second["dials"][dial][field]
            }


@HAS_SWE
def test_germany_publishes_native_geometry_with_bounded_claims():
    result = calculate_germany_chart_analysis(**astro_payload())
    layer = result["midpoint_analysis"]
    assert layer["profile"]["factor_count"] == 22
    assert len(layer["midpoint_axes"]) == 253
    assert layer["profile"]["coordinate_rounding_before_comparison"] is False
    assert layer["original_text_conformance"] == "not_assessed"
    assert layer["real_world_efficacy"] == "not_tested"
    # Preserve the published legacy list; the new layer has its own identity.
    assert len(result["midpoints"]) == 21


def test_no_swiss_runtime_cannot_fabricate_native_or_hypothetical_factors(monkeypatch):
    monkeypatch.setattr(runtime, "swe", None)
    result = build_midpoint_analysis(None, {"chart_profile": {"zodiac": "tropical"}})
    assert result["status"] == "unavailable"
    assert "factors" not in result


def test_chart13_explains_the_actual_partition_and_limits():
    result = calculate_core_chart_analysis(chart_variant="chart13", **astro_payload())
    profile = result["sector_profile"]
    assert profile["sector_count"] == 13
    assert profile["astronomical_constellations"] is False
    assert profile["real_world_efficacy"] == "not_tested"
    assert "IAU" in result["interpretation"]["variant_note"]
    assert all(1 <= row["sector13"] <= 13 for row in result["planets"])
