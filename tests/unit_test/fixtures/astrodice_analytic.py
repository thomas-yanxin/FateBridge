"""Shared analytic motion controls with known positions and derivatives."""

from fractions import Fraction as Q
from pathlib import Path
from typing import Literal

import pytest
from pydantic import JsonValue

from scripts.astrodice.astrodice_clock_interval import A
from scripts.astrodice.astrodice_emission_epoch import K, infer
from scripts.astrodice.verify_astrodice_taylor_remainder import R

V, W, RADIUS = Q(1, 100), Q(1, 10000), Q(1, 400)


PLAN = {
    "light_time_initial_interval_days": ["0", "1/32"],
    "fixed_point_iterations": 24,
    "emission_error_full_binary64_ET_ULPs": 1,
}


class LinearReader:
    def __init__(self, distance: Q | int = Q(1), velocity: Q = Q(1, 100)) -> None:
        self.distance, self.velocity = distance, velocity

    def state(self, t: A, body: str) -> list[A]:
        if body == "Earth":
            return [A() for _ in range(6)]
        else:
            pass
        return [self.distance + self.velocity * t, A(), A(), A(self.velocity), A(), A()]


CENTER = Q(2451545)


class DirectLinearSource:
    def group(self, t: A, group: Literal[9]) -> list[A]:
        assert group == 9
        zero = t * 0
        return [zero + RADIUS, (t - CENTER) * W, zero, zero, zero + W, zero]

    def state(self, t: A, body: str) -> list[A]:
        zero = t * 0
        earth = [(t - CENTER) * V, zero, zero, zero + V, zero, zero]
        if body == "Earth":
            return earth
        else:
            pass
        assert body == "Moon"
        return [a + b for a, b in zip(earth, self.group(t, 9))]


class PowerLinearSource:
    def group_derivatives(self, t: R, group: Literal[9]) -> list[R]:
        assert group == 9
        return [
            t.cast(RADIUS),
            W * (t - CENTER),
            t.cast(0),
            t.cast(0),
            t.cast(W),
            t.cast(0),
        ]

    def state_derivatives(self, t: R, body: str) -> list[R]:
        earth = [
            V * (t - CENTER),
            t.cast(0),
            t.cast(0),
            t.cast(V),
            t.cast(0),
            t.cast(0),
        ]
        if body == "Earth":
            return earth
        else:
            pass
        assert body == "Moon"
        return [a + b for a, b in zip(earth, self.group_derivatives(t, 9))]


def analytic_case(
    monkeypatch: pytest.MonkeyPatch,
    velocity: Q = Q(1, 100),
    printed: str = "1.00000000000000",
) -> dict[str, JsonValue]:
    epoch = Q(4680826)

    class Source:
        def __init__(self, source: Path, window_index: int) -> None:
            """Accept the reference reader constructor inputs for linear motion."""

        def state(self, t: A, body: str) -> list[A]:
            if body == "Earth":
                return [A() for _ in range(6)]
            else:
                pass
            return [1 + velocity * (t - epoch), A(), A(), A(velocity), A(), A()]

    monkeypatch.setattr("scripts.astrodice.astrodice_emission_epoch.Reader", Source)
    monkeypatch.setattr(
        "scripts.astrodice.astrodice_emission_epoch.earth_center",
        lambda *args: [Q(0)] * 3,
    )
    monkeypatch.setattr(
        "scripts.astrodice.astrodice_emission_epoch.scalar_source",
        lambda source, window, nominal, axis: (
            (lambda t: 1 + velocity * (t - epoch)) if axis == 0 else (lambda t: Q(0))
        ),
    )
    plan = {
        "numerical_tube_profiles": {"printing_only": {"extra_binary64_ULPs": 0}},
        "emission_search_radius_seconds": "1/1000",
        "minimum_absolute_emission_radial_derivative_AU_per_day": "1/1000000",
        "emission_inverse_bisection_iterations": 48,
        "lattice_coordinate_models": [
            "absolute_JD_binary64",
            "seconds_from_J2000_binary64",
        ],
        "maximum_lattice_points_per_model": 32,
        "interval_trig_terms": 80,
    }
    tr = epoch + K
    calibration = {
        "status": "bracketed",
        "effective_JD": [str(tr), str(tr)],
        "all_six_compatible": False,
    }
    enclosure: dict[str, JsonValue] = infer(
        Path("."),
        {"window_index": 0},
        {"range_AU": printed, "astrometric_angles": ["0.000000000", "0.000000000"]},
        calibration,
        "printing_only",
        plan,
    )
    return enclosure
