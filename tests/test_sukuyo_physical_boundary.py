"""Keep the physical epoch when a supported local/host day has UTC year zero."""

from datetime import datetime, timedelta, timezone

import pytest

from fatebridge.core import almanac, guolao
from fatebridge.core.astro import runtime
from fatebridge.core.astro.clock_observation import observer
from fatebridge.core.local_techniques.suzhan import build_suzhan_result
from fatebridge.services.divination import calculate_suzhan_analysis
from fatebridge.utils.civil_time import utc_calendar, utc_ordering_key
from tests.test_sukuyo_transports import (
    test_calendar_and_relations_across_all_real_transports as run_transport_check,
)

BASIS = "japanese_naoj_historical_utc09"
PAYLOAD = dict(
    date="0001-01-01",
    time="00:19:00",
    zone="Asia/Tokyo",
    calendar_basis=BASIS,
)


@pytest.mark.parametrize("mode", [0, 1])
def test_both_full_chart_modes_preserve_the_unrepresentable_utc_epoch(mode):
    result = calculate_suzhan_analysis(**PAYLOAD, szchart=mode)
    sky = result["astronomy"]
    assert result["chart"]["ok"]
    assert sky["utc_datetime"] == "0000-12-31T15:00:01+00:00"
    calendar = result["sukuyo"]["calendar"]
    assert calendar["calendar_date"] == "0001-01-01"
    assert (calendar["lunar_year"], calendar["lunar_month"], calendar["lunar_day"]) == (
        0,
        11,
        20,
    )
    assert calendar["natal_su27"] == "轸"
    assert not calendar["calendar_reference"]["historical_local_time_reconstruction"]
    assert {b["id"] for b in sky["bodies"]} == set(guolao.CN)
    assert len(sky["boundaries"]) == 28
    assert not sky["classical_boundary_acceptance"]
    assert (
        "物理时刻参考标签（UTC记法）：0000-12-31T15:00:01+00:00"
        in result["snapshot_text"]
    )
    assert "TT儒略日" in result["snapshot_text"]
    assert "同一时刻；年编号跨界不改写出生输入" in result["snapshot_text"]
    assert "不能视为已确认地点" in result["snapshot_text"]
    assert "未建立现实预测效力；未获权威认证" in result["snapshot_text"]
    # An independent direct call checks the time normalization and seven
    # coordinates against the same declared native numerical engine. It is
    # not an independent physical observation or ancient-mansion oracle.
    swe = runtime.swe
    tt, ut1 = runtime.ephemeris_call("utc_to_jd", 0, 12, 31, 15, 0, 1.0, swe.GREG_CAL)
    assert sky["julian_day_tt"] == tt
    assert sky["julian_day_ut1"] == ut1
    flags = swe.FLG_SWIEPH | swe.FLG_SPEED | swe.FLG_EQUATORIAL
    for body in sky["bodies"]:
        native, _ = runtime.ephemeris_call(
            "calc", tt, getattr(swe, body["id"].upper()), flags
        )
        assert body["right_ascension"] == native[0]
        assert body["declination"] == native[1]


@pytest.mark.parametrize("mode", [0, 1])
def test_equivalent_second_offset_keeps_the_complete_sky_and_chart(mode):
    named = calculate_suzhan_analysis(**PAYLOAD, szchart=mode)
    fixed = calculate_suzhan_analysis(**{**PAYLOAD, "zone": "+09:18:59"}, szchart=mode)
    assert named["astronomy"] == fixed["astronomy"]
    assert named["chart"] == fixed["chart"]


@pytest.mark.parametrize("mode", [0, 1])
def test_exact_host_boundary_and_previous_second_are_not_clipped(mode):
    with pytest.raises(ValueError, match="超出可表示"):
        build_suzhan_result(**{**PAYLOAD, "time": "00:18:58"}, szchart=mode)
    boundary = calculate_suzhan_analysis(
        **{**PAYLOAD, "time": "00:18:59"}, szchart=mode
    )
    assert boundary["astronomy"]["utc_datetime"] == "0000-12-31T15:00:00+00:00"
    assert boundary["sukuyo"]["calendar"]["calendar_date"] == "0001-01-01"


@pytest.mark.parametrize("clock", ["01:30:00", "02:30:00"])
def test_clock_validation_still_rejects_folds_and_gaps(clock):
    day = "2025-11-02" if clock == "01:30:00" else "2025-03-09"
    with pytest.raises(ValueError):
        build_suzhan_result(date=day, time=clock, zone="America/New_York")


def test_clock_trace_labels_the_normalized_utc_instead_of_the_local_carrier():
    records = []
    token = observer.set(records.append)
    try:
        calculate_suzhan_analysis(**PAYLOAD)
    finally:
        observer.reset(token)
    direct = [
        r
        for r in records
        if r["kind"] == "civil_to_tt_ut1"
        and r["native_utc_to_jd"] == [0, 12, 31, 15, 0, 1.0, runtime.swe.GREG_CAL]
    ]
    assert direct
    assert all(r["utc_label"] == "0000-12-31T15:00:01+00:00" for r in direct)


def test_supplied_zero_coordinates_are_preserved_as_explicit_input():
    result = calculate_suzhan_analysis(**PAYLOAD, gps_lat=0, gps_lon=0)
    assert result["params"]["birthLatitude"] == 0
    assert result["params"]["birthLongitude"] == 0
    assert "沿用默认坐标" not in result["snapshot_text"]


def test_year_pillar_comparison_keeps_exact_instants_without_datetime_utc(monkeypatch):
    zone = "+09:18:59"
    offset = timezone(timedelta(hours=9, minutes=18, seconds=59))
    boundary = datetime(1, 1, 1, 0, 19, tzinfo=offset)
    term = almanac.SolarTerm(
        "立春", boundary, "0001-01-01", "", resolution_provider="swiss"
    )
    monkeypatch.setattr(almanac, "get_solar_terms_for_year", lambda *a: [term])
    monkeypatch.setattr(almanac, "require_calculated_solar_term", lambda *a: None)
    assert utc_calendar(boundary).as_datetime() is None
    assert almanac.get_bazi_year(boundary - timedelta(microseconds=1), zone) == 0
    assert almanac.get_bazi_year(boundary, zone) == 1
    assert almanac.get_bazi_year(boundary + timedelta(microseconds=1), zone) == 1


@pytest.mark.parametrize("offset", [-12, 0, 14])
def test_integer_instant_order_agrees_with_representable_utc(offset):
    instant = datetime(2025, 2, 3, 23, 1, 2, 345678, timezone(timedelta(hours=offset)))
    universal = instant.astimezone(timezone.utc)
    assert utc_ordering_key(instant) == utc_ordering_key(universal)
    assert utc_ordering_key(instant - timedelta(microseconds=1)) < utc_ordering_key(
        universal
    )


@pytest.mark.parametrize("mode", [0, 1])
def test_full_suzhan_boundary_across_actual_rest_native_mcp_cli(
    monkeypatch, capsys, mode
):
    run_transport_check(
        monkeypatch,
        capsys,
        "suzhan",
        {**PAYLOAD, "szchart": mode},
        ["astronomy", "chart", "sukuyo", "validation", "rulesets"],
    )
