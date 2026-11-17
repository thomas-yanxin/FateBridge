"""Year-edge consumers use real adjacent labels, not whole invalid year grids."""

import gzip
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from fatebridge.core import almanac, timing
from fatebridge.core.astro.time_scales import utc_calendar_from_tt
from fatebridge.core.astro.tt_epoch import TTInstant
from fatebridge.core.calendar import BaZiCalendar
from fatebridge.core.guolao_monthly import month_context
from fatebridge.core.timing import TimingAnalysis
from fatebridge.utils.civil_time import UTCCalendar, ZonedCalendar, gregorian_ordinal
from fatebridge.utils.timezones import parse_timezone_name
from tests.support.ephemeris_case_runtime import (
    native_ephemeris_files as native_ephemeris_files,
)

PATH = (
    Path(__file__).parents[1] / "fixtures/solar-calendar-boundary-reference-v1.json.gz"
)
REFERENCE = json.loads(gzip.decompress(PATH.read_bytes()))


@pytest.fixture
def frozen_boundaries(monkeypatch):
    """Use independent clock fields; this fixture does not execute an ephemeris."""
    assert (
        hashlib.sha256(PATH.read_bytes()).hexdigest()
        == PATH.with_suffix(".sha256").read_text().strip()
    )
    rows = {
        (row["context_year"], row["year"], row["index"]): row
        for row in REFERENCE["rows"]
    }
    observed = []

    def selected(year, zone, context_year, *, term_index=None):
        observed.append((year, context_year, term_index))
        terms = []
        for index in range(24) if term_index is None else (term_index,):
            clock = rows[context_year, year, index]["clock"]
            if clock["kind"] == "ERFA_frozen_leap_table":
                y, m, d, h, minute, second, fraction = clock["calendar_fields"]
                micros = ((h * 60 + minute) * 60 + second) * 1000000 + fraction
            else:
                y, m, d, h, minute, seconds = clock["fields"]
                micros = round((h * 3600 + minute * 60 + seconds) * 1000000)
            calendar = ZonedCalendar(
                UTCCalendar(gregorian_ordinal(y, m, d), micros),
                parse_timezone_name(zone),
            )
            terms.append(
                almanac.SolarTerm(
                    almanac.SOLAR_TERM_NAMES[index], calendar, "swisseph", "swieph"
                )
            )
        return tuple(terms)

    monkeypatch.setattr(
        almanac,
        "get_solar_terms_for_year",
        lambda year, zone: selected(year, zone, year),
    )
    monkeypatch.setattr(almanac, "_solar_terms_for_context_year", selected)
    monkeypatch.setattr(
        timing,
        "get_solar_terms_for_year",
        lambda year, zone: selected(year, zone, year),
    )
    monkeypatch.setattr(timing, "_solar_terms_for_context_year", selected)
    timing._calculate_liuyue_cached.cache_clear()
    try:
        yield observed
    finally:
        timing._calculate_liuyue_cached.cache_clear()


@pytest.mark.parametrize("zone", ["UTC", "+08:00", "-08:00", "Asia/Shanghai"])
@pytest.mark.parametrize("year,month,day", [(1, 1, 1), (9999, 12, 31)])
def test_jie_windows_keep_the_actual_auxiliary_year(
    frozen_boundaries, zone, year, month, day
):
    moment = datetime(year, month, day)
    first, last, branch, _ = almanac.get_bazi_month_boundaries(moment, zone)
    assert branch == "子"
    assert first.name == "大雪" and last.name == "小寒"
    assert first.calendar.local_parts[0] == (0 if year == 1 else 9999)
    assert last.calendar.local_parts[0] == (1 if year == 1 else 10000)
    assert all(context == year for _, context, _ in frozen_boundaries)
    assert [(y, index) for y, _, index in frozen_boundaries if y != year] == (
        [(0, 22), (0, 23)] if year == 1 else [(10000, 0), (10000, 1)]
    )


