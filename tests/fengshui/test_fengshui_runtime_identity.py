"""Observed calculation identity and honest calendar fallback receipts."""

import pytest

from fatebridge.core.fengshui import calendar
from fatebridge.services import replay_metadata
from fatebridge.services.fengshui import (
    calculate_annual_stars,
    calculate_directions,
    calculate_minggua,
    calculate_xuankong_natal,
)
from fatebridge.services.run_metadata import attach_run_metadata
from tests.fixtures.fengshui import payload


def test_runtime_receipt_includes_observed_field_arithmetic_version(monkeypatch):
    original = replay_metadata.version
    replay_metadata.environment_receipt.cache_clear()
    try:
        before = replay_metadata.environment_receipt()
        assert before["dependencies"]["mpmath"] == original("mpmath")
        monkeypatch.setattr(
            replay_metadata,
            "version",
            lambda name: "9.9.9" if name == "mpmath" else original(name),
        )
        replay_metadata.environment_receipt.cache_clear()
        after = replay_metadata.environment_receipt()
        assert after["dependencies"]["mpmath"] == "9.9.9"
        assert after != before
    finally:
        replay_metadata.environment_receipt.cache_clear()


@pytest.mark.parametrize("kind", ["annual", "birth_date", "period"])
def test_used_calendar_fallback_reaches_outer_receipt_even_away_from_boundary(
    monkeypatch, kind
):
    original = calendar.lichun_resolution
    fallback = lambda *a: {
        **original(*a),
        "provider": "linear_fallback",
        "approximate": True,
    }
    monkeypatch.setattr(calendar, "lichun_resolution", fallback)
    # bazhai and xuankong bind this helper explicitly as well.
    from fatebridge.core.fengshui import bazhai, xuankong

    monkeypatch.setattr(bazhai, "lichun_resolution", fallback)
    monkeypatch.setattr(xuankong, "lichun_resolution", fallback)
    if kind == "annual":
        result = calculate_annual_stars(effective_year=2026)
    elif kind == "birth_date":
        result = calculate_minggua(birth_date="2000-07-01", gender_convention="male")
    else:
        request = payload("xuankong_natal")
        request["period"] = {
            "basis": "construction_completion",
            "effective_event_year": 2004,
            "evidence": "fixture only",
        }
        result = calculate_xuankong_natal(**request)
    assert result["status"] == "complete"
    assert (
        attach_run_metadata(result, tool_name="fengshui_" + kind)["run_metadata"][
            "engine_is_approximate"
        ]
        is True
    )


def test_no_false_degradation_from_unused_solver_or_statistical_uncertainty(
    monkeypatch,
):
    monkeypatch.setattr(calendar.almanac, "swe", None)
    # No solar-term lookup is needed for a confirmed effective birth year.
    monkeypatch.setattr(
        calendar, "lichun_resolution", lambda *a: pytest.fail("unused solver called")
    )
    result = calculate_minggua(effective_birth_year=2000, gender_convention="male")
    assert (
        attach_run_metadata(result, tool_name="fengshui_minggua")["run_metadata"][
            "engine_is_approximate"
        ]
        is False
    )
    result = calculate_directions(
        geomagnetic_reference={
            "latitude": 80,
            "longitude": 0,
            "height_km_wgs84": 0,
            "decimal_year": 2025.0,
            "evidence": "Engineering numeric input; no actual site",
        }
    )
    assert (
        attach_run_metadata(result, tool_name="fengshui_directions")["run_metadata"][
            "engine_is_approximate"
        ]
        is False
    )
    unrelated = {"approximate": True, "evidence": {"provider": "linear_fallback"}}
    assert (
        attach_run_metadata(unrelated, tool_name="fengshui_assess")["run_metadata"][
            "engine_is_approximate"
        ]
        is False
    )
