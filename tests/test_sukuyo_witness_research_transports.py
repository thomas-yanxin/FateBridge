"""New selected-source research survives actual REST, MCP and CLI projection."""

import pytest

from tests.test_sukuyo_transports import (
    test_calendar_and_relations_across_all_real_transports as _check_surfaces,
)


@pytest.mark.parametrize(
    "key,payload,fields",
    [
        (
            "suzhan",
            {
                "date": "1903-06-25",
                "time": "12:00:00",
                "zone": "+08:00",
                "calendar_profile": "hinoo_t1299_host27",
                "calendar_day_part": "first_half",
            },
            [
                "sukuyo.calendar.profile_calculation.hinoo_source.critical_calendar_reference.image_witness_research",
                "sukuyo.reading_text",
            ],
        ),
        (
            "sukuyo_compatibility",
            {
                "person1_date": "1903-06-25",
                "person1_time": "12:00:00",
                "person2_date": "1957-09-24",
                "person2_time": "12:00:00",
                "calendar_profile": "hinoo_t1299_host27",
                "person1_calendar_day_part": "first_half",
                "person2_calendar_day_part": "first_half",
            },
            [
                "person1.calendar.profile_calculation.hinoo_source.critical_calendar_reference.image_witness_research",
                "person2.calendar.profile_calculation.hinoo_source.critical_calendar_reference.image_witness_research",
                "candidate_relation_analysis",
                "summary",
            ],
        ),
    ],
)
def test_actual_transports_deliver_the_added_source_reference(
    monkeypatch, capsys, key, payload, fields
):
    _check_surfaces(monkeypatch, capsys, key, payload, fields)
