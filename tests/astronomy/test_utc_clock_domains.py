"""Published UTC domains and optional-native clock providers, without ephemeris files."""

import json
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path

import pytest

from fatebridge.core.astro import runtime
from fatebridge.core.astro.historical_utc import (
    HistoricalUTCAdjustment,
    historical_tai_minus_utc,
    historical_tai_minus_utc_exact,
    historical_utc_from_tt,
    historical_utc_from_tt_point,
    historical_utc_to_tt_point,
)
from fatebridge.core.astro.iers_ut1 import active_ut1, c04_table, use_ut1_source
from fatebridge.core.astro.time_scales import (
    datetime_from_tt,
    ephemeris_time,
    tt_from_ut1,
    ut1_from_tt,
    utc_clock,
)
from fatebridge.core.astro.tt_epoch import TTInstant
from fatebridge.core.solar_term_clock import native_solar_root_time_policy
from tests.support.ephemeris_context import empty_ephemeris_path

REFERENCE = json.loads(
    (
        Path(__file__).parents[1] / "fixtures/historical-utc-domain-reference-v1.json"
    ).read_text()
)


@pytest.mark.parametrize(
    "label,method,future",
    [
        ("1960-04-01T12:00:00+00:00", "SOFA_1960_UTC_drift_to_TT", False),
        ("2026-10-01T12:00:00+00:00", "IERS_UTC_to_TT", False),
        ("2300-01-01T12:00:00+00:00", "IERS_UTC_to_TT", True),
    ],
)
def test_atomic_clock_and_solar_policy_do_not_query_unrelated_ut1(
    label, method, future, monkeypatch
):
    moment = datetime.fromisoformat(label)
    expected = utc_clock(moment)
    calls = []

    def no_rotation(*args):
        calls.append(args)
        raise AssertionError("Atomic UTC conversion queried Earth rotation")

    with use_ut1_source("iers_c04"):
        selected = c04_table()
        with monkeypatch.context() as change:
            change.setattr(selected, "ut1_from_tt", no_rotation)
            actual = utc_clock(moment)
            policy = native_solar_root_time_policy(moment)
            assert active_ut1.get() is selected
        assert actual == expected
        assert actual.method == method
        assert actual.future_leap_seconds_assumed_unchanged is future
        assert policy == {
            "civil_time_policy": method,
            "historical_ut1_convention": False,
            "future_leap_seconds_assumed_unchanged": future,
        }
        assert calls == []
        with pytest.raises(ValueError, match="no prediction, extrapolation"):
            ephemeris_time(moment)


def test_full_tt_solar_calendar_does_not_require_ut1_at_unused_yearly_terms(
    monkeypatch,
):
    from fatebridge.core.almanac import get_solar_terms_for_year

    calls = []

    def no_rotation(*args):
        calls.append(args)
        raise AssertionError("TT solar calendar queried Earth rotation")

    with empty_ephemeris_path(), use_ut1_source("iers_c04"):
        selected = c04_table()
        monkeypatch.setattr(selected, "ut1_from_tt", no_rotation)
        terms = get_solar_terms_for_year(2026, "UTC")
        assert len(terms) == 24
        assert active_ut1.get() is selected and calls == []
        for term in terms:
            details = term.as_dict()["solar_model_details"]
            assert details["root_time_scale"] == "TT"
            assert details["civil_time_policy"] == "IERS_UTC_to_TT"
            assert details["future_leap_seconds_assumed_unchanged"] is False


def test_ordinary_historical_labels_obey_the_source_domain_without_native(monkeypatch):
    monkeypatch.setattr(runtime, "swe", None)
    for row in REFERENCE["historical_forward_rows"]:
        moment = datetime.fromisoformat(row["UTC"])
        if row["class"] == "removed_UTC_label":
            for forward in (
                historical_tai_minus_utc,
                historical_tai_minus_utc_exact,
                historical_utc_to_tt_point,
                ephemeris_time,
            ):
                with pytest.raises(ValueError, match="removed"):
                    forward(moment)
        elif row["class"] == "outside_historical":
            assert historical_tai_minus_utc_exact(moment) is None
            assert historical_utc_to_tt_point(moment) is None
            assert ephemeris_time(moment).jd_tt is not None
        else:
            expected = Fraction(row["offset_seconds"])
            assert historical_tai_minus_utc_exact(moment) == expected
            assert historical_tai_minus_utc(moment) == float(expected)
            assert historical_utc_to_tt_point(moment).days == Fraction(
                row["expected_TT"]
            )
            clock = ephemeris_time(moment)
            assert abs(
                Fraction(clock.jd_tt) - Fraction(row["expected_TT"])
            ) * 86400 < Fraction("0.0002")


