"""IERS historical UTC coefficients, clock adjustments and real chart epochs."""

from datetime import datetime, timedelta, timezone

import pytest

from fatebridge.core.astro import runtime
from fatebridge.core.astro.geometry import _julian_day
from fatebridge.core.astro.historical_utc import (
    HistoricalUTCAdjustment,
    historical_tai_minus_utc,
)
from fatebridge.core.astro.time_scales import datetime_from_tt, ephemeris_time
from fatebridge.core.human_design import chart_at, design_epoch
from fatebridge.core.human_design_time import sun_at_tt

UTC = timezone.utc


@pytest.mark.parametrize(
    "date,expected_offset",
    [
        ("1961-01-01", 1.422818),
        ("1961-08-01", 1.647570),
        ("1962-01-01", 1.845858),
        ("1963-11-01", 2.6972788),
        ("1964-01-01", 2.765794),
        ("1964-04-01", 2.983730),
        ("1964-09-01", 3.282018),
        ("1965-01-01", 3.540130),
        ("1965-03-01", 3.716594),
        ("1965-07-01", 3.974706),
        ("1965-09-01", 4.155058),
        ("1966-01-01", 4.313170),
        ("1968-02-01", 6.185682),
        ("1971-12-01", 9.811890),
    ],
)
def test_iers_historical_offsets_at_published_segment_boundaries(date, expected_offset):
    # Numeric expectations calculated from the published IERS rows and MJD
    # labels, without calling this implementation's table or conversion.
    instant = datetime.fromisoformat(date).replace(tzinfo=UTC)
    assert historical_tai_minus_utc(instant) == pytest.approx(
        expected_offset, abs=1e-10
    )
    times = ephemeris_time(instant)
    assert (times.jd_tt - _julian_day(instant)) * 86400 == pytest.approx(
        expected_offset + 32.184, abs=0.00005
    )
    assert times.method == "IERS_1961_1971_UTC_drift_to_TT_swiss_delta_t_to_UT1"
    if date not in {"1961-08-01", "1968-02-01"}:
        assert abs((datetime_from_tt(times.jd_tt) - instant).total_seconds()) < 0.0002
    # Step-related intervals have passed after five seconds, including the two
    # downward offset steps whose exact boundary lacks a unique affine label.
    after = instant + timedelta(seconds=5)
    assert (
        abs((datetime_from_tt(ephemeris_time(after).jd_tt) - after).total_seconds())
        < 0.0002
    )


@pytest.mark.parametrize(
    "year,expected_drift", [(1961, 0.000648), (1963, 0.0005616), (1969, 0.001296)]
)
def test_historical_utc_retains_fractional_day_drift(year, expected_drift):
    midnight = datetime(year, 5, 17, tzinfo=UTC)
    difference = historical_tai_minus_utc(
        midnight + timedelta(hours=12)
    ) - historical_tai_minus_utc(midnight)
    assert difference == pytest.approx(expected_drift, abs=1e-11)


@pytest.mark.parametrize("year", range(1960, 1972))
def test_every_historical_utc_year_round_trips_interior_fractional_seconds(year):
    moment = datetime(year, 5, 17, 3, 12, 34, 500000, tzinfo=UTC)
    restored = datetime_from_tt(ephemeris_time(moment).jd_tt)
    assert abs((restored - moment).total_seconds()) < 0.0002


@pytest.mark.parametrize("date", ["1959-12-31", "1972-01-01"])
def test_historical_drift_does_not_extend_outside_its_published_scope(date):
    assert (
        historical_tai_minus_utc(datetime.fromisoformat(date).replace(tzinfo=UTC))
        is None
    )


@pytest.mark.parametrize(
    "date,tt_minus_civil",
    [
        ("1961-01-01", 1.422818 + 32.184 - 0.0025),  # SOFA 5ms step
        ("1961-08-01", 1.647570 + 32.184 + 0.025),  # two affine labels
        ("1964-04-01", 2.983730 + 32.184 - 0.05),  # no affine label
        ("1972-01-01", 10 + 32.184 - 0.05),
    ],
)
def test_fractional_utc_adjustments_do_not_get_an_invented_datetime(
    date, tt_minus_civil
):
    instant = datetime.fromisoformat(date).replace(tzinfo=UTC)
    tt = _julian_day(instant) + tt_minus_civil / 86400
    with pytest.raises(HistoricalUTCAdjustment):
        datetime_from_tt(tt)


def test_design_epoch_preserves_tt_when_fractional_utc_adjustment_has_no_unique_label():
    # Freeze the source-defined April 1964 adjustment, not an engine-produced
    # expected civil clock. Swiss' independent solcross constructs the birth.
    design_tt = (
        _julian_day(datetime(1964, 4, 1, tzinfo=UTC))
        + (2.983730 + 32.184 - 0.05) / 86400
    )
    birth_tt = runtime.ephemeris_call(
        "solcross",
        (sun_at_tt(design_tt) + 88) % 360,
        design_tt + 70,
        runtime.swe.FLG_SWIEPH,
    )
    birth = datetime_from_tt(birth_tt)
    chart = chart_at(birth)
    assert chart["design_utc"] is None
    assert (
        chart["design_solver"]["utc_label_status"]
        == "unrepresentable_historical_fractional_UTC_adjustment"
    )
    assert chart["time_scales"]["design"]["utc_is_leap_second"] is False
    assert abs(chart["time_scales"]["design"]["jd_tt"] - design_tt) * 86400 < 0.002
    assert abs(chart["design_solver"]["residual_degrees"]) < 1e-7
    with pytest.raises(ValueError, match="UTC 调整区间"):
        design_epoch(birth)


def test_corrected_historical_tt_is_used_for_the_actual_moon_calculation(monkeypatch):
    # This minute crosses a Base boundary with local Swiss files. Moshier's
    # 0.37 arcsecond position difference puts it on the other side already, so
    # do not pretend one backend's Base is a universal independent oracle.
    # Verify the IERS physical epoch reaches calc(), not only output metadata.
    moment = datetime(1971, 12, 1, 0, 58, tzinfo=UTC)
    expected_tt = _julian_day(moment) + (9.8119944 + 32.184) / 86400
    assert abs(ephemeris_time(moment).jd_tt - expected_tt) * 86400 < 0.00005
    original = runtime.ephemeris_call
    moon_epochs = []

    def observe(operation, *args, **kwargs):
        if operation == "calc" and args[1] == runtime.swe.MOON:
            moon_epochs.append(args[0])
        return original(operation, *args, **kwargs)

    monkeypatch.setattr(runtime, "ephemeris_call", observe)
    chart = chart_at(moment)
    # The nominal birth/design pair remains first. Later Moon calls must be
    # exactly the published root-candidate epochs, each observed once.
    from fatebridge.core.human_design_solar_root_validation import (
        verify_solar_root_context,
    )

    assert len(moon_epochs[:2]) == 2
    precision = chart["design_solver"]["numerical_precision"]
    declared = {chart["time_scales"]["personality"]["jd_tt"]} | {
        r["jd_tt"] for r in precision["design_body_endpoint_assessment"]["evaluations"]
    }
    family = precision["local_root_family"]
    if family is not None:
        declared.update(r["jd_tt"] for r in family["candidates"])
    assert len(moon_epochs) == len(declared)
    assert set(moon_epochs) == declared
    assert verify_solar_root_context(chart)["errors"] == []
    assert abs(moon_epochs[0] - expected_tt) * 86400 < 0.00005
    assert moon_epochs[1] == chart["time_scales"]["design"]["jd_tt"]