def test_upper_year_month_timeline_keeps_the_next_xiaohan_without_a_full_auxiliary_grid(
    frozen_boundaries,
):
    timeline = TimingAnalysis.calculate_liuyue_timeline(9999, "-08:00")
    assert len(timeline) == 12
    assert timeline[-1]["next_term"]["datetime_with_offset"].startswith("+010000-")
    assert timeline[-1]["gregorian_window"]["days"] > 0
    assert frozen_boundaries[:2] == [(9999, 9999, None), (10000, 9999, 0)]
    assert all(index in (0, 1) for year, _, index in frozen_boundaries if year == 10000)


def test_complete_month_instant_controls_all_calendar_labels(frozen_boundaries):
    moment = datetime(2026, 11, 1, tzinfo=timezone.utc)
    result = TimingAnalysis.calculate_liuyue(
        2025, 1, 1, "Asia/Shanghai", target_date=moment
    )
    assert (result["year"], result["month"], result["day"]) == (2026, 11, 1)
    assert result["analysis_datetime"] == "2026-11-01 08:00:00"
    assert result["pillar"] == "戊戌"


def test_available_local_utc8_month_is_not_lost_to_an_unrepresentable_utc_label(
    frozen_boundaries,
):
    moment = datetime.fromisoformat("0001-01-01T00:00:00+08:00")
    result = month_context(moment, "jie_month")
    assert result["status"] == "available"
    assert result["month_number"] == 11 and result["month_branch"] == "子"
    assert result["calendar_datetime"] == moment.isoformat()
    assert result["instant_utc"] == "0000-12-31T16:00:00+00:00"


def test_all_pinned_day_hour_edges_match_two_independent_calendars():
    path = PATH.parent / "calendar-day-hour-edges-v1.json.gz"
    raw = path.read_bytes()
    assert (
        hashlib.sha256(raw).hexdigest()
        == path.with_suffix(".sha256").read_text().strip()
    )
    reference = json.loads(gzip.decompress(raw))
    assert len(reference["rows"]) == 336
    assert reference["oracle_disagreements"] == []
    for row in reference["rows"]:
        year, month, day, hour = row["input"]
        actual = [
            "".join(BaZiCalendar.calculate_day_pillar(year, month, day, hour=hour)),
            "".join(BaZiCalendar.calculate_hour_pillar(year, month, day, hour)),
        ]
        assert actual == row["lunar_python"] == row["sxtwl"], row["input"]


@pytest.mark.local_data
def test_every_native_edge_root_and_declared_clock_matches_the_frozen_external_solver(
    native_ephemeris_files, monkeypatch
):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    assert len(REFERENCE["rows"]) == 336
    for row in REFERENCE["rows"]:
        term = almanac._solar_terms_for_context_year(
            row["year"], "UTC", row["context_year"], term_index=row["index"]
        )[0]
        actual_tt = term.solar_model_details["selected_crossing_jd_tt"]
        assert abs(actual_tt - row["jd_tt"]) * 86400 <= 0.001
        assert term.ephemeris_model == "swieph" and term.ephemeris_retflags == (2,)
        clock = row["clock"]
        if clock is None:
            continue  # Historical affine UTC is covered by its separate source corpus.
        actual = utc_calendar_from_tt(TTInstant.from_float(row["jd_tt"]))
        if clock["kind"] == "ERFA_frozen_leap_table":
            y, m, d, h, minute, second, fraction = clock["calendar_fields"]
            micros = ((h * 60 + minute) * 60 + second) * 1000000 + fraction
        else:
            y, m, d, h, minute, seconds = clock["fields"]
            micros = round((h * 3600 + minute * 60 + seconds) * 1000000)
        error = (
            (actual.ordinal - gregorian_ordinal(y, m, d)) * 86400000000
            + actual.microseconds_of_day
            - micros
        )
        assert abs(error) <= 200
