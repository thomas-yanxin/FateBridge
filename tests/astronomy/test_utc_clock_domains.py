"""Published UTC domains and optional-native clock providers, without ephemeris files."""

import gzip
import json
import math
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from pathlib import Path

import pytest

from fatebridge.core.astro import runtime
from fatebridge.core.astro.historical_utc import (
    HistoricalUTCAdjustment,
    historical_tai_minus_utc,
    historical_tai_minus_utc_exact,
    historical_utc_from_tt,
    historical_utc_to_tt_point,
)
from fatebridge.core.astro.iers_ut1 import active_ut1, c04_table, use_ut1_source
from fatebridge.core.astro.physical_epoch import PhysicalEpoch
from fatebridge.core.astro.time_scales import (
    EphemerisTime,
    datetime_from_tt,
    datetime_from_ut1,
    ephemeris_time,
    resolve_tt_from_ut1,
    tt_from_ut1,
    ut1_from_tt,
    utc_clock,
)
from fatebridge.core.astro.tt_epoch import TTInstant
from fatebridge.core.solar_term_clock import native_solar_root_time_policy
from tests.support.c04_clock import CLOCK, SCALAR_GATE, assert_clock_point
from tests.support.ephemeris_context import empty_ephemeris_path

REFERENCE = json.loads(
    (
        Path(__file__).parents[1] / "fixtures/historical-utc-domain-reference-v1.json"
    ).read_text()
)


@pytest.mark.parametrize(
    ("civil_label", "utc_label", "has_datetime_carrier"),
    [
        ("2026-07-01T12:00:00+08:00", "2026-07-01T04:00:00+00:00", True),
        ("2026-07-01T12:00:00-05:00", "2026-07-01T17:00:00+00:00", True),
        (
            "2026-07-01T12:00:00+00:00:01.123456",
            "2026-07-01T11:59:58.876544+00:00",
            True,
        ),
        ("9999-12-31T23:00:00-08:00", "+010000-01-01T07:00:00+00:00", False),
    ],
)
def test_physical_epoch_delivers_utc_instead_of_the_input_wall_label(
    civil_label: str, utc_label: str, has_datetime_carrier: bool
) -> None:
    epoch = PhysicalEpoch.from_civil(datetime.fromisoformat(civil_label))
    assert epoch.utc_label == utc_label
    if has_datetime_carrier:
        assert epoch.utc_datetime == datetime.fromisoformat(utc_label)
    else:
        assert epoch.utc_datetime is None


