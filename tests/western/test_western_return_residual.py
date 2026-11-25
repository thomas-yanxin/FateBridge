"""Exact supplied-angle signs, public carriers and original native root cases.

The controlled source proves the governing-window rule, not real planetary
positions, a measured event date or an ephemeris accuracy bound.
"""

import hashlib
import json
import math
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path

import pytest

from fatebridge.core.astro.physical_epoch import PhysicalEpoch
from fatebridge.core.astro.time_scales import ephemeris_time
from fatebridge.core.astro.tt_epoch import TTInstant
from fatebridge.core.predictive import returns
from fatebridge.core.predictive._common import (
    build_natal_subject,
    build_predictive_birth_info,
    build_subject,
)
from tests.support.transports import SPECS, business


@pytest.mark.local_data
def test_native_returns_resolve_original_interior_points(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fatebridge.core import ephemeris_runtime

    reference = json.loads(
        (
            Path(__file__).parents[1] / "data/native_return_crossings_swisseph_v1.json"
        ).read_text()
    )
    ephe = Path(__file__).parents[2] / "ephe"
    for filename in ("sepl_18.se1", "semo_18.se1"):
        assert hashlib.sha256((ephe / filename).read_bytes()).hexdigest() == (
            reference["source_reference"]["native_source_sha256"][filename]
        )
    # The original source files are local dependencies, excluded from CI.
    # Restore the environment before restoring the caller's native path.
    with ephemeris_runtime.preserve_ephemeris_path(), monkeypatch.context() as native:
        native.setenv("SE_EPHE_PATH", str(ephe))
        native.delenv("FATEBRIDGE_JPL_FILE", raising=False)
        returns.swe.set_ephe_path(str(ephe))
        for row in reference["cases"]:
            body = returns.swe.SUN if row["body"] == "sun" else returns.swe.MOON
            # Replay the author's original query independently of the candidate.
            crossing = (
                returns.swe.solcross if row["body"] == "sun" else returns.swe.mooncross
            )
            flags = returns.swe.FLG_SWIEPH | returns.swe.FLG_SPEED
            author_tt = crossing(row["target_longitude"], row["author_start_tt"], flags)
            author_coordinates, author_flags = returns.swe.calc(author_tt, body, flags)
            author = returns._longitude_tt(body, author_tt)
            assert author.hex() == float(author_coordinates[0]).hex(), row["id"]
            assert author_flags == row["author_flags"], row["id"]
            solved = returns.governing_return_tt(
                body, row["target_longitude"], row["analysis_tt"]
            )
            actual = returns._longitude_tt(body, solved)
            residual = (
                Fraction(actual) - Fraction(row["target_longitude"]) + 180
            ) % 360 - 180
            author_residual = (
                Fraction(author) - Fraction(row["target_longitude"]) + 180
            ) % 360 - 180
            assert abs(residual) <= abs(author_residual), row["id"]
            assert solved <= row["analysis_tt"], row["id"]


def test_native_subject_retains_the_source_tt_in_its_physical_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import importlib

    import erfa

    attitude_module = importlib.import_module("fatebridge.core.astro.earth_attitude")
    physical = attitude_module.physical_equator
    reduction = attitude_module.equatorial_reduction
    targets, source_epochs = [], []

    def observe_target(module, jd_ut1, *, julian_day_tt=None):
        result = physical(module, jd_ut1, julian_day_tt=julian_day_tt)
        targets.append(result)
        return result

    def observe_source(tt, *args, **kwargs):
        source_epochs.append(TTInstant.from_value(tt).days)
        return reduction(tt, *args, **kwargs)

    monkeypatch.setattr(attitude_module, "physical_equator", observe_target)
    monkeypatch.setattr(attitude_module, "equatorial_reduction", observe_source)
    expected = Fraction(26397351585456151, 10800000000)
    subject = build_subject(
        name="original-retained-TT-control",
        local_datetime=datetime(1979, 11, 21, 17, 17, 13, 465208, tzinfo=timezone.utc),
        longitude=120,
        latitude=30,
        timezone_name="UTC",
        house_system="P",
    )
    assert subject.tt.days == expected
    assert subject.julian_day_tt == float(expected)
    high = float(expected)
    reference = tuple(
        tuple(float(value) for value in row)
        for row in erfa.pnm06a(high, float(expected - Fraction(high)))
    )
    assert targets and all(item.tt.days == expected for item in targets)
    assert all(item.matrix == reference for item in targets)
    # The native ray must still be decoded at the SDK's actual scalar epoch.
    assert source_epochs and all(value == Fraction(high) for value in source_epochs)


@pytest.mark.parametrize("zodiac", ["Tropic", "Sidereal"])
@pytest.mark.parametrize("key", ["solar_return", "lunar_return"])
def test_native_return_at_natal_epoch_retains_present_cycle(
    zodiac: str, key: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Native identity at a known instant; not independent sky accuracy."""
    moments = (
        datetime(1900, 1, 1, tzinfo=timezone.utc),
        datetime(1972, 1, 1, tzinfo=timezone.utc),
        datetime(2000, 2, 29, 18, 15, tzinfo=timezone.utc),
        datetime(2099, 12, 31, 23, 59, tzinfo=timezone.utc),
    )
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    for moment in moments:
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


@pytest.mark.local_data
@pytest.mark.parametrize(
    "tool, birth_zone, birth_hour, birth_minute, analysis_minute, display_zone, utc, local",
    [
        pytest.param(
            "solarreturn",
            "Etc/GMT+12",
            12,
            0,
            0,
            "Etc/GMT+12",
            "+010000-01-01T00:00:00+00:00",
            "9999-12-31T12:00:00-12:00",
            id="exact-cutoff-extended-utc",
        ),
        pytest.param(
            "lunarreturn",
            "Etc/GMT+12",
            12,
            0,
            1,
            "Etc/GMT+12",
            "+010000-01-01T00:00:00.000014+00:00",
            "9999-12-31T12:00:00.000014-12:00",
            id="numeric-root-extended-utc",
        ),
        pytest.param(
            "lunarreturn",
            "UTC",
            23,
            59,
            59,
            "Etc/GMT-14",
            "9999-12-31T23:59:00+00:00",
            None,
            id="true-local-overflow-keeps-utc",
        ),
    ],
)
def test_returns_project_at_civil_year_limit(
    tool: str,
    birth_zone: str,
    birth_hour: int,
    birth_minute: int,
    analysis_minute: int,
    display_zone: str,
    utc: str,
    local: str | None,
    rest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ephe = Path(__file__).parents[2] / "ephe"
    monkeypatch.setenv("SE_EPHE_PATH", str(ephe))
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    response = rest.post(
        SPECS[tool].rest_path,
        params={"include_snapshot_text": "false", "response_char_limit": 0},
        json=dict(
            birth_year=9999,
            birth_month=12,
            birth_day=31,
            birth_hour=birth_hour,
            birth_minute=birth_minute,
            birth_timezone=birth_zone,
            birth_longitude=0,
            birth_latitude=40,
            analysis_year=9999,
            analysis_month=12,
            analysis_day=31,
            analysis_hour=birth_hour,
            analysis_minute=analysis_minute,
            return_timezone=display_zone,
            house_system="W",
        ),
    )
    assert response.status_code == 200, response.text
    result = response.json()[tool]
    assert result["calculation_basis"]["ephemeris_model"] == "swieph"
    assert result["return_datetime_utc"] == utc
    assert result.get("return_datetime") == local
    assert result["solver"]["event_not_after_analysis"] is True
    assert result["solver"]["residual_arcseconds"] == 0


def test_return_summary_preserves_utc_when_display_zone_has_no_local_clock(
    rest, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # IANA 2026f marks the display zone unspecified during the 1994 closure.
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    payload = dict(
        birth_year=1994,
        birth_month=7,
        birth_day=1,
        birth_hour=12,
        birth_minute=0,
        birth_timezone="UTC",
        birth_longitude=0,
        birth_latitude=51.5,
        analysis_year=1994,
        analysis_month=7,
        analysis_day=1,
        analysis_hour=12,
        analysis_minute=0,
        return_timezone="Antarctica/Vostok",
        house_system="W",
    )
    response = rest.post(
        SPECS["western_timing_analysis"].rest_path,
        json=payload,
        params={"include_snapshot_text": "false", "response_char_limit": 0},
    )
    assert response.status_code == 200, response.text
    result = response.json()

    utc = "1994-07-01T12:00:00+00:00"
    assert f"太阳返照 {utc}，月返 {utc}，" in result["summary"]
    for key in ("solar_return", "lunar_return"):
        event = result["returns"][key]
        assert event.get("return_datetime") is None
        assert event["return_datetime_utc"] == utc
        assert event["solver"]["julian_day_tt"] == 2449535.0007081483
        assert event["solver"]["residual_arcseconds"] == 0

    # Single-field displays carry the instant with an unknown local offset.
    utc_with_unknown_offset = "1994-07-01T12:00:00Z"
    assert (
        result["transits"]["current_transit"]["analysis_datetime"]
        == utc_with_unknown_offset
    )
    given_year = result["directions"]["given_year"]
    assert given_year["analysis_datetime"] == utc_with_unknown_offset
    assert given_year["year_start"] == utc_with_unknown_offset
    assert given_year["year_end"] == "1995-07-01T19:00:00+07:00"
    first_month = given_year["monthly_profections"][0]
    assert first_month["start"] == utc_with_unknown_offset
    assert first_month["end"] == "1994-07-31T22:00:00Z"
    assert first_month["active"] is True


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
def test_solved_tt_is_preserved_through_native_chart(jd_tt: float) -> None:
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


@pytest.mark.parametrize(
    "zone,expected_local",
    [
        ("UTC", "2016-12-31T23:59:60.{fraction}+00:00"),
        ("+05:45", "2017-01-01T05:44:60.{fraction}+05:45"),
        ("+00:00:30", None),
    ],
)
@pytest.mark.parametrize("at_start", [False, True], ids=["interior", "start"])
def test_tt_leap_second_keeps_physical_chart_and_explicit_utc_label(
    zone: str, expected_local: str | None, at_start: bool
) -> None:
    if at_start:
        # IERS Bulletin C52 puts the insertion 68.184 TT seconds after
        # the nominal 2017-01-01 midnight JD (36 s TAI−UTC plus 32.184 s).
        solved = TTInstant(Fraction(4915509, 2) + Fraction(68184, 1000) / 86400)
        fraction = "000000"
    else:
        midnight = ephemeris_time(datetime(2017, 1, 1, tzinfo=timezone.utc)).jd_tt
        solved = TTInstant.from_float(midnight - 0.5 / 86400)
        fraction = "499996"
    epoch = PhysicalEpoch.from_tt(solved)
    chart = build_subject(
        name="inserted-second-carrier-control",
        physical_epoch=epoch,
        longitude=0,
        latitude=40,
        timezone_name=zone,
        house_system="W",
    )
    assert chart.tt == solved
    assert chart.julian_day_tt == solved.as_float()
    assert epoch.utc_datetime is None
    assert epoch.utc_is_leap_second is True
    assert epoch.utc_label == f"2016-12-31T23:59:60.{fraction}+00:00"
    assert chart.iso_formatted_utc_datetime == epoch.utc_label
    assert chart.iso_formatted_local_datetime == (
        expected_local.format(fraction=fraction) if expected_local else None
    )
    assert (
        chart.calculation_basis["utc_representation"]["datetime_representable"] is False
    )


def test_adjacent_angle_signs_and_exact_zero() -> None:
    for target in (0.0, 1.0, 10.0, 60.0, 120.0, 180.0, 359.0):
        for longitude in (
            math.nextafter(target, -math.inf),
            target,
            math.nextafter(target, math.inf),
        ):
            exact = (Fraction(longitude) - Fraction(target) + 180) % 360 - 180
            assert returns._signed_offset(longitude, target) == float(exact)


def test_antipodal_endpoint_convention_and_actual_wrap() -> None:
    cases = [
        (180.0, 0.0, -180.0),
        (0.0, 180.0, -180.0),
        (359.0, 179.0, -180.0),
        (179.0, 359.0, -180.0),
        (0.25, 359.75, 0.5),
        (359.75, 0.25, -0.5),
        (360.0, 0.0, 0.0),
        (0.0, 360.0, 0.0),
    ]
    for longitude, target, expected in cases:
        assert returns._signed_offset(longitude, target) == expected


def test_governing_return_before_at_after_analysis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    analysis, target = 2451545.0, 1.0
    for body, period in ((returns.swe.SUN, 360), (returns.swe.MOON, 30)):
        rate, epsilon = Fraction(360, period), Fraction(1, 2**53)
        for phase in ("before", "at", "after"):
            root = Fraction(analysis) + (
                epsilon / rate
                if phase == "before"
                else 0 if phase == "at" else -Fraction(math.ulp(analysis))
            )

            def longitude(body_id, jd, _rate=rate, _root=root, **kwargs):
                return float((Fraction(target) + _rate * (Fraction(jd) - _root)) % 360)

            with monkeypatch.context() as mp:
                mp.setattr(returns, "_longitude_tt", longitude)
                solved = returns.governing_return_tt(body, target, analysis)
            expected = root - period if phase == "before" else root
            assert abs(solved - float(expected)) <= 1e-9
            assert solved <= analysis


@pytest.mark.parametrize("body", [returns.swe.SUN, returns.swe.MOON])
def test_antipodal_discontinuity_is_not_a_return(
    body, monkeypatch: pytest.MonkeyPatch
) -> None:
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
    tool: str,
    period: int,
    body,
    zodiac: str,
    monkeypatch: pytest.MonkeyPatch,
    rest,
    surface_calls,
) -> None:
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
    if tool == "solarreturn" and zodiac == "Tropic":
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
        outputs = (response.json(), cli, protocol.structured_content)
        assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    else:
        response = rest.post(spec.rest_path, json=payload, params=query)
        assert response.status_code == 200, response.text
        outputs = (response.json(),)
    exact_previous = Fraction(analysis_tt) - period + epsilon / rate
    for result in outputs:
        solver = result[tool]["solver"]
        assert abs(solver["julian_day_tt"] - float(exact_previous)) <= math.ulp(
            analysis_tt
        )
        assert solver["event_not_after_analysis"] is True
