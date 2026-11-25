"""Historical solar clocks, shared time-scale inversion and input provenance."""

import json
import math
from datetime import datetime, timedelta, timezone
from fractions import Fraction

import pytest
from pydantic import ValidationError

from fatebridge.cli import run
from fatebridge.core.astro import runtime
from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.astro.birth_clock import (
    resolve_solar_birth_clock,
    resolve_solar_epoch,
)
from fatebridge.core.astro.sensitivity import time_sensitivity
from fatebridge.core.astro.time_scales import (
    datetime_from_ut1,
    ephemeris_time,
    tt_from_ut1,
    ut1_from_tt,
)
from fatebridge.core.requests.astrology import (
    AstroChartPolyRequest,
    AstroGermanyRequest,
)
from fatebridge.services.astrology import (
    calculate_core_chart_analysis,
    calculate_germany_chart_analysis,
)

HAS_SWE = pytest.mark.skipif(runtime.swe is None, reason="Swiss Ephemeris required")


@HAS_SWE
@pytest.mark.parametrize("year", [1, 400, 1000, 1600, 1879, 1900, 1955, 1959])
def test_pre_utc_ut1_helpers_preserve_the_native_forward_clock_policy(
    year: int,
) -> None:
    recorded = datetime(year, 5, 14, 22, 20, tzinfo=timezone.utc)
    jd_ut1 = recorded.toordinal() + 1721424.5 + (22 * 3600 + 20 * 60) / 86400
    native_tt, native_ut1 = runtime.ephemeris_call(
        "utc_to_jd", year, 5, 14, 22, 20, 0.0, runtime.swe.GREG_CAL
    )
    assert jd_ut1 == native_ut1
    assert tt_from_ut1(jd_ut1) == native_tt
    assert ut1_from_tt(native_tt) == native_ut1
    assert abs((datetime_from_ut1(jd_ut1) - recorded).total_seconds()) < 0.0002


@HAS_SWE
@pytest.mark.parametrize("year", [1960, 1968, 1972, 2000, 2050, 3000])
def test_offset_utc_era_uses_the_existing_shared_clock_policy(year: int) -> None:
    recorded = datetime(year, 5, 14, 22, 20, tzinfo=timezone.utc)
    scales = ephemeris_time(recorded)
    assert abs(tt_from_ut1(scales.jd_ut1) - scales.jd_tt) * 86400 < 0.0002
    assert ut1_from_tt(scales.jd_tt) == scales.jd_ut1
    assert abs((datetime_from_ut1(scales.jd_ut1) - recorded).total_seconds()) < 0.0002


def _apparent_label_seconds(moment, longitude):
    # Independent Cartesian ecliptic -> equatorial rotation and local solar
    # hour angle; no production EOT function or inverse clock routine.
    scales = ephemeris_time(moment)
    swe = runtime.swe
    lon, lat = runtime.ephemeris_call("calc", scales.jd_tt, swe.SUN, swe.FLG_SWIEPH)[0][
        :2
    ]
    eps = math.radians(runtime.ephemeris_call("calc", scales.jd_tt, swe.ECL_NUT)[0][0])
    lon, lat = math.radians(lon), math.radians(lat)
    x = math.cos(lon) * math.cos(lat)
    y = math.sin(lon) * math.cos(lat) * math.cos(eps) - math.sin(lat) * math.sin(eps)
    ra = math.degrees(math.atan2(y, x)) % 360
    hour_angle = (
        runtime.ephemeris_call("sidtime", scales.jd_ut1) * 15 + longitude - ra
    ) % 360
    return (hour_angle * 240 + 43200) % 86400


def _clock_error_seconds(actual, expected):
    return (actual - expected + 43200) % 86400 - 43200


