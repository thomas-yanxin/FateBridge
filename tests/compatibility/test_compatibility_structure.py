"""Check natal structure and cross-participant BaZi evidence."""

from fatebridge.core.bazi.compatibility import (
    analyze_cross_shensha,
    analyze_day_pillar_synergy,
    analyze_element_complementarity,
    analyze_nayin_compatibility,
    cross_chart_relations,
)
from fatebridge.core.bazi.relations import (
    check_clash_patterns,
    check_harmony_patterns,
)
from fatebridge.core.bazi.strength import analyze_elements_and_structure
from fatebridge.services.calculation import calculate_destiny_analysis
from fatebridge.utils.birth_input import create_person_info


def test_build_structure_profile_detects_yang_ren_jia_sha() -> None:
    pillars = {
        "year": ("庚", "申"),
        "month": ("己", "卯"),
        "day": ("甲", "寅"),
        "hour": ("庚", "午"),
    }

    element_analysis = analyze_elements_and_structure(pillars)
    structure_profile = element_analysis["structure_profile"]

    assert structure_profile["assessment_status"] == "adjudicated"
    assert structure_profile["useful_elements"]
    dominant = structure_profile["dominant_structure"]
    assert dominant["key"] == "yue_ren"
    assert dominant["label"] == "月刃格"
    assert dominant["formation_status"] == "formed"
    assert "羊刃驾杀" in dominant["rescues"]
    assert any(
        item["key"] == "yang_ren_jia_sha" and item["formation_status"] == "formed"
        for item in structure_profile["recognized_structures"]
    )


def test_analyze_harmony_patterns_detects_three_harmony() -> None:
    pillars = {
        "year": ("甲", "寅"),
        "month": ("丙", "午"),
        "day": ("戊", "戌"),
        "hour": ("辛", "卯"),
    }
    element_analysis = analyze_elements_and_structure(pillars)
    harmonies = check_harmony_patterns(pillars)

    assert any(
        triple["branches"] == ["寅", "午", "戌"] and triple["type"] == "三合火局"
        for triple in harmonies["three_harmony"]
    )
    assert element_analysis["favorable_elements"]


def test_cross_chart_includes_six_breaks_and_hidden_combinations() -> None:
    first = {
        "year": ("甲", "子"),
        "month": ("丙", "寅"),
        "day": ("甲", "午"),
        "hour": ("庚", "辰"),
    }
    second = {
        "year": ("乙", "酉"),
        "month": ("丁", "丑"),
        "day": ("己", "亥"),
        "hour": ("辛", "未"),
    }
    merged = cross_chart_relations(first, second)
    kinds = {row["kind"] for row in merged["pairs"]}
    assert "六破" in kinds  # 子-酉
    assert "暗合" in kinds  # 寅-丑, 午-亥

    assert ["子", "酉"] in check_clash_patterns(
        {
            "year": ("甲", "子"),
            "month": ("乙", "酉"),
            "day": ("丙", "寅"),
            "hour": ("丁", "卯"),
        }
    )["six_break"]
    assert check_harmony_patterns(
        {
            "year": ("甲", "寅"),
            "month": ("乙", "丑"),
            "day": ("丙", "午"),
            "hour": ("丁", "亥"),
        }
    )["hidden_harmony"]


def test_nayin_day_pillar_synergy_complementarity_and_cross_shensha() -> None:
    first = {
        "year": ("庚", "午"),
        "month": ("辛", "巳"),
        "day": ("甲", "子"),
        "hour": ("庚", "辰"),
    }
    second = {
        "year": ("辛", "未"),
        "month": ("丁", "亥"),
        "day": ("己", "丑"),
        "hour": ("丙", "寅"),
    }
    nayin = analyze_nayin_compatibility(first, second)
    assert nayin["person1_year_nayin"] == "路旁土"
    assert nayin["person2_year_nayin"] == "路旁土"
    assert nayin["relation"] == "比和"

    synergy = analyze_day_pillar_synergy(first, second)
    assert synergy["stem_combination"] is True  # 甲己合
    assert synergy["branch_six_harmony"] is True  # 子丑合
    assert synergy["yuanyang_he"] is True

    comp = analyze_element_complementarity(
        ["水", "木"],
        ["火", "土"],
        {"金": 20.0, "木": 10.0, "水": 10.0, "火": 40.0, "土": 20.0},
        ["火", "土"],
        ["水", "木"],
        {"金": 15.0, "木": 30.0, "水": 35.0, "火": 10.0, "土": 10.0},
    )
    assert "水" in comp["person2_supports_person1_useful"]
    assert "火" in comp["person1_supports_person2_useful"]

    shensha = analyze_cross_shensha(first, second)
    assert "person1_activated_by_person2" in shensha
    assert "person2_activated_by_person1" in shensha


def test_analyze_combined_chart_events_detects_cross_person_three_harmony() -> None:
    person1_pillars = {
        "year": ("甲", "申"),
        "month": ("丁", "子"),
        "day": ("甲", "寅"),
        "hour": ("丙", "午"),
    }
    person2_pillars = {
        "year": ("乙", "辰"),
        "month": ("己", "酉"),
        "day": ("辛", "卯"),
        "hour": ("壬", "戌"),
    }

    merged = cross_chart_relations(person1_pillars, person2_pillars)

    event = next(
        item
        for item in merged["groups"]
        if item["kind"] == "三合" and item["branches"] == ["申", "子", "辰"]
    )
    assert event["positions"] == ["person1.year", "person1.month", "person2.year"]
    assert event["natal_matches"] == []
    assert event["source_scope"] == "cross_person"


def test_calculate_destiny_analysis_exposes_structure_profile() -> None:
    person = create_person_info(
        birth_year=1994,
        birth_month=8,
        birth_day=23,
        birth_hour=14,
        name="张三",
        gender="男",
        birth_place="上海",
        birth_minute=30,
        birth_timezone="Asia/Shanghai",
    )

    result = calculate_destiny_analysis(person)

    assert "structure_profile" in result
    assert (
        result["favorable_elements"] == result["structure_profile"]["useful_elements"]
    )
    assert result["structure_profile"]["assessment_status"] == "adjudicated"
    assert result["structure_profile"]["dominant_structure"]["key"]
    assert "harmony" in result["patterns"]


def test_cross_chart_day_stem_control_and_branch_clash_are_two_facts() -> None:
    first = dict(
        zip(
            ("year", "month", "day", "hour"),
            map(tuple, ("甲申", "丙子", "甲子", "庚辰")),
        )
    )
    second = {**first, "day": ("戊", "午")}
    relations = cross_chart_relations(first, second)
    assert {
        row["kind"]
        for row in relations["pairs"]
        if row["positions"] == ["person1.day", "person2.day"]
    } >= {"六冲", "天干相克"}
