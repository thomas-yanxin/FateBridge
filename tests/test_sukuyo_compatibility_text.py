"""Unknown dates still require the actual conditional relationships in prose."""

from fatebridge.services.divination import calculate_sukuyo_compatibility

HISTORICAL = "japanese_naoj_historical_utc09"


def test_unknown_dates_explain_all_four_directed_relationship_rows():
    result = calculate_sukuyo_compatibility(
        person1_name="甲",
        person1_date="1346-07-17",
        person1_zone="+08:00",
        person2_name="乙",
        person2_date="1346-08-29",
        person2_zone="+08:00",
        calendar_basis=HISTORICAL,
    )
    text = result["summary"]
    assert result["pair"] is None
    for phrase in (
        "甲的参考日期1346-07-17：1346年6月20日，宿奎",
        "甲的参考日期1346-07-18：1346年6月21日，宿娄",
        "乙的参考日期1346-08-29：1346年8月4日，宿房",
        "乙的参考日期1346-08-30：1346年8月5日，宿心",
        "奎→房为親，反向为栄",
        "奎→心为胎，反向为業",
        "娄→房为友，反向为衰",
        "娄→心为親，反向为栄",
    ):
        assert phrase in text
    assert "需审慎一侧" in text and "宜结交一侧" in text
    assert "不是优劣排名或概率" in text
    assert all(
        not r["applied_to_primary"]
        for r in result["candidate_relation_analysis"]["rows"]
    )


def test_unresolved_leap_candidate_is_not_called_complete_in_native_text():
    result = calculate_sukuyo_compatibility(
        person1_date="2025-07-25",
        person1_zone="+08:00",
        person2_date="2025-03-04",
        person2_zone="+08:00",
    )
    assert not result["candidate_relation_analysis"][
        "candidate_set_complete_within_profile"
    ]
    assert "候选集未穷尽" in result["summary"]
    assert "已列组合不能当全部可能关系" in result["summary"]
    assert result["pair"] is None


def test_declared_half_is_retained_when_leap_priority_remains_unresolved():
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
    assert "原典前半已声明" in result["summary"]
    assert "候选参、毕" in result["summary"] and "候选星、鬼" in result["summary"]
    analysis = result["candidate_relation_analysis"]
    assert len(analysis["rows"]) == 2
    assert len(analysis["unconstrained_rows"]) == 4
    assert analysis["shared_reconstruction_analysis"]["unsupported_row_count"] == 2
