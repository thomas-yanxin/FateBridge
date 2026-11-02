"""A missing unrelated sunset must not erase supported solar components."""

import json
import math
from datetime import datetime
from pathlib import Path

import pytest

from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.astro.time_scales import datetime_from_ut1
from fatebridge.core.jyotish import build_india, positions
from fatebridge.core.jyotish_evidence import strength_context
from fatebridge.core.jyotish_kala import solar_parts, temporal_balas
from tests.fixtures.surface_payloads import astro_payload

REFERENCE = json.loads(
    (
        Path(__file__).parent / "fixtures/jyotish-solar-bracket-regressions.json"
    ).read_text()
)
RISE = 2451544.75  # Gregorian Saturday2000-01-01 06:00, mathematical fixture


def packet(*pairs):
    return {
        "events": [
            {"kind": kind, "julian_day_ut1": RISE + offset} for kind, offset in pairs
        ]
    }


def test_first_day_after_polar_night_keeps_its_supported_solar_components():
    birth = build_astro_birth_info(
        birth_year=2026,
        birth_month=2,
        birth_day=23,
        birth_hour=12,
        birth_longitude=0,
        birth_latitude=80,
        birth_timezone="UTC",
    )
    india = build_india(birth, divisions=[])
    kala = india["strengths"]["kala_bala"]
    assert kala["components"]["dina_bala"]["ruler"] == "Moon"
    assert kala["components"]["hora_bala"]["ruler"] == "Moon"
    assert kala["components"]["tribhaga_bala"]["ruler"] == "Sun"


@pytest.mark.parametrize(
    "case,expected", list(zip(REFERENCE["cases"], REFERENCE["expected"]))
)
def test_both_hemispheres_against_frozen_event_inputs_and_manual_component_expectations(
    case, expected
):
    actual = solar_parts(case["jd_ut1"], 0, {"events": case["events"]})
    assert actual["status"] == "bracketed"
    assert actual["sunrise_day_status"] == actual["active_arc_status"] == "bracketed"
    for key, value in expected.items():
        assert actual[key] == value
    stamp = datetime.fromisoformat(case["instant"])
    birth = build_astro_birth_info(
        birth_year=stamp.year,
        birth_month=stamp.month,
        birth_day=stamp.day,
        birth_hour=stamp.hour,
        birth_timezone="UTC",
        birth_longitude=0,
        birth_latitude=case["latitude"],
    )
    current = build_india(birth, divisions=[])["strengths"]["kala_bala"][
        "solar_context"
    ]
    for key, value in expected.items():
        assert current[key] == value


@pytest.mark.parametrize("hours,ruler", [(2, "Mercury"), (6, "Sun"), (10, "Saturn")])
def test_day_arc_does_not_require_any_previous_sunset(hours, ruler):
    context = packet(("rise", 0), ("set", 0.5), ("rise", 1))
    actual = solar_parts(RISE + hours / 24, 0, context)
    assert actual["status"] == "bracketed"
    assert actual["is_day"] and actual["tribhaga_lord"] == ruler
    assert actual["day_lord"] == "Saturn"
    assert actual == solar_parts(
        RISE + hours / 24, 0, {"events": list(reversed(context["events"]))}
    )


@pytest.mark.parametrize("hours,ruler", [(14, "Moon"), (18, "Venus"), (22, "Mars")])
def test_night_arc_does_not_require_a_future_sunset(hours, ruler):
    actual = solar_parts(
        RISE + hours / 24, 0, packet(("rise", 0), ("set", 0.5), ("rise", 1))
    )
    assert actual["status"] == "bracketed"
    assert not actual["is_day"] and actual["tribhaga_lord"] == ruler
    assert actual["day_lord"] == "Saturn"


@pytest.mark.parametrize(
    "pairs,ruler,is_day",
    [
        ([("rise", 0), ("set", 0.5)], "Mercury", True),
        ([("set", 0), ("rise", 0.5)], "Moon", False),
    ],
)
def test_day_or_night_third_is_independent_of_missing_sunrise_day(pairs, ruler, is_day):
    actual = solar_parts(RISE + 0.125, 0, packet(*pairs))
    assert actual["status"] == "partial_solar_brackets"
    assert (
        actual["active_arc_status"] == "bracketed"
        and actual["sunrise_day_status"] == "not_bracketed"
    )
    assert actual["tribhaga_lord"] == ruler and actual["is_day"] is is_day
    assert actual["day_lord"] is actual["hora_lord"] is None


