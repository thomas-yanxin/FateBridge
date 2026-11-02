"""Manually frozen original pages, independent arithmetic and adversarial gates."""

import hashlib
import json
import math
import zipfile
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace

import pytest

from fatebridge.core.astrology_horary import (
    _applying_aspect,
    _judge_perfection,
    _moon_void_of_course,
    _planet_state,
)
from fatebridge.core.horary_events import BODIES, solve_planetary_events
from fatebridge.core.lilly_houses import dwelling_clause, house_condition
from fatebridge.core.lilly_orbs import (
    DEFAULT_ORB_PROFILE,
    full_orbs,
    orb_receipt,
    pair_radius,
)
from fatebridge.core.requests.western_events import AstroHoraryRequest
from fatebridge.services.western_horary import calculate_horary
from tests.test_western_horary import QUESTION
from tests.test_western_horary_motion import state

FIXTURES = Path(__file__).parent / "fixtures"
SOURCE = json.loads((FIXTURES / "western-lilly-orbs-houses-1647.json").read_text())
FIRST, SECOND = SOURCE["orb_tables"]


def test_original_pages_and_manual_annotation_are_frozen_before_implementation():
    assert (
        hashlib.sha256(
            (FIXTURES / "western-lilly-orbs-houses-1647.json").read_bytes()
        ).hexdigest()
        == "46ae9590f0a1260015e04ada799baa38beffd66ada2de6b7258af967b0ae6d94"
    )
    archive = FIXTURES / "western-lilly-orbs-houses-sources.zip"
    assert (
        hashlib.sha256(archive.read_bytes()).hexdigest()
        == "a0ba43b4ed29aa115824807a47b299dc79f0057c9e717bcd1b34b472b4da448e"
    )
    with zipfile.ZipFile(archive) as z:
        for row in SOURCE["source_receipts"]:
            assert (
                hashlib.sha256(z.read(f"{row['page']}.{row['type']}")).hexdigest()
                == row["sha256"]
            )
    assert SOURCE["production_imports"] is False
    assert SOURCE["full_original_text_acceptance"] is False
    assert SOURCE["expert_reviewed"] is False


def test_both_printed_columns_and_all_49_pair_radii_match_independent_fractions():
    for profile, table in SOURCE["orb_tables"].items():
        assert full_orbs(profile) == table
        receipt = orb_receipt(profile)
        assert receipt["full_orbs_degrees"] == table
        for a in table:
            for b in table:
                expected = (Fraction(str(table[a])) + Fraction(str(table[b]))) / 2
                assert pair_radius(a, b, profile) == expected
        assert receipt["pair_rule"] == SOURCE["pair_rule"]
        assert "implementation convention" in receipt["boundary_convention"]
    assert DEFAULT_ORB_PROFILE == FIRST
    assert AstroHoraryRequest.model_fields["orb_profile"].default == FIRST


def test_printed_venus_saturn_example_matches_first_column_moieties():
    row = SOURCE["printed_example"]
    result = _applying_aspect(
        state("Venus", row["Venus_longitude"], 1),
        state("Saturn", row["Saturn_longitude"], 0.02),
    )
    assert result["orb"] == row["residual_degrees"] == 8
    assert result["orb_limit"] == row["first_pair_radius"] == 9
    assert result["aspect"] == "trine" and result["orb_profile"] == FIRST


def test_preexisting_hybrid_mars_allowance_is_rejected_without_erasing_source_variants():
    for row in SOURCE["counterexamples"]:
        a, b = [state(p, lon, 1) for p, lon in zip(row["planets"], row["longitudes"])]
        for profile, key in ((FIRST, "first"), (SECOND, "second")):
            assert (_applying_aspect(a, b, orb_profile=profile) is not None) is row[key]
    assert full_orbs(FIRST)["Mars"] == 7.5
    assert full_orbs(SECOND)["Mars"] == 7


@pytest.mark.parametrize("profile,limit", [(FIRST, 7.25), (SECOND, 7.0)])
def test_orb_equality_convention_classifies_adjacent_floats_before_rounding(
    profile, limit
):
    a = state("Mars", 0, 0.5)
    for value, expected in (
        (math.nextafter(limit, 0), True),
        (limit, True),
        (math.nextafter(limit, math.inf), False),
    ):
        assert (
            _applying_aspect(a, state("Mercury", value, 1), orb_profile=profile)
            is not None
        ) is expected


