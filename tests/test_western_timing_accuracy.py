"""Independent timing references and invariants, not life-event validation."""

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.astro.time_scales import datetime_from_tt, ephemeris_time
from fatebridge.core.astrology_events import find_cardinal_ingress_utc
from fatebridge.core.ephemeris_runtime import preserve_ephemeris_path, swe
from fatebridge.core.predictive._common import (
    build_natal_subject,
    build_subject,
    point_attribute_name,
)
from fatebridge.core.predictive.primary_directions import (
    build_primary_direction_equatorial_context,
    build_reprojected_mundane_primary_direction_chart_layers,
    build_reprojected_primary_direction_chart_layers,
    point_equatorial_position,
)
from fatebridge.core.predictive.returns import build_return_payload, governing_return_tt
from fatebridge.core.ptolemy import build_ptolemy_layer

FIXTURES = Path(__file__).parent / "fixtures"
POSITIONS = json.loads((FIXTURES / "western-horizons.json").read_text())
RETURNS = json.loads((FIXTURES / "western-returns-horizons.json").read_text())
FORTUNE = json.loads(
    (FIXTURES / "western-ptolemy-fortune-robbins-1940.json").read_text()
)


def subject_at(when, *, zone="UTC", latitude=51.5, house="P", zodiac="Tropic"):
    return build_subject(
        name="fictional-audit",
        local_datetime=when,
        longitude=0.0,
        latitude=latitude,
        timezone_name=zone,
        house_system=house,
        zodiac_type=zodiac,
    )


def angular_error(a, b):
    return abs((a - b + 180) % 360 - 180)


@pytest.fixture
def moshier(monkeypatch, tmp_path):
    # Native fallback must pass the same independently fixed tolerance.
    from fatebridge.core.astro.ephemeris import _swisseph_planet_state

    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    with preserve_ephemeris_path():
        # Exercise the operator's real configuration path across ecliptic,
        # equatorial and supporting motion calls; split imported aliases can
        # otherwise make a supposed fallback test mix two physical models.
        result = _swisseph_planet_state("Moon", 2451545.0, julian_day_tt=2451545.0)
        assert result is not None and result[1] == "moshier"
        yield


@pytest.mark.parametrize("reference", POSITIONS["references"], ids=lambda r: r["body"])
def test_timing_positions_against_independent_nasa(reference, moshier):
    assert (
        hashlib.sha256(reference["response"]["result"].encode()).hexdigest()
        == reference["response_sha256"]
    )
    for row in reference["rows"]:
        chart = subject_at(datetime.fromisoformat(row["utc"]))
        point = getattr(chart, reference["body"].lower())
        assert (
            angular_error(point.abs_pos, row["apparent_ecliptic_longitude"]) * 3600
            <= POSITIONS["tolerance_arcseconds"]
        )
        assert (
            abs(point.latitude - row["apparent_ecliptic_latitude"]) * 3600
            <= POSITIONS["tolerance_arcseconds"]
        )


@pytest.mark.parametrize(
    "case", RETURNS["cases"], ids=lambda c: f"{c['planet']}-{c['case_id']}"
)
def test_return_against_independently_solved_nasa_event(case, moshier):
    natal = subject_at(datetime.fromisoformat(case["birth_utc"]))
    analysis = datetime.fromisoformat(case["analysis_utc"])
    key = "solar_return" if case["planet"] == "Sun" else "lunar_return"
    result = build_return_payload(
        natal,
        analysis_datetime=analysis,
        return_longitude=85.32,
        return_latitude=27.72,
        return_timezone="+05:45",
        include=[key],
    )[key]
    event = datetime.fromisoformat(result["return_datetime"])
    expected = datetime.fromisoformat(case["expected_return_utc"])
    assert (
        abs((event - expected).total_seconds())
        <= RETURNS["tolerances_seconds"][case["planet"]]
    )
    assert event <= analysis
    assert event.utcoffset() == timedelta(hours=5, minutes=45)
    assert result["solver"]["residual_arcseconds"] < 0.002
    assert result["solver"]["event_not_after_analysis"] is True
    assert result["calculation_basis"]["engine_backend"] == "fatebridge_swisseph_native"
    actual = result[case["planet"].lower()]["longitude"]
    assert actual == result["solver"]["solved_longitude"]
    assert angular_error(actual, result["solver"]["target_longitude"]) * 3600 < 0.002


