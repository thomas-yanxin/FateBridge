"""Exact analytic higher-derivative identities; no celestial reference data."""

import json
import math
import struct
from fractions import Fraction as Q
from pathlib import Path

import pytest

from scripts.astrodice_clock_interval import I
from scripts.astrodice_taylor_remainder import (
    J,
    K,
    TaylorSource,
    angular_rates,
    emission_jet,
    interval_record,
    jet_record,
    segment_clearance,
    uniform_root,
)
from scripts.verify_astrodice_observer_clock import independent_pi
from scripts.verify_astrodice_taylor_remainder import (
    DerivativeSource,
    R,
    coefficient,
    finite_segment_clearance,
    rate_derivatives,
    verify_implicit,
)

PLAN = json.loads(
    (
        Path(__file__).parent.parent
        / "docs/validation/astrodice-derivative-remainder-run-2026-10-28/design-before-development.json"
    ).read_text()
)


def encloses(box, expected):
    low, high = box.bounds() if isinstance(box, I) else box
    assert low <= expected <= high


def test_quotient_and_square_root_derivatives_have_the_correct_factorials():
    t, raw = J([0, 1] + [0] * 7), R([0, 1] + [0] * 7)
    for value, separate in (
        (1 / (1 - t), 1 / (1 - raw)),
        (((1 + t) * (1 + t)).sqrt(), ((1 + raw) * (1 + raw)).sqrt()),
    ):
        for k in range(9):
            encloses(value.c[k], coefficient(separate, k)[0])
            encloses(value.c[k], coefficient(separate, k)[1])
    quotient, exact_root = 1 / (1 - t), ((1 + t) * (1 + t)).sqrt()
    for k in range(9):
        encloses(quotient.c[k], Q(1))
        encloses(exact_root.c[k], Q(k in (0, 1)))