def test_sunrise_day_keeps_dina_hora_without_inventing_a_day_night_arc():
    actual = solar_parts(RISE + 0.125, 0, packet(("rise", 0), ("rise", 1)))
    assert actual["status"] == "partial_solar_brackets"
    assert actual["sunrise_day_status"] == "bracketed"
    assert actual["active_arc_status"] == "inconsistent_event_sequence"
    assert actual["day_lord"] == "Saturn" and actual["hora_number"] == 4
    assert actual["tribhaga_lord"] is None


@pytest.mark.parametrize(
    "pairs", [[], [("rise", 0)], [("set", 0.5)], [("set", 0), ("set", 0.5)]]
)
def test_empty_one_sided_or_same_kind_support_does_not_create_an_arc(pairs):
    actual = solar_parts(RISE + 0.125, 0, packet(*pairs))
    assert actual["status"] == "solar_day_not_bracketed"
    assert actual["day_lord"] is actual["hora_lord"] is actual["tribhaga_lord"] is None


@pytest.mark.parametrize(
    "pairs",
    [[("rise", 0), ("set", 0), ("rise", 1)], [("rise", 0), ("rise", 1), ("set", 1)]],
)
def test_exact_coincident_opposite_events_are_not_arbitrarily_ordered(pairs):
    actual = solar_parts(RISE + 0.125, 0, packet(*pairs))
    assert actual["active_arc_status"] == "ambiguous_coincident_events"
    assert actual["tribhaga_lord"] is None


@pytest.mark.parametrize(
    "offset,previous,next_ruler",
    [(0.25, "Mercury", "Sun"), (0.5, "Sun", "Saturn"), (0.75, "Saturn", "Moon")],
)
def test_exact_thirds_and_sunset_keep_half_open_binary_boundaries(
    offset, previous, next_ruler
):
    context = packet(("rise", 0), ("set", 0.75), ("rise", 1))
    edge = RISE + offset
    assert (
        solar_parts(math.nextafter(edge, -math.inf), 0, context)["tribhaga_lord"]
        == previous
    )
    assert solar_parts(edge, 0, context)["tribhaga_lord"] == next_ruler
    assert (
        solar_parts(math.nextafter(edge, math.inf), 0, context)["tribhaga_lord"]
        == next_ruler
    )


def test_known_constant_and_per_planet_explanation_survive_a_partial_arc():
    birth = build_astro_birth_info(**astro_payload())
    raw = positions(birth)
    jd = raw["julian_day_ut"]
    support = {
        "events": [
            {"kind": "rise", "julian_day_ut1": jd - 0.125},
            {"kind": "rise", "julian_day_ut1": jd + 0.875},
        ]
    }
    kala = temporal_balas(raw, support, birth.longitude)["kala_bala"]
    assert kala["components"]["tribhaga_bala"]["summary"]["Jupiter"] == 60
    assert kala["components"]["tribhaga_bala"]["summary"]["Sun"] is None
    assert kala["components"]["dina_bala"]["ruler"] is not None
    assert kala["components"]["hora_bala"]["ruler"] is not None
    assert (
        strength_context("kala_bala", "Jupiter", kala)["value_status"]
        == "computed_consensus"
    )
    sun = strength_context("kala_bala", "Sun", kala)
    assert sun["value_status"] == "unavailable"
    assert {r["component"] for r in sun["missing_evidence"]} == {"tribhaga_bala"}
    assert "india.strengths.kala_bala.solar_context" in sun["context_paths"]
    constraints = {
        r["fact_path"].rsplit(".", 1)[1]: r["value"] for r in sun["constraints"]
    }
    assert constraints["sunrise_day_status"] == "bracketed"
    assert constraints["active_arc_status"] == "inconsistent_event_sequence"


def test_first_sunrise_uncertainty_retains_available_and_unavailable_grid_states():
    case = REFERENCE["cases"][0]
    moment = datetime_from_ut1(case["events"][0]["julian_day_ut1"])
    birth = build_astro_birth_info(
        birth_year=moment.year,
        birth_month=moment.month,
        birth_day=moment.day,
        birth_hour=moment.hour,
        birth_minute=moment.minute,
        birth_second=moment.second,
        birth_microsecond=moment.microsecond,
        birth_timezone="UTC",
        birth_longitude=0,
        birth_latitude=80,
    )
    result = build_india(birth, divisions=[], birth_time_uncertainty_minutes=1)
    context = result["birth_time_sensitivity"]
    states = context["solar_bracket_states_on_grid"]
    assert sum(row["sample_count"] for row in states) == context["sample_count"] == 5
    assert {row["sunrise_day_status"] for row in states} == {
        "bracketed",
        "not_bracketed",
    }
    assert context["status"] == "changes_detected"
    assert {"not_available", "Moon"} <= set(
        context["time_lord_alternatives"]["dina_bala"]
    )
    assert {"not_available", "Mercury"} <= set(
        context["time_lord_alternatives"]["tribhaga_bala"]
    )