def test_return_reference_recordings_and_fixed_tolerances():
    assert RETURNS["tolerances_seconds"] == {"Sun": 120, "Moon": 15}
    assert len(RETURNS["cases"]) == 6
    for recording in RETURNS["recordings"]:
        assert (
            hashlib.sha256(recording["response"]["result"].encode()).hexdigest()
            == recording["response_sha256"]
        )


@pytest.mark.parametrize("body,minimum_days", [(swe.SUN, 360), (swe.MOON, 25)])
def test_governing_return_switches_at_actual_event(body, minimum_days):
    analysis = ephemeris_time(datetime(2026, 1, 1, tzinfo=timezone.utc)).jd_tt
    root = governing_return_tt(body, 150.0, analysis)
    after = governing_return_tt(body, 150.0, root + 1 / 86400)
    before = governing_return_tt(body, 150.0, root - 1 / 86400)
    assert abs(after - root) * 86400 < 0.001
    assert root - before > minimum_days


def test_unbracketed_return_fails_instead_of_inventing_future_event(monkeypatch):
    monkeypatch.setattr(
        "fatebridge.core.predictive.returns._longitude_tt", lambda *a, **k: 123.0
    )
    with pytest.raises(ValueError, match="No governing return was bracketed"):
        governing_return_tt(swe.SUN, 150.0, 2461000.0)


def test_native_chart_preserves_fractional_seconds():
    instant = datetime(2024, 3, 20, 6, 30, tzinfo=timezone.utc)
    first = subject_at(instant)
    second = subject_at(instant + timedelta(seconds=0.5))
    elapsed = (second.moon.abs_pos - first.moon.abs_pos) / first.moon.speed * 86400
    assert elapsed == pytest.approx(0.5, abs=0.0001)
    assert angular_error(first.ascendant.abs_pos, second.ascendant.abs_pos) > 0.0001


@pytest.mark.parametrize("year", [1500, 1900, 1969, 1972, 2017, 2026, 2099])
def test_tt_civil_round_trip_uses_same_historical_and_future_policy(year):
    instant = datetime(year, 5, 17, 3, 12, 34, 500000, tzinfo=timezone.utc)
    restored = datetime_from_tt(ephemeris_time(instant).jd_tt)
    assert abs((restored - instant).total_seconds()) < 0.0002


def test_unrepresentable_utc_leap_second_is_explicit():
    midnight_tt = ephemeris_time(datetime(2017, 1, 1, tzinfo=timezone.utc)).jd_tt
    with pytest.raises(ValueError, match="UTC leap second"):
        datetime_from_tt(midnight_tt - 0.5 / 86400)


def test_polar_latitude_is_preserved_and_undefined_placidus_fails():
    instant = datetime(2024, 6, 21, 12, tzinfo=timezone.utc)
    whole_sign = subject_at(instant, latitude=80.0, house="W")
    assert whole_sign.lat == 80.0
    assert whole_sign.is_diurnal is True
    with pytest.raises(ValueError, match="Cannot compute P houses"):
        subject_at(instant, latitude=80.0)


@pytest.mark.parametrize("zodiac", ["Tropic", "Sidereal"])
@pytest.mark.parametrize(
    "builder",
    [
        build_reprojected_primary_direction_chart_layers,
        build_reprojected_mundane_primary_direction_chart_layers,
    ],
)
def test_zero_arc_direction_restores_original_chart(zodiac, builder):
    birth = build_astro_birth_info(
        birth_year=1990,
        birth_month=5,
        birth_day=17,
        birth_hour=15,
        birth_minute=30,
        birth_timezone="Asia/Shanghai",
        birth_longitude=121.47,
        birth_latitude=31.23,
    )
    natal = build_natal_subject(birth, zodiac_type=zodiac)
    points, _, _ = builder(birth, natal, arc_degrees=0)
    for name, directed in points.items():
        original = getattr(natal, point_attribute_name(name))
        assert angular_error(directed["absolute_degree"], original.abs_pos) <= 0.000051
    context = build_primary_direction_equatorial_context(birth)
    _, declination = point_equatorial_position("Medium_Coeli", natal, **context)
    assert abs(declination) > 1


