"""Untimed historical notes must not silently certify half-day reconstructions."""

from datetime import date

import pytest

from fatebridge.core.sukuyo import calendar_mansion, day_evidence
from fatebridge.core.sukuyo_calendar_text import render_day_reading
from fatebridge.core.sukuyo_historical_calendar import date_reference
from fatebridge.core.sukuyo_shogonji import month_header_reference
from scripts.sukuyo.check_sukuyo_shogonji import verify_headers

HISTORICAL = "japanese_naoj_historical_utc09"


def reading(civil, **kwargs):
    calendar = calendar_mansion(
        civil, zone="+09:00", calendar_basis=HISTORICAL, **kwargs
    )
    return calendar, render_day_reading(day_evidence(calendar))


def test_complete_selected_corpus_retains_all_missing_and_qualified_records():
    r = verify_headers()
    assert not r["errors"]
    assert r["month_headers_checked"] == 37
    assert r["year_lengths"] == {1345: 355, 1346: 383, 1347: 354}
    assert r["marginal_qualification_counts"] == {
        "clear": 27,
        "absent_in_selected_header": 8,
        "kana_glyph_uncertain": 1,
        "displaced_stamp": 1,
    }
    assert len(r["observed_marginals_with_different_hinoo_halves"]) == 3
    assert len(r["missing_marginals_with_different_hinoo_halves"]) == 1
    assert not r["daily_annotations_transcribed"]
    assert not r["manuscripts_independently_collated"]


@pytest.mark.parametrize(
    "civil,first,observed",
    [
        ("1346-07-27", "星", "张"),
        ("1347-08-15", "星", "张"),
        ("1347-12-11", "箕", "斗"),
    ],
)
def test_actual_marginal_difference_does_not_overwrite_declared_half(
    civil, first, observed
):
    c, text = reading(
        civil,
        calendar_profile="hinoo_t1299_host27",
        calendar_day_part="first_half",
    )
    assert c["natal_su27"] == first
    assert f"本次主宿{first}与月首朱注候选不同" in text
    assert "不能验收所选半日规则" in text
    assert not c["calendar_reference"]["manuscript_month_header"][
        "reference_applied_to_primary_mansion"
    ]
    second, text = reading(
        civil,
        calendar_profile="hinoo_t1299_host27",
        calendar_day_part="second_half",
    )
    assert second["natal_su27"] == observed
    assert f"本次主宿{observed}与月首朱注候选相同" in text
    assert "不能验收所选半日规则" in text


def test_missing_stamp_is_not_completed_using_generic_prose_anchors():
    c, text = reading("1345-09-05", calendar_profile="hinoo_t1299_host27")
    assert c["natal_su27"] is None
    assert set(c["candidate_su27s"]) == {"轸", "角"}
    header = c["calendar_reference"]["manuscript_month_header"]
    assert header["header"]["marginal_mansion_normalized_candidate"] is None
    assert not header["generic_prose_anchors_fill_missing_annotations"]
    assert "未用作者转引的渡边敏夫配宿表补缺" in text
    assert "也未断言原卷无注" in text


def test_same_leap_result_is_not_a_priority_discriminant():
    c, text = reading(
        "1346-10-24",
        calendar_profile="hinoo_t1299_host27",
        calendar_day_part="first_half",
    )
    precedence = c["profile_calculation"]["short_month_assignment"][
        "leap_short_month_precedence"
    ]
    assert precedence["adjacent_month_first_half"] == "氐"
    assert precedence["repeat_true_month_first_half"] == "氐"
    assert not precedence["source_rule_priority_established"]
    assert "此例没有区分力" in text
    assert "不能确立次序优先级" in text


@pytest.mark.parametrize(
    "civil,expected",
    [
        ("1345-05-11", "两个读字候选均保留"),
        ("1345-06-09", "保留错位，未改成二日实录"),
        ("1346-07-28", "本日不是初一"),
    ],
)
def test_glyph_position_and_nonfirst_day_limits_survive_native_prose(civil, expected):
    _, text = reading(civil)
    assert expected in text
    assert "1345年正文五行是纳音，不能当七曜" in text
    assert "不等于1092天逐日宿曜实录或预测样本" in text


def test_modern_and_uncovered_years_do_not_acquire_a_manuscript_reference():
    for civil in (date(1344, 2, 1), date(1349, 2, 1), date(1, 1, 1)):
        assert "manuscript_month_header" not in date_reference(civil)
    assert month_header_reference(2025, 1, False, 1) is None
    assert month_header_reference(1345, 9, True, 1) is None


