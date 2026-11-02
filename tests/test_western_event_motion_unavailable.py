"""A failed precision derivative is unknown; physical-source drift stays fatal."""

from types import SimpleNamespace

import pytest

from fatebridge.core import horary_events as events
from fatebridge.core.output_western import PlanetaryEventHistory
from fatebridge.utils.errors import EphemerisSourceError


@pytest.mark.parametrize(
    "reason",
    [
        "position_motion_not_converged",
        "model_changed",
        "physical_configuration_changed",
        "coordinate_contract_changed",
    ],
)
def test_failed_search_preserves_question_states_without_substituting_rates(
    reason, monkeypatch
):
    at = 2451545.0
    calls = []

    def sample(planet, ut1=None, *, julian_day_tt, **kwargs):
        assert ut1 is None, "TT event sampling must not require an Earth-rotation epoch"
        calls.append((planet, julian_day_tt))
        if julian_day_tt != at:
            raise EphemerisSourceError(reason)
        return {"longitude": 42.0, "latitude": 0.0, "longitude_speed": 0.1}, "moshier"

    def search(epoch, sampler):
        sampler("Venus", epoch + 1)
        raise AssertionError("An unknown rate was silently substituted")

    monkeypatch.setattr(events, "_swisseph_planet_state", sample)
    monkeypatch.setattr(events, "solve_planetary_events", search)
    subject = SimpleNamespace(julian_day_tt=at, zodiac_type="Tropic")
    if reason != "position_motion_not_converged":
        with pytest.raises(EphemerisSourceError) as raised:
            events.native_planetary_events(subject)
        assert raised.value.reason == reason
        return
    result = events.native_planetary_events(subject)
    PlanetaryEventHistory.model_validate(result)
    assert result["status"] == "unavailable" and result["events"] == []
    assert result["unavailable_code"] == reason
    assert result["failed_sample"] == {"planet": "Venus", "julian_day_tt": at + 1}
    assert set(result["question_states"]) == set(events.BODIES)
    assert result["constant_velocity_projection"] is False
    assert result["full_original_text_acceptance"] is False
    assert len(calls) == len(events.BODIES) + 1


def test_audit_cannot_pass_unavailable_events_as_an_empty_success(monkeypatch):
    from scripts import audit_western_reference_points as audit

    monkeypatch.setattr(
        audit,
        "native_planetary_events",
        lambda subject: {
            "status": "unavailable",
            "unavailable_code": "position_motion_not_converged",
        },
    )
    monkeypatch.setattr(
        audit,
        "_swisseph_planet_state",
        lambda *args, **kwargs: ({"longitude": 0.0}, "moshier"),
    )
    result = audit.audit()
    assert result["same_point_event_times_compared"] == 0
    assert result["same_point_event_times_expected"] == 212
    assert len(result["unavailable_event_cases"]) == 2
    assert result["complete_event_comparison"] is False
    assert result["same_point_numerical_acceptance"] is False
    assert result["body_center_comparison_passed"] is False
