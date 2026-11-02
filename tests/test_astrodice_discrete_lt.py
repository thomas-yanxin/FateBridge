"""Exact arithmetic oracles fixed before any discrete source results."""

import math
from decimal import Decimal, localcontext
from fractions import Fraction as Q
from pathlib import Path

import pytest

from scripts import astrodice_discrete_lt as producer
from scripts.verify_astrodice_discrete_lt import radial_membership, square_membership


@pytest.mark.parametrize("value", [Q(0), Q(1), Q(9, 4), Q(2) ** -2148])
def test_exact_square_rounds_to_its_literal_binary64_root(value):
    expected = {
        Q(0): 0.0,
        Q(1): 1.0,
        Q(9, 4): 1.5,
        Q(2) ** -2148: float.fromhex("0x0.0000000000001p-1022"),
    }[value]
    assert producer.nearest_sqrt(value) == expected


def test_nearest_even_ties_on_each_side_of_an_odd_float():
    even = 1.0
    odd = math.nextafter(even, math.inf)
    following = math.nextafter(odd, math.inf)
    assert producer.nearest_sqrt(((Q(even) + Q(odd)) / 2) ** 2) == even
    assert producer.nearest_sqrt(((Q(odd) + Q(following)) / 2) ** 2) == following


def test_midpoint_is_excluded_by_an_odd_rounding_cell():
    odd = math.nextafter(1.0, math.inf)
    midpoint = (Q(1) + Q(odd)) / 2
    for function in (producer.sqrt_in_interval, square_membership):
        assert function(midpoint**2, midpoint, Q(2), True)
        assert not function(midpoint**2, midpoint, Q(2), False)


@pytest.mark.parametrize(
    "numerator,bounds,expected",
    [
        (Q(1), (Q(0), Q(1)), True),
        (Q(-1), (Q(-1), Q(0)), True),
        (Q(1), (Q(-1), Q(0)), False),
        (Q(-1), (Q(0), Q(1)), False),
        (Q(0), (Q(0), Q(0)), True),
        (Q(1), (Q(1), Q(2)), False),
    ],
)
def test_radial_projection_signs_and_square_root_bounds(numerator, bounds, expected):
    assert producer.ratio_in_interval(numerator, Q(2), bounds) == expected
    assert radial_membership(numerator, Q(2), bounds) == expected


def decimal_text(value):
    with localcontext() as context:
        context.prec = 160
        return format(Decimal(value.numerator) / Decimal(value.denominator), "f")


def test_one_round_and_two_round_subtractions_can_disagree(monkeypatch):
    distance = Q(2) ** -54 + Q(2) ** -110
    monkeypatch.setattr(producer, "K", Q(1, 86400))
    monkeypatch.setattr(
        producer,
        "exact_state",
        lambda source, window, t, body: (
            [distance, Q(0), Q(0), Q(0), Q(0), Q(0)] if body == "Venus" else [Q(0)] * 6
        ),
    )
    vector = {
        "printed_state": [decimal_text(distance), *["0.000000000000000"] * 5],
        "range_AU": decimal_text(distance),
        "range_rate_AU_per_day": "0.000000000000000",
        "light_time_days": "0.000000000000000000000000000000001",
    }
    observer = {
        "range_AU": vector["range_AU"],
        "deldot_km_per_second": "0.000000000000000",
    }
    result = producer.candidate(
        Path("."),
        0,
        vector,
        observer,
        0,
        "seconds_from_J2000_binary64",
        1.0,
        math.nextafter(1.0, -math.inf),
    )
    assert result["source_vector_qualified"]
    assert result["rounding_hypotheses"] == {
        "one_round_source_norm": True,
        "two_round_source_norm": False,
    }
    assert result["rounded_light_time_hex"] == float.fromhex("0x1p-54").hex()
    assert not result["physical_or_internal_algorithm_certified"]


def test_incomplete_cartesian_product_is_unknown_and_never_refuted():
    low = Q(2451545)
    high = Q(math.nextafter(float(low), math.inf))
    family = {
        "status": "enclosed",
        "selected_equations_parametric_unique_root_proved": True,
        "reception_JD": list(map(str, (low, high))),
        "emission_JD": list(map(str, (low, high))),
    }
    plan = {
        "numerical_tube_profiles": {"test": {"extra_binary64_ULPs": 0}},
        "lattice_coordinate_models": ["absolute_JD_binary64"],
        "maximum_lattice_points_per_model": 4,
        "maximum_pairs_per_model": 2,
    }
    result = producer.infer(Path("."), {}, {}, {}, "test", family, plan)["models"][
        "absolute_JD_binary64"
    ]
    assert result["enumeration_status"] == "enumeration_limit" and result["pairs"] == 4
    assert result["candidates"] == [] and not any(
        result["conditional_refuted"].values()
    )


def test_unproved_input_family_remains_unknown():
    assert producer.infer(
        Path("."), {}, {}, {}, "test", {"status": "conditioning_unknown"}, {}
    ) == {"status": "input_family_unknown", "models": {}}
