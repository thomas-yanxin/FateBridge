"""Bind the complete adverse research reference through actual local protocols."""

import pytest

from tests.test_sukuyo_transports import (
    test_calendar_and_relations_across_all_real_transports as _check_surfaces,
)


@pytest.mark.parametrize("date", ["1903-06-25", "2024-08-04"])
def test_research_direction_reference_across_actual_transports(
    monkeypatch, capsys, date
):
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
            "sukuyo.calendar_day.clock_doctrine.dayan_reconstruction_scope_reference",
            "sukuyo.calendar",
            "sukuyo.reading_text",
        ],
    )
