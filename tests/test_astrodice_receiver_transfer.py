"""Analytic identities for endpoint charts and implicit retarded-time rates."""

import json
from fractions import Fraction as Q
from pathlib import Path

import pytest

from scripts.astrodice_clock_interval import A, I
from scripts.astrodice_emission_transfer import (
    SRS,
    K,
    continuous_emission,
    signed_rates,
)
from scripts.astrodice_receiver_transfer import (
    angle_change,
    atan_small,
    geometry,
    implicit_factor,
    models,
)
from scripts.verify_astrodice_emission_transfer import D
from scripts.verify_astrodice_observer_clock import independent_pi
from scripts.verify_astrodice_receiver_transfer import angle_change as separate_angle

ROOT = (
    Path(__file__).parent.parent
    / "docs/validation/astrodice-receiver-transfer-run-2026-10-28"
)
PLAN = json.loads((ROOT / "design-before-development.json").read_text())
EMISSION = json.loads((ROOT / "emission-design-original.json").read_text())


def exact_small_angle(t):
    value = 2 * sum(
        (Q((-1) ** k, 2 * k + 1) * t ** (2 * k + 1) for k in range(16)), Q()
    )
    tail = 2 * abs(t) ** 33 / 33
    pi = independent_pi()
    return (value - tail) * 648000 / pi[1], (value + tail) * 648000 / pi[0]


@pytest.mark.parametrize("axis", (0, 1))
@pytest.mark.parametrize("sign", (-1, 1))
def test_exact_rational_rotation_and_wrap_have_rigorous_signed_angle(axis, sign):
    t = Q(sign, 10**10)
    before = [1, -t, 0] if axis == 0 else [1, 0, -t]
    after = [1, t, 0] if axis == 0 else [1, 0, t]
    actual = angle_change([A(v) for v in before], [A(v) for v in after], PLAN)
    independent = separate_angle([D(v) for v in before], [D(v) for v in after], PLAN)
    expected = exact_small_angle(t)
    # For negative values division reverses which pi endpoint is extremal.
    expected = min(expected), max(expected)
    lo, hi = actual[axis].bounds()
    assert lo <= expected[0] <= expected[1] <= hi
    assert lo <= independent[axis][0] <= independent[axis][1] <= hi
    assert actual[1 - axis].contains(0)


def test_identity_endpoints_contain_zero_and_never_a_full_turn():
    values = [A(Q(3, 5)), A(Q(4, 5)), A(Q(1, 7))]
    shifted = angle_change(values, values, PLAN)
    assert all(v.contains(0) and v.absolute_upper() < Q(1, 10**50) for v in shifted)


@pytest.mark.parametrize("argument", (Q(1, 10**6), Q(-1, 10**6)))
def test_fixed_atan_domain_is_not_silently_expanded(argument):
    with pytest.raises(ValueError, match="domain"):
        atan_small(I(argument), PLAN)


@pytest.mark.parametrize("after", ((-1, 0, 0), (0, 0, 1)))
def test_ambiguous_lift_and_coordinate_pole_are_refused(after):
    with pytest.raises(ValueError):
        angle_change([A(1), A(), A()], [A(v) for v in after], PLAN)


class LinearReader:
    def __init__(self, earth_speed, venus_speed):
        self.ve, self.vv = earth_speed, venus_speed

    def state(self, epoch, body):
        offset, speed = (Q(1), self.ve) if body == "Earth" else (Q(2), self.vv)
        return [offset + speed * epoch, A(), A(), A(speed), A(), A()]


@pytest.mark.parametrize("earth_speed", (Q(1, 1000), Q(-1, 1000), Q(0)))
def test_linear_light_path_has_known_root_and_implicit_derivative(earth_speed):
    venus_speed = Q(2, 1000)
    reader = LinearReader(earth_speed, venus_speed)
    expected_root = -K / (1 + K * venus_speed)
    emitted, proof = continuous_emission(reader, Q(0), expected_root, EMISSION)
    assert emitted.contains(expected_root) and len(proof["history"]) == 24
    result, denominator = implicit_factor(reader, I(0), emitted, PLAN)
    assert result.contains((1 + K * earth_speed) / (1 + K * venus_speed))
    assert denominator.contains(1 + K * venus_speed)


def test_observer_acceleration_is_propagated_through_all_aberration_models():
    acceleration = Q(1, 10**6)

    class AcceleratedReader:
        def state(self, epoch, body):
            if body == "Earth":
                return [
                    A(1),
                    acceleration * epoch * epoch / 2,
                    A(),
                    A(),
                    acceleration * epoch,
                    A(),
                ]
            if body == "Venus":
                return [A(2), A(), A(), A(), A(), A()]
            return [A(), A(), A(), A(), A(), A()]

    prepared = geometry(AcceleratedReader(), I(0), I(-K), 1, 1)
    pi = independent_pi()
    for identity, proper, _ in models(prepared, EMISSION):
        potential = identity[2]
        coefficient = acceleration * K * (1 + potential * SRS) * 648000
        expected = coefficient / pi[1], coefficient / pi[0]
        actual = signed_rates(proper)
        low, high = actual[0].bounds()
        assert low <= expected[0] <= expected[1] <= high
        assert actual[1].contains(0)
