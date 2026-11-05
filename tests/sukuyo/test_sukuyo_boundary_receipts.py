"""A single reference day must retain one explicit weekday boundary everywhere."""

from datetime import date

import pytest

from fatebridge.core.sukuyo import calendar_mansion, day_evidence, rulesets
from fatebridge.core.sukuyo_special_days import (
    scope_for_weekday_basis,
    special_day_evidence,
)

BASES = [
    ("chinese_hko_utc08", "2000-01-01", "1999-12-31", "08"),
    ("japanese_hutime_1002_1_utc09", "2000-01-01", "2000-01-01", "09"),
    ("japanese_naoj_historical_utc09", "0820-03-22", "0820-03-22", "09"),
]


def assert_same_boundary(day, offset):
    expected = f"modern_utc_plus{offset}_civil_midnight"
    assert day["weekday"]["basis"] == expected
    assert day["special_day_evidence"]["weekday_basis"] == expected
    assert f"现代UTC+{offset}历日" in day["special_day_evidence"]["scope"]
    assert (
        f"现代UTC+{('08' if offset == '09' else '09')}历日"
        not in day["special_day_evidence"]["scope"]
    )
    assert day["lower_methods"]["weekday"]["basis"] == expected
    expected_index = (
        date.fromisoformat(day["calendar"]["calendar_date"]).weekday() + 1
    ) % 7
    assert day["weekday"]["index_sunday_zero"] == expected_index
    assert day["special_day_evidence"]["weekday_index"] == expected_index
    assert not day["special_day_evidence"]["classical_daybreak_boundary_acceptance"]


@pytest.mark.parametrize("basis,entered,reference,offset", BASES)
def test_known_clock_preserves_selected_host_day_in_all_weekday_layers(
    basis, entered, reference, offset
):
    calendar = calendar_mansion(entered, "00:30:00", "+09:00", calendar_basis=basis)
    assert calendar["calendar_date"] == reference
    assert (
        f"现代UTC+{offset}历日"
        in rulesets(calendar_basis=basis)["special_days"]["scope"]
    )
    day = day_evidence(calendar)
    assert_same_boundary(day, offset)
    text = day["reading_text"]
    assert calendar["input_datetime"] in text
    assert f"输入时区{calendar['input_timezone']}" in text
    assert f"所选宿主时区{calendar['calendar_timezone']}" in text
    assert f"参考历日为{reference}" in text
    assert "将同一时刻换算" in text
    assert (
        "换算后参考历日与输入当地日期不同"
        if entered != reference
        else "换算后参考历日与输入当地日期相同"
    ) in text
    assert "本次七曜与特殊日索引均按该参考历日" in text
    assert "已知民用钟时不表示已确定古代平明日界" in text


def test_next_host_day_reading_explains_same_instant_and_both_timezones():
    calendar = calendar_mansion(
        "2000-01-01",
        "23:30:00",
        "+08:00",
        calendar_basis="japanese_hutime_1002_1_utc09",
    )
    day = day_evidence(calendar)
    assert day["day_mansion"] == "尾"
    assert calendar["calendar_date"] == "2000-01-02"
    assert "2000-01-01T23:30:00+08:00" in day["reading_text"]
    assert "输入时区+08:00" in day["reading_text"]
    assert "所选宿主时区UTC+09:00" in day["reading_text"]
    assert "参考历日为2000-01-02" in day["reading_text"]
    assert "换算后参考历日与输入当地日期不同" in day["reading_text"]
    assert_same_boundary(day, "09")


@pytest.mark.parametrize("basis,entered,reference,offset", BASES)
def test_unknown_clock_keeps_each_reference_day_and_its_boundary(
    basis, entered, reference, offset
):
    calendar = calendar_mansion(entered, zone="+00:00", calendar_basis=basis)
    assert calendar["status"] == "partial"
    day = day_evidence(calendar)
    assert day["special_day_evidence"] is None
    assert len(day["candidate_days"]) == 2
    assert len({r["calendar"]["calendar_date"] for r in day["candidate_days"]}) == 2
    for branch in day["candidate_days"]:
        assert_same_boundary(branch, offset)
        assert "推导候选" in branch["reading_text"]
        assert "不是另一个已观测的出生日期" in branch["reading_text"]
        assert "已知输入民用时刻" not in branch["reading_text"]
        assert "仅知输入当地日期" not in branch["reading_text"]
    assert f"出生当地日期{entered}（+00:00）" in day["reading_text"]
    assert "未补造出生时刻" in day["reading_text"]


