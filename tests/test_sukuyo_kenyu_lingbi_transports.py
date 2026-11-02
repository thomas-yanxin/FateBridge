"""The new period reference survives actual REST, native MCP and CLI."""

import pytest

from tests.test_sukuyo_transports import (
    test_calendar_and_relations_across_all_real_transports as run_transport_check,
)


@pytest.mark.parametrize(
    "date,basis,zone",
    [
        ("2024-02-11", "chinese_hko_utc08", "+08:00"),
        ("1903-06-25", "chinese_hko_utc08", "+08:00"),
        ("0821-01-11", "japanese_naoj_historical_utc09", "+09:00"),
    ],
)
def test_sukuyo_lingbi_reference_across_actual_transports(
    monkeypatch, capsys, date, basis, zone
):
    run_transport_check(
        monkeypatch,
        capsys,
        "suzhan",
        {
            "date": date,
            "time": "06:30:00",
            "zone": zone,
            "calendar_basis": basis,
            "calendar_profile": "hinoo_t1299_host27",
            "calendar_day_part": "first_half",
        },
        [
            "sukuyo.kenyu_lingbi_reference",
            "sukuyo.calendar",
            "sukuyo.day_mansion",
            "sukuyo.reading_text",
        ],
    )
