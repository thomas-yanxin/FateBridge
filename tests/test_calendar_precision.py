"""Regressions for civil/solar clocks, timezone offsets and explicit dates."""

from datetime import datetime, timedelta

import pytest

from fatebridge.core.almanac import get_solar_terms_for_year, localize_datetime
from fatebridge.core.calendar import BaZiCalendar
from fatebridge.core.local_techniques.chart import _build_metaphysics_seed
from fatebridge.core.timing import TimingAnalysis
from fatebridge.services.bazi import _resolve_analysis_date, calculate_bazi_birth
from fatebridge.services.birth_context import (
    build_birth_computation_context as _build_birth_computation_context,
)
from fatebridge.services.calendar_tools import calculate_nongli_time
from fatebridge.services.metaphysics import _build_analysis_seed, _build_person_seed
from fatebridge.services.timing import calculate_dayun_analysis
from fatebridge.utils.birth_input import create_person_info
from fatebridge.utils.timezones import parse_timezone_name


def _person(moment: datetime, *, longitude: float = 116.4074):
    return create_person_info(
        moment.year,
        moment.month,
        moment.day,
        moment.hour,
        gender="男",
        birth_minute=moment.minute,
        birth_timezone="Asia/Shanghai",
        birth_longitude=longitude,
        use_true_solar_time=True,
    )


@pytest.mark.parametrize("term_name", ["立春", "惊蛰", "清明", "立夏", "小寒"])
@pytest.mark.parametrize("direction", [-1, 1])
def test_solar_adjustment_does_not_move_seasonal_boundary(term_name, direction):
    term = next(
        term
        for term in get_solar_terms_for_year(2024, "Asia/Shanghai")
        if term.name == term_name
    )
    # West/east longitude puts the corrected clock on the opposite side.
    moment = (term.moment + timedelta(minutes=direction * 2)).replace(second=0)
    person = _person(moment, longitude=60 if direction > 0 else 180)
    context = _build_birth_computation_context(person)
    civil_pillars = BaZiCalendar.get_four_pillars(moment)
    corrected_pillars = BaZiCalendar.get_four_pillars(
        context.normalized_birth_time.corrected_datetime
    )
    assert context.birth_pillars["year"] == civil_pillars["year"]
    assert context.birth_pillars["month"] == civil_pillars["month"]
    assert context.birth_pillars["day"] == corrected_pillars["day"]
    assert context.birth_pillars["hour"] == corrected_pillars["hour"]
    seasonal_context = context.birth_calendar_context
    assert seasonal_context["solar_term_delta"]["days_since_current"] >= 0
    assert seasonal_context["solar_term_delta"]["days_until_next"] >= 0
    assert (
        seasonal_context["lunar_calendar"]["jieqi"]
        == seasonal_context["current_solar_term"]["name"]
    )


def test_beijing_lichun_birth_and_metaphysics_paths_keep_civil_year_month():
    moment = datetime(2024, 2, 4, 16, 30)
    person = _person(moment)
    seeds = [
        _build_person_seed(person),
        _build_analysis_seed(
            analysis_year=2024,
            analysis_month=2,
            analysis_day=4,
            analysis_hour=16,
            analysis_minute=30,
            analysis_timezone="Asia/Shanghai",
            analysis_longitude=116.4074,
            use_true_solar_time=True,
        ),
        _build_metaphysics_seed(
            date_text="2024-02-04",
            time_text="16:30",
            timezone_name="Asia/Shanghai",
            gps_lat=39.9042,
            gps_lon=116.4074,
            use_true_solar_time=True,
        ),
    ]
    for seed in seeds:
        assert seed.pillars["year"] == ("甲", "辰")
        assert seed.pillars["month"] == ("丙", "寅")
        assert seed.calendar_context["current_solar_term"]["name"] == "立春"
        assert seed.calendar_context["lunar_calendar"]["jieqi"] == "立春"

    result = calculate_bazi_birth(
        person, analysis_year=2025, analysis_month=1, analysis_day=1
    )
    assert result["bazi_birth"]["four_pillars"]["year"]["stem"] == "甲"
    assert result["bazi_birth"]["four_pillars"]["month"]["stem"] == "丙"
    assert (
        result["bazi_birth"]["calendar_context"]["current_solar_term"]["name"] == "立春"
    )
    nongli = calculate_nongli_time(
        date="2024-02-04",
        time="16:30",
        zone="Asia/Shanghai",
        gps_lon=116.4074,
        time_alg=0,
    )
    assert nongli["year"] == "甲辰"
    assert nongli["monthGanZi"] == "丙寅"
    assert nongli["jieqi"] == "立春"


