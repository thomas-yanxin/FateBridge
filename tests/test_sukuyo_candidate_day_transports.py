"""The actual conditional branch survives REST, native MCP and CLI."""

import pytest

from tests.test_sukuyo_transports import (
    test_calendar_and_relations_across_all_real_transports as check_surfaces,
)


@pytest.mark.parametrize("part", [None, "first_half", "second_half"])
def test_conditional_mansion_days_across_all_surfaces(monkeypatch, capsys, part):
    payload = {
        "date": "2024-08-04",
        "time": "09:00:00",
        "zone": "+08:00",
        "calendar_profile": "hinoo_t1299_host27",
        "natal_mansion": "室",
        "activity": "travel",
        "activity_details": ["personal_departure"],
    }
    if part is not None:
        payload["calendar_day_part"] = part
    check_surfaces(
        monkeypatch,
        capsys,
        "suzhan",
        payload,
        [
            "sukuyo.calendar",
            "sukuyo.day_mansion",
            "sukuyo.personal_day",
            "sukuyo.activity_assessment",
            "sukuyo.candidate_mansion_days",
            "sukuyo.reading_text",
        ],
    )
