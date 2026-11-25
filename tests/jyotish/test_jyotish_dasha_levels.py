"""Frozen primary arithmetic predates the kernel; no external package at runtime."""

import hashlib
import json
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from pathlib import Path

import pytest

from fatebridge.core.jyotish import vimshottari
from fatebridge.core.jyotish_dasha_levels import active_levels
from tests.support.vimshottari import (
    DAY_MICROSECONDS,
    YEAR_DAYS,
    quantize_microseconds,
    reference_periods,
)

PATH = Path(__file__).parents[1] / "fixtures/jyotish-deep-dasha-primary.json"
DATA = (
    json.loads(PATH.read_text())
    if PATH.exists()
    else {"deep_cases": [], "pratyantar_groups": []}
)
ORIGIN = datetime(2000, 1, 1, tzinfo=timezone.utc)


def ticks(value):
    elapsed = datetime.fromisoformat(value) - ORIGIN
    return (elapsed.days * 86400 + elapsed.seconds) * 1000000 + elapsed.microseconds


@pytest.mark.local_data
def test_reference_frozen_before_kernel():
    assert (
        PATH.exists()
    ), "Required pinned deep-dasha reference is absent; provision the original fixture"
    assert (
        hashlib.sha256(PATH.read_bytes()).hexdigest()
        == "adc61db103cbbfd4ff7185f5c55febb674cf6de04d683861237a339ac42ba99a"
    )
    assert DATA["real_event_cases"] == 0
    assert len(DATA["deep_cases"]) == 972
    assert sum(len(g["rows"]) for g in DATA["pratyantar_groups"]) == 2187


@pytest.mark.local_data
@pytest.mark.parametrize("case", DATA["pratyantar_groups"])
def test_every_primary_pd_and_half_open_boundary(case):
    for expected in case["rows"]:
        for target in (expected["start_offset_us"], expected["end_offset_us"] - 1):
            result = active_levels(
                case["major"],
                ORIGIN,
                ORIGIN + timedelta(microseconds=target),
                year_basis=case["year_basis"],
                depth=3,
            )
            actual = result["current_levels"][-1]
            assert actual["lord_chain"] == [
                case["major"],
                case["sub"],
                expected["lord"],
            ]
            assert ticks(actual["start"]) == expected["start_offset_us"]
            assert ticks(actual["end"]) == expected["end_offset_us"]
        # At the exact end this PD no longer contains the target, including an AD or MD boundary.
        target = expected["end_offset_us"]
        if (
            target
            == DATA["years"][case["major"]]
            * DATA["year_microseconds"][case["year_basis"]]
        ):
            with pytest.raises(ValueError, match="complete supplied major"):
                active_levels(
                    case["major"],
                    ORIGIN,
                    ORIGIN + timedelta(microseconds=target),
                    year_basis=case["year_basis"],
                    depth=3,
                )
        else:
            actual = active_levels(
                case["major"],
                ORIGIN,
                ORIGIN + timedelta(microseconds=target),
                year_basis=case["year_basis"],
                depth=3,
            )["current_levels"][-1]
            assert actual["lord_chain"] != [
                case["major"],
                case["sub"],
                expected["lord"],
            ]


@pytest.mark.local_data
@pytest.mark.parametrize("case", DATA["deep_cases"])
def test_deep_siblings_and_active_ancestry_match_frozen_rational_reference(case):
    result = active_levels(
        case["major"],
        ORIGIN,
        ORIGIN + timedelta(microseconds=case["target_offset_us"]),
        year_basis=case["year_basis"],
        depth=case["depth"],
    )
    assert [r["lord"] for r in result["current_levels"]] == case["current_lords"]
    assert result["depth"] == case["depth"]
    for actual, expected in zip(
        result["siblings_by_level"], case["levels"], strict=True
    ):
        assert actual["level"] == expected["level"]
        assert actual["parent_lord_chain"] == expected["parent_chain"]
        for row, frozen in zip(actual["periods"], expected["rows"], strict=True):
            assert row["lord"] == frozen["lord"]
            assert ticks(row["start"]) == frozen["start_offset_us"]
            assert ticks(row["end"]) == frozen["end_offset_us"]
        parent = result["current_levels"][actual["level"] - 2]
        assert actual["periods"][0]["start"] == parent["start"]
        assert actual["periods"][-1]["end"] == parent["end"]
        assert all(
            a["end"] == b["start"]
            for a, b in zip(actual["periods"], actual["periods"][1:])
        )


@pytest.mark.parametrize("depth", [True, False, 1, 7, 2.0, None, "3"])
def test_invalid_depth_is_not_coerced(depth):
    with pytest.raises(ValueError, match="integer2..6"):
        active_levels("Sun", ORIGIN, ORIGIN, year_basis="savana_360", depth=depth)


