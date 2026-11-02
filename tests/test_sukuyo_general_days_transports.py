"""Whole-list evidence is available through the three public transports."""

import pytest

from tests.test_sukuyo_transports import (
    test_calendar_and_relations_across_all_real_transports as run_transport_check,
)


@pytest.mark.parametrize("date", ["2024-06-15", "1957-09-24"])
def test_whole_day_lists_across_actual_transports(monkeypatch, capsys, date):
    run_transport_check(
        monkeypatch,
        capsys,
        "suzhan",
        {
            "date": date,
            "time": "06:30:00",
            "zone": "+08:00",
            "calendar_profile": "hinoo_t1299_host27",
            "calendar_day_part": "first_half",
        },
        [
            "sukuyo.calendar_day.japanese_selected_reference.primary_general_day_reference",
            "sukuyo.calendar_day.japanese_selected_reference.full_favorable_membership_comparison",
            "sukuyo.calendar_day.classifications",
            "sukuyo.reading_text",
        ],
    )
