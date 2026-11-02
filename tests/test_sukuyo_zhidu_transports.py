"""Expose the same complete primary context through the actual local transports."""

import pytest

from tests.test_sukuyo_transports import (
    test_calendar_and_relations_across_all_real_transports as _check_surfaces,
)


@pytest.mark.parametrize("date", ["1903-06-25", "2024-08-04"])
def test_zhidu_context_across_actual_transports(monkeypatch, capsys, date):
    _check_surfaces(
        monkeypatch,
        capsys,
        "suzhan",
        {
            "date": date,
            "time": "12:00:00",
            "zone": "+08:00",
            "calendar_profile": "hinoo_t1299_host27",
        },
        [
            "sukuyo.calendar_day.clock_doctrine.source_specific_time_calibration.daybreak_source_comparison.T2217_printed_collation.subsequent_quotation_comparison.upstream_calendar_context",
            "sukuyo.calendar",
            "sukuyo.reading_text",
        ],
    )
