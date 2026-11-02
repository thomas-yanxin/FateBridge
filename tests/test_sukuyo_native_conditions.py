"""Native explanations must deliver computed conditions, not only caveats."""

import pytest

from fatebridge.core.sukuyo import calendar_mansion, day_evidence


@pytest.mark.parametrize(
    "date,known_inside,known_outside,unknown_count",
    [("1957-09-24", "火", None, 6), ("1903-06-25", "日", "月", 5)],
)
def test_native_leap_month_delivers_all_conditions_without_selecting_one(
    date, known_inside, known_outside, unknown_count
):
    day = day_evidence(
        calendar_mansion(
            date,
            "06:30:00",
            calendar_profile="hinoo_t1299_host27",
            calendar_day_part="first_half",
        ),
        "角",
        "travel",
    )
    reference = day["kenyu_lingbi_reference"]
    text = day["reading_text"]
    assert reference["selected_civil_month_start_lookup"] is None
    assert len(reference["conditional_month_start_lookups"]) == 7
    assert text.count("本月未列，成员判断未定") == unknown_count
    assert f"若月首{known_inside}曜，表列" in text and "本日在内" in text
    if known_outside:
        assert f"若月首{known_outside}曜，表列" in text and "本日在外" in text
    for condition in reference["conditional_month_start_lookups"]:
        assert f"若月首{condition['condition_month_start_luminary']}曜" in text
        for interval in condition["matching_intervals"]:
            assert interval["literal"] in text
    assert not reference["applied_to_primary_or_activities"]
    assert day["day_mansion"] is None


@pytest.mark.parametrize("zone", ["+14:00", "America/New_York"])
def test_native_unknown_clock_explains_every_support_interval_without_imputation(zone):
    day = day_evidence(
        calendar_mansion("2024-02-11", zone=zone),
        "角",
        "clothing",
        ["wearing_new_garments"],
    )
    support = day["calendar"]["date_support"]
    assert not support["birth_time_imputed"]
    assert len(day["candidate_days"]) >= 2
    for row in support["utc_support_intervals"]:
        expected = (
            f"参考历日{row['calendar_date']}由UTC区间"
            f"[{row['start_utc_inclusive']}, {row['end_utc_exclusive']})支持。"
        )
        assert expected in day["reading_text"]
    assert "不是实际出生时刻或概率" in day["reading_text"]
    assert day["day_mansion"] is None


def test_native_named_peak_keeps_its_specific_meaning_and_learning_uncovered():
    day = day_evidence(
        calendar_mansion("2025-04-14", "06:30:00"),
        "室",
        "study",
        ["religious_learning"],
    )
    assert day["special_day_evidence"]["primary"]["matched_labels"] == ["金刚峰"]
    assert day["activity_assessment"]["evidence_status"] == "uncovered"
    assert "金刚峰标签的传统词义另参考下卷大正" in day["reading_text"]
    assert "降伏法" in day["reading_text"] and "作護摩" in day["reading_text"]
    assert "未声称其他印本说明全文相同" in day["reading_text"]


def test_native_candidate_nectar_is_not_called_an_empty_match_or_selected():
    day = day_evidence(
        calendar_mansion(
            "1903-06-25",
            "03:20:00",
            calendar_profile="hinoo_t1299_host27",
            calendar_day_part="first_half",
        ),
        "室",
        "commerce",
    )
    candidate = day["special_day_evidence"]["candidate_primary"][0]
    assert candidate["mansion"] == "鬼" and candidate["matched_labels"] == ["甘露"]
    assert "不以该支空匹配" not in day["reading_text"]
    assert "甘露标签的传统词义另参考下卷大正" in day["reading_text"]
    assert "受灌頂法" in day["reading_text"] and "習學經法" in day["reading_text"]
    assert day["day_mansion"] is None
