"""Unknown dates and leap candidates retain structured conditional matrices."""

from fatebridge.services.divination import calculate_sukuyo_compatibility

HISTORICAL = "japanese_naoj_historical_utc09"


def test_unknown_dates_explain_all_four_directed_relationship_rows() -> None:
    result = calculate_sukuyo_compatibility(
        person1_name="甲",
        person1_date="1346-07-17",
        person1_zone="+08:00",
        person2_name="乙",
        person2_date="1346-08-29",
        person2_zone="+08:00",
        calendar_basis=HISTORICAL,
    )
    assert result["pair"] is None
    rows = result["candidate_relation_analysis"]["rows"]
    assert {(r["person1_su27"], r["person2_su27"]) for r in rows} == {
        ("奎", "房"),
        ("奎", "心"),
        ("娄", "房"),
        ("娄", "心"),
    }
    assert all(not r["applied_to_primary"] for r in rows)


def test_unresolved_leap_candidate_is_not_called_complete() -> None:
    result = calculate_sukuyo_compatibility(
        person1_date="2025-07-25",
        person1_zone="+08:00",
        person2_date="2025-03-04",
        person2_zone="+08:00",
    )
    assert not result["candidate_relation_analysis"][
        "candidate_set_complete_within_profile"
    ]
    assert result["pair"] is None


def test_declared_half_is_retained_when_leap_priority_remains_unresolved() -> None:
    result = calculate_sukuyo_compatibility(
        person1_date="1341-05-24",
        person1_zone="+09:00",
        person2_date="1349-07-24",
        person2_zone="+09:00",
        calendar_basis=HISTORICAL,
        calendar_profile="hinoo_t1299_host27",
        person1_calendar_day_part="first_half",
        person2_calendar_day_part="first_half",
    )
    assert result["pair"] is None
    assert set(result["person1"]["calendar"]["candidate_su27s"]) == {"参", "毕"}
    assert set(result["person2"]["calendar"]["candidate_su27s"]) == {"星", "鬼"}
    analysis = result["candidate_relation_analysis"]
    assert len(analysis["rows"]) == 2
    assert len(analysis["unconstrained_rows"]) == 4
    assert analysis["shared_reconstruction_analysis"]["unsupported_row_count"] == 2