@HAS_SWE
@pytest.mark.parametrize("longitude", [-180.0, -73.98765, 0.0, 10.0, 121.4667, 180.0])
def test_historical_lmt_uses_east_positive_longitude_and_exact_clock_arithmetic(
    longitude,
) -> None:
    wall = datetime(1879, 5, 14, 23, 1, 17)
    actual, receipt = resolve_solar_birth_clock(wall, longitude, "local_mean_solar")
    expected = wall.replace(tzinfo=timezone.utc) - timedelta(
        microseconds=round(Fraction(longitude) * 240 * 1_000_000)
    )
    assert actual == expected
    assert receipt["input_wall_datetime"] == wall.isoformat()
    assert receipt["clock_accuracy_certified"] is False
    assert receipt["measured_eop_applied"] is False
    assert "equation_of_time_seconds" not in receipt


@HAS_SWE
def test_explicit_historical_lmt_and_equivalent_civil_offset_have_identical_native_geometry() -> (
    None
):
    data = dict(
        birth_year=1879,
        birth_month=5,
        birth_day=14,
        birth_hour=23,
        birth_longitude=10,
        birth_latitude=53.55,
    )
    lmt = calculate_germany_chart_analysis(**data, birth_clock_basis="local_mean_solar")
    civil = calculate_germany_chart_analysis(**data, birth_timezone="+00:40")
    for field in ("factors", "midpoint_axes", "dials", "interpretations"):
        assert lmt["midpoint_analysis"][field] == civil["midpoint_analysis"][field]


@HAS_SWE
@pytest.mark.parametrize(
    "date,longitude",
    [
        ((1879, 5, 14), 10.0),
        ((2000, 2, 29), -73.98765),
        ((1960, 7, 1), 0.0),
        ((2026, 11, 3), 121.4667),
        ((1000, 1, 2), -180.0),
        ((1600, 12, 31), 180.0),
    ],
)
def test_lat_inversion_matches_independent_apparent_hour_angle(date, longitude) -> None:
    wall = datetime(*date, 0, 7, 19)
    actual, receipt = resolve_solar_birth_clock(wall, longitude, "local_apparent_solar")
    expected_seconds = wall.hour * 3600 + wall.minute * 60 + wall.second
    assert (
        abs(
            _clock_error_seconds(
                _apparent_label_seconds(actual, longitude), expected_seconds
            )
        )
        < 0.0002
    )
    assert abs(receipt["ut1_roundtrip_error_seconds"]) < 0.0002
    assert receipt["solar_ephemeris_model"] in {"swieph", "moshier", "jpl"}
    assert receipt["input_clock_basis"] == "local_apparent_solar"
    assert receipt["converted_utc"] == actual.isoformat()
    assert receipt["sidereal_time_model"] == (
        "Swiss_longterm_with_boundary_phase_alignment"
        if date[0] < 1800
        else "IAU2006_2000A_CIO"
    )


@HAS_SWE
def test_modern_lmt_is_ut1_and_must_not_be_relabelled_as_utc() -> None:
    wall = datetime(2000, 2, 29, 23)
    actual, receipt = resolve_solar_birth_clock(wall, 10.0, "local_mean_solar")
    expected_ut1 = wall.toordinal() + 1721424.5 + (23 * 3600 - 2400) / 86400
    assert receipt["target_julian_day_ut1"] == expected_ut1
    assert ephemeris_time(actual).jd_ut1 == expected_ut1
    assert actual != datetime(2000, 2, 29, 22, 20, tzinfo=timezone.utc)