@pytest.mark.parametrize("term", ["春分", "夏至", "秋分", "冬至"])
def test_cardinal_ingress_against_hong_kong_observatory(term):
    reference = json.loads((FIXTURES / "bazi-timing-hko-2026.json").read_text())
    expected = next(c["at"] for c in reference["cases"] if c["term"] == term)
    actual = find_cardinal_ingress_utc(2026, term)
    assert (
        abs((actual - datetime.fromisoformat(expected)).total_seconds())
        <= reference["tolerance_seconds"]
    )


@pytest.mark.parametrize("case", FORTUNE["cases"])
def test_robbins_iii10_fortune_uses_same_formula_day_and_night(case):
    layer = build_ptolemy_layer(
        {"Sun": case["Sun"], "Moon": case["Moon"]},
        case["sect"],
        tropical=True,
        ascendant=case["ascendant"],
    )
    assert layer["lot_of_fortune"]["longitude"] == case["expected_longitude"]
    assert layer["chapters"]["lot_of_fortune"] == "III.10 (Fortune formula only)"
    assert layer["lot_of_fortune"]["source_url"].endswith("3B%2A.html#10")


def test_robbins_fortune_wrap_and_missing_ascendant():
    positions = {"Sun": 350.0, "Moon": 10.0}
    assert (
        build_ptolemy_layer(positions, "night", tropical=True, ascendant=355)[
            "lot_of_fortune"
        ]["longitude"]
        == 15.0
    )
    assert (
        build_ptolemy_layer(positions, "night", tropical=True)["lot_of_fortune"] is None
    )


@pytest.mark.parametrize("semiarc", [0.0, 180.0, float("nan")])
def test_circumpolar_semiarc_is_not_clamped_into_fictitious_coordinates(semiarc):
    from fatebridge.core.predictive.primary_directions import (
        hour_angle_from_mundane_coordinate,
        mundane_semiarc_position,
    )

    with pytest.raises(ValueError, match="undefined for circumpolar"):
        mundane_semiarc_position(hour_angle=0, semiarc_degrees=semiarc)
    with pytest.raises(ValueError, match="undefined for circumpolar"):
        hour_angle_from_mundane_coordinate(90, semiarc_degrees=semiarc)


def test_sidereal_whole_sign_cusps_and_rates_match_actual_coordinate_system():
    instant = datetime(2026, 3, 20, 12, tzinfo=timezone.utc)
    first = subject_at(instant, zodiac="Sidereal", house="W")
    second = subject_at(instant + timedelta(seconds=10), zodiac="Sidereal", house="W")
    assert first.first_house.abs_pos % 30 == 0
    assert first.first_house.sign == first.ascendant.sign
    assert (
        second.sun.abs_pos - first.sun.abs_pos
    ) / first.sun.speed * 86400 == pytest.approx(10, abs=0.001)


def test_case_sensitive_swiss_sunshine_house_variant_is_preserved():
    chart = subject_at(datetime(2026, 3, 20, 12, tzinfo=timezone.utc), house="i")
    assert chart.houses_system_identifier == "i"


@pytest.mark.parametrize("month,day,hour", [(3, 10, 2), (11, 3, 1)])
def test_analysis_wall_clock_rejects_dst_gap_and_fold(month, day, hour):
    from fatebridge.core.predictive._common import build_analysis_datetime

    birth = build_astro_birth_info(
        birth_year=1990,
        birth_month=1,
        birth_day=1,
        birth_hour=12,
        birth_timezone="America/New_York",
        birth_longitude=-74,
        birth_latitude=40.7,
    )
    with pytest.raises(ValueError, match="分析钟时"):
        build_analysis_datetime(birth, 2024, month, day, hour, 30)
