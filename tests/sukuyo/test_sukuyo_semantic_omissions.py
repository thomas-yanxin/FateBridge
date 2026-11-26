"""Structured Sukuyo day and compatibility facts without prose reading walls."""

import pytest

from fatebridge.core.sukuyo.calendar import calendar_mansion, day_evidence
from fatebridge.services.divination import calculate_sukuyo_compatibility

HISTORICAL = "japanese_naoj_historical_utc09"


@pytest.mark.parametrize("civil", ["1346-08-30", "1346-08-29"])
def test_heart_source_restriction_is_retained_beside_general_favorable_day(
    civil: str,
) -> None:
    c = calendar_mansion(
        civil,
        time_text="23:30:00" if civil.endswith("29") else "12:00:00",
        zone="+08:00" if civil.endswith("29") else "+09:00",
        calendar_basis=HISTORICAL,
    )
    d = day_evidence(c)
    assert d["day_mansion"] == "心" and d["activity_assessment"] is None
    assert "reading_text" not in d
    assert any(
        c["assessment"] == "favorable" for c in d["calendar_day"]["classifications"]
    )


@pytest.mark.parametrize("part", [None, "first_half"])
def test_unresolved_mansion_retains_candidate_list_and_palace(
    part: str | None,
) -> None:
    c = calendar_mansion(
        "1341-05-24",
        time_text="12:00:00",
        zone="+09:00",
        calendar_basis=HISTORICAL,
        calendar_profile="hinoo_t1299_host27",
        calendar_day_part=part,
    )
    d = day_evidence(c)
    assert d["day_mansion"] is None and set(c["candidate_su27s"]) == {"参", "毕"}
    assert "reading_text" not in d
    assert d["palace_reference"]["mansion_candidates"] == ["参", "毕"]


def test_pair_structured_data_preserves_date_candidates_and_resolved_palace() -> None:
    r = calculate_sukuyo_compatibility(
        person1_name="甲",
        person1_date="1346-07-17",
        person1_zone="+08:00",
        person2_name="乙",
        person2_date="1346-08-29",
        person2_zone="+08:00",
        calendar_basis=HISTORICAL,
    )
    assert r["person2"]["palace_reference"]["selected_palace"]["name"] == "蝎宫"
    assert r["person1"]["calendar"]["date_support"]["utc_support_intervals"]
    assert r["person2"]["calendar"]["date_support"]["utc_support_intervals"]
    assert "candidate_relation_analysis" in r