@HAS_SWE
@pytest.mark.parametrize("basis", ["local_mean_solar", "local_apparent_solar"])
def test_solar_clock_interval_maps_endpoints_before_building_the_utc_grid(
    basis: str,
) -> None:
    wall = datetime(2000, 2, 29, 23, 1, 17)
    birth = build_astro_birth_info(
        birth_year=2000,
        birth_month=2,
        birth_day=29,
        birth_hour=23,
        birth_minute=1,
        birth_second=17,
        birth_longitude=10,
        birth_latitude=53.55,
        birth_clock_basis=basis,
    )
    result = time_sensitivity(birth, sidereal=False, uncertainty_minutes=1)
    samples = result["samples"]
    moments = [datetime.fromisoformat(row["recorded_utc"]) for row in samples]
    assert birth.utc_datetime in moments
    assert all(
        b > a and (b - a).total_seconds() <= 30 for a, b in zip(moments, moments[1:])
    )
    assert (
        result["recorded_interval_start_clock"]
        == (wall - timedelta(minutes=1)).isoformat()
    )
    assert (
        result["recorded_interval_end_clock"]
        == (wall + timedelta(minutes=1)).isoformat()
    )
    assert result["input_clock_basis"] == basis
    for actual, expected in [
        (moments[0], wall - timedelta(minutes=1)),
        (moments[-1], wall + timedelta(minutes=1)),
    ]:
        if basis == "local_apparent_solar":
            seconds = expected.hour * 3600 + expected.minute * 60 + expected.second
            assert (
                abs(_clock_error_seconds(_apparent_label_seconds(actual, 10), seconds))
                < 0.0002
            )
        else:
            jd_lmt = ephemeris_time(actual).jd_ut1 + 10 / 360
            expected_jd = (
                expected.toordinal()
                + 1721424.5
                + (expected.hour * 3600 + expected.minute * 60 + expected.second)
                / 86400
            )
            assert abs(jd_lmt - expected_jd) * 86400 < 0.0002
    assert result["continuous_interval_proven"] is False


@HAS_SWE
@pytest.mark.parametrize("variant", ["germany", "chart13"])
def test_solar_clock_provenance_and_instant_reach_native_services_and_directions(
    variant: str,
) -> None:
    data = dict(
        birth_year=1879,
        birth_month=5,
        birth_day=14,
        birth_hour=23,
        birth_longitude=10,
        birth_latitude=53.55,
        birth_clock_basis="local_mean_solar",
    )
    if variant == "germany":
        data.update(
            analysis_datetime=datetime(1879, 5, 14, 22, 20, tzinfo=timezone.utc),
            birth_time_uncertainty_minutes=0,
        )
    else:
        pass
    result = calculate_core_chart_analysis(**data, chart_variant=variant)
    base = result["base_chart"] if variant == "germany" else result
    receipt = base["person_info"]["clock_conversion"]
    assert receipt["input_wall_datetime"] == "1879-05-14T23:00:00"
    assert receipt["converted_utc"] == "1879-05-14T22:20:00+00:00"
    assert base["person_info"]["birth_timezone"] == "UTC"
    assert base["person_info"]["utc_datetime"] == receipt["converted_utc"]
    if variant == "germany":
        solar = result["midpoint_analysis"]["solar_arc_analysis"]
        assert solar["profile"]["elapsed_calendar_days"] == 0
        assert solar["profile"]["solar_arc_degrees"] == 0
        assert (
            solar["daily_meridian"]["birth_time_sensitivity"]["input_clock_basis"]
            == "local_mean_solar"
        )
    else:
        assert "1879-05-14T23:00:00（地方平太阳时）" in result["snapshot_text"]
        assert result["time_sensitivity"]["status"] == "not_assessed"