def test_historical_point_and_ieee_entries_share_source_valid_intervals(monkeypatch):
    monkeypatch.setattr(runtime, "swe", None)
    for row in REFERENCE["historical_inverse_rows"]:
        point = TTInstant(Fraction(row["TT"]))
        ieee = TTInstant.from_float(row["float_TT"])
        for expected, functions in (
            (
                row["point"],
                (
                    lambda: historical_utc_from_tt_point(point),
                    lambda: datetime_from_tt(point),
                ),
            ),
            (
                row["IEEE"],
                (
                    lambda: historical_utc_from_tt(row["float_TT"]),
                    lambda: datetime_from_tt(row["float_TT"], exact_epoch=True),
                    lambda: datetime_from_tt(ieee),
                ),
            ),
        ):
            if expected["class"] == "outside_historical":
                assert functions[0]() is None
            elif expected["class"] == "unique":
                label = expected["candidates"][0]["UTC"]
                for inverse in functions:
                    assert inverse().isoformat() == label
            else:
                for inverse in functions:
                    with pytest.raises(HistoricalUTCAdjustment):
                        inverse()


def test_modern_inserted_seconds_and_ordinary_neighbors_are_distinct(monkeypatch):
    monkeypatch.setattr(runtime, "swe", None)
    for row in REFERENCE["modern_rows"]:
        point = TTInstant(Fraction(row["TT"]))
        if row["source_class"] == "ordinary":
            assert datetime_from_tt(point).isoformat() == row["expected_UTC"]
        else:
            with pytest.raises(ValueError, match="UTC leap second not representable"):
                datetime_from_tt(point)


def test_nominal_scalar_midnights_do_not_require_native_state(monkeypatch):
    monkeypatch.setattr(runtime, "swe", None)
    for row in REFERENCE["nominal_midnight_aliases"]:
        expected = datetime.fromisoformat(row["UTC"])
        assert datetime_from_tt(row["nominal_float_TT"]) == expected
        assert (
            historical_utc_from_tt(row["nominal_float_TT"], nominal_boundaries=True)
            == expected
        )


def test_known_atomic_tt_is_retained_without_a_native_ut1_provider(monkeypatch):
    monkeypatch.setattr(runtime, "swe", None)
    for row in REFERENCE["optional_native_forward"]["default_source_controls"]:
        moment = datetime.fromisoformat(row["UTC"])
        if row["source_class"] == "removed_UTC_label":
            with pytest.raises(ValueError, match="removed"):
                ephemeris_time(moment)
            continue
        actual = ephemeris_time(moment)
        if row["source_class"] == "preUTC_unadjudicated":
            assert actual.jd_tt is None
            assert actual.method == "UTC_as_UT1_approximation"
        else:
            expected = sum((Fraction(v) for v in row["ERFA_TT_parts"]), Fraction(0))
            assert abs(Fraction(actual.jd_tt) - expected) * 86400 < Fraction("0.0002")
            assert actual.method == "frozen_UTC_offsets_to_TT_UTC_as_UT1_approximation"
        assert actual.jd_ut1 == actual.jd_utc
        assert (
            actual.future_leap_seconds_assumed_unchanged
            == row["future_offset_assumption"]
        )


def test_selected_c04_clock_uses_its_data_without_native_calls(monkeypatch):
    monkeypatch.setattr(runtime, "swe", None)
    with use_ut1_source("iers_c04"):
        for row in REFERENCE["optional_native_forward"]["existing_C04_controls"]:
            assert (
                abs(ut1_from_tt(row["jd_tt"]) - row["jd_ut1_continuous"]) * 86400
                < 0.0002
            )
            assert (
                abs(tt_from_ut1(row["jd_ut1_continuous"]) - row["jd_tt"]) * 86400
                < 0.0002
            )
            if ":60" in row["utc"]:
                continue  # This input type cannot carry second60; both physical axes were checked.
            moment = datetime.fromisoformat(row["utc"]).replace(tzinfo=timezone.utc)
            actual = ephemeris_time(moment)
            assert abs(actual.jd_tt - row["jd_tt"]) * 86400 < 0.0002
            assert abs(actual.jd_ut1 - row["jd_ut1_continuous"]) * 86400 < 0.0002
            assert (
                actual.method
                == "frozen_UTC_offsets_to_TT_IERS20_C04_UT1_TAI_interpolation"
            )


def test_preutc_inverse_keeps_its_declared_native_model_requirement(monkeypatch):
    monkeypatch.setattr(runtime, "swe", None)
    point = TTInstant.from_parts(2430000.5, 0.001)
    with pytest.raises(ImportError, match="pre-UTC"):
        datetime_from_tt(point)
