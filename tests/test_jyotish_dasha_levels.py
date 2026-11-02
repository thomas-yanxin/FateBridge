"""Frozen primary arithmetic predates the kernel; no external package at runtime."""

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from fatebridge.core.jyotish_dasha_levels import active_levels

PATH = Path(__file__).parent / "fixtures/jyotish-deep-dasha-primary.json"
DATA = json.loads(PATH.read_text())
ORIGIN = datetime(2000, 1, 1, tzinfo=timezone.utc)


def ticks(value):
    elapsed = datetime.fromisoformat(value) - ORIGIN
    return (elapsed.days * 86400 + elapsed.seconds) * 1000000 + elapsed.microseconds


def test_reference_frozen_before_kernel():
    assert (
        hashlib.sha256(PATH.read_bytes()).hexdigest()
        == "adc61db103cbbfd4ff7185f5c55febb674cf6de04d683861237a339ac42ba99a"
    )
    assert DATA["real_event_cases"] == 0
    assert len(DATA["deep_cases"]) == 972
    assert sum(len(g["rows"]) for g in DATA["pratyantar_groups"]) == 2187


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