@HAS_SWE
@pytest.mark.parametrize("offset_microseconds", [-1, 1], ids=["before", "after"])
def test_historical_mean_solar_arc_orders_targets_with_the_same_native_tt_word(
    offset_microseconds,
) -> None:
    # 23:00 LMT minus 10 degrees east at 240 seconds per degree.
    center = datetime(1879, 5, 14, 22, 20, tzinfo=timezone.utc)
    result = calculate_germany_chart_analysis(
        birth_year=1879,
        birth_month=5,
        birth_day=14,
        birth_hour=23,
        birth_longitude=10,
        birth_latitude=53.55,
        birth_clock_basis="local_mean_solar",
        analysis_datetime=center + timedelta(microseconds=offset_microseconds),
        birth_time_uncertainty_minutes=0,
    )
    if offset_microseconds < 0:
        assert result["error_code"] == "validation_error"
        assert result["status_code"] == 400
        assert result["retryable"] is False
        assert result["error"] == (
            "Solar arc supports target instants 0..150 Julian key years after birth"
        )
        return
    else:
        pass

    solar = result["midpoint_analysis"]["solar_arc_analysis"]
    profile = solar["profile"]
    target_tt = solar["daily_meridian"]["profile"]["target_julian_day_tt"]
    days = Fraction(1, 86_400_000_000)
    assert profile["elapsed_calendar_days"] == float(days)
    assert profile["key_years"] == float(days / Fraction(1461, 4))
    assert target_tt == profile["birth_julian_day_tt"]
    assert profile["progressed_julian_day_tt"] == profile["birth_julian_day_tt"]


@HAS_SWE
def test_historical_mean_solar_conversion_keeps_native_seconds_before_rounding() -> (
    None
):
    wall = datetime(1894, 4, 18, 9, 15, 27)
    longitude = float.fromhex("0x1.5500000000000p-24")
    seconds = Fraction(27) - Fraction(longitude) * 240
    native_tt, native_ut1 = runtime.ephemeris_call(
        "utc_to_jd", 1894, 4, 18, 9, 15, float(seconds), runtime.swe.GREG_CAL
    )
    epoch, _ = resolve_solar_epoch(wall, longitude, "local_mean_solar")
    assert epoch.source_calendar is not None
    expected_day = (
        wall.toordinal() + Fraction(3442849, 2) + (9 * 3600 + 15 * 60 + seconds) / 86400
    )
    assert epoch.source_calendar.day == expected_day
    assert (epoch.time.jd_tt, epoch.time.jd_ut1) == (native_tt, native_ut1)
    assert epoch.utc_datetime == datetime(
        1894, 4, 18, 9, 15, 26, 999981, tzinfo=timezone.utc
    )


@HAS_SWE
@pytest.mark.parametrize("longitude, admitted", [(1 / 2048, False), (3 / 2048, True)])
def test_historical_solar_arc_uses_exact_mean_clock_at_the_rounded_label(
    longitude, admitted: bool
) -> None:
    wall = datetime(1894, 4, 18, 9, 15, 27, tzinfo=timezone.utc)
    target = wall - timedelta(microseconds=round(Fraction(longitude) * 240 * 1_000_000))
    result = calculate_germany_chart_analysis(
        birth_year=wall.year,
        birth_month=wall.month,
        birth_day=wall.day,
        birth_hour=wall.hour,
        birth_minute=wall.minute,
        birth_second=wall.second,
        birth_longitude=longitude,
        birth_latitude=41.5,
        birth_clock_basis="local_mean_solar",
        analysis_datetime=target,
        birth_time_uncertainty_minutes=0,
    )
    if not admitted:
        assert result["error_code"] == "validation_error"
        assert result["error"] == (
            "Solar arc supports target instants 0..150 Julian key years after birth"
        )
        return
    else:
        pass

    profile = result["midpoint_analysis"]["solar_arc_analysis"]["profile"]
    days = Fraction(1, 172_800_000_000)
    assert profile["elapsed_calendar_days"] == float(days)
    assert profile["key_years"] == float(days / Fraction(1461, 4))
    assert profile["progressed_julian_day_tt"] == profile["birth_julian_day_tt"]


@pytest.mark.parametrize(
    "conflict", [{"birth_timezone": "UTC"}, {"use_true_solar_time": True}]
)
@pytest.mark.parametrize("model", [AstroGermanyRequest, AstroChartPolyRequest])
def test_conflicting_clock_definitions_are_rejected(conflict, model) -> None:
    data = dict(
        birth_year=1879,
        birth_month=5,
        birth_day=14,
        birth_hour=23,
        birth_longitude=10,
        birth_latitude=53.55,
        birth_clock_basis="local_mean_solar",
        **conflict,
    )
    if model is AstroChartPolyRequest:
        data["chart_variant"] = "germany"
    else:
        pass
    with pytest.raises(ValidationError, match="Local solar birth clocks"):
        model.model_validate(data)


