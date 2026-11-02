"""Actual REST, native MCP and CLI retain the same new collation evidence."""

import pytest

from tests.test_sukuyo_transports import (
    test_calendar_and_relations_across_all_real_transports as _check_surfaces,
)


@pytest.mark.parametrize("date", ["2025-01-29", "1903-06-25"])
def test_printed_collation_across_actual_transports(monkeypatch, capsys, date):
    suffix = "calendar_day.clock_doctrine.source_specific_time_calibration.daybreak_source_comparison.T2217_printed_collation"
    payload = {
        "date": date,
        "time": "12:00:00",
        "zone": "+08:00",
        "calendar_profile": "hinoo_t1299_host27",
    }
    fields = ["sukuyo." + suffix, "sukuyo.calendar", "sukuyo.reading_text"]
    _check_surfaces(monkeypatch, capsys, "suzhan", payload, fields)
