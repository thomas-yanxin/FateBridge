"""Exact supplied-angle signs and public carriers with an analytic source.

The controlled source proves the governing-window rule, not real planetary
positions, a measured event date or an ephemeris accuracy bound.
"""

import math
from datetime import datetime, timezone
from fractions import Fraction

import pytest

from fatebridge.core.astro.physical_epoch import PhysicalEpoch
from fatebridge.core.astro.time_scales import ephemeris_time
from fatebridge.core.predictive import returns
from fatebridge.core.predictive._common import (
    build_natal_subject,
    build_predictive_birth_info,
    build_subject,
)
from tests.support.transports import SPECS, business, rest, surface_calls


@pytest.mark.parametrize(
    "moment",
    [
        datetime(1900, 1, 1, tzinfo=timezone.utc),
        datetime(1950, 6, 21, 12, tzinfo=timezone.utc),
        datetime(1969, 7, 20, 20, 17, tzinfo=timezone.utc),
        datetime(1972, 1, 1, tzinfo=timezone.utc),
        datetime(1985, 12, 31, 5, 15, tzinfo=timezone.utc),
        datetime(1990, 4, 6, 1, 33, tzinfo=timezone.utc),
        datetime(1999, 12, 31, 23, 59, tzinfo=timezone.utc),
        datetime(2000, 2, 29, 18, 15, tzinfo=timezone.utc),
        datetime(2024, 3, 20, 6, 30, tzinfo=timezone.utc),
        datetime(2026, 10, 22, tzinfo=timezone.utc),
        datetime(2050, 12, 21, 12, tzinfo=timezone.utc),
        datetime(2099, 12, 31, 23, 59, tzinfo=timezone.utc),
    ],
)
@pytest.mark.parametrize("zodiac", ["Tropic", "Sidereal"])
@pytest.mark.parametrize("key", ["solar_return", "lunar_return"])
def test_native_return_at_natal_epoch_retains_present_cycle(
    moment, zodiac, key, monkeypatch, tmp_path
):
    """Native identity at a known instant; not independent sky accuracy."""
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    natal = build_subject(
        name="explicit-return-identity-control",
        local_datetime=moment,
        longitude=0,
        latitude=40,
        timezone_name="UTC",
        house_system="W",
        zodiac_type=zodiac,
    )
    result = returns.build_return_payload(
        natal,
        analysis_datetime=moment,
        return_longitude=85.32,
        return_latitude=27.72,
        return_timezone="+05:45",
        include=[key],
    )[key]
    assert result["solver"]["julian_day_tt"] == ephemeris_time(moment).jd_tt
    assert (
        result["calculation_basis"]["julian_day_tt"]
        == result["solver"]["julian_day_tt"]
    )
    assert result["return_datetime_utc"] == moment.isoformat()
    assert datetime.fromisoformat(result["return_datetime"]) == moment
    assert result["solver"]["residual_arcseconds"] == 0
    assert result["solver"]["event_not_after_analysis"] is True


@pytest.mark.parametrize(
    "jd_tt",
    [
        2300000.123456789,
        2415020.500123456,
        2451545.123456789,
        2457754.5007949537,
        2488069.499123456,
    ],
)
def test_solved_tt_is_preserved_through_native_chart(jd_tt):
    """Supplied physical epochs remain operands; labels are representations."""
    epoch = PhysicalEpoch.from_tt(jd_tt)
    chart = build_subject(
        name="supplied-physical-epoch-control",
        physical_epoch=epoch,
        longitude=85.32,
        latitude=27.72,
        timezone_name="+05:45",
        house_system="W",
    )
    assert epoch.time.jd_tt == chart.julian_day_tt == jd_tt
    assert chart.calculation_basis["julian_day_tt"] == jd_tt
    assert chart.calculation_basis["julian_day_ut1"] == epoch.time.jd_ut1


@pytest.mark.parametrize("zone", ["UTC", "+05:45"])
def test_tt_leap_second_keeps_physical_chart_and_explicit_utc_label(zone):
    midnight = ephemeris_time(datetime(2017, 1, 1, tzinfo=timezone.utc)).jd_tt
    solved = midnight - 0.5 / 86400
    epoch = PhysicalEpoch.from_tt(solved)
    chart = build_subject(
        name="inserted-second-carrier-control",
        physical_epoch=epoch,
        longitude=0,
        latitude=40,
        timezone_name=zone,
        house_system="W",
    )
    assert chart.julian_day_tt == solved
    assert epoch.utc_datetime is None
    assert epoch.utc_is_leap_second is True
    assert epoch.utc_label.startswith("2016-12-31T23:59:60.")
    assert chart.iso_formatted_utc_datetime == epoch.utc_label
    assert chart.iso_formatted_local_datetime == (
        epoch.utc_label if zone == "UTC" else None
    )
    assert (
        chart.calculation_basis["utc_representation"]["datetime_representable"] is False
    )


