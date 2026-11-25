"""Check natal structure and cross-participant BaZi evidence."""

from fatebridge.core.bazi.bazi_branch_facts import (
    check_clash_patterns,
    check_harmony_patterns,
)
from fatebridge.core.bazi.bazi_evidence import cross_chart_relations
from fatebridge.core.bazi.bazi_pattern_facts import analyze_special_patterns
from fatebridge.core.elements import ElementAnalysis
from fatebridge.core.rules import BaZiRules
from fatebridge.services.calculation import calculate_destiny_analysis
from fatebridge.utils.birth_input import create_person_info


def test_build_structure_profile_detects_yang_ren_jia_sha() -> None:
    pillars = {
        "year": ("庚", "申"),
        "month": ("己", "卯"),
        "day": ("甲", "寅"),
        "hour": ("庚", "午"),
    }

    element_analysis = ElementAnalysis.comprehensive_analysis(pillars)
    structure_profile = BaZiRules.build_structure_profile(
        pillars=pillars,
        element_analysis=element_analysis,
        harmony_patterns=check_harmony_patterns(pillars),
        clash_patterns=check_clash_patterns(pillars),
        special_patterns=analyze_special_patterns(pillars),
    )

    dominant = structure_profile["dominant_structure"]
    assert dominant["key"] == "month_use_reference"
    assert dominant["formation_status"] == "not_adjudicated"
    assert dominant["useful_ten_gods"] == []

    selection = structure_profile["candidate_selection"]
    assert selection["selected_month"]["label"] == "月刃格"
    assert selection["selected_month"]["selection_rule"] == "qualified_yang_blade_seat"
    assert selection["chosen_path_id"] is None
    path = next(row for row in selection["paths"] if row["id"] == "blade_killer")
    assert path["status"] == "requires_force_adjudication"
    assert set(path["observed_conditions"][0]["star_refs"]) == {
        "year:stem:庚",
        "year:hidden:庚",
        "hour:stem:庚",
    }
    candidate = next(
        item
        for item in structure_profile["recognized_structures"]
        if item["key"] == "yang_ren_jia_sha"
    )
    assert candidate["label"] == "羊刃驾杀"
    assert candidate["formation_status"] == "candidate_only"


def test_analyze_harmony_effects_returns_structured_event_payload() -> None:
    pillars = {
        "year": ("甲", "寅"),
        "month": ("丙", "午"),
        "day": ("戊", "戌"),
        "hour": ("辛", "卯"),
    }
    element_analysis = ElementAnalysis.comprehensive_analysis(pillars)
    structure_profile = BaZiRules.build_structure_profile(
        pillars=pillars,
        element_analysis=element_analysis,
        harmony_patterns=check_harmony_patterns(pillars),
        clash_patterns=check_clash_patterns(pillars),
        special_patterns=analyze_special_patterns(pillars),
    )

    events = BaZiRules.analyze_harmony_effects(pillars, structure_profile)

    triple_event = next(event for event in events if event["type"] == "three_harmony")
    assert triple_event["result_element"] == "火"
    assert "strengthens" in triple_event
    assert "consumes" in triple_event
    assert "impact_on_day_master" in triple_event
    assert "impact_on_structure" in triple_event


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
    assert "recognized_structures" in result["patterns"]["special"]
    assert "metadata" in result["patterns"]["special"]


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
