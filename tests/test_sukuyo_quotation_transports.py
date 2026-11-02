"""The current quotation comparison survives the actual three transports."""

import pytest

from tests.test_sukuyo_transports import (
    test_calendar_and_relations_across_all_real_transports as _check_surfaces,
)


@pytest.mark.parametrize("date", ["1903-06-25", "2024-08-04"])
def test_quotation_comparison_across_actual_transports(monkeypatch, capsys, date):
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
            "sukuyo.calendar_day.clock_doctrine.source_specific_time_calibration.daybreak_source_comparison.T2217_printed_collation",
            "sukuyo.calendar_day.clock_doctrine.source_specific_time_calibration.daybreak_source_comparison.T2217_printed_collation.subsequent_quotation_comparison.kanbun_printed_witness",
            "sukuyo.calendar",
            "sukuyo.reading_text",
        ],
    )