def test_reference_mutation_cannot_alter_later_source_bytes_or_readings():
    r = month_header_reference(1346, 9, True, 1)
    r["header"]["marginal_mansion_normalized_candidate"] = "牛"
    r["authors"].clear()
    later = month_header_reference(1346, 9, True, 1)
    assert later["header"]["marginal_mansion_normalized_candidate"] == "氐"
    assert len(later["authors"]) == 3


def test_julian_author_dates_are_converted_before_comparing_input_labels():
    r = verify_headers()
    assert [
        (c["author_julian_date"], c["proleptic_gregorian_date"])
        for c in r["author_julian_date_label_checks"]
    ] == [("1345-09-12", "1345-09-20"), ("1346-02-22", "1346-03-02")]
    assert all(
        c["agrees_with_selected_lunar_date"] and not c["eclipse_astronomy_reproduced"]
        for c in r["author_julian_date_label_checks"]
    )


def test_known_civil_noon_does_not_invent_the_manuscript_annotation_half():
    c, text = reading(
        "1346-07-27", time_text="12:00:00", calendar_profile="hinoo_t1299_host27"
    )
    assert c["birth_time_known"] and c["natal_su27"] is None
    assert set(c["candidate_su27s"]) == {"星", "张"}
    assert "月首朱注未用于消除补配候选" in text


def test_appendix_era_digit_is_not_silently_corrected_to_author_year_assignment():
    c, text = reading("1345-02-11")
    assert c["lunar_year"] == 1345
    reference = c["calendar_reference"]["manuscript_month_header"]
    variant = reference["year_header_variants"][0]
    assert variant["appendix_year_header_literal"] == "康永二年"
    assert not variant["literal_digit_replaced"]
    assert not variant["cause_or_author_erratum_established"]
    assert "二／四差异未改字" in text
    assert "同栏年干支为乙酉" in text


def test_april_stamp_placement_and_glyph_questions_are_separate():
    c, text = reading("1345-05-11")
    reference = c["calendar_reference"]["manuscript_month_header"]
    assert reference["author_placement_notes"][0]["number"] == 3
    assert reference["header"]["marginal_status"] == "kana_glyph_uncertain"
    assert "四月朱印位于初一与初二之间" in text
    assert "两个读字候选均保留" in text


def test_shogonji_semantic_month_length_is_not_formatted_as_a_day_number():
    _, text = reading("1346-07-27")
    assert "1346年7月，月长30日；月首初一干支丁丑" in text
    assert "1346年7月30日，初一干支" not in text


def test_shogonji_semantic_corpus_denominators_are_explicit_in_native_text():
    _, text = reading("1346-02-01")
    for phrase in ("27条清晰", "2条带限定", "8处所选栏未见", "1092是月长合计"):
        assert phrase in text


def test_shogonji_semantic_computed_candidate_labels_are_not_omitted():
    _, text = reading("1345-09-05", calendar_profile="hinoo_t1299_host27")
    assert "候选轸的上卷主表标签为甘露" in text
    assert "候选角的上卷主表未匹配标签" in text
    assert "未作为确定本日标签或事项结论" in text


@pytest.mark.parametrize(
    "civil,phrase",
    [("1345-06-09", "不宜舉百事"), ("1346-02-01", "諸事並不宜作")],
)
def test_shogonji_semantic_no_activity_does_not_erase_material_caution(civil, phrase):
    c, text = reading(civil)
    assert day_evidence(c)["activity_assessment"] is None
    assert phrase in text
    assert "没有事项输入" in text
    assert "未形成事项汇总" in text


def test_shogonji_semantic_unassigned_text_retains_both_substantive_halves():
    _, text = reading(
        "1346-10-24",
        calendar_profile="hinoo_t1299_host27",
        calendar_day_part="first_half",
    )
    assert "凡諸有大為作事並不可作" in text
    assert "宜醞酒漿" in text
    assert "不能单凭段序断定归氐或推广全27宿" in text


@pytest.mark.parametrize(
    "civil,part",
    [("1346-07-27", "first_half"), ("1346-10-24", "second_half")],
)
def test_new_reference_survives_rest_fresh_native_mcp_and_cli(
    monkeypatch, capsys, civil, part
):
    from tests.sukuyo.test_sukuyo_transports import (
        test_calendar_and_relations_across_all_real_transports as check,
    )

    check(
        monkeypatch,
        capsys,
        "suzhan",
        {
            "date": civil,
            "time": "12:00:00",
            "zone": "+09:00",
            "calendar_basis": HISTORICAL,
            "calendar_profile": "hinoo_t1299_host27",
            "calendar_day_part": part,
        },
        [
            "sukuyo.calendar.calendar_reference.manuscript_month_header",
            "sukuyo.calendar.profile_calculation",
            "sukuyo.reading_text",
        ],
    )