def test_ambiguous_original_clock_basis_is_not_guessed_from_a_label() -> None:
    with pytest.raises(ValidationError):
        AstroGermanyRequest.model_validate(
            dict(
                birth_year=1879,
                birth_month=5,
                birth_day=14,
                birth_hour=23,
                birth_longitude=10,
                birth_latitude=53.55,
                birth_clock_basis="OZ",
            )
        )


@pytest.mark.parametrize("variant", ["chart", "hellen_chart", "guolao_chart"])
def test_chart_variants_enforce_declared_solar_input_scope(variant: str) -> None:
    data = dict(
        birth_year=1879,
        birth_month=5,
        birth_day=14,
        birth_hour=23,
        birth_longitude=10,
        birth_latitude=53.55,
        birth_clock_basis="local_mean_solar",
        chart_variant=variant,
    )
    if variant == "guolao_chart":
        # Explicit admission replaces the former unsupported-feature gate;
        # other variants and invalid simultaneous civil zones still reject.
        assert AstroChartPolyRequest.model_validate(data).birth_clock_basis == (
            "local_mean_solar"
        )
        with pytest.raises(ValidationError):
            AstroChartPolyRequest.model_validate({**data, "birth_timezone": "UTC"})
        return
    else:
        pass
    with pytest.raises(ValidationError, match="Noncivil birth_clock_basis"):
        AstroChartPolyRequest.model_validate(data)


@HAS_SWE
def test_unrepresentable_utc_leap_second_is_not_shifted_to_an_adjacent_label() -> None:
    wall = datetime(2017, 1, 1)
    midnight = ephemeris_time(wall.replace(tzinfo=timezone.utc)).jd_tt
    during_leap_ut1 = ut1_from_tt(midnight - 0.5 / 86400)
    label = wall.toordinal() + 1721424.5
    longitude = (label - during_leap_ut1) * 360
    with pytest.raises(ValueError, match="leap second"):
        resolve_solar_birth_clock(wall, longitude, "local_mean_solar")


@HAS_SWE
def test_local_solar_clock_cli_flag_does_not_require_a_fake_civil_timezone(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = run(
        [
            "hamburg_midpoint_chart",
            "--birth-year",
            "1879",
            "--birth-month",
            "5",
            "--birth-day",
            "14",
            "--birth-hour",
            "23",
            "--birth-longitude",
            "10",
            "--birth-latitude",
            "53.55",
            "--birth-clock-basis",
            "local_mean_solar",
            "--fields",
            "base_chart.person_info",
            "--strict-fields",
            "--no-include-snapshot-text",
        ]
    )
    output = json.loads(capsys.readouterr().out)
    assert code == 0, output
    info = output["base_chart"]["person_info"]
    assert info["utc_datetime"] == "1879-05-14T22:20:00+00:00"
    assert info["clock_conversion"]["input_wall_datetime"] == "1879-05-14T23:00:00"


@HAS_SWE
@pytest.mark.parametrize(
    "wall,longitude", [(datetime(1, 1, 1), 180.0), (datetime(9999, 12, 31, 23), -180.0)]
)
def test_lmt_dates_outside_datetime_range_are_rejected_instead_of_wrapped(
    wall, longitude
) -> None:
    with pytest.raises(ValueError):
        resolve_solar_birth_clock(wall, longitude, "local_mean_solar")


def test_missing_astronomical_backend_cannot_fabricate_an_apparent_solar_instant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(runtime, "swe", None)
    with pytest.raises(ValueError, match="Swiss Ephemeris"):
        resolve_solar_birth_clock(
            datetime(1879, 5, 14, 23), 10.0, "local_apparent_solar"
        )
