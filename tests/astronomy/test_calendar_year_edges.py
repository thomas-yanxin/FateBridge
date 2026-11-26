"""Year-edge consumers use real adjacent labels, not whole invalid year grids."""

import gzip
import hashlib
import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core import almanac, timing
from fatebridge.core.astro.time_scales import utc_calendar_from_tt, utc_point_from_tt
from fatebridge.core.astro.tt_epoch import TTInstant
from fatebridge.core.calendar import BaZiCalendar
from fatebridge.core.contracts.output_canping_solar import CanpingSolarBoundary
from fatebridge.core.contracts.output_chinese import SolarTerm as SolarTermEvidence
from fatebridge.core.contracts.output_civil_time import CivilPointEvidence
from fatebridge.core.guolao.guolao_monthly import month_context
from fatebridge.core.liuyao.liuyao_judgment import timing_candidates
from fatebridge.core.numerology.canping_solar import ResolvedProjectionBoundary
from fatebridge.core.timing import TimingAnalysis
from fatebridge.utils.civil_time import (
    CivilPoint,
    UTCCalendar,
    ZonedCalendar,
    gregorian_ordinal,
    utc_calendar,
)
from fatebridge.utils.timezones import parse_timezone_name
from scripts.astronomy.solar_term_reference import load_solar_term_reference
from tests.support.ephemeris_case_runtime import (
    native_ephemeris_files as native_ephemeris_files,
)

PATH = (
    Path(__file__).parents[1] / "fixtures/solar-calendar-boundary-reference-v1.json.gz"
)
REFERENCE = json.loads(gzip.decompress(PATH.read_bytes()))
POINT_REFERENCE = json.loads(
    (Path(__file__).parents[1] / "data/retained_civil_points_v1.json").read_bytes()
)


@pytest.mark.parametrize(
    "microseconds,lower,upper",
    [
        (Fraction(-1, 2), UTCCalendar(719162, 86399999999), UTCCalendar(719163, 0)),
        (Fraction(0), UTCCalendar(719163, 0), UTCCalendar(719163, 0)),
        (Fraction(1, 2), UTCCalendar(719163, 0), UTCCalendar(719163, 1)),
    ],
)
def test_nominal_point_bracket_uses_exact_floor_and_ceil(
    microseconds, lower, upper
) -> None:
    point = CivilPoint(Fraction(4881175, 2) + microseconds / 86400000000)
    assert point.nominal_calendar_bracket() == (lower, upper)


@pytest.mark.parametrize("year", [1, 10000])
def test_nominal_bracket_preserves_auxiliary_labels_and_does_not_clamp_cap(
    year: int,
) -> None:
    cap = UTCCalendar(gregorian_ordinal(year, 1, 1), 0)
    excluded = cap.julian_day_exact()
    point = CivilPoint(excluded - Fraction(1, 345600000000), excluded)
    previous = UTCCalendar(cap.ordinal - 1, 86399999999)
    assert point.as_calendar() == previous
    assert point.nominal_calendar_bracket() == (previous, cap)
    # An enclosing nominal label is not a newly qualified ordinary UTC label.


@pytest.mark.parametrize(
    "zone,cut,expected_date,expected_offset,expected_fold",
    [
        ("Antarctica/Vostok", "1994-01-31T17:00:00", "19940131", 25200, 0),
        ("Antarctica/Vostok", "1994-11-01T00:00:00", None, None, None),
        ("America/New_York", "2024-03-10T07:00:00", "20240310", -18000, 0),
        ("America/New_York", "2024-11-03T06:00:00", "20241103", -14400, 0),
        ("Pacific/Apia", "2011-12-30T10:00:00", "20111229", -36000, 0),
        ("Etc/UTC", "2024-03-10T00:00:00", "20240309", 0, 0),
    ],
)
def test_fractional_solar_term_label_stays_on_exact_side_of_local_cut(
    zone: str,
    cut: str,
    expected_date: str | None,
    expected_offset,
    expected_fold: int | None,
) -> None:
    cut_at = datetime.fromisoformat(cut).replace(tzinfo=timezone.utc)
    cap = utc_calendar(cut_at).julian_day_exact()
    point = CivilPoint(cap - Fraction(1, 345600000000))
    calendar = ZonedCalendar(point.as_calendar(), parse_timezone_name(zone))
    term = almanac.SolarTerm("立春", calendar, civil_point=point)

    record = replace(term).as_dict()
    assert term.point == CivilPoint(point.day, cap)
    assert record.get("date_key") == expected_date
    assert record.get("utc_offset_seconds") == expected_offset
    assert record.get("fold") == expected_fold
    receipt = ResolvedProjectionBoundary(
        cut_at.year, term, "ordinary_public_year_grid"
    ).to_record()
    assert receipt["instant_utc"] == (cut_at - timedelta(microseconds=1)).isoformat()
    CanpingSolarBoundary.model_validate(receipt, context={"full_result": True})


