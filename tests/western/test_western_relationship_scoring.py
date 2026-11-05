"""Role symmetry, exact cutoff boundaries and independently replayed arithmetic."""

import math
import random

import pytest

from fatebridge.core.astro.aspects import (
    _build_directional_relative_aspects,
    _flatten_directional_relative_aspects,
)
from fatebridge.core.astro.parts import _build_planet_record
from fatebridge.core.astro.relationship_scoring import compatibility_with_evidence

NAMES = ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn"]


def planets(angles):
    return [
        _build_planet_record(name, angle, 0, 0, "whole_sign")
        for name, angle in zip(NAMES, angles)
    ]


def contacts(a, b):
    return _flatten_directional_relative_aspects(
        _build_directional_relative_aspects(a, b),
        source_key="inner",
        target_key="outer",
    )


def replay(scores, evidence, original):
    for dimension, key in (
        ("element", "element_harmony_score"),
        ("modality", "modality_balance_score"),
    ):
        detail = evidence[dimension + "_overlap"]
        left, right = detail["inner_counts"], detail["outer_counts"]
        shared = sum(
            min(left.get(k, 0), right.get(k, 0)) for k in left.keys() | right.keys()
        )
        assert detail["overlap_count"] == shared
        assert detail["denominator"] == max(sum(left.values()), sum(right.values()), 1)
        assert (
            detail["score"]
            == scores[key]
            == round(100 * shared / detail["denominator"])
        )
    selection = evidence["aspect_selection"]
    raw = selection["baseline"]
    for contact in selection["selected_contacts"]:
        index = contact["synastry_aspect_index"]
        assert {k: contact[k] for k in original[index]} == original[index]
        raw += contact["delta"]
    assert selection["unclamped_score"] == raw
    assert (
        selection["score"] == scores["synastry_aspect_score"] == min(100, max(0, raw))
    )
    assert evidence["overall"]["numerator"] == sum(
        value for key, value in scores.items() if key != "overall_score"
    )
    assert (
        evidence["overall"]["score"]
        == scores["overall_score"]
        == round(evidence["overall"]["numerator"] / 3)
    )


def test_frozen_angular_counterexample_is_invariant_under_role_swap_and_shuffles():
    # Synthetic lattice, not a claim that these are simultaneous birth positions.
    a = planets([180, 270, 270, 210, 60, 0, 0])
    b = planets([30, 30, 90, 90, 0, 150, 300])
    rows = contacts(a, b)
    actual, evidence = compatibility_with_evidence(a, b, rows)
    # Independent integer sign-step enumeration: 16 positive, 17 negative.
    steps = [
        min((x - y) % 12, (y - x) % 12)
        for x in [6, 9, 9, 7, 2, 0, 0]
        for y in [1, 1, 3, 3, 0, 5, 10]
    ]
    assert sum(step in {0, 2, 4} for step in steps) == 16
    assert sum(step in {3, 6} for step in steps) == 17
    assert len(rows) == 33
    assert actual == {
        "element_harmony_score": 71,
        "modality_balance_score": 71,
        "synastry_aspect_score": 46,
        "overall_score": 63,
    }
    assert evidence["aspect_selection"]["positive_count"] == 16
    assert evidence["aspect_selection"]["negative_count"] == 17
    assert evidence["aspect_selection"]["selected_count"] == 33
    assert evidence["aspect_selection"]["boundary_tie_count"] == 33
    replay(actual, evidence, rows)
    assert compatibility_with_evidence(b, a, contacts(b, a))[0] == actual
    rng = random.Random(39183)
    for _ in range(30):
        rng.shuffle(rows)
        score, detail = compatibility_with_evidence(a, b, rows)
        assert score == actual
        replay(score, detail, rows)


def boundary_rows():
    pairs = [(a, b) for a in NAMES for b in NAMES]
    return [
        {
            "inner": a,
            "outer": b,
            "aspect": "trine" if i % 2 == 0 else "square",
            "orb": 1.0 if i < 23 else 2.0,
        }
        for i, (a, b) in enumerate(pairs[:25])
    ]


def test_cutoff_tie_can_lower_or_raise_the_old_arbitrary_choice():
    rows = boundary_rows()
    p = planets([0] * 7)
    scores, evidence = compatibility_with_evidence(p, p, rows)
    # First 23 sum to +4; equal-orb square and trine cancel each other.
    assert scores["synastry_aspect_score"] == 54
    assert evidence["aspect_selection"]["selected_count"] == 25
    assert evidence["aspect_selection"]["boundary_tie_count"] == 2
    assert 50 < scores["synastry_aspect_score"] < 58
    rows[23], rows[24] = rows[24], rows[23]
    assert compatibility_with_evidence(p, p, rows)[0] == scores
    replay(scores, evidence, boundary_rows())


def test_next_float_is_distinct_from_exact_cutoff_not_an_epsilon_tie():
    rows = boundary_rows()
    rows[-1]["orb"] = math.nextafter(2.0, math.inf)
    p = planets([0] * 7)
    scores, detail = compatibility_with_evidence(p, p, rows)
    assert detail["aspect_selection"]["selected_count"] == 24
    assert detail["aspect_selection"]["boundary_tie_count"] == 1
    assert scores["synastry_aspect_score"] == 50


@pytest.mark.parametrize(
    "aspect,expected,unclamped", [("trine", 100, 146), ("square", 0, -46)]
)
def test_clamping_is_visible_and_does_not_hide_the_arithmetic(
    aspect, expected, unclamped
):
    rows = boundary_rows()[:24]
    for row in rows:
        row["aspect"] = aspect
    p = planets([0] * 7)
    scores, evidence = compatibility_with_evidence(p, p, rows)
    assert scores["synastry_aspect_score"] == expected
    assert evidence["aspect_selection"]["unclamped_score"] == unclamped
    assert evidence["aspect_selection"]["clamped"] is True
    replay(scores, evidence, rows)


def test_no_contacts_is_a_declared_baseline_and_not_observed_compatibility():
    p = planets([0] * 7)
    scores, evidence = compatibility_with_evidence(p, p, [])
    assert scores["synastry_aspect_score"] == 50
    assert evidence["aspect_selection"]["cutoff_orb"] is None
    assert evidence["aspect_selection"]["selected_count"] == 0
    replay(scores, evidence, [])


@pytest.mark.parametrize("bad", [math.nan, math.inf, -1])
def test_nonfinite_or_negative_orbs_cannot_silently_affect_membership(bad):
    rows = boundary_rows()
    rows[-1]["orb"] = bad
    p = planets([0] * 7)
    with pytest.raises(ValueError, match="finite seven-planet"):
        compatibility_with_evidence(p, p, rows)
