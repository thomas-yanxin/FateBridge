"""Source polynomial AD and branch guards before apparent holdout sampling."""

import json
from decimal import Decimal as N
from decimal import localcontext
from fractions import Fraction
from pathlib import Path

import pytest

from scripts.astrodice_apparent_source_reference import (
    D,
    Reader,
    aberration,
    clenshaw,
    enclosed_mass,
    sample,
)
from scripts.gen_astrodice_apparent_source_reference import reference_row

FIXTURE = Path(__file__).parent / "fixtures/astrodice-de441-records-v1"


def test_dual_chain_product_quotient_and_sqrt_match_closed_derivative():
    with localcontext() as context:
        context.prec = 70
        t = D(3, 1)
        result = (t * t + 4).sqrt() / (1 + 2 * t)
        expected = -N(5) / (49 * N(13).sqrt())
        assert abs(result.d - expected) < N("1e-65")
        assert abs(result.v - N(13).sqrt() / 7) < N("1e-65")


def test_source_chebyshev_velocity_remains_differentiable_through_epoch_chain():
    t = D("0.5", 1)
    x = t * t
    p, dp_dx = clenshaw([D(0), D(0), D(0), D(1)], x)
    assert p.v == 4 * x.v**3 - 3 * x.v
    assert p.d == (12 * x.v**2 - 3) * 2 * t.v
    assert dp_dx.v == 12 * x.v**2 - 3
    assert dp_dx.d == 24 * x.v * 2 * t.v


@pytest.mark.parametrize("index", range(7))
def test_dual_source_states_match_the_previously_independent_rational_reference(index):
    row = json.loads((FIXTURE / "geometric-reference.json").read_text())["rows"][index]
    expected = row["states_at_binary64_argument_au_and_au_per_day"]
    body = "Mercury" if index in (0, 1, 3, 5) else "Venus"
    with localcontext() as context:
        context.prec = 100
        actual = Reader(FIXTURE, index).states(
            D(row["native_numeric_argument"], 1), body
        )
        for name, values in actual.items():
            for result, target in zip(values, expected[name]):
                target = Fraction(target)
                exact = N(target.numerator) / N(target.denominator)
                assert abs(result.v - exact) < N("1e-85")
            for position, velocity in zip(values[:3], values[3:]):
                assert abs(position.d - velocity.v) < N("1e-85")


def test_zero_observer_velocity_keeps_aberration_position_and_spatial_derivative():
    ray = [D(1, 2), D(3, -1), D(4, 5)]
    result = aberration(ray, [D(0), D(0), D(0)])
    assert [(v.v, v.d) for v in result] == [(v.v, v.d) for v in ray]


def test_legacy_sample_does_not_certify_light_time_convergence_or_horizons_clock():
    row = json.loads((FIXTURE / "geometric-reference.json").read_text())["rows"][2]
    result = sample(
        Reader(FIXTURE, 2),
        "Venus",
        Fraction(row["epoch_jd_tdb_exact"]),
        [],
        precision=70,
    )
    assert len(result["light_time_history"]) == 2
    assert result["light_time_model"] == "legacy_two_linearized_delays"
    assert result["light_time_convergence_certified"] is False
    assert result["Horizons_emission_epoch_mapping_certified"] is False
    assert result["continuous_unrounded_source_epoch_model"] is True
    assert result["exact_TT_conversion"] is False


@pytest.mark.parametrize("impact", [0, 0.01, 1.0])
def test_profile_knots_are_not_silently_given_a_single_derivative(impact):
    profile = [("1.000", "1.000000"), ("0.010", "0.002767"), ("0.000", "0.000000")]
    with pytest.raises(ValueError):
        enclosed_mass(D(impact, 1), profile)


def test_source_reader_cannot_silently_substitute_venus_for_an_unplanned_body():
    with pytest.raises(ValueError, match="body"):
        Reader(FIXTURE, 0).states(D(2451545, 1), "Mars")


def test_profile_value_at_a_knot_survives_when_its_derivative_is_unqualified():
    profile = [("1.000", "1.000000"), ("0.010", "0.002767"), ("0.000", "0.000000")]
    value, cell = enclosed_mass(D(0.01), profile, allow_knot_value=True)
    assert value.v == N.from_float(0.002767)
    assert value.d == 0 and cell["cell"] == "boundary_value"
    with pytest.raises(ValueError):
        enclosed_mass(D(0.01, 1), profile)


def test_reference_derivative_exception_does_not_erase_qualified_position(monkeypatch):
    def point(*args, seed=1, **kwargs):
        if seed:
            raise ValueError("Known source profile knot")
        return {"direction_icrf": ["1", "0", "0"]}

    monkeypatch.setattr("scripts.gen_astrodice_apparent_source_reference.sample", point)
    result = reference_row(
        {
            "id": "control",
            "window_index": 0,
            "date_tdb": "1106-04-24T15:31:11",
            "body": "Mercury",
        },
        FIXTURE,
        [],
        {
            "reference_precisions": [70, 100],
            "reference_precision_component_line": "1e-45",
        },
    )
    assert result["position_status"] == "qualified_under_declared_source_position_model"
    assert result["status"] == result["rate_status"] == "reference_quality_unresolved"
    assert result["rate_reference_error"]["error_type"] == "ValueError"
    assert len(result["position_centers"]) == 2
