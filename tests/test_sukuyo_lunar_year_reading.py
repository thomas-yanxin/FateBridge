"""Keep lunar-year identity when an unguessed date crosses Chinese New Year."""

import hashlib
import re
from pathlib import Path

import pytest

from fatebridge.core.sukuyo import calendar_mansion, day_evidence

HKO = Path(__file__).parent / "fixtures/ziwei_independent/hko"


def test_primary_cny_rows_bind_the_two_lunar_years():
    for year, expected in (
        (2024, "0120d4df9b6638b084dcf35a0633f970ec47f8c1adde2553fba3e3c3570217fc"),
        (2025, "7a2803584dcd12a38a13e3710e643369996f59e690d684b9e3705fc5e988ebc2"),
    ):
        raw = (HKO / f"T{year}c.txt").read_bytes()
        assert hashlib.sha256(raw).hexdigest() == expected
    assert re.search(r"2024年2月10日\s+正月", (HKO / "T2024c.txt").read_text())
    table = (HKO / "T2025c.txt").read_text()
    assert re.search(r"2025年1月28日\s+廿九", table)
    assert re.search(r"2025年1月29日\s+正月", table)


@pytest.mark.parametrize(
    "date,year,month,day,mansion",
    [("2025-01-28", 2024, 12, 29, "危"), ("2025-01-29", 2025, 1, 1, "室")],
)
def test_lunar_year_is_not_silently_replaced_by_gregorian_year(
    date, year, month, day, mansion
):
    calendar = calendar_mansion(date)
    assert (calendar["lunar_year"], calendar["lunar_month"], calendar["lunar_day"]) == (
        year,
        month,
        day,
    )
    assert calendar["natal_su27"] == mansion
    assert f"农历{year}年{month}月{day}日" in day_evidence(calendar)["reading_text"]


def test_one_microsecond_branch_keeps_its_own_lunar_year_and_utc_support():
    calendar = calendar_mansion("2025-01-29", zone="8.0000000002777778")
    assert calendar["input_datetime"] is None and not calendar["birth_time_known"]
    assert [
        (r["calendar_date"], r["lunar_year"], r["natal_su27"])
        for r in calendar["calendar_candidates"]
    ] == [("2025-01-28", 2024, "危"), ("2025-01-29", 2025, "室")]
    assert [
        (r["start_utc_inclusive"], r["end_utc_exclusive"])
        for r in calendar["date_support"]["utc_support_intervals"]
    ] == [
        ("2025-01-28T15:59:59.999999+00:00", "2025-01-28T16:00:00+00:00"),
        ("2025-01-28T16:00:00+00:00", "2025-01-29T15:59:59.999999+00:00"),
    ]
    text = day_evidence(calendar)["reading_text"]
    for date, lunar, mansion in (
        ("2025-01-28", "2024年12月29日", "危"),
        ("2025-01-29", "2025年1月1日", "室"),
    ):
        assert f"中国历日{date}（UTC+08），农历{lunar}；本次历日27宿为{mansion}" in text
