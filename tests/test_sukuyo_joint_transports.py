"""The shared-model condition and full envelope survive all public surfaces."""

import pytest

from tests.test_sukuyo_transports import (
    test_calendar_and_relations_across_all_real_transports as run_transport_check,
)


@pytest.mark.parametrize(
    "first_part, second_part, first_date, first_zone",
    [
        ("first_half", "first_half", "1341-05-24", "+09:00"),
        (None, None, "1341-05-24", "+09:00"),
        ("first_half", "first_half", "1341-05-23", "+08:00"),
        ("second_half", "second_half", "1341-05-24", "+09:00"),
    ],
)
def test_sukuyo_joint_support_across_rest_native_mcp_and_cli(
    monkeypatch, capsys, first_part, second_part, first_date, first_zone
):
    payload = {
        "person1_date": first_date,
        "person1_zone": first_zone,
        "person2_date": "1341-05-24",
        "person2_zone": "+09:00",
        "calendar_profile": "hinoo_t1299_host27",
        "calendar_basis": "japanese_naoj_historical_utc09",
    }
    for key, value in (
        ("person1_calendar_day_part", first_part),
        ("person2_calendar_day_part", second_part),
    ):
        if value is not None:
            payload[key] = value
    run_transport_check(
        monkeypatch,
        capsys,
        "sukuyo_compatibility",
        payload,
        ["person1", "person2", "candidate_relation_analysis", "summary"],
    )
