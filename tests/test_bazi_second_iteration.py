"""Qualification counterexamples and explicit birth-clock sensitivity."""

from datetime import datetime

import pytest

from fatebridge.analysis.timing_effects import TimingEffectsAnalysis
from fatebridge.core.classical import determine_monthly_structure
from fatebridge.services.timing import (
    calculate_comprehensive_timing,
    calculate_dayun_analysis,
)
from fatebridge.utils.birth_input import create_person_info


@pytest.mark.parametrize(
    "stem,branch", list(zip("甲乙丙丁戊己庚辛壬癸", "寅卯巳午巳午申酉亥子"))
)
def test_lu_qualification_uses_actual_seat_even_when_main_qi_is_not_peer(stem, branch):
    chart = {
        "year": ("庚", "申"),
        "month": ("甲", branch),
        "day": (stem, "子"),
        "hour": ("壬", "子"),
    }
    result = determine_monthly_structure(chart, stem)
    assert result["label"] == "建禄格"
    assert result["structure_god"]["ten_god"] == "比肩"
    assert result["selection_rule"] == "qualified_lu_seat"


@pytest.mark.parametrize("stem,branch", list(zip("甲丙戊庚壬", "卯午午酉子")))
def test_yang_blade_is_qualified_by_seat_not_main_hidden_god(stem, branch):
    chart = {
        "year": ("庚", "申"),
        "month": ("甲", branch),
        "day": (stem, "子"),
        "hour": ("壬", "子"),
    }
    result = determine_monthly_structure(chart, stem)
    assert result["label"] == "月刃格"
    assert result["structure_god"]["ten_god"] == "劫财"
    assert result["seat_qualification"]["is_yang_blade"]


def test_miscellaneous_qi_preserves_revealed_meeting_without_claiming_transformation():
    chart = {
        "year": ("壬", "戌"),
        "month": ("丁", "未"),
        "day": ("戊", "申"),
        "hour": ("乙", "卯"),
    }
    result = determine_monthly_structure(chart, "戊")
    assert result["label"] == "正官格"
    assert result["selection_rule"] == "misc_revealed_meeting_support"
    assert not result["is_special"]
    # Removing the actual 卯 changes this prerequisite, rather than preserving
    # a source-case lookup answer for every chart with these four stems.
    changed = determine_monthly_structure({**chart, "hour": ("乙", "酉")}, "戊")
    assert changed["selection_rule"] == "revealed_rank"
    assert changed["label"] == "正印格"


def test_original_officer_god_survives_revealed_seal_with_legacy_audit_label():
    chart = {
        "year": ("甲", "申"),
        "month": ("壬", "申"),
        "day": ("乙", "巳"),
        "hour": ("戊", "寅"),
    }
    result = determine_monthly_structure(chart, "乙")
    assert result["original_structure"]["ten_god"] == "正官"
    assert result["label"] == "正官格"
    assert result["selection_rule"] == "officer_with_wealth_seal_support"


def test_birth_time_range_detects_hour_boundary_and_preserves_nominal_inputs():
    person = create_person_info(
        2000, 5, 1, 1, birth_minute=0, gender="男", use_true_solar_time=False
    )
    before = person.model_dump()
    result = calculate_dayun_analysis(
        person, analysis_year=2028, birth_time_uncertainty_minutes=5
    )
    sensitive = result["birth_time_sensitivity"]
    assert sensitive["status"] == "sensitive"
    assert sensitive["sample_count"] == 11
    assert {p["pillars"]["hour"][-1] for p in sensitive["pillars_candidates"]} == {
        "子",
        "丑",
    }
    assert "birth_pillars" in sensitive["affected_fields"]
    assert person.model_dump() == before
    assert all(
        p["earliest_start_at"] <= p["latest_start_at"]
        for p in sensitive["dayun_boundary_ranges"]
    )