@pytest.mark.parametrize(
    "label,method,future",
    [
        ("1960-04-01T12:00:00+00:00", "SOFA_1960_UTC_drift_to_TT", False),
        ("2026-10-01T12:00:00+00:00", "IERS_UTC_to_TT", False),
        ("2300-01-01T12:00:00+00:00", "IERS_UTC_to_TT", True),
    ],
)
def test_atomic_clock_and_solar_policy_do_not_query_unrelated_ut1(
    label: str, method: str, future: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
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
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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


def test_ordinary_historical_labels_obey_the_source_domain_without_native(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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


def test_historical_point_and_ieee_entries_share_source_valid_intervals(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(runtime, "swe", None)
    for row in REFERENCE["historical_inverse_rows"]:
        point = TTInstant(Fraction(row["TT"]))
        ieee = TTInstant.from_float(row["float_TT"])
        for expected, functions in (
            (
                row["point"],
                (
                    lambda: historical_utc_from_tt(point),
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


def test_modern_inserted_seconds_and_ordinary_neighbors_are_distinct(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(runtime, "swe", None)
    for row in REFERENCE["modern_rows"]:
        point = TTInstant(Fraction(row["TT"]))
        if row["source_class"] == "ordinary":
            assert datetime_from_tt(point).isoformat() == row["expected_UTC"]
        else:
            with pytest.raises(ValueError, match="UTC leap second not representable"):
                datetime_from_tt(point)


def test_nominal_scalar_midnights_do_not_require_native_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(runtime, "swe", None)
    for row in REFERENCE["nominal_midnight_aliases"]:
        expected = datetime.fromisoformat(row["UTC"])
        assert datetime_from_tt(row["nominal_float_TT"]) == expected
        assert (
            historical_utc_from_tt(row["nominal_float_TT"], nominal_boundaries=True)
            == expected
        )


def test_known_atomic_tt_is_retained_without_a_native_ut1_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(runtime, "swe", None)
    for row in REFERENCE["optional_native_forward"]["default_source_controls"]:
        moment = datetime.fromisoformat(row["UTC"])
        if row["source_class"] == "removed_UTC_label":
            with pytest.raises(ValueError, match="removed"):
                ephemeris_time(moment)
            continue
        else:
            pass
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


def test_selected_c04_clock_uses_its_data_without_native_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(runtime, "swe", None)
    with use_ut1_source("iers_c04"):
        for row in REFERENCE["optional_native_forward"]["existing_C04_controls"]:
            label = row["utc"]
            legacy = CLOCK["ieee"][label]
            exact = CLOCK["utc"][label]
            assert row["jd_tt"].hex() == legacy["tt_input"]
            assert row["jd_ut1_continuous"].hex() == legacy["ut1_input"]
            forward, inverse = legacy["forward"], legacy["inverse"]
            if forward.get("domain") == "outside":
                with pytest.raises(ValueError, match="outside"):
                    ut1_from_tt(row["jd_tt"])
            else:
                assert ut1_from_tt(row["jd_tt"]).hex() == forward["ut1"]["RN_hex"]
            point = TTInstant(Fraction(exact["tt"]))
            u = ut1_from_tt(point)
            assert u.hex() == exact["ut1"]["RN_hex"]
            assert abs(u - row["jd_ut1_continuous"]) * 86400 < SCALAR_GATE
            if inverse.get("domain") == "outside":
                with pytest.raises(ValueError, match="outside"):
                    tt_from_ut1(row["jd_ut1_continuous"])
            else:
                t = tt_from_ut1(row["jd_ut1_continuous"])
                assert t.hex() == inverse["tt"]["RN_hex"]
                assert abs(t - row["jd_tt"]) * 86400 < SCALAR_GATE
            if ":60" in label:
                continue  # This input type cannot carry second60; both physical axes were checked.
            else:
                pass
            moment = datetime.fromisoformat(label).replace(tzinfo=timezone.utc)
            actual = ephemeris_time(moment)
            assert actual.tt == point
            assert_clock_point(actual.ut1.days, exact["ut1"])
            assert abs(actual.jd_tt - row["jd_tt"]) * 86400 < SCALAR_GATE
            assert abs(actual.jd_ut1 - row["jd_ut1_continuous"]) * 86400 < SCALAR_GATE
            assert (
                actual.method
                == "frozen_UTC_offsets_to_TT_IERS20_C04_UT1_TAI_interpolation"
            )


def test_preutc_inverse_keeps_its_declared_native_model_requirement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(runtime, "swe", None)
    point = TTInstant.from_parts(2430000.5, 0.001)
    with pytest.raises(ImportError, match="pre-UTC"):
        datetime_from_tt(point)


def test_primary_ut1_epoch_does_not_reencode_its_display_as_a_new_clock() -> None:
    reference = json.loads(
        (Path(__file__).parents[1] / "data/ut1_primary_epoch_v1.json").read_text()
    )
    with empty_ephemeris_path(), use_ut1_source("swiss_delta_t"):
        for row in reference["rows"]:
            ut1 = float.fromhex(row["ut1_hex"])
            expected_tt = float.fromhex(row["tt_hex"])
            epoch = PhysicalEpoch.from_ut1(ut1)
            assert epoch.time.jd_ut1 == ut1
            assert epoch.time.jd_tt == expected_tt
            assert epoch.utc_datetime is not None
            assert (
                epoch.utc_label
                == datetime_from_tt(TTInstant.from_float(expected_tt)).isoformat()
            )


def test_solved_ut1_display_keeps_the_physical_side_of_a_leap_boundary() -> None:
    # Frozen default-source UT1 points recover these exact IEEE TT points.
    # SOFA's published UTC offsets classify the first as just before the
    # inserted second and the second as within it; nominal scalar aliases
    # must not replace a solved event with an intended civil boundary.
    with empty_ephemeris_path(), use_ut1_source("swiss_delta_t"):
        before_leap = float.fromhex("0x1.2a08dbfffc4d5p+21")
        inside_leap = float.fromhex("0x1.2a08dc00025ecp+21")
        assert tt_from_ut1(before_leap).hex() == "0x1.2a08dc00fffa9p+21"
        assert tt_from_ut1(inside_leap).hex() == "0x1.2a08dc01060c0p+21"
        assert datetime_from_ut1(before_leap).isoformat() == (
            "1972-06-30T23:59:59.999999+00:00"
        )
        with pytest.raises(ValueError, match="UTC leap second not representable"):
            datetime_from_ut1(inside_leap)


def test_primary_c04_epoch_requires_only_its_selected_clock_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(runtime, "swe", None)
    monkeypatch.setattr("fatebridge.core.ephemeris_runtime.swe", None)
    with use_ut1_source("iers_c04"):
        for row in REFERENCE["optional_native_forward"]["existing_C04_controls"]:
            label = row["utc"]
            ut1 = row["jd_ut1_continuous"]
            reference = CLOCK["ieee"][label]["inverse"]
            assert Fraction(ut1) == Fraction(reference["ut1"])
            if reference.get("domain") == "outside":
                with pytest.raises(ValueError, match="outside"):
                    PhysicalEpoch.from_ut1(ut1)
                exact = CLOCK["utc"][label]
                epoch = PhysicalEpoch.from_tt(TTInstant(Fraction(exact["tt"])))
                assert epoch.time.tt.days == Fraction(exact["tt"])
                assert_clock_point(epoch.time.ut1.days, exact["ut1"])
            else:
                epoch = PhysicalEpoch.from_ut1(ut1)
                assert epoch.time.ut1.days == Fraction(ut1)
                assert_clock_point(epoch.time.tt.days, reference["tt"])
            assert abs(epoch.time.jd_tt - row["jd_tt"]) * 86400 < SCALAR_GATE
        # The scalar UT1 controls have a 0.2ms comparison bound; at a leap
        # boundary they cannot identify the original UTC label's exact side.
        # Check label membership against the frozen exact TT controls instead.
        for row in REFERENCE["modern_rows"]:
            epoch = PhysicalEpoch.from_tt(TTInstant(Fraction(row["TT"])))
            assert epoch.utc_is_leap_second is (row["source_class"] != "ordinary")
            if row["source_class"] == "ordinary":
                assert epoch.utc_label == row["expected_UTC"]
                assert epoch.utc_datetime is not None
            else:
                assert epoch.utc_datetime is None


def test_solar_birth_retains_primary_axes_through_charts_workers_and_retargeting() -> (
    None
):
    from fatebridge.core.astro.birth import build_astro_birth_info
    from fatebridge.core.astro.birth_clock import resolve_solar_epoch
    from fatebridge.core.astro.chart import build_core_chart_payload
    from fatebridge.core.astro.native_execution import decode, encode
    from fatebridge.core.astro.relationship_geometry import davison_birth
    from fatebridge.core.astro.sensitivity import time_sensitivity
    from fatebridge.core.astro.sensitivity_timing import specialty_sample_times
    from fatebridge.core.predictive._common import build_natal_subject

    # The longitude reaches an original source-clock failure under the full
    # Swiss source. Other supported sources may solve a different physical
    # epoch; every consumer must retain that same chosen epoch.
    with empty_ephemeris_path(), use_ut1_source("swiss_delta_t"):
        birth = build_astro_birth_info(
            birth_year=294,
            birth_month=10,
            birth_day=13,
            birth_hour=23,
            birth_minute=58,
            birth_second=54,
            birth_clock_basis="local_apparent_solar",
            birth_longitude=-3.190392558044337,
            birth_latitude=40,
        )
        assert birth.native_epoch is not None
        assert birth.time_scales is birth.native_epoch.time
        chart = build_core_chart_payload(birth, "chart13")
        assert chart["chart_profile"]["julian_day_ut1"] == birth.time_scales.jd_ut1
        assert chart["chart_profile"]["julian_day_tt"] == birth.time_scales.jd_tt
        decoded = decode(encode(birth))
        assert type(decoded) is type(birth)
        assert decoded.time_scales == birth.time_scales
        assert decoded.native_epoch == birth.native_epoch
        subject = build_natal_subject(birth)
        assert subject.julian_day == birth.time_scales.jd_ut1
        assert subject.julian_day_tt == birth.time_scales.jd_tt
        midpoint, policy = davison_birth(birth, birth)
        assert midpoint.native_epoch is not None
        assert midpoint.time_scales == birth.time_scales
        assert policy["midpoint_jd_ut1"] == birth.time_scales.jd_ut1
        for uncertainty in (0, 0.5):
            sampled = time_sensitivity(
                midpoint,
                sidereal=False,
                uncertainty_minutes=uncertainty,
                include_hypothetical=False,
            )
            nominal = next(
                row for row in sampled["samples"] if row["offset_seconds"] == 0
            )
            assert nominal["julian_day_ut1"] == midpoint.time_scales.jd_ut1
            assert nominal["julian_day_tt"] == midpoint.time_scales.jd_tt
            assert nominal["recorded_utc"] == midpoint.utc_isoformat
        interval = specialty_sample_times(birth, 0.5)
        center = interval.samples[interval.nominal_index]
        assert center.recorded.epoch is center.effective is birth.native_epoch
        shifted = interval.samples[-1]
        expected, _ = resolve_solar_epoch(
            datetime(294, 10, 13, 23, 59, 24),
            birth.longitude,
            "local_apparent_solar",
        )
        assert shifted.recorded.epoch == shifted.effective == expected
        assert shifted.effective.time.ut1 != birth.time_scales.ut1


@pytest.mark.parametrize(
    "origin,offset_microseconds,expected",
    [
        (datetime.min, -1, None),
        (datetime(1899, 12, 31), Fraction(-1, 2), datetime(1899, 12, 31)),
        (datetime(9999, 12, 31), 86_399_999_999, datetime.max),
    ],
)
def test_solar_wall_clock_rounds_exact_local_mean_label(
    origin, offset_microseconds, expected
) -> None:
    from fatebridge.core.astro.birth_clock import solar_wall_clock
    from fatebridge.core.astro.ut1_epoch import UT1Instant
    from fatebridge.utils.civil_time import utc_calendar

    day = utc_calendar(origin.replace(tzinfo=timezone.utc)).julian_day_exact()
    ut1 = UT1Instant(day + Fraction(offset_microseconds) / 86_400_000_000)
    epoch = PhysicalEpoch(
        EphemerisTime(None, ut1, TTInstant(ut1.days), "explicit", False),
        None,
        None,
        False,
    )
    with empty_ephemeris_path():
        if expected is None:
            with pytest.raises(OverflowError, match="date value out of range"):
                solar_wall_clock(epoch, 0.0, "local_mean_solar")
        else:
            assert solar_wall_clock(epoch, 0.0, "local_mean_solar") == expected


@pytest.mark.parametrize("operation", ["components", "rebase"])
@pytest.mark.parametrize(
    "stamp,expected",
    [
        (
            "1979-11-21T17:17:13.465208+00:00",
            Fraction(26397351585456151, 10800000000),
        ),
        (
            "1979-11-21T17:17:00+00:00",
            Fraction(8799117194591, 3600000),
        ),
    ],
)
def test_forward_solar_clocks_retain_tt_target_and_scalar_native_source(
    monkeypatch: pytest.MonkeyPatch, operation: str, stamp: str, expected
) -> None:
    import fatebridge.core.astro_models as models
    from fatebridge.core.astro import earth_attitude
    from fatebridge.core.astro.birth_clock import solar_clock_components
    from fatebridge.core.astro.solar_rebase import solar_rebase_adjustment

    assert Fraction(float(expected)) != expected
    targets = []
    native_epochs = []
    original_call = runtime.ephemeris_call

    def capture_target(original):
        def observed(module, jd_ut1, *, julian_day_tt=None):
            result = original(module, jd_ut1, julian_day_tt=julian_day_tt)
            targets.append(result.tt.days)
            return result

        return observed

    def capture_call(operation, *args, **kwargs):
        result = original_call(operation, *args, **kwargs)
        if (
            operation == "calc"
            and args[1] == runtime.swe.SUN
            and args[2] & runtime.swe.FLG_EQUATORIAL
        ):
            native_epochs.append(args[0])
        else:
            pass
        return result

    monkeypatch.setattr(
        earth_attitude,
        "physical_equator",
        capture_target(earth_attitude.physical_equator),
    )
    monkeypatch.setattr(
        models, "physical_equator", capture_target(models.physical_equator)
    )
    monkeypatch.setattr(runtime, "ephemeris_call", capture_call)
    moment = datetime.fromisoformat(stamp)
    with empty_ephemeris_path(), use_ut1_source("swiss_delta_t"):
        if operation == "components":
            solar_clock_components(moment, 120.0, "local_apparent_solar")
        else:
            solar_rebase_adjustment(moment, "UTC", 120.0)
    assert targets and all(point == expected for point in targets)
    assert native_epochs and all(
        type(value) is float and value == float(expected) for value in native_epochs
    )


def test_scalar_clocks_round_independent_sofa_source_values_once() -> None:
    from fatebridge.core.astro.julian_day import _julian_day
    from fatebridge.utils.civil_time import utc_calendar

    reference = json.loads(
        gzip.decompress(
            (
                Path(__file__).parents[1]
                / "data/clock_scalar_rounding_v1/reference.json.gz"
            ).read_bytes()
        )
    )
    for row in reference["rows"]:
        moment = datetime.fromisoformat(row["utc"])
        expected = Fraction(row["nominal_exact"])
        assert utc_calendar(moment).julian_day_exact() == expected, row["id"]
        assert _julian_day(moment) == float(expected), row["id"]
        if "tt_exact" in row:
            atomic = utc_clock(moment)
            assert atomic.civil_jd == float(expected), row["id"]
            assert atomic.jd_tt == float(Fraction(row["tt_exact"])), row["id"]
        else:
            pass


def test_physical_tt_points_keep_source_leap_intervals_and_nominal_aliases(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fatebridge.core.astro.physical_epoch import utc_from_tt

    reference = json.loads(
        gzip.decompress(
            (
                Path(__file__).parents[1]
                / "data/physical_epoch_points_v1/reference.json.gz"
            ).read_bytes()
        )
    )
    monkeypatch.setattr(runtime, "swe", None)
    for row in reference["rows"]:
        value = float.fromhex(row["input_tt_hex"])
        label, moment, leap = utc_from_tt(value)
        assert leap is row["expected_leap"], row["id"]
        assert label == row["expected_utc_label"], row["id"]
        if leap:
            assert moment is None, row["id"]
        else:
            assert moment is not None, row["id"]
            assert moment.isoformat() == row["expected_utc_label"], row["id"]
        nominal = row["legacy_nominal"]
        if nominal["error"] is not None:
            with pytest.raises(ValueError, match="UTC leap second"):
                datetime_from_tt(value)
        else:
            assert datetime_from_tt(value).isoformat() == nominal["label"], row["id"]


def test_exact_tt_constructor_preserves_aware_calendar_boundary_instants() -> None:
    # SOFA2023-10-11 cal2jd local-midnight parts plus exact clock/zone
    # microseconds and explicit TAI-UTC assumptions. These are numerical
    # controls, not historical/future offset-table or ancient UTC claims.
    # cal2jd.c SHA256:996773197e46c7dd7d7559a05281542b14694d781828fc8fa019829e059730b5
    cases = [
        (
            (1, 1, 1, 0, 0, 0, 0),
            43_200_000_000,
            "0",
            "688570000149/400000",
        ),
        (
            (9999, 12, 31, 23, 59, 59, 999999),
            -43_200_000_000,
            "37",
            "51585456007687111/9600000000",
        ),
        (
            (1, 1, 1, 12, 0, 0, 0),
            43_200_000_000,
            "0",
            "688570200149/400000",
        ),
        (
            (9999, 12, 31, 11, 59, 59, 999999),
            -43_200_000_000,
            "37",
            "51585451207687111/9600000000",
        ),
        (
            (2000, 1, 1, 12, 0, 0, 0),
            0,
            "32",
            "26476686008023/10800000",
        ),
        (
            (2026, 11, 17, 13, 42, 17, 123456),
            19_800_000_000,
            "37",
            "553806414599759/225000000",
        ),
        (
            (1965, 3, 1, 0, 0, 0, 1),
            -123456,
            "1864581/500000",
            "210714091236036619/86400000000",
        ),
        (
            (1970, 1, 1, 0, 0, 0, 0),
            123456,
            "1/3",
            "9884379376518463/4050000000",
        ),
    ]
    for fields, offset_microseconds, atomic_offset, expected in cases:
        moment = datetime(
            *fields, tzinfo=timezone(timedelta(microseconds=offset_microseconds))
        )
        assert TTInstant.from_utc(
            moment, tai_minus_utc_seconds=Fraction(atomic_offset)
        ).days == Fraction(expected)


def test_atomic_clock_retains_source_tt_beside_unchanged_scalar_adapter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Keep every original scalar obligation. The new primary point is a
    # separately checked result, not a replacement for the two-part gate.
    reference = json.loads(
        gzip.decompress(
            (
                Path(__file__).parents[1]
                / "data/clock_scalar_rounding_v1/reference.json.gz"
            ).read_bytes()
        )
    )
    monkeypatch.setattr(runtime, "swe", None)
    for row in reference["rows"]:
        if "tt_exact" not in row:
            continue
        else:
            pass
        moment = datetime.fromisoformat(row["utc"])
        expected = Fraction(row["tt_exact"])
        atomic = utc_clock(moment)
        scales = ephemeris_time(moment)
        assert atomic.tt.days == expected, row["id"]
        assert scales.tt.days == expected, row["id"]
        assert atomic.jd_tt == scales.jd_tt == float(expected), row["id"]
        # Canonical dataclass replacement cannot leave a competing stored JD.
        ieee = TTInstant.from_float(atomic.jd_tt)
        replaced = replace(atomic, tt=ieee)
        assert replaced.tt is ieee and replaced.jd_tt == ieee.as_float()


def test_primary_exact_tt_and_ieee_input_remain_distinct_physical_epochs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    moment = datetime(1979, 11, 21, 17, 17, 13, 465208, tzinfo=timezone.utc)
    point = TTInstant(Fraction(26397351585456151, 10800000000))
    assert point == TTInstant.from_utc(moment, tai_minus_utc_seconds=18)
    monkeypatch.setattr(runtime, "swe", None)
    with use_ut1_source("iers_c04"):
        precise = PhysicalEpoch.from_tt(point)
        scalar = PhysicalEpoch.from_tt(point.as_float())
    assert precise.time.tt is point
    assert precise.utc_datetime == moment
    assert scalar.time.tt.days == Fraction(point.as_float())
    assert scalar.time.tt != precise.time.tt
    assert scalar.time.jd_tt == precise.time.jd_tt


def test_two_part_adapter_keeps_the_primary_fraction_and_small_residual() -> None:
    point = TTInstant(Fraction(42136105025861137882925761, 17280000000000000000))
    high, residual = point.as_parts()
    assert high == point.as_float()
    represented = Fraction(high) + Fraction(residual)
    assert abs(represented - point.days) <= Fraction.from_float(math.ulp(residual)) / 2
    assert TTInstant.from_value(point) is point
    assert point.shifted_by(Fraction(1, 86400000000)).days == (
        point.days + Fraction(1, 86400000000)
    )
    scalar = float.fromhex("0x1.2a5d39c45a692p+21")
    assert TTInstant.from_float(scalar).as_parts() == (scalar, 0.0)
    # Original SOFA source row historical_tt:1 was the first stage1
    # integer-head adapter failure; keep its original precision criterion.
    original = TTInstant(Fraction(21078417963024256877307697, 8640000000000000000))
    first, second = original.as_parts()
    error_us = abs(Fraction(first) + Fraction(second) - original.days) * 86400000000
    assert error_us <= Fraction(1968195175127, 1717986918400000000)


def test_native_wire_preserves_a_primary_fraction_in_the_birth_epoch() -> None:
    from fatebridge.core.astro.birth import AstroBirthInfo
    from fatebridge.core.astro.native_execution import decode, encode

    moment = datetime(1979, 11, 21, 17, 17, 13, 465208, tzinfo=timezone.utc)
    point = TTInstant(Fraction(26397351585456151, 10800000000))
    civil = float(point.days - Fraction(6273, 125 * 86400))
    scales = EphemerisTime(civil, civil, point, "synthetic_codec_point", False)
    epoch = PhysicalEpoch(scales, moment.isoformat(), moment, False)
    birth = AstroBirthInfo(
        "synthetic_codec_point",
        "synthetic_coordinates",
        "UTC",
        120.0,
        30.0,
        moment,
        moment,
        native_epoch=epoch,
    )
    # Exercise the actual JSON wire, whose numeric leaves cannot hold Fraction.
    restored = decode(json.loads(json.dumps(encode(birth), allow_nan=False)))
    assert restored.native_epoch.time.tt.days == Fraction(
        26397351585456151, 10800000000
    )
    assert restored.native_epoch.time.jd_tt == point.as_float()
    assert restored.native_epoch.time.tt.days != Fraction(point.as_float())
    assert restored.native_epoch.utc_datetime == moment


# Independent expectations were frozen in Round19/reference-nine.json before
# production edits, from the original six C04 rows and nominal atomic offsets.
# These are finite source arithmetic controls, not new EOP observations.
C04_CANONICAL_SOURCE_ANCHORS = [
    (
        37665,
        "35102383205671643/14400000000",
        "1053071496000163169/432000000000",
    ),
    (
        37666,
        "175511988028359151/72000000000",
        "702047952000106849/288000000000",
    ),
    (
        60462,
        "3321624376081/1350000",
        "2125839599999795653/864000000000",
    ),
    (
        60463,
        "3321625726081/1350000",
        "2125840463999789599/864000000000",
    ),
    (
        61301,
        "3322757026081/1350000",
        "1063282247999955317/432000000000",
    ),
    (
        61302,
        "3322758376081/1350000",
        "2126565359999905723/864000000000",
    ),
]
C04_CANONICAL_UTC_INPUTS = [
    (
        "1961-12-31T23:59:59.999999+00:00",
        False,
        "42122859846805971399999997/17280000000000000000",
        None,
    ),
    (
        "1962-01-01T00:00:00+00:00",
        True,
        "35102383205671643/14400000000",
        "0x1.29910c000032bp+21",
    ),
    (
        "1962-01-01T00:00:00.000001+00:00",
        True,
        "210614299234029859000000013/86400000000000000000",
        "0x1.29910c000032bp+21",
    ),
    (
        "2026-09-18T23:59:59.999999+00:00",
        True,
        "23628504007687111/9600000000",
        "0x1.2c73b3fffff16p+21",
    ),
    (
        "2026-09-19T00:00:00+00:00",
        True,
        "3322758376081/1350000",
        "0x1.2c73b3fffff16p+21",
    ),
    (
        "2026-09-19T00:00:00.000001+00:00",
        False,
        "212656536069184001/86400000000",
        None,
    ),
    (
        "2024-06-01T11:59:59.999999+00:00",
        True,
        "23620444807687111/9600000000",
        "0x1.2c5977ffffdfdp+21",
    ),
    (
        "2024-06-01T12:00:00+00:00",
        True,
        "3321625051081/1350000",
        "0x1.2c5977ffffdfdp+21",
    ),
    (
        "2024-06-01T12:00:00.000001+00:00",
        True,
        "212584003269184001/86400000000",
        "0x1.2c5977ffffdfdp+21",
    ),
]


@pytest.mark.parametrize("mjd,tt_exact,ut1_exact", C04_CANONICAL_SOURCE_ANCHORS)
def test_c04_source_anchor_points_and_known_tt_receipts(
    mjd, tt_exact, ut1_exact
) -> None:
    table = c04_table()
    point = TTInstant(Fraction(tt_exact))
    anchor = table.samples[mjd - 37665]
    assert (anchor.mjd, anchor.tt, anchor.ut1) == (mjd, point, Fraction(ut1_exact))

    utc = (datetime(1858, 11, 17) + timedelta(days=mjd)).isoformat()
    reference = CLOCK["utc"][utc]
    assert point.days == Fraction(reference["tt"])
    evaluation = table.evaluate(point)
    assert evaluation.tt is point
    assert_clock_point(evaluation.ut1, reference["ut1"])
    assert [table.samples[i].mjd for i in evaluation.indices] == reference["mjd"]
    assert list(evaluation.weights) == reference["weights"]
    assert evaluation.weights[reference["mjd"].index(mjd)] == 1
    inverse = CLOCK["nominal_inverse"][str(mjd)]
    given_ut1 = Fraction(ut1_exact)
    assert given_ut1 == Fraction(inverse["ut1"])
    if inverse.get("domain") == "outside":
        with pytest.raises(ValueError, match="outside"):
            table.tt_from_ut1(given_ut1)
    else:
        assert_clock_point(table.tt_from_ut1(given_ut1).days, inverse["tt"])
    scalar = table.ut1_from_tt(point)
    assert scalar.hex() == reference["ut1"]["RN_hex"]
    receipt = table.receipt(point, scalar)
    assert receipt["source_mjd"] == reference["mjd"]
    assert receipt["instant_value_kind"] == (
        "daily_regularized_base_plus_instantaneous_model_terms"
    )
    assert receipt["subdaily_tides_applied"]
    assert receipt["interpolation_weights"] == reference["weights"]
    assert receipt["query_julian_day_tt"] == point.as_float()
    assert receipt["interpolation_error_bound_seconds"] is None
    assert not receipt["absolute_accuracy_certified"]


@pytest.mark.parametrize("utc,inside,tt_exact,ut1_hex", C04_CANONICAL_UTC_INPUTS)
def test_c04_canonical_coverage_precedes_scalar_projection(
    utc, inside, tt_exact, ut1_hex
) -> None:
    moment = datetime.fromisoformat(utc)
    reference = CLOCK["utc"][utc.removesuffix("+00:00")]
    assert Fraction(reference["tt"]) == Fraction(tt_exact)
    assert (reference.get("domain") != "outside") is inside
    with use_ut1_source("iers_c04"):
        if not inside:
            with pytest.raises(ValueError, match="outside"):
                ephemeris_time(moment)
            return
        else:
            pass
        actual = ephemeris_time(moment)
        assert actual.tt.days == Fraction(tt_exact)
        assert_clock_point(actual.ut1.days, reference["ut1"])
        assert abs(actual.jd_ut1 - float.fromhex(ut1_hex)) * 86400 < SCALAR_GATE
        receipt = c04_table().receipt(actual.tt, actual.jd_ut1)
        assert receipt["source_sha256"] == (
            "2f451f2b9faf42dc32f7368888980c92c3e773957019963c5d22df9ac20c8c82"
        )


def test_c04_inverse_retains_the_resolved_tt_for_the_original_ieee_ut1() -> None:
    query = float.fromhex("0x1.2c5977ffffdfdp+21")
    reference = CLOCK["ieee"]["2024-06-01T12:00:00"]["inverse"]
    assert Fraction(query) == Fraction(reference["ut1"])
    with use_ut1_source("iers_c04"):
        resolved = resolve_tt_from_ut1(query)
        assert_clock_point(resolved.days, reference["tt"])
        assert c04_table().tt_from_ut1(query) == resolved
        assert tt_from_ut1(query) == resolved.as_float()
        epoch = PhysicalEpoch.from_ut1(query)
        assert epoch.time.tt == resolved
        assert epoch.time.jd_ut1 == query
        assert epoch.utc_datetime == datetime_from_tt(resolved)


def test_c04_explicit_ieee_endpoint_queries_are_not_source_aliases() -> None:
    table = c04_table()
    # The first scalar TT is 11.735us inside and is not the published point.
    first_scalar = float.fromhex("0x1.29910c00ce7f9p+21")
    first = table.evaluate(first_scalar)
    expected = CLOCK["ieee"]["1962-01-01T00:00:00"]["forward"]
    assert first.tt.days == Fraction(first_scalar) == Fraction(expected["tt"])
    assert [float(w) for w in first.weights] == expected["weights"]
    assert [table.samples[i].mjd for i in first.indices] == expected["mjd"]
    assert_clock_point(first.ut1, expected["ut1"])
    # The last scalar TT is 14.201us outside. Both rounded source UT1 values
    # are outside too; a known-TT receipt above must not invert these values.
    with pytest.raises(ValueError, match="outside"):
        table.ut1_from_tt(float.fromhex("0x1.2c73b401a3d1ap+21"))
    for query_hex in ("0x1.29910c000032bp+21", "0x1.2c73b3fffff16p+21"):
        with pytest.raises(ValueError, match="outside"):
            table.tt_from_ut1(float.fromhex(query_hex))