@pytest.mark.parametrize("target", [0.0, 1.0, 10.0, 60.0, 120.0, 180.0, 359.0])
def test_adjacent_angle_signs_and_exact_zero(target):
    for longitude in (
        math.nextafter(target, -math.inf),
        target,
        math.nextafter(target, math.inf),
    ):
        exact = (Fraction(longitude) - Fraction(target) + 180) % 360 - 180
        assert returns._signed_offset(longitude, target) == float(exact)


@pytest.mark.parametrize(
    "longitude,target,expected",
    [
        (180.0, 0.0, -180.0),
        (0.0, 180.0, -180.0),
        (359.0, 179.0, -180.0),
        (179.0, 359.0, -180.0),
        (0.25, 359.75, 0.5),
        (359.75, 0.25, -0.5),
        (360.0, 0.0, 0.0),
        (0.0, 360.0, 0.0),
    ],
)
def test_antipodal_endpoint_convention_and_actual_wrap(longitude, target, expected):
    assert returns._signed_offset(longitude, target) == expected


@pytest.mark.parametrize(
    "body,period", [(returns.swe.SUN, 360), (returns.swe.MOON, 30)]
)
@pytest.mark.parametrize("phase", ["before", "at", "after"])
def test_governing_return_before_at_after_analysis(body, period, phase, monkeypatch):
    analysis, target = 2451545.0, 1.0
    rate, epsilon = Fraction(360, period), Fraction(1, 2**53)
    root = Fraction(analysis) + (
        epsilon / rate
        if phase == "before"
        else 0 if phase == "at" else -Fraction(math.ulp(analysis))
    )

    def longitude(body_id, jd, **kwargs):
        return float((Fraction(target) + rate * (Fraction(jd) - root)) % 360)

    monkeypatch.setattr(returns, "_longitude_tt", longitude)
    solved = returns.governing_return_tt(body, target, analysis)
    expected = root - period if phase == "before" else root
    assert abs(solved - float(expected)) <= 1e-9
    assert solved <= analysis


@pytest.mark.parametrize("body", [returns.swe.SUN, returns.swe.MOON])
def test_antipodal_discontinuity_is_not_a_return(body, monkeypatch):
    monkeypatch.setattr(
        returns,
        "_longitude_tt",
        lambda body, jd, **kwargs: (180 + (jd - 2451545.0) / 1000) % 360,
    )
    with pytest.raises(ValueError, match="No governing return"):
        returns.governing_return_tt(body, 0.0, 2451545.0)


@pytest.mark.parametrize("zodiac", ["Tropic", "Sidereal"])
@pytest.mark.parametrize(
    "tool,period,body",
    [("solarreturn", 360, returns.swe.SUN), ("lunarreturn", 30, returns.swe.MOON)],
)
def test_analytic_source_retains_governing_period_on_actual_three_adapters(
    tool, period, body, zodiac, monkeypatch, surface_calls
):
    payload = dict(
        birth_year=2000,
        birth_month=5,
        birth_day=3,
        birth_hour=0,
        birth_minute=0,
        birth_timezone="UTC",
        birth_longitude=0.0,
        birth_latitude=40.0,
        analysis_year=2002,
        analysis_month=1,
        analysis_day=1,
        analysis_hour=0,
        analysis_minute=0,
        house_system="W",
        zodiac_type=zodiac,
    )
    birth = build_predictive_birth_info(
        **{key: value for key, value in payload.items() if key.startswith("birth_")}
    )
    natal = build_natal_subject(birth, house_system="W", zodiac_type=zodiac)
    target = float(getattr(natal, "sun" if body == returns.swe.SUN else "moon").abs_pos)
    assert 0 < target < 128
    analysis_tt = ephemeris_time(datetime(2002, 1, 1, tzinfo=timezone.utc)).jd_tt
    epsilon = Fraction(target) - Fraction(math.nextafter(target, -math.inf))
    rate = Fraction(360, period)

    def longitude(body_id, jd, **kwargs):
        assert body_id == body
        return float(
            (Fraction(target) + rate * (Fraction(jd) - Fraction(analysis_tt)) - epsilon)
            % 360
        )

    monkeypatch.setattr(returns, "_longitude_tt", longitude)
    spec = SPECS[tool]
    fields = [f"{tool}.solver", f"{tool}.return_datetime_utc"]
    query = [("fields", field) for field in fields] + [
        ("strict_fields", "true"),
        ("include_snapshot_text", "false"),
        ("response_char_limit", 0),
    ]
    response, protocol, code, cli = surface_calls(
        spec,
        payload,
        params=query,
        options={
            "fields": fields,
            "strict_fields": True,
            "include_snapshot_text": False,
        },
        flags=["--fields", *fields, "--strict-fields"],
    )
    assert response.status_code == 200, response.text
    assert code == 0 and not protocol.is_error
    assert (
        business(response.json())
        == business(cli)
        == business(protocol.structured_content)
    )
    exact_previous = Fraction(analysis_tt) - period + epsilon / rate
    for result in (response.json(), cli, protocol.structured_content):
        solver = result[tool]["solver"]
        assert abs(solver["julian_day_tt"] - float(exact_previous)) <= math.ulp(
            analysis_tt
        )
        assert solver["event_not_after_analysis"] is True