def test_small_range_crosses_decade_selection_without_changing_natal_pillars():
    person = create_person_info(
        1990,
        5,
        15,
        10,
        birth_minute=30,
        gender="男",
        use_true_solar_time=False,
        birth_timezone="Asia/Shanghai",
    )
    # The declared rule yields 2027-08-31 19:06 for the central birth minute;
    # a birth-clock minute moves the converted boundary by about two hours.
    result = calculate_dayun_analysis(
        person,
        analysis_year=2027,
        analysis_month=8,
        analysis_day=31,
        analysis_hour=19,
        analysis_minute=6,
        birth_time_uncertainty_minutes=1,
    )
    sensitivity = result["birth_time_sensitivity"]
    assert len(sensitivity["pillars_candidates"]) == 1
    assert {c["pillar"] for c in sensitivity["current_dayun_candidates"]} == {
        "甲申",
        "乙酉",
    }
    assert sensitivity["affected_fields"] == ["current_dayun"]
    snapshot = result["snapshot_text"]
    assert "±1分钟" in snapshot
    assert "当前大运候选：甲申、乙酉" in snapshot
    assert "名义出生输入" in snapshot
    assert "采样数量不是概率" in snapshot


def test_uncertainty_is_not_invented_when_no_range_was_supplied():
    person = create_person_info(2000, 5, 1, 10, gender="男", use_true_solar_time=False)
    assert "birth_time_sensitivity" not in calculate_dayun_analysis(
        person, analysis_age=30
    )
    declared = calculate_dayun_analysis(
        person, analysis_age=30, birth_time_uncertainty_minutes=0
    )
    assert declared["birth_time_sensitivity"]["sample_count"] == 1


@pytest.mark.parametrize("hour,scope", [(1, "sensitive"), (10, "partial")])
def test_unknown_gender_retains_birth_range_and_independent_timing(hour, scope):
    person = create_person_info(
        2000, 5, 1, hour, birth_minute=0, gender=None, use_true_solar_time=False
    )
    result = calculate_comprehensive_timing(
        person, analysis_year=2028, birth_time_uncertainty_minutes=5
    )
    assert "error" not in result
    sensitivity = result["birth_time_sensitivity"]
    assert sensitivity["status"] == scope
    assert sensitivity["status_scope"] == "natal_pillars_only"
    assert sensitivity["dayun_assessment_status"] == "unavailable_missing_gender"
    assert sensitivity["unavailable_fields"] == [
        "dayun_direction",
        "current_dayun",
        "dayun_boundary_ranges",
    ]
    assert sensitivity["current_dayun_candidates"] == []
    assert sensitivity["dayun_boundary_ranges"] == []
    assert result["liunian_analysis"]["pillar"]
    assert "未计算（顺逆所需性别未提供）" in result["snapshot_text"]


def test_utc_sampling_keeps_both_clocks_in_a_dst_fold():
    person = create_person_info(
        2000,
        10,
        29,
        0,
        birth_minute=30,
        gender="男",
        use_true_solar_time=False,
        birth_timezone="America/New_York",
    )
    result = calculate_dayun_analysis(
        person, analysis_year=2028, birth_time_uncertainty_minutes=120
    )
    sensitive = result["birth_time_sensitivity"]
    assert sensitive["sample_count"] == 241
    assert sensitive["birth_at_range"]["start"].endswith("-04:00")
    assert sensitive["birth_at_range"]["end"].endswith("-05:00")


def test_low_level_comprehensive_keeps_independent_layers_without_gender():
    result = TimingEffectsAnalysis.comprehensive_timing_analysis(
        {
            "year": ("庚", "辰"),
            "month": ("庚", "辰"),
            "day": ("己", "未"),
            "hour": ("甲", "子"),
        },
        datetime(2000, 5, 1),
        None,
        analysis_date=datetime(2028, 1, 20, 12),
    )
    assert result["dayun_analysis"]["status"] == "unavailable_missing_gender"
    assert result["liunian_analysis"]["liunian_info"]["pillar"]
    assert not any(
        node["layer"] == "dayun" for node in result["interaction_analysis"]["nodes"]
    )


@pytest.mark.parametrize("month,day,hour", [(4, 2, 2), (10, 29, 1)])
def test_nonexistent_or_ambiguous_birth_clock_is_rejected(month, day, hour):
    person = create_person_info(
        2000,
        month,
        day,
        hour,
        birth_minute=30,
        gender="男",
        use_true_solar_time=False,
        birth_timezone="America/New_York",
    )
    result = calculate_dayun_analysis(person, analysis_year=2028)
    assert "error" in result
    assert "夏令时" in result["error"]
