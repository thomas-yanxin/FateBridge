"""The conditional model and the unknown printed value survive each transport."""

import pytest

from tests.test_sukuyo_transports import (
    test_calendar_and_relations_across_all_real_transports as run_transport_check,
)


@pytest.mark.parametrize("date", ["2017-10-17", "2017-10-19", "1957-09-24"])
def test_sukuyo_pair_comparison_across_actual_transports(monkeypatch, capsys, date):
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
        ["sukuyo.kenyu_lingbi_reference", "sukuyo.calendar", "sukuyo.reading_text"],
    )
