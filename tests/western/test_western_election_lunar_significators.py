"""Ramesey p175 source roles use actual event order, without scoring it."""

import copy

import pytest

import fatebridge.core.astro.astrology_election as election
from fatebridge.core.contracts.western import Election
from tests.fixtures.western_event_cases import (
    event_result,
    synthetic_subject,
)

EPOCH = 2451545.0


def contact(other, offset, side, *, width=0.001, topology="crossing"):
    at = EPOCH + offset
    return {
        "kind": "contact",
        "bodies": ["Moon", other],
        "julian_day_tt": at,
        "root_bracket_tt": [at - width, at + width],
        "epoch_relation": side,
        "topology": topology,
        "aspect": "sextile",
        "ray_degrees": 60,
        "direction": 1,
        "states": {},
        "state_brackets": {},
    }


@pytest.fixture
def source_case(monkeypatch):
    history = {
        "status": "computed",
        "constant_velocity_projection": False,
        "method_id": "synthetic_order_control_not_physical_observations",
        "window_tt": [EPOCH - 30, EPOCH + 30],
        "events": [
            contact("Jupiter", -0.5, "past"),
            contact("Mars", -0.1, "past"),
            contact("Venus", 0.1, "future"),
            contact("Mercury", 0.5, "future"),
        ],
        "unresolved_intervals": [],
    }
    monkeypatch.setattr(
        election, "native_lunar_contacts", lambda subject: event_result(False)
    )
    monkeypatch.setattr(
        election,
        "native_planetary_events",
        lambda subject: copy.deepcopy(history),
    )
    subject = synthetic_subject()
    subject.houses_system_identifier = "R"
    return subject, history


def test_original_natural_and_lunar_roles_follow_the_two_adjacent_contacts(
    source_case,
) -> None:
    subject, _ = source_case
    result = election.build_election_payload(subject, topic_id="marriage")
    Election.model_validate(result)
    receipt = result["marriage_significators"]
    first, second = receipt["parties"]
    assert [first["natural_significator"], second["natural_significator"]] == [
        "Sun",
        "Venus",
    ]
    assert [first["lunar_significator"], second["lunar_significator"]] == [
        "Mars",
        "Venus",
    ]
    assert first["contact"]["epoch_relation"] == "past"
    assert second["contact"]["epoch_relation"] == "future"
    assert (
        first["contact_order_established"]
        is second["contact_order_established"]
        is True
    )
    assert "full_original_text_acceptance" not in receipt


def test_uncertain_history_preserves_other_facts(
    source_case,
) -> None:
    subject, history = source_case
    known = election.build_election_payload(subject, topic_id="marriage")
    history.update(
        status="unavailable", unavailable_reason="Synthetic missing event history"
    )
    unknown = election.build_election_payload(subject, topic_id="marriage")
    assert {k: v for k, v in known.items() if k != "marriage_significators"} == {
        k: v for k, v in unknown.items() if k != "marriage_significators"
    }
    receipt = unknown["marriage_significators"]
    assert receipt["event_history"]["status"] == "unavailable"
    assert all(row["lunar_significator"] is None for row in receipt["parties"])
    assert all(row["ruler"] is not None for row in receipt["houses"])


def test_overlapping_past_brackets_do_not_assign_the_source_party(source_case) -> None:
    subject, history = source_case
    history["events"].insert(1, contact("Saturn", -0.101, "past"))
    first, second = election.build_election_payload(subject, topic_id="marriage")[
        "marriage_significators"
    ]["parties"]
    assert first["contact"] is not None
    assert (
        first["contact_order_established"] is None
        and first["lunar_significator"] is None
    )
    assert second["lunar_significator"] == "Venus"


def test_earlier_unclassified_contact_prevents_a_certain_next_party(
    source_case,
) -> None:
    subject, history = source_case
    history["events"].insert(
        2, contact("Saturn", 0.05, "future", topology="tangent_unclassified")
    )
    first, second = election.build_election_payload(subject, topic_id="marriage")[
        "marriage_significators"
    ]["parties"]
    assert first["lunar_significator"] == "Mars"
    assert (
        second["contact_order_established"] is None
        and second["lunar_significator"] is None
    )


def test_unknown_asc_does_not_erase_the_known_lunar_roles_or_mc(source_case) -> None:
    subject, _ = source_case
    subject.calculation_basis["angle_definition"] = {
        "geometric_ascendant_resolved": False
    }
    receipt = election.build_election_payload(subject, topic_id="marriage")[
        "marriage_significators"
    ]
    assert receipt["status"] == "partial_reference_geometry"
    assert (
        receipt["houses"][0]["ruler"] is None
        and receipt["houses"][2]["ruler"] is not None
    )
    assert [row["lunar_significator"] for row in receipt["parties"]] == [
        "Mars",
        "Venus",
    ]


def test_other_selected_zodiac_does_not_substitute_a_source_chart(source_case) -> None:
    subject, _ = source_case
    subject.zodiac_type = "Sidereal"
    receipt = election.build_election_payload(subject, topic_id="marriage")[
        "marriage_significators"
    ]
    assert receipt["status"] == "not_assessed_for_selected_method"
    assert receipt["parties"] == [] and receipt["event_history"] is None