def test_date_only_same_host_reading_does_not_invent_an_observed_clock():
    calendar = calendar_mansion("2000-01-01", zone="+08:00")
    text = day_evidence(calendar)["reading_text"]
    assert "仅知输入当地日期2000-01-01（输入时区+08:00）" in text
    assert "未提供出生钟时" in text
    assert "已知输入民用时刻" not in text
    assert "None" not in text


@pytest.mark.parametrize("basis", ["", "UTC+09:00", "classical_daybreak", None])
def test_special_lookup_rejects_unestablished_or_missing_boundary(basis):
    with pytest.raises(ValueError, match="七曜依据"):
        special_day_evidence("尾", 0, weekday_basis=basis)


def test_special_lookup_cannot_default_a_missing_boundary():
    with pytest.raises(TypeError, match="weekday_basis"):
        special_day_evidence("尾", 0)


@pytest.mark.parametrize(
    "changed", ["metadata changed", "现代UTC+08历日现代UTC+08历日"]
)
def test_changed_or_ambiguous_metadata_anchor_requires_revalidation(changed):
    with pytest.raises(ValueError, match="占位已改变"):
        scope_for_weekday_basis(changed, "modern_utc_plus09_civil_midnight")


@pytest.mark.parametrize(
    "civil,adjacent,repeated",
    [
        ("1903-06-25", "前半按5月30日查得鬼", "前半按5月1日查得参"),
        ("1957-09-24", "前半按8月1日查得角", "前半按7月30日查得轸"),
    ],
)
def test_native_reading_explains_both_derivations_and_separates_manuscript_evidence(
    civil, adjacent, repeated
):
    day = day_evidence(
        calendar_mansion(
            civil,
            calendar_profile="hinoo_t1299_host27",
            calendar_day_part="first_half",
        )
    )
    text = day["reading_text"]
    assert adjacent in text and repeated in text
    assert "相邻月补配重建" in text and "重用普通月初一重建" in text
    assert "京都大学藏《檜尾口決 朱校》第28幅所选黑字" in text
    assert "12月30日室；大正选文" in text
    assert "12月30日星；本档案宿主望宿算法" in text
    assert "写本例题未替换计算结果" in text
    assert "未识别为大正底本或甲本" in text
    assert "尚未完成全本校勘" in text
    assert "不将其认定为无条件删文" in text
    assert day["calendar"]["natal_su27"] is None


def test_explicit_second_half_keeps_bounded_source_conditions_in_native_reading():
    day = day_evidence(
        calendar_mansion(
            "2024-08-04",
            "09:00:00",
            calendar_profile="hinoo_t1299_host27",
            calendar_day_part="second_half",
        )
    )
    assert day["calendar"]["natal_su27"] == "张"
    assert "按此取宿，没有按民用钟时自动判半" in day["reading_text"]
    assert "不据所选例题裁定补配次序或半日钟时" in day["reading_text"]


def test_default_profile_does_not_inherit_hinoo_manuscript_claims():
    day = day_evidence(calendar_mansion("2025-03-04"))
    # The library also holds the separately identified RB00017017 print.
    # Check Hinoo evidence itself, not a shared institution's name.
    assert day["calendar"]["profile_calculation"]["hinoo_source"] is None
    assert "京都所选末句候选" not in day["reading_text"]
    assert "京都大学藏《檜尾口決 朱校》" not in day["reading_text"]
    assert "十六字校记" not in day["reading_text"]
    assert day["calendar"]["natal_su27"] == "毕"
    direct = day["special_day_evidence"]["direct_printed_comparisons"][1]
    assert direct["source_reference"]["record_id"] == "RB00017017"
    assert direct["witness"] == "lower_kyoto_enpo_selected"
    assert not direct["applied_to_primary"]
    assert "RB00017017" in day["reading_text"]
    phase_reference = day["calendar_day"]["clock_doctrine"][
        "senmyo_phase_annotation_reference"
    ]
    assert phase_reference["current_input_phase_annotation_status"] == "not_evaluated"
    assert not phase_reference["scope"]["hinoo_half_mapping_established"]
    assert not phase_reference["scope"]["leap_short_month_priority_established"]
