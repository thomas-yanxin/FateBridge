"""Calculated named-source guards must not be explained as another model."""

from datetime import date, datetime, timezone

from fatebridge.core.aa1996_solar import MODEL_ID
from fatebridge.core.fengshui import bazhai, xuankong
from fatebridge.core.fengshui.models import HousePeriod, MingguaRequest


def resolution():
    return {
        "moment": "2024-02-04T00:00:01+00:00",
        "ephemeris_model": MODEL_ID,
        "approximate": False,
        "precision_scope": "controlled_named_source_guard_fixture",
    }


def test_calculated_period_guard_is_not_explained_as_approximate(monkeypatch):
    monkeypatch.setattr(
        xuankong,
        "year_context",
        lambda *a, **k: {
            "effective_year": None,
            "effective_year_status": "requires_confirmation",
            "candidate_effective_years": [2023, 2024],
            "provisional_effective_year": 2024,
            "boundary_resolution": {
                **resolution(),
                "uncertainty_reason": "aa1996_solar_model_guard_not_accuracy_certification",
            },
        },
    )
    monkeypatch.setattr(xuankong, "lichun_resolution", lambda *a: resolution())
    monkeypatch.setattr(
        xuankong, "_period_interval", lambda i, z: {"number": i % 9 + 1}
    )
    result = xuankong.period_context(
        HousePeriod(
            basis="first_occupancy",
            event_at=datetime(2024, 2, 4, tzinfo=timezone.utc),
            timezone_name="UTC",
            evidence="Controlled source-label regression",
        )
    )
    assert result["number"] is None and result["candidate_period_numbers"] == [8, 9]
    assert result["timing"]["event_year_boundary"]["approximate"] is False
    assert (
        result["confirmation_reason"]
        == "aa1996_solar_model_precision_guard_in_period_changeover_year"
    )


def test_date_only_guard_names_source_without_inventing_a_birth_hour(monkeypatch):
    monkeypatch.setattr(bazhai, "lichun_resolution", lambda *a: resolution())
    request = MingguaRequest(
        birth_date=date(2024, 2, 3), timezone_name="UTC", gender_convention="male"
    )
    result = bazhai.minggua(request)
    time = result["time_context"]
    assert request.birth_at is None and time["effective_year"] is None
    assert time["input_basis"] == "civil_date_no_fabricated_birth_hour"
    assert time["boundary_resolution"]["approximate"] is False
    assert time["boundary_precision_policy"]["ephemeris_model"] == MODEL_ID
    assert (
        time["boundary_precision_policy"]["reason"]
        == "aa1996_solar_guard_crosses_civil_date_not_fabricated_birth_hour"
    )
