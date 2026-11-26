"""Integer displays use raw intervals; real calendar selection stays unchanged."""

from datetime import datetime, timedelta, timezone
from fractions import Fraction

import pytest

import fatebridge.core.bazi.timing as timing
from fatebridge.analysis.timing_effects import TimingEffectsAnalysis
from fatebridge.core.almanac import SolarTerm, get_solar_terms_for_year
from fatebridge.utils.civil_time import CivilPoint, ZonedCalendar, utc_calendar


def exact_age_ceiling(birth, boundary):
    delta = abs(boundary.astimezone(timezone.utc) - birth.astimezone(timezone.utc))
    micros = (delta.days * 86400 + delta.seconds) * 1_000_000 + delta.microseconds
    divisor = 3 * 86400 * 1_000_000
    return max(1, (micros + divisor - 1) // divisor)


@pytest.mark.parametrize("integer", range(1, 11))
@pytest.mark.parametrize("micros", [-1, 0, 1])
@pytest.mark.parametrize("forward", [False, True])
def test_integer_ceiling_at_each_unrounded_boundary(
    integer, micros, forward: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Controlled boundary oracle; not a new astronomical or historical source.
    # Given calendar-grid source -> None: an actual solar root need not equal moment.
    term = SolarTerm(
        "立夏",
        ZonedCalendar.from_datetime(datetime(2026, 5, 5, 12, tzinfo=timezone.utc)),
    )
    delta = timedelta(days=3 * integer, microseconds=micros)
    birth = term.moment.astimezone(timezone.utc) + (-delta if forward else delta)
    monkeypatch.setattr(timing, "get_bazi_year", lambda *args: 2026)
    monkeypatch.setattr(
        timing, "get_bazi_month_boundaries", lambda *args: (term, term, "巳", 3)
    )
    result = timing.TimingAnalysis.calculate_dayun_start_details(
        birth, "男" if forward else "女", "Asia/Shanghai"
    )
    expected = max(1, integer + (micros > 0))
    assert result["start_age_rounded"] == expected
    assert result["start_age_rounded"] == exact_age_ceiling(birth, term.moment)


@pytest.mark.parametrize("integer", range(1, 11))
@pytest.mark.parametrize("ticks", [-2, -1, 0, 1, 2])
def test_integer_ceiling_keeps_submicrosecond_source_remainders(integer, ticks) -> None:
    # Independent integer-neighbor classification, not a solar-accuracy claim.
    span = 3 * integer + Fraction(ticks, 16384 * 86400 * 1_000_000)
    birth = datetime(2000, 1, 1, tzinfo=timezone.utc)
    point = CivilPoint(utc_calendar(birth).julian_day_exact() + span)
    calendar = point.as_calendar().as_datetime()
    assert calendar is not None
    term = SolarTerm("小寒", ZonedCalendar.from_datetime(calendar), civil_point=point)
    details = timing.DayunStartResolution(birth, term, True, "庚", span).to_details()
    assert details["start_age_rounded"] == integer + (ticks > 0)


def test_explicit_age_uses_retained_span_at_all_three_boundaries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Fixed R28 N03_K+1 source point. It is just after three nominal years.
    # Integer ages 3, 13 and 123 fall before start, in period 1 and in period 12.
    birth = datetime(2000, 1, 1, tzinfo=timezone.utc)
    span = 9 + Fraction(1, 16384 * 86400 * 1_000_000)
    point = CivilPoint(utc_calendar(birth).julian_day_exact() + span)
    calendar = point.as_calendar().as_datetime()
    assert calendar is not None
    term = SolarTerm("小寒", ZonedCalendar.from_datetime(calendar), civil_point=point)
    resolution = timing.DayunStartResolution(birth, term, True, "庚", span)
    monkeypatch.setattr(
        timing.TimingAnalysis, "resolve_dayun_start", lambda *args: resolution
    )
    pillars = {
        "year": ("庚", "辰"),
        "month": ("戊", "寅"),
        "day": ("甲", "子"),
        "hour": ("甲", "子"),
    }
    for age, expected in ((3, "before_dayun"), (13, 1), (123, 12)):
        value = TimingEffectsAnalysis.analyze_dayun_effects(
            pillars, birth, "男", age, timezone_name="UTC"
        )
        actual = (
            value["dayun_info"]["period"] if "dayun_info" in value else value["status"]
        )
        assert actual == expected


def test_minimum_one_is_only_display_and_does_not_delay_an_exact_zero_start(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Exact given source point; a real solar root's datetime is only a display.
    term = SolarTerm(
        "立夏",
        ZonedCalendar.from_datetime(datetime(2026, 5, 5, 12, tzinfo=timezone.utc)),
    )
    monkeypatch.setattr(timing, "get_bazi_year", lambda *args: 2026)
    monkeypatch.setattr(
        timing, "get_bazi_month_boundaries", lambda *args: (term, term, "巳", 3)
    )
    details = timing.TimingAnalysis.calculate_dayun_start_details(
        term.moment, "女", "Asia/Shanghai"
    )
    assert details["start_age_unrounded"] == 0
    assert details["start_age_rounded"] == 1
    value = timing.TimingAnalysis.calculate_dayun_timeline(
        term.moment, "女", ("癸", "巳"), "Asia/Shanghai"
    )
    assert datetime.fromisoformat(value["start_at"]).astimezone(
        timezone.utc
    ) == term.moment.astimezone(timezone.utc)


def test_dayun_resolution_retains_source_point_without_a_json_roundtrip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "de440")
    term = next(t for t in get_solar_terms_for_year(2024, "UTC") if t.name == "立秋")
    expected = term.point.day
    birth = datetime(2024, 8, 6, 18, 9, 16, 454006, tzinfo=timezone.utc)
    monkeypatch.setattr(timing, "get_bazi_year", lambda *args: 2024)
    monkeypatch.setattr(
        timing, "get_bazi_month_boundaries", lambda *args: (term, term, "申", 6)
    )

    def no_serialization(self):
        raise AssertionError("resolution must retain the actual SolarTerm")

    monkeypatch.setattr(type(term), "as_dict", no_serialization)
    resolved = timing.TimingAnalysis.resolve_dayun_start(birth, "男", "UTC")
    assert resolved.target_term is term
    assert resolved.target_term.point.day == expected
    assert resolved.nominal_days == expected - utc_calendar(birth).julian_day_exact()
    assert resolved.birth == birth
    assert resolved.forward_direction is True and resolved.year_stem == "甲"
