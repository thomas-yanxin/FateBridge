"""Analytic controls and malformed-source refusal, independent of ephemeris fits."""

import math
import struct
from pathlib import Path

import pytest

from fatebridge.core.astro.jpl_kinematics import (
    chebyshev_kinematics,
    checked_fixed_acceleration,
    source_kinematics,
)
from fatebridge.utils.errors import EphemerisSourceError

FIXTURE = Path(__file__).parent / "data/astrodice/tables/de441-j2000.eph"


@pytest.mark.parametrize("x", [-1.0, -0.5, 0.0, 0.25, 1.0])
def test_known_chebyshev_value_and_both_derivatives(x):
    # 2 + 3*T1 - 5*T2 + 7*T3, derived without the implementation.
    expected = (
        7 - 18 * x - 10 * x * x + 28 * x**3,
        -18 - 20 * x + 84 * x * x,
        -20 + 168 * x,
    )
    assert chebyshev_kinematics([2, 3, -5, 7], x) == expected


@pytest.mark.parametrize("c", [[4.0], [4.0, 3.0]])
def test_constant_and_affine_have_zero_second_derivative(c):
    result = chebyshev_kinematics(c, 0.25)
    assert result[2] == 0
    assert result[1] == (0 if len(c) == 1 else 3)


@pytest.mark.parametrize(
    "c,x", [([], 0), ([math.nan], 0), ([1], math.nan), ([1], 1.01)]
)
def test_invalid_polynomial_is_rejected(c, x):
    with pytest.raises(EphemerisSourceError):
        chebyshev_kinematics(c, x)


@pytest.mark.parametrize("angle", [0.0, 0.7, math.pi / 2])
def test_two_vector_frame_recovers_known_proper_rotation(angle):
    raw = [1.0, 0.2, 0.3, -0.004, 0.02, 0.003, -0.0003, 0.00002, 0.00001]
    c, s = math.cos(angle), math.sin(angle)

    def rotate(v):
        return (c * v[0] - s * v[1], s * v[0] + c * v[1], v[2])

    native = (*rotate(raw[:3]), *rotate(raw[3:6]))
    acceleration, policy = checked_fixed_acceleration(raw, native)
    assert math.dist(acceleration, rotate(raw[6:])) <= 1e-18
    assert policy["frame_derivative_added"] is False


@pytest.mark.parametrize("bad", ["length", "state", "collinear", "nan"])
def test_rotation_does_not_normalize_away_a_changed_source(bad):
    raw = [1, 0, 0, 0, 0.02, 0, -0.0003, 0, 0]
    native = [1, 0, 0, 0, 0.02, 0]
    if bad == "length":
        raw.pop()
    elif bad == "state":
        native[0] += 1e-7
    elif bad == "collinear":
        native[3:] = [0.02, 0, 0]
    else:
        raw[0] = math.nan
    with pytest.raises(EphemerisSourceError):
        checked_fixed_acceleration(raw, native)


@pytest.mark.parametrize("body", ["Mercury", "Venus", "Earth", "Moon", "Sun", "Mars"])
def test_selected_record_and_units_are_explicit(body):
    state, policy = source_kinematics(FIXTURE, 2451545.0, body)
    assert len(state) == 9 and all(math.isfinite(v) for v in state)
    assert policy["record_start"] <= 2451545.0 <= policy["record_end"]
    assert policy["tt_tdb_conversion_applied"] is False
    assert policy["source_time_scale"] == "TDB"
    assert policy["atomic_file_read_proven"] is False
    assert policy["observational_accuracy_certified"] is False


@pytest.mark.parametrize(
    "problem", ["truncated", "nan_record", "wrong_grid", "outside", "unknown_body"]
)
def test_bad_sources_never_degrade_to_numerical_differences(tmp_path, problem):
    path = tmp_path / "source.eph"
    data = bytearray(FIXTURE.read_bytes())
    epoch, body = 2451545.0, "Earth"
    if problem == "truncated":
        data = data[:-1]
    elif problem == "nan_record":
        struct.pack_into("<d", data, 3 * 8144 + 8 * 230, math.nan)
    elif problem == "wrong_grid":
        struct.pack_into("<d", data, 3 * 8144, 2451537.5)
    elif problem == "outside":
        epoch = 2400000
    else:
        body = "made-up"
    path.write_bytes(data)
    with pytest.raises(EphemerisSourceError):
        source_kinematics(path, epoch, body)


@pytest.mark.parametrize("side", [-1, 0, 1])
def test_wide_origin_preserves_one_ulp_before_a_record_boundary(tmp_path, side):
    # Manufactured sparse address-layout test, not an astronomical reference.
    header = bytearray(FIXTURE.read_bytes()[:8144])
    start = -3000000.5
    records = 200000
    record_index = 150000
    boundary = start + record_index * 32
    struct.pack_into("<2d", header, 2652, start, start + records * 32)
    path = tmp_path / "synthetic-wide-origin.eph"
    source = FIXTURE.read_bytes()
    with path.open("wb") as out:
        out.truncate((records + 2) * 8144)
        out.seek(0)
        out.write(header)
        out.write(source[8144:16288])
        for index in [record_index - 1, record_index]:
            raw = bytearray(source[3 * 8144 : 4 * 8144])
            struct.pack_into(
                "<2d", raw, 0, start + index * 32, start + (index + 1) * 32
            )
            out.seek((index + 2) * 8144)
            out.write(raw)
    epoch = boundary if side == 0 else math.nextafter(boundary, math.inf * side)
    _, policy = source_kinematics(path, epoch, "Earth")
    assert policy["record_index"] == record_index - int(side < 0)
