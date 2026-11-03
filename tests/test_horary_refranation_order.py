"""Lilly's continuing recipient cannot be inferred from ambiguous station order.

These are numerical event receipts, not observed sky events. Closed adjacent
TT-float brackets can touch; their rounded midpoints do not prove strict order.
"""

import math

import pytest

from fatebridge.core.astrology_horary import _applying_aspect
from fatebridge.core.horary_event_paths import evaluate_event_paths


@pytest.fixture
def controlled_history():
    epoch = 2451545.0
    at = epoch + 4
    following = math.nextafter(at, math.inf)
    positions = dict(
        Sun=250, Moon=100, Mercury=160, Venus=200, Mars=7, Jupiter=330, Saturn=12
    )
    speeds = {planet: 0.1 for planet in positions}
    speeds.update(Mars=0.8, Saturn=0.02)
    states = {
        planet: {
            "planet": planet,
            "planet_label": planet,
            "longitude": longitude,
            "speed": speeds[planet],
            "sign": "Aries",
            "dignities": [],
        }
        for planet, longitude in positions.items()
    }
    history = {
        "status": "computed",
        "constant_velocity_projection": False,
        "question_julian_day_tt": epoch,
        "events": [
            {
                "kind": "station",
                "bodies": ["Mars"],
                "root_bracket_tt": [at, following],
                "julian_day_tt": (at + following) / 2,
                "epoch_relation": "future",
                "direction": -1,
            }
        ],
    }
    return history, states


@pytest.mark.parametrize("reverse_roles", [False, True])
@pytest.mark.parametrize("recipient_station", ["before", "touching", "question"])
def test_recipient_reversal_that_can_precede_applicant_does_not_certify_pattern(
    controlled_history, recipient_station, reverse_roles
):
    history, states = controlled_history
    applicant = history["events"][0]
    if recipient_station == "before":
        left = right = applicant["root_bracket_tt"][0] - 1
    elif recipient_station == "touching":
        left = applicant["root_bracket_tt"][1]
        right = math.nextafter(left, math.inf)
        # Both brackets have the width of one JD float, as the physical solver
        # can produce. The second midpoint is later, but strict order is unknown.
        assert (left + right) / 2 > applicant["julian_day_tt"]
    else:
        left = history["question_julian_day_tt"]
        right = math.nextafter(left, math.inf)
    history["events"].append(
        {
            "kind": "station",
            "bodies": ["Saturn"],
            "root_bracket_tt": [left, right],
            "julian_day_tt": (left + right) / 2,
            "epoch_relation": (
                "question_boundary" if recipient_station == "question" else "future"
            ),
            "direction": -1,
        }
    )
    history["events"].sort(key=lambda e: e["julian_day_tt"])
    roles = ("Saturn", "Mars") if reverse_roles else ("Mars", "Saturn")
    result = evaluate_event_paths(history, *roles, "day", states, _applying_aspect)
    assert not result["refranation_patterns"]
    direct = next(path for path in result["paths"] if path["mode"] == "direct")
    condition = next(
        c
        for c in direct["conditions"]
        if c["code"] == "no_selected_refranation_pattern"
    )
    assert condition["passed"] is None
    assert result["full_original_text_acceptance"] is False


@pytest.mark.parametrize("recipient_after", [False, True])
def test_no_recipient_station_or_a_strictly_later_one_preserves_selected_pattern(
    controlled_history, recipient_after
):
    history, states = controlled_history
    applicant = history["events"][0]
    if recipient_after:
        at = math.nextafter(applicant["root_bracket_tt"][1], math.inf)
        history["events"].append(
            {
                "kind": "station",
                "bodies": ["Saturn"],
                "root_bracket_tt": [at, at],
                "julian_day_tt": at,
                "epoch_relation": "future",
                "direction": -1,
            }
        )
    result = evaluate_event_paths(
        history, "Mars", "Saturn", "day", states, _applying_aspect
    )
    assert len(result["refranation_patterns"]) == 1
    assert result["refranation_patterns"][0]["applicant"] == "Mars"
    assert result["full_original_text_acceptance"] is False