def test_profile_selection_is_local_for_proxy_lunar_annotations_and_concurrent_calls():
    a, b = state("Mars", 0, 1), state("Mercury", 7.125, 0.5)
    moon = state("Moon", 7, 13)
    states = {
        p: state(p, lon, speed)
        for p, lon, speed in [
            ("Saturn", 201, 0.02),
            ("Jupiter", 218, 0.1),
            ("Sun", 194, 1),
            ("Venus", 233, 1.2),
        ]
    }
    states.update(Mars=a, Mercury=b, Moon=moon)
    for profile, expected in ((FIRST, True), (SECOND, False), (FIRST, True)):
        value = _judge_perfection(
            a,
            b,
            moon,
            states,
            "Mars",
            "Mercury",
            orb_profile=profile,
        )
        assert (value["mode"] == "direct") is expected
        result = _moon_void_of_course(
            state("Moon", 0, 13), [state("Mars", 9.8, 0)], orb_profile=profile
        )
        assert result["next_aspect"]["inside_current_orb"] is expected
        assert result["next_aspect"]["orb_profile"] == profile
    profiles = [FIRST, SECOND] * 20
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(
            pool.map(
                lambda p: _applying_aspect(a, b, orb_profile=p) is not None, profiles
            )
        )
    assert results == [True, False] * 20
    table = full_orbs(FIRST)
    table["Mars"] = 999
    assert full_orbs(FIRST)["Mars"] == 7.5


def test_unknown_orb_profile_fails_before_chart_construction():
    with pytest.raises(ValueError, match="orb_profile"):
        full_orbs("hybrid")
    result = calculate_horary(**QUESTION, orb_profile="hybrid")
    assert result["error_code"] == "validation_error" and "horary" not in result


def test_house_rank_and_house_points_are_distinct_original_rows():
    for rank, house in enumerate(SOURCE["p48_house_strength_order"], 1):
        row = house_condition(house, "R", "Tropic")
        assert row["p48_strength_rank"] == rank
        assert row["p115_house_points"] == SOURCE["p115_house_points"][str(house)]
        assert house in SOURCE["house_classes"][row["house_class"]]
        assert "otherwise equally dignified" in row["p48_rank_condition"]
        assert row["full_original_text_acceptance"] is False
    assert (
        house_condition(1, "R", "Tropic")["p115_house_points"]
        == house_condition(10, "R", "Tropic")["p115_house_points"]
    )
    assert (
        house_condition(3, "R", "Tropic")["p48_strength_rank"]
        < house_condition(2, "R", "Tropic")["p48_strength_rank"]
    )
    assert (
        house_condition(3, "R", "Tropic")["p115_house_points"]
        < house_condition(2, "R", "Tropic")["p115_house_points"]
    )
    assert (
        house_condition(1, "W", "Sidereal")["source_method_scope"]
        == "other_or_unknown_chart_method_not_original_edition_acceptance"
    )
    with pytest.raises(ValueError):
        house_condition(0, "R", "Tropic")


def test_native_occupied_house_is_not_confused_with_significator_role_or_guessed():
    point = SimpleNamespace(abs_pos=20.0, speed=1.0, house="Tenth_House")
    result = _planet_state(SimpleNamespace(venus=point), "Venus")
    assert result["occupied_house"] == 10 and "house" not in result
    del point.house
    result = _planet_state(SimpleNamespace(venus=point), "Venus")
    assert (
        result["occupied_house"] is None
        and result["house_condition"]["p115_house_points"] is None
    )


def dwelling_inputs():
    states = {
        p: state(p, lon, speed)
        for p, lon, speed in [("Moon", 12, 13), ("Mars", 10, 0.5), ("Venus", 14, 1)]
    }
    states["Mars"]["occupied_house"] = 1

    def contact(other, time):
        return {
            "kind": "contact",
            "bodies": ["Moon", other],
            "aspect": "conjunction",
            "topology": "crossing",
            "epoch_relation": "past" if time < 0 else "future",
            "root_bracket_tt": [time - 0.001, time + 0.001],
        }

    history = {
        "status": "computed",
        "constant_velocity_projection": False,
        "events": [contact("Mars", -1), contact("Venus", 1)],
    }
    return states, history


def clause(states, history, querent="Venus", quesited="Mars", event_paths=None):
    return dwelling_clause(
        states,
        querent,
        quesited,
        history,
        event_paths or {"paths": []},
        _applying_aspect,
    )


def test_dwelling_clause_computes_direction_without_promoting_subset_to_judgement():
    states, history = dwelling_inputs()
    result = clause(states, history)
    assert result["quesited_in_first_house"] is True
    assert result["lunar_sequence_subconditions_satisfied"] is True
    assert result["named_necessary_conditions_satisfied"] is True
    assert result["dwelling_alone_sufficient"] is False
    assert result["full_judgement_accepted"] is False
    assert "必要子条件" in result["conditional_reading_zh"]
    reversed_history = deepcopy(history)
    reversed_history["events"][0]["bodies"] = ["Moon", "Venus"]
    reversed_history["events"][1]["bodies"] = ["Moon", "Mars"]
    assert (
        clause(states, reversed_history)["lunar_sequence_subconditions_satisfied"]
        is False
    )