def test_invalid_lord_basis_naive_range_and_endpoints():
    with pytest.raises(ValueError, match="Unknown"):
        active_levels("Ascendant", ORIGIN, ORIGIN, year_basis="savana_360", depth=3)
    with pytest.raises(ValueError, match="Unknown"):
        active_levels("Sun", ORIGIN, ORIGIN, year_basis="calendar_year", depth=3)
    for start, target in [
        (ORIGIN.replace(tzinfo=None), ORIGIN),
        (ORIGIN, ORIGIN.replace(tzinfo=None)),
    ]:
        with pytest.raises(ValueError, match="timezone"):
            active_levels("Sun", start, target, year_basis="savana_360", depth=3)
    with pytest.raises(ValueError, match="complete supplied major"):
        active_levels(
            "Sun",
            ORIGIN,
            ORIGIN - timedelta(microseconds=1),
            year_basis="savana_360",
            depth=3,
        )
    late = datetime(9999, 1, 1, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="datetime range"):
        active_levels("Sun", late, late, year_basis="savana_360", depth=3)


def test_rao_example_50_printed_balance_and_calendar_discrepancy() -> None:
    """Rao printed211 supplies a longitude and a clock, not a new ephemeris fit."""
    birth = datetime.fromisoformat("2000-04-28T05:50:00-04:00").astimezone(timezone.utc)
    printed_moon_degrees = Fraction(302 * 60 + 23, 60)
    remaining_years = Fraction(257, 800) * 7
    assert remaining_years == Fraction(1799, 800)
    remaining_microseconds = int(remaining_years * 360 * DAY_MICROSECONDS)
    assert remaining_microseconds == 69_945_120_000_000
    result = vimshottari(
        birth,
        float(printed_moon_degrees),
        birth,
        year_basis="savana_360",
        dasha_depth=6,
    )
    assert (result["seed"]["name"], result["seed"]["pada"]) == ("Dhanishta", 3)
    assert result["birth_balance"]["lord"] == "Mars"
    assert result["birth_balance"]["remaining_years"] == pytest.approx(
        float(remaining_years), abs=1e-13
    )
    assert result["birth_balance"]["remaining_microseconds"] == remaining_microseconds
    assert result["birth_balance"]["major_start"] == "1995-08-22T23:02:00+00:00"
    assert result["birth_balance"]["major_end"] == "2002-07-16T23:02:00+00:00"
    printed_approximate_end = datetime.fromisoformat("2002-07-15T19:00:00-04:00")
    assert datetime.fromisoformat(result["birth_balance"]["major_end"]) - (
        printed_approximate_end
    ) == timedelta(days=1, minutes=2)
    assert [row["lord"] for row in result["subdivisions"]["current_levels"]] == [
        "Mars",
        "Ketu",
        "Jupiter",
        "Venus",
        "Venus",
        "Ketu",
    ]
    assert result["current_sub"]["start"] < birth.isoformat()


@pytest.mark.parametrize("year_basis", YEAR_DAYS)
@pytest.mark.parametrize("depth", range(3, 7))
@pytest.mark.parametrize("moon_degrees", [123.456, 302 + 23 / 60])
def test_independent_rational_adjacent_microseconds(
    year_basis: str, depth: int, moon_degrees: float
) -> None:
    """A rounded parent duration or inclusive end changes the selected deep chain."""
    target_microseconds = 1000 * DAY_MICROSECONDS
    _, reference_chain = reference_periods(
        Fraction(moon_degrees), target_microseconds, year_basis, depth
    )
    edge_microseconds = quantize_microseconds(reference_chain[-1].end_microseconds)
    probes = []
    for displacement in (-1, 0, 1):
        probe_microseconds = edge_microseconds + displacement
        _, expected_chain = reference_periods(
            Fraction(moon_degrees), probe_microseconds, year_basis, depth
        )
        result = vimshottari(
            ORIGIN,
            moon_degrees,
            ORIGIN + timedelta(microseconds=probe_microseconds),
            year_basis=year_basis,
            dasha_depth=depth,
        )
        actual_chain = result["subdivisions"]["current_levels"]
        for actual, expected in zip(actual_chain, expected_chain, strict=True):
            assert actual["lord_chain"] == list(expected.lord_chain)
            assert (actual["start"], actual["end"]) == expected.clocks(ORIGIN)
        probes.append(actual_chain[-1])
    assert probes[0]["end"] == probes[1]["start"]
    assert probes[0]["lord_chain"] != probes[1]["lord_chain"]
    assert probes[1] == probes[2]
