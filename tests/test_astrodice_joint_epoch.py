"""Analytic root enclosures, theorem scope and frozen-support edge cases."""

from decimal import Decimal, localcontext
from fractions import Fraction as Q
from pathlib import Path

import pytest

from scripts.astrodice_clock_interval import A, I
from scripts.astrodice_joint_epoch import K, infer_joint, krawczyk_step
from scripts.verify_astrodice_joint_epoch import predicate_layers


def text(q):
    q = Q(q)
    with localcontext() as c:
        c.prec = 100
        return format(Decimal(q.numerator) / Decimal(q.denominator), ".40f")


def test_exact_affine_contractor_proves_an_interior_root():
    step = krawczyk_step(
        [I(-1, 1), I(-1, 1)],
        [[-1, 0], [0, 1]],
        [[I(-1), I()], [I(), I(1)]],
        [I(Q(1, 4)), I(-Q(3, 8))],
    )
    assert step["strict_image_interior"] and not step["empty_intersection"]
    assert Q(step["contraction_upper"]) == 0
    assert [[Q(x) for x in v] for v in step["next_seconds"]] == [
        [Q(1, 4)] * 2,
        [Q(3, 8)] * 2,
    ]


def test_affine_root_outside_search_is_not_a_global_nonexistence_claim():
    step = krawczyk_step(
        [I(-1, 1), I(-1, 1)],
        [[-1, 0], [0, 1]],
        [[I(-1), I()], [I(), I(1)]],
        [I(2), I(-Q(3, 8))],
    )
    assert step["empty_intersection"] and step["next_seconds"] is None
    assert not step["strict_image_interior"]


def test_singular_map_is_not_promoted_by_a_small_residual():
    step = krawczyk_step(
        [I(-1, 1), I(-1, 1)], [[0, 0], [0, 0]], [[I(), I()], [I(), I()]], [I(), I()]
    )
    assert Q(step["contraction_upper"]) == 1
    assert not step["strict_image_interior"]


def analytic(
    monkeypatch, epsilon=Q(0), reception_root=Q(1, 4), wrong_third=False, parallel=False
):
    centers = [Q(2451545), Q(2451545) - K]

    class Model:
        def __init__(self, *args):
            pass

        def state(self, t, body):
            u = (t - centers[0 if body == "Earth" else 1]) * 86400
            if body == "Earth" or parallel:
                return [
                    u / 86400,
                    A(),
                    A() if body == "Earth" else A(1),
                    A(1),
                    A(),
                    A(),
                ]
            return [
                A(),
                (u + epsilon * u * u) / 86400,
                A(1),
                A(),
                1 + 2 * epsilon * u,
                A(),
            ]

    def point(source, window, t, body):
        u = (t - centers[0 if body == "Earth" else 1]) * 86400
        if body == "Earth" or parallel:
            return [
                u / 86400,
                Q(0),
                Q(0) if body == "Earth" else Q(1),
                Q(1),
                Q(0),
                Q(0),
            ]
        return [
            Q(0),
            (u + epsilon * u * u) / 86400,
            Q(1),
            Q(0),
            1 + 2 * epsilon * u,
            Q(0),
        ]

    monkeypatch.setattr("scripts.astrodice_joint_epoch.Reader", Model)
    monkeypatch.setattr("scripts.astrodice_joint_epoch.exact_state", point)
    emission_root = Q(3, 8)
    vector = {
        "printed_state": [
            text(-reception_root / 86400),
            text((emission_root + epsilon * emission_root**2) / 86400),
            "1.100000000000000" if wrong_third else "1.000000000000000",
            "0.000000000000000",
            "0.000000000000000",
            "0.000000000000000",
        ],
        "range_AU": "1.000000000000000",
        "light_time_days": text(K),
        "range_rate_AU_per_day": "0.000000000000000",
    }
    observer = {
        "range_AU": "1.000000000000000",
        "deldot_km_per_second": "0.000000000000000",
    }
    plan = {
        "numerical_tube_profiles": {"printing_only": {"extra_binary64_ULPs": 0}},
        "reception_search_radius_seconds": "1",
        "emission_search_radius_seconds": "1",
        "joint_contractor_iterations": 8,
        "lattice_coordinate_models": [
            "absolute_JD_binary64",
            "seconds_from_J2000_binary64",
        ],
        "maximum_lattice_points_per_model": 4096,
    }
    return infer_joint(
        Path("."),
        {"nominal_JD": "2451545", "window_index": 0},
        vector,
        observer,
        "printing_only",
        plan,
    )


