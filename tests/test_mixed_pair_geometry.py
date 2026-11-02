"""Independent exhaustive layer enumeration and exact boundary counterexamples."""

import math
import random
from fractions import Fraction
from itertools import combinations, product

import pytest

from fatebridge.core.astro.mixed_pairs import (
    mixed_pair_geometry,
    unavailable_mixed_pairs,
)
from fatebridge.core.output_midpoints import MixedPairGeometry


def expand(result, period):
    dial = result["dials"][str(period)]
    rows = [*dial["arc_dependent_contacts"], *dial["arc_invariant_contacts"]]
    found = {}
    for row in rows:
        names = tuple(row[k] for k in ("id_a", "id_b", "id_c", "id_d"))
        assert len(set(names)) == 4
        for layers in row["factor_layer_assignments"]:
            bits = tuple(int(layers[n] == "solar_arc") for n in names)
            identity = (names, bits)
            assert identity not in found
            found[identity] = row
    return found


@pytest.mark.parametrize("period", [90, 45])
def test_every_retained_layering_matches_independent_direct_factor_arithmetic(period):
    rng = random.Random(194505)
    natal = {str(i): rng.randrange(360 * 64) / 64 for i in range(6)}
    arc, orb = 23.125, 1.0
    result = mixed_pair_geometry(natal, arc, hypothetical_ids={"5"})
    found = expand(result, period)
    expected = {}
    for quartet in combinations(sorted(natal), 4):
        a, *rest = quartet
        for b in rest:
            c, d = (n for n in rest if n != b)
            names = (a, b, c, d)
            for bits in product((0, 1), repeat=4):
                if bits[0] == bits[1] and bits[2] == bits[3]:
                    continue
                # Compute all four actual factor coordinates before summing;
                # do not reuse the production grouping/coefficient expression.
                x = [
                    Fraction(natal[n]) + bit * Fraction(arc)
                    for n, bit in zip(names, bits)
                ]
                left, right = (x[0] + x[1]) / 2, (x[2] + x[3]) / 2
                difference = left - right
                turns = math.floor(difference / period + Fraction(1, 2))
                residual = difference - turns * period
                if abs(residual) <= Fraction(orb):
                    expected[(names, bits)] = residual
    assert set(found) == set(expected)
    for key, residual in expected.items():
        row = found[key]
        assert row["signed_orb"] == float(residual)
        assert row["arc_invariant"] == (sum(key[1][:2]) == sum(key[1][2:]))
        assert row["contains_hypothetical"] == ("5" in key[0])
    assert result["profile"]["pair_partitions_tested_per_dial"] == math.comb(6, 4) * 3
    assert (
        result["profile"]["layer_assignments_represented_per_dial"]
        == math.comb(6, 4) * 36
    )
    assert (
        len(found)
        == result["contact_counts"][str(period)]["represented_layer_assignments"]
    )


def test_half_arc_contact_missing_from_homogeneous_pair_catalogue_is_computed():
    result = mixed_pair_geometry({"A": 0, "B": 20, "C": 10, "D": 30}, 20, orb_degrees=0)
    matches = [
        row
        for row in result["dials"]["90"]["arc_dependent_contacts"]
        if [row[k] for k in ("id_a", "id_b", "id_c", "id_d")] == ["A", "B", "C", "D"]
    ]
    assert len(matches) == 1
    row = matches[0]
    assert row["midpoint_arc_coefficient"] == 0.5
    assert row["orb"] == 0 and not row["arc_invariant"]
    assert len(row["factor_layer_assignments"]) == 4
    assert {"A": "solar_arc", "B": "natal", "C": "natal", "D": "natal"} in row[
        "factor_layer_assignments"
    ]


def test_one_directed_factor_on_each_side_cancels_without_creating_timing_signal():
    natal = {"A": 0, "B": 40, "C": 10, "D": 30}
    previous = None
    for arc in (0, 0.125, 17, 90, 359.5):
        result = mixed_pair_geometry(natal, arc, orb_degrees=0)
        rows = result["dials"]["90"]["arc_invariant_contacts"]
        signature = [
            (r["equation"], r["signed_orb"], r["factor_layer_assignments"])
            for r in rows
        ]
        if previous is not None:
            assert signature == previous
        previous = signature
        assert len(rows) == 1
        assert rows[0]["midpoint_arc_coefficient"] == 0
        assert all(
            sum(v == "solar_arc" for v in a.values()) == 2
            for a in rows[0]["factor_layer_assignments"]
        )
        assert "not a timing trigger" in result["profile"]["arc_invariant_means"]


@pytest.mark.parametrize(
    "arc", [math.nextafter(18.0, -math.inf), 18.0, math.nextafter(18.0, math.inf)]
)
def test_half_arc_inclusive_orb_preserves_nextafter_boundary_side(arc):
    # Base difference -10; at arc18 the residual is exactly -1degree.
    result = mixed_pair_geometry({"A": 0, "B": 20, "C": 10, "D": 30}, arc)
    rows = result["dials"]["90"]["arc_dependent_contacts"]
    match = [
        r
        for r in rows
        if (r["id_a"], r["id_b"], r["id_c"], r["id_d"], r["midpoint_arc_coefficient"])
        == ("A", "B", "C", "D", 0.5)
    ]
    assert bool(match) == (arc >= 18)


def test_input_order_and_common_display_rotation_do_not_change_relations():
    source = {"A": 2, "B": 22, "C": 12, "D": 32, "E": 199}
    first = mixed_pair_geometry(source, 20)
    rotated = mixed_pair_geometry(
        {k: (v + 197) % 360 for k, v in reversed(list(source.items()))}, 20
    )
    assert first == rotated
    typed = MixedPairGeometry.model_validate(first).model_dump(exclude_unset=True)
    assert typed == first


@pytest.mark.parametrize(
    "values,arc,orb",
    [
        ({"A": math.nan}, 1, 1),
        ({"A": True}, 1, 1),
        ({"": 1}, 1, 1),
        ({"A": 1}, math.inf, 1),
        ({"A": 1}, 1, -1),
        ({"A": 1}, 1, 6),
    ],
)
def test_invalid_coordinates_or_orb_cannot_become_empty_success(values, arc, orb):
    with pytest.raises(ValueError):
        mixed_pair_geometry(values, arc, orb_degrees=orb)


def test_unavailable_native_layer_is_unknown_instead_of_zero_contacts():
    result = unavailable_mixed_pairs("controlled missing-native input")
    assert result["status"] == "unavailable"
    assert result["profile"] is result["contact_counts"] is None
    assert "dials" not in result
    assert MixedPairGeometry.model_validate(result).status == "unavailable"
