"""Shared rule uncertainty must not be mistaken for independent birth inputs."""

from copy import deepcopy

import pytest

from fatebridge.core.sukuyo import calendar_mansion, candidate_relation_analysis
from fatebridge.services.divination import calculate_sukuyo_compatibility

HISTORICAL = "japanese_naoj_historical_utc09"
ADJACENT = "adjacent_month_short_day_assignment"
REPEATED = "repeat_regular_month_first_day_assignment"


def pair(
    date1="1341-05-24",
    date2="1341-05-24",
    part1="first_half",
    part2="first_half",
    **extra,
):
    return calculate_sukuyo_compatibility(
        person1_date=date1,
        person1_zone="+09:00",
        person2_date=date2,
        person2_zone="+09:00",
        calendar_basis=HISTORICAL,
        calendar_profile="hinoo_t1299_host27",
        person1_calendar_day_part=part1,
        person2_calendar_day_part=part2,
        **extra,
    )


def names(rows):
    return {(r["person1_su27"], r["person2_su27"]) for r in rows}


@pytest.mark.parametrize(
    "date2, expected",
    [
        ("1341-05-24", {("参", "参"), ("毕", "毕")}),
        ("1349-07-24", {("参", "星"), ("毕", "鬼")}),
    ],
)
def test_same_reconstruction_cannot_choose_opposite_priorities_for_two_people(
    date2, expected
):
    result = pair(date2=date2)
    analysis = result["candidate_relation_analysis"]
    assert names(analysis["rows"]) == expected
    assert len(analysis["unconstrained_rows"]) == 4
    assert analysis["shared_reconstruction_analysis"]["unsupported_row_count"] == 2
    assert result["status"] == "partial" and result["pair"] is None
    assert all(not r["applied_to_primary"] for r in analysis["rows"])


def test_unknown_halves_are_independent_even_when_rule_hypothesis_is_shared():
    analysis = pair(part1=None, part2=None)["candidate_relation_analysis"]
    assert names(analysis["rows"]) == {
        ("参", "参"),
        ("参", "毕"),
        ("毕", "参"),
        ("毕", "毕"),
    }
    cross = next(
        r
        for r in analysis["rows"]
        if (r["person1_su27"], r["person2_su27"]) == ("参", "毕")
    )
    assert cross["shared_reconstruction_ids"] == [ADJACENT]
    assert any(
        s["person1"]["calendar_day_part"] == "first_half"
        and s["person2"]["calendar_day_part"] == "second_half"
        for s in cross["joint_support"]
    )
    assert analysis["shared_reconstruction_analysis"]["person_half_days_independent"]


def test_only_one_unknown_half_does_not_silently_become_the_other_person_half():
    analysis = pair(part1=None)["candidate_relation_analysis"]
    assert names(analysis["rows"]) == {("参", "参"), ("毕", "参"), ("毕", "毕")}
    assert len(analysis["unconstrained_rows"]) == 4


def test_opposite_declared_halves_retain_both_supported_results_and_models():
    analysis = pair(part2="second_half")["candidate_relation_analysis"]
    assert names(analysis["rows"]) == {("参", "毕"), ("毕", "毕")}
    by_name = {r["person1_su27"]: r for r in analysis["rows"]}
    assert by_name["参"]["shared_reconstruction_ids"] == [ADJACENT]
    assert by_name["毕"]["shared_reconstruction_ids"] == [REPEATED]


def test_supported_date_pairs_are_not_reconstructed_from_marginal_date_unions():
    result = calculate_sukuyo_compatibility(
        person1_date="1341-05-23",
        person1_zone="+08:00",
        person2_date="1341-05-24",
        person2_zone="+09:00",
        calendar_basis=HISTORICAL,
        calendar_profile="hinoo_t1299_host27",
        person1_calendar_day_part="first_half",
        person2_calendar_day_part="first_half",
    )
    analysis = result["candidate_relation_analysis"]
    for row in analysis["rows"]:
        for support in row["joint_support"]:
            assert support["person1"]["natal_su27"] == row["person1_su27"]
            assert support["person2"]["natal_su27"] == row["person2_su27"]
            assert support["person2"]["calendar_date"] == "1341-05-24"
            assert support["person1"]["calendar_date"] in {"1341-05-23", "1341-05-24"}
            if support["person1"]["calendar_date"] == "1341-05-24":
                assert row["person1_su27"] == row["person2_su27"]
    assert len(result["person1"]["calendar"]["calendar_candidates"]) == 2


