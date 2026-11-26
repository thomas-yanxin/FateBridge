"""Observed calculation identity and honest calendar fallback receipts."""

import pytest

from fatebridge.application.domain_validators import detect_fengshui_approximate
from fatebridge.core.fengshui import calendar
from fatebridge.core.fengshui.models import (
    AnnualRequest,
    DirectionsRequest,
    MingguaRequest,
    XuankongRequest,
)
from fatebridge.services.fengshui import (
    calculate_annual_stars as _calculate_annual_stars,
)
from fatebridge.services.fengshui import calculate_directions as _calculate_directions
from fatebridge.services.fengshui import calculate_minggua as _calculate_minggua
from fatebridge.services.fengshui import (
    calculate_xuankong_natal as _calculate_xuankong_natal,
)
from fatebridge.services.run_metadata import attach_run_metadata
from tests.fixtures.fengshui import payload


def calculate_annual_stars(**kwargs):
    return _calculate_annual_stars(AnnualRequest.model_validate(kwargs))


def calculate_directions(**kwargs):
    return _calculate_directions(DirectionsRequest.model_validate(kwargs))


def calculate_minggua(**kwargs):
    return _calculate_minggua(MingguaRequest.model_validate(kwargs))


def calculate_xuankong_natal(**kwargs):
    return _calculate_xuankong_natal(XuankongRequest.model_validate(kwargs))


@pytest.mark.parametrize("kind", ["annual", "birth_date", "period"])
def test_used_calendar_fallback_reaches_outer_receipt_even_away_from_boundary(
    monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
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
        attach_run_metadata(
            result,
            tool_name="fengshui_" + kind,
            approximate_record=detect_fengshui_approximate,
        )["run_metadata"]["engine_is_approximate"]
        is True
    )


def test_no_false_degradation_from_unused_solver_or_statistical_uncertainty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(calendar.almanac, "swe", None)
    # No solar-term lookup is needed for a confirmed effective birth year.
    monkeypatch.setattr(
        calendar, "lichun_resolution", lambda *a: pytest.fail("unused solver called")
    )
    result = calculate_minggua(effective_birth_year=2000, gender_convention="male")
    assert (
        attach_run_metadata(
            result,
            tool_name="fengshui_minggua",
            approximate_record=detect_fengshui_approximate,
        )["run_metadata"]["engine_is_approximate"]
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
        attach_run_metadata(
            result,
            tool_name="fengshui_directions",
            approximate_record=detect_fengshui_approximate,
        )["run_metadata"]["engine_is_approximate"]
        is False
    )
    unrelated = {"approximate": True, "evidence": {"provider": "linear_fallback"}}
    assert (
        attach_run_metadata(
            unrelated,
            tool_name="fengshui_assess",
            approximate_record=detect_fengshui_approximate,
        )["run_metadata"]["engine_is_approximate"]
        is False
    )
