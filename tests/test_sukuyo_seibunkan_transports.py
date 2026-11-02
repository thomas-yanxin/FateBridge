"""The selected source and candidate state agree across local interfaces."""

import pytest

from tests.test_sukuyo_transports import (
    test_calendar_and_relations_across_all_real_transports as _check_surfaces,
)


@pytest.mark.parametrize("part", [None, "first_half", "second_half"])
def test_later_book_context_across_rest_mcp_cli(monkeypatch, capsys, part):
    payload = {
        "date": "1957-09-24",
        "time": "12:00:00",
        "zone": "+08:00",
        "calendar_profile": "hinoo_t1299_host27",
    }
    if part is not None:
        payload["calendar_day_part"] = part
    _check_surfaces(
        monkeypatch,
        capsys,
        "suzhan",
        payload,
        [
            "sukuyo.calendar.profile_calculation.hinoo_source.critical_calendar_reference.later_seibunkan_comparison",
            "sukuyo.calendar.status",
            "sukuyo.calendar.natal_su27",
            "sukuyo.calendar.candidate_su27s",
            "sukuyo.reading_text",
        ],
    )
