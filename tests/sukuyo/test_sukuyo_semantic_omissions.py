"""Retained first-review omissions must fail before their native-text repairs."""

import pytest

from fatebridge.core.sukuyo import calendar_mansion, day_evidence
from fatebridge.services.divination import calculate_sukuyo_compatibility

HISTORICAL = "japanese_naoj_historical_utc09"


@pytest.mark.parametrize("civil", ["1346-08-30", "1346-08-29"])
def test_heart_source_restriction_is_retained_beside_general_favorable_day(civil):
    c = calendar_mansion(
        civil,
        time_text="23:30:00" if civil.endswith("29") else "12:00:00",
        zone="+08:00" if civil.endswith("29") else "+09:00",
        calendar_basis=HISTORICAL,
    )
    d = day_evidence(c)
    assert d["day_mansion"] == "心" and d["activity_assessment"] is None
    assert "唯除营功德事自余不可" in d["reading_text"]
    assert "原段" in d["reading_text"]


@pytest.mark.parametrize("part", [None, "first_half"])
def test_unresolved_mansion_retains_conditional_rasetsu_meaning(part):
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
    assert "不宜舉百事" in d["reading_text"]
    assert "候选取参" in d["reading_text"]
    assert "未形成事项汇总" in d["reading_text"]


def test_pair_native_preserves_input_uncovered_day_and_resolved_palace_sublayer():
    r = calculate_sukuyo_compatibility(
        person1_name="甲",
        person1_date="1346-07-17",
        person1_zone="+08:00",
        person2_name="乙",
        person2_date="1346-08-29",
        person2_zone="+08:00",
        calendar_basis=HISTORICAL,
    )
    text = r["summary"]
    assert "甲输入当地日期1346-07-17，时区+08:00，时刻未知" in text
    assert "乙输入当地日期1346-08-29，时区+08:00，时刻未知" in text
    assert "实际配宿档案t1299_fullmoon27" in text
    assert "1346-08-29未被本批逐日旁注选录覆盖" in text
    assert "不等于原卷无注" in text
    assert "乙：按已列历日宿名查原典分足表，表内宫名候选只有蝎宫" in text
    assert "未确定个人本命宫" in text
    assert "UTC支持区间" in text
    assert "字面28宿表为危" in text
    assert "字面28宿表为室" in text
    assert "不覆盖本次27宿或三九结果" in text
