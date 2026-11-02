"""Actual REST, native MCP and CLI preserve the named printed reference."""

import pytest

from tests.test_sukuyo_transports import (
    test_calendar_and_relations_across_all_real_transports as run_transport_check,
)


@pytest.mark.parametrize(
    "date,basis,zone",
    [
        ("2025-02-02", "chinese_hko_utc08", "+08:00"),
        ("1957-09-24", "chinese_hko_utc08", "+08:00"),
        ("0820-03-22", "japanese_naoj_historical_utc09", "+09:00"),
    ],
)
def test_sukuyo_printed_clock_across_actual_transports(
    monkeypatch, capsys, date, basis, zone
):
    run_transport_check(
        monkeypatch,
        capsys,
        "suzhan",
        {
            "date": date,
            "time": "12:00:00",
            "zone": zone,
            "calendar_basis": basis,
            "calendar_profile": "hinoo_t1299_host27",
            "calendar_day_part": "first_half",
        },
        [
            "sukuyo.calendar_day.clock_doctrine.kenyu_printed_reference",
            "sukuyo.calendar",
            "sukuyo.day_mansion",
            "sukuyo.reading_text",
        ],
    )
