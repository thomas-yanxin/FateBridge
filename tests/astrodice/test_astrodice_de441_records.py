"""Exact source polynomials, epoch boundaries and excerpt integrity guards."""

import struct
from fractions import Fraction as F
from pathlib import Path

import pytest

from scripts.astrodice.astrodice_de441_records import (
    RECORD_BYTES,
    calendar_jd_tdb,
    clenshaw_with_derivative,
    geometric_states,
    header,
    mini_kernel,
)

J2000 = Path(__file__).parents[1] / "data/astrodice/tables/de441-j2000.eph"


@pytest.mark.parametrize("degree", range(15))
def test_differentiated_clenshaw_matches_independent_chebyshev_identities(degree):
    x = F(7, 19)
    t0, t1 = F(1), x
    for _ in range(degree):
        t0, t1 = t1, 2 * x * t1 - t0
    u0, u1 = F(0), F(1)
    for _ in range(degree):
        u0, u1 = u1, 2 * x * u1 - u0
    position, derivative = clenshaw_with_derivative([F(0)] * degree + [F(1)], x)
    assert position == t0
    assert derivative == degree * u0


def test_full_polynomial_is_linear_in_original_coefficients():
    coefficients = [F(3, 7), F(-9, 16), F(5, 2), F(6, 13)]
    x = F(-2, 5)
    expected = coefficients[0] + coefficients[1] * x
    expected += coefficients[2] * (2 * x**2 - 1)
    expected += coefficients[3] * (4 * x**3 - 3 * x)
    derivative = coefficients[1] + coefficients[2] * 4 * x
    derivative += coefficients[3] * (12 * x**2 - 3)
    assert clenshaw_with_derivative(coefficients, x) == (expected, derivative)


def test_tdb_epoch_is_exact_and_is_not_a_civil_timezone():
    assert calendar_jd_tdb("2000-01-01T12:00:00") == 2451545
    assert calendar_jd_tdb("0001-01-01T00:00:00") == F(3442851, 2)
    assert calendar_jd_tdb("2000-01-01T12:00:00.000001") - 2451545 == F(1, 86400000000)
    with pytest.raises(ValueError, match="timezone"):
        calendar_jd_tdb("2000-01-01T12:00:00+00:00")


def test_excerpt_preserves_all_original_constants_and_coefficients():
    raw = J2000.read_bytes()
    h, constants = raw[:RECORD_BYTES], raw[RECORD_BYTES : 2 * RECORD_BYTES]
    records = [
        raw[i : i + RECORD_BYTES]
        for i in range(2 * RECORD_BYTES, len(raw), RECORD_BYTES)
    ]
    result = mini_kernel(h, constants, records)
    assert result[RECORD_BYTES:] == raw[RECORD_BYTES:]
    differences = [i for i, (a, b) in enumerate(zip(h, result)) if a != b]
    assert all(i < 252 or 2652 <= i < 2668 for i in differences)
    with pytest.raises(ValueError, match="Nonconsecutive"):
        mini_kernel(h, constants, [records[0], records[-1]])


def test_exact_evaluation_retains_moon_earth_barycentric_identity():
    raw = J2000.read_bytes()
    meta = header(raw[:RECORD_BYTES])
    records = [
        raw[i : i + RECORD_BYTES]
        for i in range(2 * RECORD_BYTES, len(raw), RECORD_BYTES)
    ]
    record = next(
        r
        for r in records
        if F(struct.unpack_from("<d", r)[0])
        <= 2451545
        < F(struct.unpack_from("<d", r, 8)[0])
    )
    states = geometric_states(meta, record, F(2451545))
    # Differentiation and origin change commute for the fixed source mass ratio.
    assert all(isinstance(v, F) for state in states.values() for v in state)
    assert (
        0.001
        < float(
            sum((m - e) ** 2 for m, e in zip(states["Moon"][:3], states["Earth"][:3]))
        )
        ** 0.5
        < 0.004
    )
    with pytest.raises(ValueError, match="outside"):
        geometric_states(meta, record, F(struct.unpack_from("<d", record, 8)[0]))


@pytest.mark.parametrize("value", [F(-1001, 1000), F(1001, 1000)])
def test_source_polynomial_cannot_be_extrapolated(value):
    with pytest.raises(ValueError):
        clenshaw_with_derivative([1, 2, 3], value)