@pytest.mark.parametrize("year", [2, 9999])
def test_solar_term_rounding_uses_local_date_across_rule_proxy_year_changes(
    year: int,
) -> None:
    cut = UTCCalendar(gregorian_ordinal(year, 1, 1), 0)
    point = CivilPoint(cut.julian_day_exact() - Fraction(1, 345600000000))
    calendar = ZonedCalendar(point.as_calendar(), parse_timezone_name("+08:00"))
    term = almanac.SolarTerm("小寒", calendar, civil_point=point)

    assert term.calendar.utc == cut
    assert term.calendar.local_parts[:3] == (year, 1, 1)
    assert term.point == point


@pytest.fixture(scope="module")
def solar_tt_reference():
    return load_solar_term_reference()


@pytest.mark.parametrize("row", POINT_REFERENCE["rows"], ids=lambda row: row["name"])
def test_selected_solar_points_control_all_24_boundary_neighbours(
    row, monkeypatch: pytest.MonkeyPatch, solar_tt_reference
) -> None:
    """Keep the frozen clock conversion and check live roots independently."""
    historical_tt = TTInstant(Fraction(row["root_tt_exact"]))
    historical_civil = utc_point_from_tt(historical_tt)
    assert historical_civil.day == Fraction(
        int(row["civil_numerator"]), int(row["civil_denominator"])
    )
    assert historical_civil.as_calendar().isoformat() == row["display_utc"]

    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "de440")
    year = 2024
    index = row["index"]
    term = almanac.get_solar_terms_for_year(year, "UTC")[index]
    independent_root = solar_tt_reference.rows[
        (year - solar_tt_reference.first_year) * 24 + index
    ]
    assert term.name == independent_root.name == row["name"]
    assert term.resolution_provider == "jpl_de440"
    details = term.solar_model_details
    assert details is not None
    assert details["source_kernel_sha256"] == solar_tt_reference.source.kernel_sha256
    assert details["reference_event_table_used"] is False

    tt_day, tt_fraction = details["selected_crossing_tt_parts"]
    current_tt = Fraction.from_float(tt_day) + Fraction.from_float(tt_fraction)
    assert term.tt_instant is not None
    assert term.tt_instant.days == current_tt
    delta_seconds = float(
        abs(current_tt - Fraction.from_float(independent_root.jd_tt)) * 86400
    )
    assert delta_seconds <= 1.0 and delta_seconds <= 0.01, independent_root

    tt_minus_utc = POINT_REFERENCE["tai_minus_utc_seconds"] + Fraction("32.184")
    expected_civil = current_tt - tt_minus_utc / 86400
    assert term.civil_point is not None
    assert term.civil_point.day == expected_civil
    assert term.civil_point.as_calendar().isoformat() == row["display_utc"]
    record = term.as_dict()
    assert record["civil_point"]["numerator"] == str(expected_civil.numerator)
    assert record["civil_point"]["denominator"] == str(expected_civil.denominator)
    assert "excluded_before" in record["civil_point"]
    assert record["comparison_policy"] == "retained_nominal_civil_point_v1"
    SolarTermEvidence.model_validate(record, context={"full_result": True})
    for sample in row["samples"]:
        at = datetime.fromisoformat(sample["label"])
        assert (
            almanac.get_adjacent_solar_terms(at, "UTC")[0].name
            == sample["current_term"]
        )
        if row["name"] == "立春":
            assert almanac.get_bazi_year(at, "UTC") == (
                2023 if sample["before_root"] else 2024
            )
        else:
            pass
        if row["index"] % 2 == 0:
            previous, following, _, _ = almanac.get_bazi_month_boundaries(at, "UTC")
            assert (following.name == row["name"]) is sample["before_root"]
            assert (
                previous.point.day
                <= utc_calendar(at).julian_day_exact()
                < following.point.day
            )
        else:
            pass