def test_dwelling_alone_intervening_planet_and_late_ray_do_not_fabricate_transfer():
    states, history = dwelling_inputs()
    history["events"].insert(
        1,
        {
            **history["events"][1],
            "bodies": ["Moon", "Jupiter"],
            "root_bracket_tt": [0.4, 0.5],
        },
    )
    result = clause(states, history)
    assert result["moon_next_contact_is_querent"] is False
    assert result["named_necessary_conditions_satisfied"] is False
    assert "仅凭居宫断成" in result["conditional_reading_zh"]
    states, history = dwelling_inputs()
    states["Moon"]["longitude"] = 15
    assert clause(states, history)["moon_applying_to_next_recipient_ray_now"] is False


@pytest.mark.parametrize(
    "ambiguity",
    ["unavailable", "missing", "overlap", "boundary", "tangent", "unresolved", "speed"],
)
def test_dwelling_retains_unknown_lunar_histories_and_numerical_ambiguity(ambiguity):
    states, history = dwelling_inputs()
    if ambiguity == "unavailable":
        history["status"] = "unavailable"
    elif ambiguity == "missing":
        history["events"] = []
    elif ambiguity in {"overlap", "boundary", "tangent"}:
        event = deepcopy(history["events"][1])
        event["bodies"] = ["Moon", "Jupiter"]
        if ambiguity == "boundary":
            event["epoch_relation"] = "question_boundary"
            event["root_bracket_tt"] = [-0.01, 0.01]
        elif ambiguity == "tangent":
            event["topology"] = "tangent"
            event["root_bracket_tt"] = [0.4, 0.5]
        history["events"].append(event)
    elif ambiguity == "speed":
        states["Moon"]["speed"] = None
    else:
        history["unresolved_intervals"] = [{"bodies": ["Moon", "Saturn"]}]
    result = clause(states, history)
    assert result["lunar_sequence_subconditions_satisfied"] is None
    assert result["named_necessary_conditions_satisfied"] is None
    assert result["full_judgement_accepted"] is False


def test_dwelling_role_collisions_and_unknown_occupancy_are_explicit():
    states, history = dwelling_inputs()
    for a, b in [("Mars", "Mars"), ("Moon", "Mars"), ("Venus", "Moon")]:
        result = clause(states, history, a, b)
        assert result["distinct_lunar_transfer_actors"] is False
        assert result["lunar_sequence_subconditions_satisfied"] is None
    del states["Mars"]["occupied_house"]
    assert clause(states, history)["quesited_in_first_house"] is None
    states["Mars"]["occupied_house"] = 10
    assert clause(states, history)["named_necessary_conditions_satisfied"] is False


def test_matching_p126_receipts_remain_distinct_from_p127_necessary_subconditions():
    states, history = dwelling_inputs()
    result = clause(
        states,
        history,
        event_paths={
            "paths": [
                {
                    "mode": "translation",
                    "actors": ["Mars", "Moon", "Venus"],
                    "sequence_conditions_satisfied": False,
                }
            ]
        },
    )
    assert result["matching_p126_event_path_indexes"] == [0]
    assert result["lunar_sequence_subconditions_satisfied"] is True
    assert result["full_original_text_acceptance"] is False


def test_actual_root_solver_feeds_dwelling_invariant_to_event_array_order():
    # Analytical motion realizes the named clause; these are engineering
    # controls, not observations or historical ephemerides printed by Lilly.
    positions = {p: 40.0 for p in BODIES}
    speeds = {p: 0.0 for p in BODIES}
    positions.update(Moon=12.0, Mars=10.0, Venus=14.0)
    speeds.update(Moon=13.0, Mars=0.5, Venus=1.0)

    def sample(planet, epoch):
        return {
            "longitude": (positions[planet] + speeds[planet] * (epoch - 2451545.0))
            % 360,
            "speed": speeds[planet],
            "latitude": 0.0,
        }

    history = solve_planetary_events(2451545.0, sample, past_days=0.5, future_days=0.5)
    states = {p: state(p, positions[p], speeds[p]) for p in BODIES}
    states["Mars"]["occupied_house"] = 1
    result = clause(states, history)
    assert result["lunar_sequence_subconditions_satisfied"] is True
    assert result["prior_lunar_contact"]["julian_day_tt"] == pytest.approx(
        2451545.0 - 2 / 12.5, abs=1e-8
    )
    assert result["next_lunar_contact"]["julian_day_tt"] == pytest.approx(
        2451545.0 + 2 / 12, abs=1e-8
    )
    history["events"].reverse()
    assert clause(states, history) == result
