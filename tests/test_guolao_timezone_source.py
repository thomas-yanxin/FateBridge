"""An unknown civil timezone must not become an astronomical UTC instant."""

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from fatebridge.core import guolao, guolao_timing
from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.services.astrology import calculate_core_chart_analysis
from fatebridge.utils.places import resolve_birth_place_context

CASE = dict(
    birth_year=2000,
    birth_month=1,
    birth_day=1,
    birth_hour=9,
    birth_minute=30,
    birth_longitude=121.47,
    birth_latitude=31.22,
)


@pytest.mark.parametrize("zone", ["UTC", "+08:00", "Asia/Shanghai"])
@pytest.mark.parametrize("solar", [False, True])
def test_explicit_timezone_including_utc_is_known_input(zone, solar):
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
def test_resolved_place_can_supply_timezone_without_moving_the_clock(place, zone):
    birth = build_astro_birth_info(**CASE, birth_place=place)
    assert birth.timezone_source == "birth_place"
    assert birth.timezone == zone
    inferred = calculate_core_chart_analysis(
        **CASE, birth_place=place, chart_variant="guolao_chart"
    )
    explicit = calculate_core_chart_analysis(
        **CASE, birth_place=place, birth_timezone=zone, chart_variant="guolao_chart"
    )
    assert "guolao" in inferred, inferred
    assert inferred == explicit


@pytest.mark.parametrize("place", [None, "未提供", "虚构的未知出生地", "通州区"])
@pytest.mark.parametrize("solar", [False, True])
def test_unresolved_timezone_rejects_before_native_ephemeris_calls(
    monkeypatch, place, solar
):
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
    result = calculate_core_chart_analysis(
        **CASE,
        birth_place=place,
        use_true_solar_time=solar,
        chart_variant="guolao_chart",
    )
    assert result["error_code"] == "validation_error"
    assert result["status_code"] == 400 and not result["retryable"]
    assert "坐标不能代替民用时区" in result["error"]
    assert "guolao" not in result


def test_direct_temporal_layer_rejects_unknown_birth_before_reading_a_payload():
    birth = build_astro_birth_info(**CASE)
    with pytest.raises(ValueError, match="未知出生时区"):
        guolao_timing.enrich_guolao_timing(
            {}, birth, datetime(2001, 1, 1, tzinfo=timezone.utc)
        )


def test_shared_position_only_consumer_keeps_its_existing_timezone_policy():
    # Suzhan shares the sky helper; Guolao's input policy belongs to its chart
    # and timing entry points, not to every caller of physical positions.
    from fatebridge.core.suzhan_astronomy import build_equatorial_mansions

    birth = build_astro_birth_info(**CASE)
    shared = build_equatorial_mansions(birth)
    explicit = build_equatorial_mansions(
        build_astro_birth_info(**CASE, birth_timezone="UTC")
    )
    assert shared == explicit


def test_a_known_mean_solar_record_does_not_masquerade_as_default_utc():
    # Shared builder provenance only; this does not enable noncivil Guolao input.
    birth = build_astro_birth_info(**CASE, birth_clock_basis="local_mean_solar")
    assert birth.timezone == "UTC"
    assert birth.timezone_source == "solar_clock_conversion"
    assert birth.clock_conversion is not None


def test_shared_default_stays_tagged_but_western_chart_requires_a_known_zone():
    # Position-only legacy construction remains distinguishable. The Western
    # chart entrypoint now requires an explicit or place-resolved civil zone.
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


def test_explicit_different_offsets_cannot_be_replaced_by_a_longitude_guess():
    utc = calculate_core_chart_analysis(
        **CASE, birth_timezone="UTC", chart_variant="guolao_chart"
    )
    utc8 = calculate_core_chart_analysis(
        **CASE, birth_timezone="+08:00", chart_variant="guolao_chart"
    )
    assert utc["person_info"]["utc_datetime"] == "2000-01-01T09:30:00+00:00"
    assert utc8["person_info"]["utc_datetime"] == "2000-01-01T01:30:00+00:00"
    assert utc["guolao"]["bodies"] != utc8["guolao"]["bodies"]
