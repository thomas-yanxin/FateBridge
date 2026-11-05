"""Optional model boundaries and unchanged independent physical references."""

import math

import pytest

from fatebridge.core import human_design_point_mass as model
from fatebridge.core.requests.human_design import HumanDesignRequest
from fatebridge.utils.errors import EphemerisSourceError


def test_point_mass_dependency_absence_is_explicit_without_native_fallback(monkeypatch):
    monkeypatch.setattr(model, "find_spec", lambda _: None)
    result = model.point_mass_positions(2451545.0)
    assert result == {
        "method_id": model.METHOD_ID,
        "status": "unavailable",
        "reason": "install_jpl_extra",
    }


def test_model_comparison_is_an_explicit_opt_in():
    request = HumanDesignRequest(
        birth_year=2000,
        birth_month=1,
        birth_day=1,
        birth_hour=12,
        birth_minute=0,
        birth_timezone="UTC",
    )
    assert request.compare_apparent_models is False
    assert request.model_copy(
        update={"compare_apparent_models": True}
    ).compare_apparent_models


def test_point_mass_rejects_non_barycentric_fallback(monkeypatch):
    monkeypatch.setattr(model.runtime, "ephemeris_call", lambda *args: ((0.0,) * 6, 4))
    with pytest.raises(EphemerisSourceError) as failure:
        model.point_mass_positions(2451545.0)
    assert failure.value.reason == "point_mass_requires_barycentric_file_states"


def test_candidate_root_uses_its_own_sun_across_zero_degrees(monkeypatch):
    calls = []
    birth = 2451545.25

    def positions(tt, *, bodies=model.PHYSICAL_BODIES):
        calls.append(bodies)
        return {
            "status": "computed",
            "software": {"test": "uniform_solar_motion"},
            "input_state_return_flags": [155506],
            "positions": [
                {"longitude": (tt - birth) % 360, "input_state_return_flags": [155506]}
            ],
        }

    monkeypatch.setattr(model, "point_mass_positions", positions)
    result = model.solve_point_mass_design_root(birth)
    assert result["design_jd_tt"] == birth - 88
    assert result["residual_degrees"] == 0
    assert set(calls) == {("Sun",)}
    assert result["default_native_root_replaced"] is False
    assert result["physical_time_error_bound_seconds"] is None


def test_candidate_root_keeps_optional_dependency_unavailable(monkeypatch):
    monkeypatch.setattr(model, "find_spec", lambda _: None)
    result = model.solve_point_mass_design_root(2451545.0)
    assert result["status"] == "unavailable"
    assert "design_jd_tt" not in result


@pytest.mark.local_data
def test_preexisting_independent_solar_neighbour_reference_is_not_replaced():
    # Frozen original TT/reference, not copied from the new producer.
    result = model.point_mass_positions(2537715.3390767695)
    assert result["status"] == "computed"
    assert result["native_output_replaced"] is False
    uranus = next(row for row in result["positions"] if row["body"] == "Uranus")
    error = abs(math.remainder(uranus["longitude"] - 252.96267204243404, 360)) * 3600
    assert error <= 2.0  # Original sealed tolerance; no special solar exclusion.
    assert result["physical_error_bound_arcseconds"] is None
    assert all(flags & 7 == 2 for flags in uranus["input_state_return_flags"])