def test_different_source_bundles_do_not_acquire_an_unproven_shared_binding():
    context = calendar_mansion(
        "1341-05-24",
        zone="+09:00",
        calendar_basis=HISTORICAL,
        calendar_profile="hinoo_t1299_host27",
        calendar_day_part="first_half",
    )
    second = deepcopy(context)
    second["profile_calculation"]["source_bundle_sha256"] = "different-explicit-source"
    before = deepcopy((context, second))
    analysis = candidate_relation_analysis(context, second)
    assert len(analysis["rows"]) == 4
    assert analysis["shared_reconstruction_analysis"]["status"] == "not_shared"
    assert (context, second) == before


def test_incomplete_context_keeps_all_unconstrained_rows_and_does_not_prune():
    context = calendar_mansion(
        "1341-05-24",
        zone="+09:00",
        calendar_basis=HISTORICAL,
        calendar_profile="hinoo_t1299_host27",
        calendar_day_part="first_half",
    )
    second = deepcopy(context)
    second["profile_calculation"][
        "candidate_set_complete_under_declared_reconstructions"
    ] = False
    analysis = candidate_relation_analysis(context, second)
    assert len(analysis["rows"]) == len(analysis["unconstrained_rows"]) == 4
    assert analysis["shared_reconstruction_analysis"]["status"] == "incomplete"
    assert not analysis["candidate_set_complete_within_profile"]


def test_native_explanation_retains_unsupported_matrix_and_does_not_certify_a_source_rule():
    result = pair()
    text = result["summary"]
    assert "共同采用同一套" in text
    assert "无共同重建支持" in text and "参→毕为友" in text
    assert "原无约束矩阵4行" in text
    assert "不证明古代各时期规则统一" in text
    shared = result["candidate_relation_analysis"]["shared_reconstruction_analysis"]
    assert not shared["source_priority_established"]
    assert not shared["historical_uniformity_established"]


def test_both_resolved_second_halves_do_not_select_a_reconstruction_model():
    result = pair(part1="second_half", part2="second_half")
    analysis = result["candidate_relation_analysis"]
    assert result["pair"] == "命" and result["status"] == "computed"
    assert analysis["status"] == "not_needed" and analysis["rows"] == []
    shared = analysis["shared_reconstruction_analysis"]
    assert shared["status"] == "not_needed" and shared["support_coverage_complete"]
    assert {s["reconstruction_id"] for s in shared["resolved_support"]} == {
        ADJACENT,
        REPEATED,
    }
    assert "宿名虽已定，仍不能确定采用哪种重建" in result["summary"]


def test_repeat_model_retains_earlier_short_month_even_after_a_long_month():
    result = calculate_sukuyo_compatibility(
        person1_date="1903-06-25",
        person2_date="1957-09-24",
        calendar_profile="hinoo_t1299_host27",
        person1_calendar_day_part="first_half",
        person2_calendar_day_part="first_half",
    )
    assert (
        result["person2"]["calendar"]["profile_calculation"]["short_month_assignment"][
            "previous_lunar"
        ]["lunar_day"]
        == 30
    )
    analysis = result["candidate_relation_analysis"]
    assert names(analysis["rows"]) == {("鬼", "角"), ("参", "轸")}
    assert len(analysis["unconstrained_rows"]) == 4


def test_model_independent_person_is_compatible_with_both_shared_models():
    result = pair(date2="1341-05-25", part2=None)
    analysis = result["candidate_relation_analysis"]
    assert len(analysis["rows"]) == 2
    assert {
        s["reconstruction_id"] for r in analysis["rows"] for s in r["joint_support"]
    } == {ADJACENT, REPEATED}
    assert all(
        s["person2"]["assignment_origin"] == "profile_result_model_independent"
        for r in analysis["rows"]
        for s in r["joint_support"]
    )


def test_missing_model_evidence_means_unknown_support_not_proven_unsupported():
    context = calendar_mansion(
        "1341-05-24",
        zone="+09:00",
        calendar_basis=HISTORICAL,
        calendar_profile="hinoo_t1299_host27",
        calendar_day_part="first_half",
    )
    second = deepcopy(context)
    second["profile_calculation"]["short_month_assignment"][
        "leap_short_month_precedence"
    ]["reconstruction_calculations"].pop()
    analysis = candidate_relation_analysis(context, second)
    assert analysis["shared_reconstruction_analysis"]["status"] == "incomplete"
    assert len(analysis["rows"]) == 4
    assert all(r["joint_support_status"] == "not_determined" for r in analysis["rows"])


