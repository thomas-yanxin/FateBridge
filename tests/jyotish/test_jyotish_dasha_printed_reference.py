"""Arithmetic check on Rao Example 50 and its printed date discrepancy."""

from datetime import datetime, timedelta, timezone
from fractions import Fraction

import pytest

from fatebridge.core.jyotish.dasha import vimshottari


def test_rao_example_50_printed_balance_and_calendar_discrepancy() -> None:
    """Rao printed211 supplies a longitude and a clock, not a new ephemeris fit."""
    birth = datetime.fromisoformat("2000-04-28T05:50:00-04:00").astimezone(timezone.utc)
    printed_moon_degrees = Fraction(302 * 60 + 23, 60)
    remaining_years = Fraction(257, 800) * 7
    assert remaining_years == Fraction(1799, 800)
    remaining_microseconds = int(remaining_years * 360 * 86_400_000_000)
    assert remaining_microseconds == 69_945_120_000_000
    result = vimshottari(
        birth,
        float(printed_moon_degrees),
        birth,
        year_basis="savana_360",
        dasha_depth=6,
    )
    assert (result["seed"]["name"], result["seed"]["pada"]) == ("Dhanishta", 3)
    assert result["birth_balance"]["lord"] == "Mars"
    assert result["birth_balance"]["remaining_years"] == pytest.approx(
        float(remaining_years), abs=1e-13
    )
    assert result["birth_balance"]["remaining_microseconds"] == remaining_microseconds
    assert result["birth_balance"]["major_start"] == "1995-08-22T23:02:00+00:00"
    assert result["birth_balance"]["major_end"] == "2002-07-16T23:02:00+00:00"
    printed_approximate_end = datetime.fromisoformat("2002-07-15T19:00:00-04:00")
    assert datetime.fromisoformat(result["birth_balance"]["major_end"]) - (
        printed_approximate_end
    ) == timedelta(days=1, minutes=2)
    assert [row["lord"] for row in result["subdivisions"]["current_levels"]] == [
        "Mars",
        "Ketu",
        "Jupiter",
        "Venus",
        "Venus",
        "Ketu",
    ]
    assert result["current_sub"]["start"] < birth.isoformat()