def test_projected_civil_cap_stays_unknown_without_querying_a_clock() -> None:
    row = POINT_REFERENCE["rows"][14]
    projected = CivilPointEvidence.model_validate(
        {"numerator": row["civil_numerator"], "denominator": row["civil_denominator"]}
    )
    assert projected.known_day() == Fraction(
        int(row["civil_numerator"]), int(row["civil_denominator"])
    )
    assert projected.known_point() is None
    complete = {
        "unit": "nominal_gregorian_day",
        "numerator": row["civil_numerator"],
        "denominator": row["civil_denominator"],
        "excluded_before": None,
    }
    assert CivilPointEvidence.model_validate(complete).known_point() is not None
    with pytest.raises(ValidationError):
        CivilPointEvidence.model_validate(
            {
                **complete,
                "excluded_before": {
                    k: complete[k] for k in ("numerator", "denominator")
                },
            }
        )


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
    frozen_boundaries, zone: str, year: int, month: int, day: int
) -> None:
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
) -> None:
    timeline = TimingAnalysis.calculate_liuyue_timeline(9999, "-08:00")
    assert len(timeline) == 12
    assert timeline[-1]["next_term"]["datetime_with_offset"].startswith("+010000-")
    assert timeline[-1]["gregorian_window"]["days"] > 0
    assert frozen_boundaries[:2] == [(9999, 9999, None), (10000, 9999, 0)]
    assert all(index in (0, 1) for year, _, index in frozen_boundaries if year == 10000)


@pytest.mark.parametrize(
    "days,branch,date_label,pillar,start,end,reassessment",
    [
        (
            1,
            "午",
            "+010000-01-01",
            "戊午",
            "9999-12-31T23:00:00-05:00",
            "+010000-01-01T23:00:00-05:00",
            False,
        ),
        (
            2,
            "未",
            "+010000-01-02",
            "己未",
            "+010000-01-01T23:00:00-05:00",
            "+010000-01-02T23:00:00-05:00",
            True,
        ),
    ],
)
def test_sixyao_windows_reassess_the_month_across_an_auxiliary_year(
    frozen_boundaries,
    days: int,
    branch: str,
    date_label: str,
    pillar: str,
    start: str,
    end: str,
    reassessment: bool,
) -> None:
    # The independent calendar fixture places Xiaohan during the second window.
    zone = "Etc/GMT+5"
    moment = datetime(9999, 12, 31, 23, tzinfo=parse_timezone_name(zone))
    result = timing_candidates(
        moment=moment,
        timezone_name=zone,
        days=days,
        selected={"location": "visible", "branch": branch},
        month="子",
        original_ganzhi="戊午",
        line={"change": False},
    )
    assert len(result["windows"]) == 1
    window = result["windows"][0]
    assert window["effective_date"] == date_label
    assert window["day_ganzhi"] == pillar
    assert (window["start_at"], window["end_at"]) == (start, end)
    assert "静逢值" in window["matched_rules"]
    assert window["requires_month_reassessment"] is reassessment


def test_complete_month_instant_controls_all_calendar_labels(frozen_boundaries) -> None:
    moment = datetime(2026, 11, 1, tzinfo=timezone.utc)
    result = TimingAnalysis.calculate_liuyue(
        2025, 1, 1, "Asia/Shanghai", target_date=moment
    )
    assert (result["year"], result["month"], result["day"]) == (2026, 11, 1)
    assert result["analysis_datetime"] == "2026-11-01 08:00:00"
    assert result["pillar"] == "戊戌"


def test_available_local_utc8_month_is_not_lost_to_an_unrepresentable_utc_label(
    frozen_boundaries,
) -> None:
    moment = datetime.fromisoformat("0001-01-01T00:00:00+08:00")
    result = month_context(moment, "jie_month")
    assert result["status"] == "available"
    assert result["month_number"] == 11 and result["month_branch"] == "子"
    assert result["calendar_datetime"] == moment.isoformat()
    assert result["instant_utc"] == "0000-12-31T16:00:00+00:00"


def test_all_pinned_day_hour_edges_match_two_independent_calendars() -> None:
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
    native_ephemeris_files, monkeypatch: pytest.MonkeyPatch
) -> None:
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
        else:
            pass
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
