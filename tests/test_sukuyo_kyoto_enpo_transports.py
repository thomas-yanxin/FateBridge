"""Named independent image evidence survives real REST, MCP and CLI."""

import pytest

from tests.test_sukuyo_transports import (
    test_calendar_and_relations_across_all_real_transports as run_transport_check,
)


@pytest.mark.parametrize("date", ["2025-01-06", "2025-01-11", "1957-09-24"])
def test_sukuyo_enpo_reference_across_actual_transports(monkeypatch, capsys, date):
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
            "sukuyo.special_day_evidence",
            "sukuyo.calendar_day.clock_doctrine",
            "sukuyo.calendar",
            "sukuyo.reading_text",
        ],
    )