@pytest.mark.parametrize(
    "part1,part2,expected",
    [
        ("first_half", "first_half", {("参", "参"), ("毕", "毕")}),
        ("first_half", "second_half", {("参", "毕"), ("毕", "毕")}),
        ("first_half", None, {("参", "参"), ("参", "毕"), ("毕", "毕")}),
        ("second_half", "first_half", {("毕", "参"), ("毕", "毕")}),
        ("second_half", "second_half", {("毕", "毕")}),
        ("second_half", None, {("毕", "参"), ("毕", "毕")}),
        (None, "first_half", {("参", "参"), ("毕", "参"), ("毕", "毕")}),
        (None, "second_half", {("参", "毕"), ("毕", "毕")}),
        (None, None, {("参", "参"), ("参", "毕"), ("毕", "参"), ("毕", "毕")}),
    ],
)
def test_complete_half_condition_table_from_reviewed_model_vectors(
    part1, part2, expected
):
    # These nine expected sets expand the independently reviewed A/B control
    # vectors. They are logical controls, not nine historical observations.
    analysis = pair(part1=part1, part2=part2)["candidate_relation_analysis"]
    shared = analysis["shared_reconstruction_analysis"]
    actual = names(analysis["rows"])
    if shared["status"] == "not_needed":
        actual = {
            (s["person1"]["natal_su27"], s["person2"]["natal_su27"])
            for s in shared["resolved_support"]
        }
    assert actual == expected
    assert shared["support_coverage_complete"]


def test_native_joint_reading_explains_each_reconstruction_predecessor():
    text = pair()["summary"]
    assert "相邻前月有29日" in text
    assert "前半按4月30日查得参" in text
    assert "所用前月末为农历3月30日" in text
    assert "前半按4月1日查得毕" in text
    assert "T2465十二月三十日星/室字面差异" in text


def test_native_long_month_case_explains_earlier_short_month():
    result = calculate_sukuyo_compatibility(
        person1_date="1903-06-25",
        person2_date="1957-09-24",
        calendar_profile="hinoo_t1299_host27",
        person1_calendar_day_part="first_half",
        person2_calendar_day_part="first_half",
    )
    assert "相邻前月有30日" in result["summary"]
    assert "所用前月末为农历7月29日" in result["summary"]


def test_resolved_joint_output_keeps_input_profile_and_source_uncertainty():
    text = pair(part1="second_half", part2="second_half")["summary"]
    assert "输入当地日期1341-05-24，时区+09:00" in text
    assert "T2465十二月三十日星/室字面差异" in text
    assert "宿名虽已定，仍不能确定采用哪种重建" in text


def test_model_independent_resolved_hinoo_pair_also_retains_source_reference():
    result = pair(date1="1341-05-25", date2="1341-05-26", part1=None, part2=None)
    assert result["status"] == "computed"
    assert "shared_reconstruction_analysis" not in result["candidate_relation_analysis"]
    assert "T2465十二月三十日星/室字面差异" in result["summary"]
    assert "写成日期未定" in result["summary"]


def test_resolved_native_relation_keeps_both_actual_directional_meanings():
    result = pair(part1="second_half", part2="second_half")
    assert "前向含义：" + result["person1_to_person2"]["meaning"] in result["summary"]
    assert "反向含义：" + result["person2_to_person1"]["meaning"] in result["summary"]


def test_native_joint_reading_identifies_actual_modern_calendar_backend_and_sources():
    result = calculate_sukuyo_compatibility(
        person1_date="1903-06-25",
        person2_date="1957-09-24",
        calendar_profile="hinoo_t1299_host27",
        person1_calendar_day_part="first_half",
        person2_calendar_day_part="first_half",
    )
    assert "modern_chinese_lunisolar" in result["summary"]
    assert "lunardate" in result["summary"] and "UTC+08:00" in result["summary"]
    for person in ("person1", "person2"):
        assert result[person]["calendar"]["calendar_source"] in result["summary"]


def test_native_joint_source_explains_active_sat_capture_and_five_apparatus_notes():
    text = pair()["summary"]
    for necessary in (
        "实慧《桧尾口诀》",
        "T2465_.78.0030c13-21",
        "T2465_.78.0030c21-26",
        "SAT完整HTML",
        "74c63f5151c2b8c3ac554f7a0acae0776e5247e740a712834e1b600a065050e6",
        "历史缓存",
        "建久六年",
        "寶暦十一年",
        "訣＝説イ＜甲＞",
        "十＝月＜甲＞",
        "〔是正･･･月〕十六字イ－＜甲＞",
        "〔宿〕－＜甲＞",
        "半＋（也）＜甲＞",
        "直宿無改代也",
        "未接纳",
    ):
        assert necessary in text


def test_native_joint_source_keeps_daybreak_separate_from_hinoo_half():
    text = pair()["summary"]
    assert "平明" in text and "明日曉時" in text
    assert "日夜各8时" in text
    assert "现代钟时" in text and "太阳高度" in text
    assert "Kotyk 2022" in text


def test_native_candidate_palace_preserves_actual_ruler_variant():
    text = pair(date2="1349-07-24")["summary"]
    assert "大陽" in text and "太陽" in text
    assert "CBETA app 0387023" in text
