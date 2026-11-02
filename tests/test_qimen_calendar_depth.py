"""Independent HKO term boundaries and physical civil-clock validation."""

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from fatebridge.core.almanac import localize_datetime
from fatebridge.services.divination import calculate_sanshiunited_analysis
from fatebridge.services.metaphysics import calculate_qimen_analysis

REFERENCE = json.loads(
    (Path(__file__).parent / "fixtures/calendar_hko_v1/reference.json").read_text()
)


def qimen(at, *, zone="America/New_York", solar=False):
    return calculate_qimen_analysis(
        analysis_year=at.year,
        analysis_month=at.month,
        analysis_day=at.day,
        analysis_hour=at.hour,
        analysis_minute=at.minute,
        analysis_timezone=zone,
        analysis_longitude=-74.006 if zone == "America/New_York" else 114.17,
        use_true_solar_time=solar,
        qimen_options={"ju_method": "chaibu"},
    )


@pytest.mark.parametrize("zone", ["Asia/Hong_Kong", "America/New_York"])
@pytest.mark.parametrize("solar", [False, True])
@pytest.mark.parametrize("year", [2026, 2027, 2028])
def test_all_72_hko_term_boundaries_drive_chaibu_by_civil_instant(zone, solar, year):
    cases = [c for c in REFERENCE["cases"] if c["year"] == year]
    for index, case in enumerate(cases):
        instant = datetime.fromisoformat(case["at"])
        before_term = cases[index - 1]["term"]  # Small Cold follows Winter Solstice.
        for minutes, expected in [(-2, before_term), (2, case["term"])]:
            civil = localize_datetime(instant + timedelta(minutes=minutes), zone)
            result = qimen(civil, zone=zone, solar=solar)
            assert "error" not in result, (case, result)
            assert result["qimen"]["ju_term"] == expected, (case, result)
            assert result["calendar_context"]["current_solar_term"]["name"] == expected


@pytest.mark.parametrize("solar", [False, True])
@pytest.mark.parametrize("entry", ["qimen", "sanshi"])
@pytest.mark.parametrize(
    "at,message",
    [
        (datetime(2026, 3, 8, 2, 30), "nonexistent local time"),
        (datetime(2026, 11, 1, 1, 30), "ambiguous local time"),
    ],
)
def test_civil_gaps_and_folds_fail_in_both_clock_modes(entry, solar, at, message):
    if entry == "qimen":
        result = qimen(at, solar=solar)
    else:
        result = calculate_sanshiunited_analysis(
            date=at.strftime("%Y-%m-%d"),
            time=at.strftime("%H:%M"),
            zone="America/New_York",
            gps_lat=40.7,
            gps_lon=-74.006,
            use_true_solar_time=solar,
        )
    assert result["error_code"] == "validation_error"
    assert result["retryable"] is False
    assert message in result["error"]
    assert "qimen" not in result


def test_corrected_solar_label_in_dst_gap_is_not_rejected_as_a_civil_input():
    at = datetime(2026, 3, 8, 3, 30)  # This physical civil instant exists.
    result = qimen(at, solar=True)
    aggregate = calculate_sanshiunited_analysis(
        date="2026-03-08",
        time="03:30",
        zone="America/New_York",
        gps_lat=40.7,
        gps_lon=-74.006,
        use_true_solar_time=True,
    )
    for body in [result, aggregate]:
        assert "error" not in body
        assert body["analysis_context"]["corrected_datetime"].startswith(
            "2026-03-08 02:"
        )
    assert result["qimen"]["palaces"] == aggregate["qimen"]["palaces"]


@pytest.mark.parametrize("solar", [False, True])
def test_explicit_offsets_resolve_the_fold_to_distinct_instants(solar):
    results = []
    for offset in ["-04:00", "-05:00"]:
        result = calculate_qimen_analysis(
            analysis_year=2026,
            analysis_month=11,
            analysis_day=1,
            analysis_hour=1,
            analysis_minute=30,
            analysis_timezone=offset,
            analysis_longitude=-74.006,
            use_true_solar_time=solar,
        )
        assert "error" not in result
        assert result["analysis_context"]["timezone"] == offset
        results.append(result)
    if solar:
        # At this longitude the earlier instant has a 子 solar hour, the later 丑.
        assert [r["qimen"]["time_ganzhi"][-1] for r in results] == ["子", "丑"]