@pytest.mark.parametrize("epsilon", [Q(0), Q(1, 10)])
def test_known_linear_and_nonlinear_roots_are_inside_proved_source_enclosures(
    monkeypatch, epsilon
):
    result = analytic(monkeypatch, epsilon)
    assert (
        result["status"] == "enclosed"
        and result["selected_equations_parametric_unique_root_proved"]
    )
    for pair, root in zip(result["final_offsets_seconds"], [Q(1, 4), Q(3, 8)]):
        lo, hi = map(Q, pair)
        assert lo <= root <= hi
    assert result["all_three_position_components_not_refuted"]
    assert result["position_source_model_not_refuted"]
    assert result["full_three_component_root_certified"] is False
    assert result["physical_time_model_certified"] is False
    assert result["continuous_Newtonian_LT_vector_model_not_refuted"] is False


def test_selected_two_equations_cannot_hide_an_unused_component_failure(monkeypatch):
    result = analytic(monkeypatch, wrong_third=True)
    assert result["selected_equations_parametric_unique_root_proved"]
    assert result["source_position_components_compatible"] == [True, True, False]
    assert not result["position_source_model_not_refuted"]
    assert all(
        not m["joint_position_and_velocity_not_refuted"]
        for m in result["velocity_models"].values()
    )


def test_parallel_source_velocities_remain_conditioning_unknown(monkeypatch):
    result = analytic(monkeypatch, parallel=True)
    assert result["status"] == "conditioning_unknown" and result["history"] == []
    assert not result["selected_equations_parametric_unique_root_proved"]


def test_boundary_root_is_not_given_a_strict_interior_certificate(monkeypatch):
    result = analytic(monkeypatch, reception_root=Q(1))
    assert result["status"] == "enclosed"
    assert not result["selected_equations_parametric_unique_root_proved"]


def test_outside_root_keeps_frozen_support_and_failure(monkeypatch):
    result = analytic(monkeypatch, reception_root=Q(2))
    assert result["status"] == "no_source_root_in_frozen_support"
    assert result["history"][-1]["empty_intersection"]
    assert not result["selected_equations_parametric_unique_root_proved"]


def test_nested_enclosures_may_add_a_refutation_without_changing_old_predicate():
    witness = []
    assert (
        predicate_layers(
            "velocity.y",
            True,
            ["-1", "1"],
            (Q(1, 2), Q(1)),
            (Q(-1, 10), Q(1, 10)),
            witness,
        )
        is False
    )
    assert witness == [
        {
            "field": "velocity.y",
            "reported_not_refuted": True,
            "independently_refuted": True,
        }
    ]


def test_refinement_cannot_turn_an_original_refutation_into_agreement():
    witness = []
    assert (
        predicate_layers(
            "x",
            False,
            ["-1", "-1/2"],
            (Q(-9, 10), Q(-6, 10)),
            (Q(0), Q(1, 10)),
            witness,
        )
        is False
    )
    assert not witness


def test_misreported_original_interval_predicate_is_rejected():
    with pytest.raises(ValueError, match="predicate changed"):
        predicate_layers(
            "x", True, ["-1", "-1/2"], (Q(-9, 10), Q(-6, 10)), (Q(0), Q(1, 10)), []
        )


def test_independent_refinement_must_be_inside_the_original_source_enclosure():
    with pytest.raises(ValueError, match="not covered"):
        predicate_layers("x", True, ["-1", "1"], (Q(2), Q(3)), (Q(0), Q(1, 10)), [])