def test_rational_circle_has_known_all_order_angular_rates():
    t, raw = J([0, 1] + [0] * 7), R([0, 1] + [0] * 7)
    actual = angular_rates([1 - t * t, 2 * t, t.cast(0)], PLAN)
    separate = rate_derivatives([1 - raw * raw, 2 * raw, raw.cast(0)], PLAN)
    pi = independent_pi()
    for k in range(8):
        expected = Q(2 * (-1) ** (k // 2)) if k % 2 == 0 else Q()
        pair = [expected * 648000 / p for p in pi]
        for x in pair:
            encloses(actual[0].c[k], x)
        encloses(actual[1].c[k], Q())
        encloses(actual[0].c[k], coefficient(separate[0], k)[0])
        encloses(actual[0].c[k], coefficient(separate[0], k)[1])


class QuadraticLightPath:
    def state(self, epoch, body):
        zero = epoch.cast(0)
        if body == "Earth":
            return [zero] * 6
        b = Q(1, 1000) / K
        return [1 + b * epoch * epoch, zero, zero, 2 * b * epoch, zero, zero]

    state_derivatives = state


def test_nonlinear_implicit_light_time_has_exact_catalan_coefficients():
    # te + (1/1000)*te^2 = tr-K has a known quadratic inverse.
    source = QuadraticLightPath()
    reception = J([K, 1] + [0] * 7)
    actual, history = emission_jet(source, reception, I(0), PLAN)
    for k in range(1, 9):
        catalan = Q(math.comb(2 * (k - 1), k - 1), k)
        expected = (-1) ** (k - 1) * catalan * Q(1, 1000) ** (k - 1)
        encloses(actual.c[k], expected)
    data = {
        "emission_normalized_coefficients": jet_record(actual),
        "implicit_recurrences": history,
    }
    separate = verify_implicit(source, R([K, 1] + [0] * 7), (Q(), Q()), data, PLAN)
    for k in range(9):
        for bound in coefficient(separate, k):
            encloses(actual.c[k], bound)


@pytest.mark.parametrize("degree", (5, 7))
@pytest.mark.parametrize("sign", (-1, 1))
def test_whole_interval_taylor_bounds_cover_exact_position_and_derivative_errors(
    degree, sign
):
    h = Q(1, 8)
    t = J([I(-h, h), 1] + [0] * 7)
    f = 1 / (1 - t)
    bound = f.derivative().c[degree].absolute_upper()
    x = sign * h
    position_error = abs(1 / (1 - x) - sum((x**k for k in range(degree + 1)), Q()))
    derivative_error = abs(
        1 / (1 - x) ** 2 - sum((k * x ** (k - 1) for k in range(1, degree + 1)), Q())
    )
    assert position_error <= bound * h ** (degree + 1) / (degree + 1)
    assert derivative_error <= bound * h**degree


def test_uniform_root_existence_covers_a_continuum_of_receivers():
    source = QuadraticLightPath()
    h = Q(1, 1000)
    root, proof = uniform_root(source, I(K - h, K + h), PLAN)
    assert root.contains(0)
    assert len(proof["iterations"]) == 24
    # Three algebraically exact emitted values and their exact reception images.
    for emitted in (-h / 2, Q(), h / 2):
        received = K + emitted + Q(1, 1000) * emitted**2
        assert K - h <= received <= K + h
        encloses(root, emitted)


@pytest.mark.parametrize(
    "earth,ray,expected,branch",
    [
        ((1, 0, 0), (1, 0, 0), Q(1), "observer_endpoint"),
        ((1, 0, 0), (Q(-1, 4), 0, 0), Q(3, 4), "source_endpoint"),
        ((1, Q(1, 2), 0), (-2, 0, 0), Q(1, 2), "interior"),
    ],
)
def test_finite_photon_segment_uses_the_correct_closest_point(
    earth, ray, expected, branch
):
    actual, chosen = segment_clearance([J([v]) for v in earth], [J([v]) for v in ray])
    independent, separate_branch = finite_segment_clearance(
        [R([v]) for v in earth], [R([v]) for v in ray]
    )
    assert chosen == separate_branch == branch
    encloses(actual, expected)
    encloses(independent, expected)


@pytest.mark.parametrize(
    "kind", ("zero_root", "zero_denominator", "pole", "mixed_order")
)
def test_invalid_analytic_domains_are_rejected(kind):
    with pytest.raises(ValueError):
        if kind == "zero_root":
            J([0, 1]).sqrt()
        elif kind == "zero_denominator":
            1 / J([I(-1, 1), 1])
        elif kind == "mixed_order":
            J([0, 1]) + J([0, 1, 0])
        else:
            z = J([1, 0, 0])
            angular_rates([z.cast(0), z.cast(0), z], PLAN)


def synthetic_source(directory):
    header = bytearray(8144)
    struct.pack_into("<i", header, 2840, 441)
    struct.pack_into("<2d", header, 2680, 1, 80)
    struct.pack_into("<3i", header, 2696 + 12, 3, 10, 1)
    (directory / "header.bin").write_bytes(header)
    folder = directory / "record-responses"
    folder.mkdir()
    records = []
    for start in (0, 32, 64):
        values = [0.0] * 1018
        values[:2] = [start, start + 32]
        values[2 + 8] = 1  # x = T8(u)
        values[2 + 10 + 3] = 2  # y = 2*T3(u)
        values[2 + 20] = 5  # z = 5
        records.append(struct.pack("<1018d", *values))
    (folder / "case-09.bin").write_bytes(b"".join(records))


def test_independent_source_high_derivatives_match_exact_chebyshev_polynomials(
    tmp_path,
):
    synthetic_source(tmp_path)
    source = TaylorSource(tmp_path, 9)
    separate = DerivativeSource(tmp_path, 9)
    actual = source.group(J([16, 1] + [0] * 7), 1)
    independent = separate.group_derivatives(R([16, 1] + [0] * 7), 1)
    # T8(x)=128x^8-256x^6+160x^4-32x^2+1; 2T3(x)=8x^3-6x.
    polys = [{0: 1, 2: -32, 4: 160, 6: -256, 8: 128}, {1: -6, 3: 8}, {0: 5}]
    for axis, polynomial in enumerate(polys):
        for k in range(9):
            expected = Q(polynomial.get(k, 0), 16**k)
            velocity = Q((k + 1) * polynomial.get(k + 1, 0), 16 ** (k + 1))
            encloses(actual[axis].c[k], expected)
            encloses(actual[axis + 3].c[k], velocity)
            encloses(coefficient(independent[axis], k), expected)
            encloses(coefficient(independent[axis + 3], k), velocity)
            assert interval_record(actual[axis].c[k]) == list(
                map(str, coefficient(independent[axis], k))
            )
