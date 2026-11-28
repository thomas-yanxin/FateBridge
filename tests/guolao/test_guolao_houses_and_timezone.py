"""Guolao whole-sign houses and civil-timezone input contracts."""

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.guolao import guolao, guolao_timing
from fatebridge.core.sukuyo.astronomy import build_equatorial_mansions
from fatebridge.services.astrology import calculate_core_chart_analysis
from fatebridge.services.guolao import calculate_guolao_chart
from fatebridge.utils.places import resolve_birth_place_context
from tests.fixtures.surface_payloads import astro_payload

CASE = dict(
    birth_year=2000,
    birth_month=1,
    birth_day=1,
    birth_hour=9,
    birth_minute=30,
    birth_longitude=121.47,
    birth_latitude=31.22,
)


def _chart(**changes):
    return calculate_guolao_chart(
        **{**astro_payload(), "use_true_solar_time": False, **changes}
    )


@pytest.mark.parametrize("zodiac_type", ["Tropic", "Sidereal"])
@pytest.mark.parametrize("hour", [0, 9, 18])
def test_whole_sign_cusps_and_planet_houses_obey_the_sign_definition(
    zodiac_type: str, hour: int
) -> None:
    result = _chart(house_system=0, zodiac_type=zodiac_type, birth_hour=hour)
    asc_sign = int(result["angles"]["ascendant"]["longitude"] // 30)
    expected = [((asc_sign + i) % 12) * 30.0 for i in range(12)]
    assert [h["cusp_longitude"] for h in result["houses"]] == expected
    for planet in result["planets"]:
        sign = int(planet["longitude"] // 30)
        assert planet["house"] == (sign - asc_sign) % 12 + 1


def test_sidereal_fix_corrects_the_previously_wrong_fixture_planet_houses() -> None:
    result = _chart(house_system=0, zodiac_type="Sidereal")
    planets = {p["id"]: p for p in result["planets"]}
    assert 60 < planets["Jupiter"]["longitude"] < 90
    assert planets["Jupiter"]["house"] == 1
    assert planets["Sun"]["house"] == 10
    assert planets["Mercury"]["house"] == 11
    assert planets["Mars"]["house"] == 8


@pytest.mark.parametrize("zodiac_type", ["Tropic", "Sidereal"])
@pytest.mark.parametrize("house_system", range(1, 9))
def test_reference_house_choice_cannot_change_source_functional_palaces(
    house_system, zodiac_type: str
) -> None:
    whole = _chart(house_system=0, zodiac_type=zodiac_type)
    unequal = _chart(house_system=house_system, zodiac_type=zodiac_type)
    assert "error" not in whole and "error" not in unequal
    assert unequal["chart_profile"]["house_system_code"] == house_system
    profile = unequal["guolao"]["profile"]
    is_sidereal = zodiac_type == "Sidereal"
    assert profile["astronomical_house_frame"] == (
        "selected_lahiri_sidereal_zodiac" if is_sidereal else "tropical_zodiac"
    )
    assert profile["astronomical_house_method"] == (
        "swisseph_houses_ex_sidereal_lahiri"
        if is_sidereal
        else "swisseph_houses_ex_tropical"
    )
    assert whole["guolao"]["bodies"] == unequal["guolao"]["bodies"]
    assert whole["guolao"]["life_palace"] == unequal["guolao"]["life_palace"]
    assert whole["guolao"]["palaces"] == unequal["guolao"]["palaces"]
    assert whole["houses"] != unequal["houses"]


@pytest.mark.parametrize("zone", ["UTC", "+08:00", "Asia/Shanghai"])
@pytest.mark.parametrize("solar", [False, True])
def test_explicit_timezone_including_utc_is_known_input(zone: str, solar: bool) -> None:
    birth = build_astro_birth_info(
        **CASE, birth_timezone=zone, use_true_solar_time=solar, preserve_instant=True
    )
    assert birth.timezone_source == "birth_timezone"
    assert birth.timezone == zone
    result = guolao.build_chart(birth)
    assert result["person_info"]["birth_timezone"] == zone
    assert result["person_info"]["utc_datetime"] == birth.utc_datetime.isoformat()
    assert not result["guolao"]["validation"]["full_marks_established"]


@pytest.mark.parametrize(
    "place,zone", [("上海", "Asia/Shanghai"), ("New York", "America/New_York")]
)
def test_resolved_place_can_supply_timezone_without_moving_the_clock(
    place: str, zone: str
) -> None:
    birth = build_astro_birth_info(**CASE, birth_place=place)
    assert birth.timezone_source == "birth_place"
    assert birth.timezone == zone
    inferred = calculate_guolao_chart(
        **CASE, birth_place=place, use_true_solar_time=False
    )
    explicit = calculate_guolao_chart(
        **CASE, birth_place=place, birth_timezone=zone, use_true_solar_time=False
    )
    assert "guolao" in inferred, inferred
    assert inferred == explicit


@pytest.mark.parametrize("place", [None, "未提供", "虚构的未知出生地", "通州区"])
@pytest.mark.parametrize("solar", [False, True])
def test_unresolved_timezone_rejects_before_native_ephemeris_calls(
    monkeypatch: pytest.MonkeyPatch, place: str | None, solar: bool
) -> None:
    assert resolve_birth_place_context(place).timezone is None
    birth = build_astro_birth_info(
        **CASE, birth_place=place, use_true_solar_time=solar, preserve_instant=True
    )
    assert birth.timezone_source == "default_utc"

    def forbidden(*args, **kwargs):
        pytest.fail(
            "an assumed timezone must be rejected before a native sky is computed"
        )

    monkeypatch.setattr(guolao.runtime, "ephemeris_call", forbidden)
    with pytest.raises(ValueError, match="birth_timezone"):
        guolao.build_chart(birth)
    result = calculate_guolao_chart(
        **CASE,
        birth_place=place,
        use_true_solar_time=solar,
    )
    assert result["error_code"] == "validation_error"
    assert result["status_code"] == 400 and not result["retryable"]
    assert "坐标不能代替民用时区" in result["error"]
    assert "guolao" not in result


def test_direct_temporal_layer_rejects_unknown_birth_before_reading_a_payload() -> None:
    birth = build_astro_birth_info(**CASE)
    with pytest.raises(ValueError, match="未知出生时区"):
        guolao_timing.enrich_guolao_timing(
            {}, birth, datetime(2001, 1, 1, tzinfo=timezone.utc)
        )


def test_shared_position_only_consumer_keeps_its_existing_timezone_policy() -> None:
    birth = build_astro_birth_info(**CASE)
    shared = build_equatorial_mansions(birth)
    explicit = build_equatorial_mansions(
        build_astro_birth_info(**CASE, birth_timezone="UTC")
    )
    assert shared == explicit


def test_a_known_mean_solar_record_does_not_masquerade_as_default_utc() -> None:
    birth = build_astro_birth_info(**CASE, birth_clock_basis="local_mean_solar")
    assert birth.timezone == "UTC"
    assert birth.timezone_source == "solar_clock_conversion"
    assert birth.clock_conversion is not None


def test_shared_default_stays_tagged_but_western_chart_requires_a_known_zone() -> None:
    birth = build_astro_birth_info(**CASE)
    assert birth.timezone == "UTC" and birth.timezone_source == "default_utc"
    known = build_astro_birth_info(**CASE, birth_timezone="UTC")
    assert replace(known, latitude=40).timezone_source == "birth_timezone"
    missing = calculate_core_chart_analysis(**CASE, chart_variant="chart")
    assert missing["error_code"] == "validation_error" and missing["status_code"] == 400
    explicit = calculate_core_chart_analysis(
        **CASE, chart_variant="chart", birth_timezone="UTC"
    )
    assert explicit["person_info"]["timezone_source"] == "birth_timezone"
    assert "error" not in explicit


def test_explicit_different_offsets_cannot_be_replaced_by_a_longitude_guess() -> None:
    utc = calculate_guolao_chart(
        **CASE, birth_timezone="UTC", use_true_solar_time=False
    )
    utc8 = calculate_guolao_chart(
        **CASE, birth_timezone="+08:00", use_true_solar_time=False
    )
    assert utc["person_info"]["utc_datetime"] == "2000-01-01T09:30:00+00:00"
    assert utc8["person_info"]["utc_datetime"] == "2000-01-01T01:30:00+00:00"
    assert utc["guolao"]["bodies"] != utc8["guolao"]["bodies"]