def test_solar_clock_crossing_midnight_preserves_existing_lunar_and_day_rules():
    person = _person(datetime(2024, 2, 10, 0, 10), longitude=60)
    context = _build_birth_computation_context(person)
    solar_clock = context.normalized_birth_time.corrected_datetime
    assert solar_clock.date() == datetime(2024, 2, 9).date()
    assert context.birth_calendar_context["lunar_calendar"]["display"] == "腊月三十"
    assert (
        context.birth_pillars["day"]
        == BaZiCalendar.get_four_pillars(solar_clock)["day"]
    )


def test_dayun_boundaries_use_civil_instant_after_solar_correction():
    moment = datetime(2024, 2, 4, 16, 30)
    person = _person(moment)
    expected = TimingAnalysis.calculate_dayun_start_details(moment, "男")
    result = calculate_dayun_analysis(person, analysis_age=12)
    assert result["dayun_info"]["start_age_precise"] == expected["start_age_precise"]
    assert result["dayun_info"]["direction"] == "顺行"


@pytest.mark.parametrize(
    "value, hours",
    [("5.5", 5.5), ("UTC+8", 8), ("+0530", 5.5), ("-05:30", -5.5)],
)
def test_normalization_and_calendar_share_offset_parser(value, hours):
    moment = datetime(2024, 2, 4, 16, 30)
    expected = timedelta(hours=hours)
    assert parse_timezone_name(value).utcoffset(moment) == expected
    assert localize_datetime(moment, value).utcoffset() == expected
    person = create_person_info(2024, 2, 4, 16, gender="男", birth_timezone=value)
    result = calculate_bazi_birth(
        person, analysis_year=2025, analysis_month=1, analysis_day=1
    )
    assert "error" not in result
    assert result["bazi_birth"]["calendar_context"]["timezone"] == value


@pytest.mark.parametrize(
    "value",
    ["UTC+08:90", "+08:60", "UTC-8:-30", "UTC+24", "UTC+15:01", "1e3"],
)
def test_normalization_and_calendar_reject_malformed_offsets(value):
    with pytest.raises(ValueError, match="Invalid birth timezone"):
        parse_timezone_name(value)
    with pytest.raises(ValueError, match="Invalid birth timezone"):
        localize_datetime(datetime(2024, 2, 4), value)


def test_complete_invalid_analysis_date_is_rejected():
    with pytest.raises(ValueError, match="day is out of range"):
        _resolve_analysis_date(2025, 2, 31)
    result = calculate_bazi_birth(
        _person(datetime(1990, 4, 6, 9)),
        analysis_year=2025,
        analysis_month=2,
        analysis_day=31,
    )
    assert result["error_code"] == "validation_error"
    assert _resolve_analysis_date(2024, 2, 29) == datetime(2024, 2, 29)


def test_partial_analysis_date_keeps_default_clamping(monkeypatch):
    monkeypatch.setattr(
        "fatebridge.services.bazi.current_local_datetime",
        lambda: datetime(2025, 2, 15),
    )
    assert _resolve_analysis_date(None, 2, 31) == datetime(2025, 2, 28)
