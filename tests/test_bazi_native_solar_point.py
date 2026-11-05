"""Actual native-selected roots, error closure and truthful source metadata."""

import json
from datetime import datetime, timezone

import pytest

from fatebridge.core import almanac, solar_term_clock
from fatebridge.utils.errors import EphemerisSourceError


@pytest.mark.parametrize(
    "error,reason",
    [
        (ValueError("private-label-and-path"), "solar_root_civil_unrepresentable"),
        (OverflowError("private-overflow"), "solar_root_civil_unrepresentable"),
        (ImportError("private-dependency-path"), "solar_root_clock_unavailable"),
        (RuntimeError("private-clock-failure"), "solar_root_clock_unavailable"),
    ],
)
def test_known_root_clock_failure_is_bounded_and_cannot_return_none(
    error, reason, monkeypatch
):
    def fail(*args):
        raise error

    monkeypatch.setattr(solar_term_clock, "datetime_from_tt_point", fail)
    with pytest.raises(solar_term_clock.SolarTermClockError) as caught:
        solar_term_clock.native_solar_root_datetime(2451545.0)
    result = caught.value.as_result()
    assert result["issues"] == [{"path": "runtime.solar_term_clock", "code": reason}]
    assert "private" not in json.dumps(result)
    assert result["retryable"] is False


def test_original_strict_source_error_is_preserved_not_wrapped(monkeypatch):
    error = EphemerisSourceError("solar_spk_changed")

    def fail(*args):
        raise error

    monkeypatch.setattr(solar_term_clock, "datetime_from_tt_point", fail)
    with pytest.raises(EphemerisSourceError) as caught:
        solar_term_clock.native_solar_root_datetime(2451545.0)
    assert caught.value is error


def test_no_native_engine_and_no_crossing_keep_their_original_unverified_fallback(
    monkeypatch,
):
    anchor = datetime(2000, 1, 1, tzinfo=timezone.utc)
    with monkeypatch.context() as context:
        context.setattr(almanac, "swe", None)
        assert almanac._solar_term_utc_via_swe(2000, 0, anchor) is None
    original = almanac.ephemeris_call

    def no_crossing(method, *args, **kwargs):
        if method == "calc":
            return ((120.0, 0, 1, 0, 0, 0), almanac.swe.FLG_MOSEPH)
        return original(method, *args, **kwargs)

    monkeypatch.setattr(almanac, "ephemeris_call", no_crossing)
    assert almanac._solar_term_utc_via_swe(2000, 0, anchor) is None


@pytest.mark.parametrize(
    "error", [ValueError("private-time"), ImportError("private-package")]
)
def test_known_native_root_clock_failure_never_becomes_a_linear_year(
    error, monkeypatch, tmp_path
):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)

    def fail(*args):
        raise error

    monkeypatch.setattr(solar_term_clock, "datetime_from_tt_point", fail)
    with pytest.raises(solar_term_clock.SolarTermClockError):
        almanac._calculate_solar_terms_for_year(2000, "UTC")
