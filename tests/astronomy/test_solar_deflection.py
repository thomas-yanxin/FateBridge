"""Original ERFA inputs/gates, stronger arithmetic and independent motion."""

import hashlib
import json
import math
from pathlib import Path

import pytest

from fatebridge.core.astro import solar_deflection
from fatebridge.core.astro.cartesian import CartesianState
from fatebridge.core.astro.solar_deflection import finite_source_solar_deflection

FIXTURES = Path(__file__).parents[1] / "fixtures"
SOLAR = json.loads((FIXTURES / "solar-deflection-erfa-reference-v1.json").read_text())
PRECISE = json.loads(
    (FIXTURES / "solar-deflection-high-precision-reference-v1.json").read_text()
)
MOTION = json.loads(
    (FIXTURES / "solar-deflection-derivative-reference-v1.json").read_text()
)
assert (
    PRECISE["original_reference_sha256"]
    == hashlib.sha256(
        (FIXTURES / "solar-deflection-erfa-reference-v1.json").read_bytes()
    ).hexdigest()
)
assert len(SOLAR["rows"]) == len(PRECISE["rows"]) == 168


def test_solar_formula_keeps_all_ERFA_inputs_and_gates_with_stronger_oracle() -> None:
    # Eight original binary ERFA results miss this exact-parameter oracle at
    # their original 1e-13 line. Preserve them; require the stable formula to
    # satisfy the same line for every original input, without fitting ERFA's
    # cancellation error or claiming its binary rounding is reproduced.
    for index in range(len(SOLAR["rows"])):
        row, reference = SOLAR["rows"][index], PRECISE["rows"][index]
        assert reference["original_row_index"] == index
        assert reference["absolute_component_gate"] == row["absolute_component_gate"]
        actual = finite_source_solar_deflection(
            CartesianState(tuple(row["ray"]), (0.0, 0.0, 0.0)),
            CartesianState(tuple(row["observer"]), (0.0, 0.0, 0.0)),
            CartesianState(tuple(row["sun_at_reception"]), (0.0, 0.0, 0.0)),
            CartesianState(tuple(row["target_at_emission"]), (0.0, 0.0, 0.0)),
            CartesianState(tuple(row["sun_at_emission"]), (0.0, 0.0, 0.0)),
        )
        distance = math.hypot(*row["ray"])
        assert [value / distance for value in actual.position] == pytest.approx(
            list(map(float, reference["high_precision_normalized"])),
            rel=0,
            abs=row["absolute_component_gate"],
        ), index


def test_solar_motion_matches_independent_complex_step_in_every_mass_cell() -> None:
    for row in MOTION["rows"]:
        actual = finite_source_solar_deflection(
            *(
                CartesianState(
                    tuple(row["states"][name]["position"]),
                    tuple(row["states"][name]["velocity"]),
                )
                for name in (
                    "ray",
                    "observer",
                    "sun_at_reception",
                    "target_at_emission",
                    "sun_at_emission",
                )
            )
        )
        assert actual.velocity is not None
        assert actual.velocity == pytest.approx(
            list(map(float, row["velocity_AU_per_TT_day"])),
            rel=0,
            abs=MOTION["gate_AU_per_TT_day"],
        ), row


def test_every_nonflat_mass_knot_has_no_invented_unique_slope() -> None:
    for row in solar_deflection._parameters()[
        "mass_profile_radius_fraction_and_effective_mass"
    ]:
        _, slope = solar_deflection.effective_solar_mass(row[0])
        assert slope is None, row[0]


@pytest.mark.parametrize("fraction", [0.5, 1.0])
@pytest.mark.parametrize("crossing", [True, False])
def test_mass_corner_crossing_keeps_position_and_tangent_motion_is_differentiable(
    fraction: float, crossing: bool
) -> None:
    radius = (
        math.radians(
            solar_deflection._parameters()["solar_radius_at_one_au_arcsec"] / 3600
        )
        * fraction
    )
    velocity = (0.001, 0.0, 0.0) if crossing else (0.0, 0.001, 0.0)
    zero = CartesianState((0.0, 0.0, 0.0), (0.0, 0.0, 0.0))
    actual = finite_source_solar_deflection(
        CartesianState((0.0, 1.0, 0.0), (0.0, 0.0, 0.0)),
        CartesianState((radius, 0.0, 0.0), velocity),
        zero,
        CartesianState((radius, 1.0, 0.0), velocity),
        zero,
    )
    assert all(math.isfinite(v) for v in actual.position)
    assert (actual.velocity is None) == crossing


def test_limiter_corner_preserves_position_without_an_invented_unique_rate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ray = (-2.0, 1e-5, 0.0)
    target = (-1.0, 1e-5, 0.0)
    length = math.hypot(*target)
    q = tuple(v / length for v in target)
    unit_sum = (q[0] + 1, q[1], q[2])
    # Put this controlled geometry exactly on a positive limiter boundary;
    # the production limiter and pinned source data remain unchanged.
    limiter = math.fsum(v * v for v in unit_sum) / 2
    monkeypatch.setattr(solar_deflection, "DEFLECTION_LIMITER", limiter)
    zero = CartesianState((0.0, 0.0, 0.0), (0.0, 0.0, 0.0))
    actual = finite_source_solar_deflection(
        CartesianState(ray, (0.0, 0.001, 0.0)),
        CartesianState((1.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
        zero,
        CartesianState(target, (0.0, 0.001, 0.0)),
        zero,
    )
    assert actual.velocity is None
    assert all(math.isfinite(v) for v in actual.position)
