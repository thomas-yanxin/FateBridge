"""A native TT point never hides its historical/future civil clock convention."""

import pytest

from fatebridge.core import almanac, solar_term_clock
from fatebridge.utils.errors import EphemerisSourceError


@pytest.mark.parametrize(
    "year,method,historical,future",
    [
        (1700, "pre_1972_swiss_UT1_delta_t", True, False),
        (1965, "IERS_1961_1971_UTC_drift_to_TT_swiss_delta_t_to_UT1", False, False),
        (1972, "IERS_UTC_to_TT_swiss_delta_t_to_UT1", False, False),
        (2000, "IERS_UTC_to_TT_swiss_delta_t_to_UT1", False, False),
        (2300, "IERS_UTC_to_TT_swiss_delta_t_to_UT1", False, True),
    ],
)
def test_actual_native_calendar_carries_each_clock_policy(
    year, method, historical, future, monkeypatch, tmp_path
):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    terms = almanac.get_solar_terms_for_year(year, "UTC")
    assert len(terms) == 24
    for term in terms:
        details = term.as_dict()["solar_model_details"]
        assert term.ephemeris_model == "moshier"
        assert details["civil_time_policy"] == method
        assert details["historical_ut1_convention"] is historical
        assert details["future_leap_seconds_assumed_unchanged"] is future
        assert details["accuracy_certified"] is False


@pytest.mark.parametrize(
    "error,reason",
    [
        (ValueError("private-policy"), "solar_root_civil_unrepresentable"),
        (ImportError("private-clock"), "solar_root_clock_unavailable"),
    ],
)
def test_policy_failure_on_selected_root_cannot_become_linear(
    error, reason, monkeypatch, tmp_path
):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)

    def fail(*args):
        raise error

    monkeypatch.setattr(solar_term_clock, "ephemeris_time", fail)
    with pytest.raises(solar_term_clock.SolarTermClockError) as caught:
        almanac.get_solar_terms_for_year(2000, "UTC")
    assert caught.value.reason == reason
    assert "private" not in str(caught.value.as_result())


def test_original_policy_source_error_is_preserved(monkeypatch):
    error = EphemerisSourceError("solar_spk_changed")

    def fail(*args):
        raise error

    monkeypatch.setattr(solar_term_clock, "ephemeris_time", fail)
    from datetime import datetime, timezone

    with pytest.raises(EphemerisSourceError) as caught:
        solar_term_clock.native_solar_root_time_policy(
            datetime(2000, 1, 1, tzinfo=timezone.utc)
        )
    assert caught.value is error
