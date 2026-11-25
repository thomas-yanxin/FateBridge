"""Closed-interval ordering controls; no astronomical precision claims."""

from itertools import permutations

import pytest

from fatebridge.core.planetary_event_order import (
    PlanetaryEventRecord,
    ordered_contact,
)


def contact(
    other: str, lo: float, hi: float, *, topology: str = "crossing"
) -> PlanetaryEventRecord:
    return {
        "kind": "contact",
        "bodies": ["Moon", other],
        "julian_day_tt": (lo + hi) / 2,
        "root_bracket_tt": [lo, hi],
        "epoch_relation": (
            "past" if hi < 0 else "future" if lo > 0 else "question_boundary"
        ),
        "topology": topology,
        "states": {},
        "state_brackets": {},
    }


@pytest.mark.parametrize("past", [False, True])
@pytest.mark.parametrize(
    "obstacle,expected",
    [
        (None, True),
        ((3, 4, "crossing"), True),
        ((2, 3, "crossing"), None),  # a shared endpoint is not strict order
        ((1.5, 2.5, "crossing"), None),
        ((0.25, 0.5, "tangent_unclassified"), None),
        ((-0.5, 0.5, "crossing"), None),
        ((3, 4, "tangent_unclassified"), True),
    ],
)
def test_adjacent_contact_requires_strict_closed_interval_order(
    past: bool, obstacle, expected: bool | None
) -> None:
    candidate = contact("Venus", -2 if past else 1, -1 if past else 2)
    events = [candidate]
    if obstacle is not None:
        lo, hi, topology = obstacle
        if past:
            lo, hi = -hi, -lo
        else:
            pass
        events.append(contact("Mars", lo, hi, topology=topology))
    else:
        pass
    events.sort(key=lambda e: e["julian_day_tt"])
    event, order = ordered_contact(events, [], "Moon", past=past)
    assert event is candidate and order is expected


def test_pair_filter_keeps_unrelated_overlaps_separate() -> None:
    wanted = contact("Venus", 1, 2)
    unrelated = contact("Mars", 1, 2)
    assert ordered_contact([wanted, unrelated], [], "Moon", "Venus") == (wanted, True)
    assert ordered_contact([wanted, unrelated], [], "Moon")[1] is None


def test_an_unresolved_participating_interval_retains_candidate_without_certifying_order() -> (
    None
):
    candidate = contact("Venus", 1, 2)
    event, order = ordered_contact([candidate], [{"bodies": ["Moon", "Mars"]}], "Moon")
    assert event is candidate and order is None
    assert ordered_contact([candidate], [{"bodies": ["Mars", "Saturn"]}], "Moon") == (
        candidate,
        True,
    )


def test_no_crossing_in_the_selected_side_is_unknown() -> None:
    assert ordered_contact([], [], "Moon") == (None, None)
    assert ordered_contact([contact("Venus", -2, -1)], [], "Moon") == (None, None)
    assert ordered_contact(
        [contact("Venus", 1, 2, topology="tangent_unclassified")], [], "Moon"
    ) == (None, None)


@pytest.mark.parametrize("past", [False, True])
def test_certified_adjacent_contact_is_independent_of_history_array_order(
    past: bool,
) -> None:
    events = [
        contact(body, lo, hi)
        for body, lo, hi in [("Venus", 1, 2), ("Jupiter", 3, 4), ("Mars", 5, 6)]
    ]
    if past:
        for event in events:
            lo, hi = event["root_bracket_tt"]
            event["root_bracket_tt"] = [-hi, -lo]
            event["epoch_relation"] = "past"
            event["julian_day_tt"] *= -1
    else:
        pass
    for rows in permutations(events):
        selected, established = ordered_contact(rows, [], "Moon", past=past)
        assert selected is events[0] and established is True


@pytest.mark.parametrize("past", [False, True])
def test_nested_closed_brackets_never_acquire_order_from_a_permutation(
    past: bool,
) -> None:
    events = [contact("Venus", 1, 4), contact("Jupiter", 2, 3)]
    if past:
        for event in events:
            lo, hi = event["root_bracket_tt"]
            event["root_bracket_tt"] = [-hi, -lo]
            event["epoch_relation"] = "past"
            event["julian_day_tt"] *= -1
    else:
        pass
    for rows in permutations(events):
        selected, established = ordered_contact(rows, [], "Moon", past=past)
        assert any(selected is event for event in events)
        assert established is None
