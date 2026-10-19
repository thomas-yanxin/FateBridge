from datetime import datetime, timedelta

import pytest

import fatebridge.services.bazi as bazi
from fatebridge.core.almanac import (
    DAY_GANZHI_STRATEGY_REFERENCE_OFFSET,
    build_calendar_context,
    get_bazi_month_context,
    get_solar_terms_for_year,
)
from fatebridge.core.calendar import BaZiCalendar
from fatebridge.core.timing import TimingAnalysis
from fatebridge.services.calculation import calculate_destiny_analysis
from fatebridge.services.timing import calculate_comprehensive_timing
from fatebridge.utils.birth_input import create_person_info


def test_lichun_boundary_updates_bazi_year_and_month():
    terms = {
        term.name: term for term in get_solar_terms_for_year(2024, "Asia/Shanghai")
    }
    li_chun = terms["立春"].moment

    before = li_chun - timedelta(minutes=1)
    after = li_chun + timedelta(minutes=1)

    before_pillars = BaZiCalendar.get_four_pillars(
        before, timezone_name="Asia/Shanghai"
    )
    after_pillars = BaZiCalendar.get_four_pillars(after, timezone_name="Asia/Shanghai")

    assert before_pillars["year"] == ("癸", "卯")
    assert before_pillars["month"] == ("乙", "丑")
    assert get_bazi_month_context(before, "Asia/Shanghai")["branch"] == "丑"

    assert after_pillars["year"] == ("甲", "辰")
    assert after_pillars["month"] == ("丙", "寅")
    assert get_bazi_month_context(after, "Asia/Shanghai")["branch"] == "寅"


def test_dayun_start_details_use_jieqi_boundary():
    birth = datetime(2028, 4, 6, 9, 33)

    details = TimingAnalysis.calculate_dayun_start_details(
        birth,
        "男",
        timezone_name="Asia/Shanghai",
    )

    assert details["forward_direction"] is True
    assert details["year_stem"] == "戊"
    assert details["reference_term"]["name"] == "立夏"
    # start_age_precise uses the delta between birth and 立夏; after switching
    # from a linear fixed-qì approximation to swisseph-resolved solar terms
    # (see almanac.get_solar_terms_for_year), the boundary moved slightly and
    # the precise age updated from ~9.76 to ~9.63. Both values are under a
    # day's drift at the term boundary; we allow 0.1 year margin to keep the
    # assertion stable across minor ephemeris updates.
    assert details["start_age_precise"] == pytest.approx(9.63, abs=0.1)
    assert details["start_age_rounded"] == 10


def test_reference_offset_day_pillars_match_reference_snapshot():
    pillars = BaZiCalendar.get_four_pillars(
        datetime(2026, 4, 4, 21, 12, 6),
        timezone_name="Asia/Shanghai",
        day_pillar_strategy=DAY_GANZHI_STRATEGY_REFERENCE_OFFSET,
    )

    assert pillars["year"] == ("丙", "午")
    assert pillars["month"] == ("辛", "卯")
    assert pillars["day"] == ("丁", "酉")
    assert pillars["hour"] == ("辛", "亥")


def test_destiny_analysis_exposes_lunar_and_meihua_context():
    person = create_person_info(
        2028,
        4,
        6,
        9,
        "测试",
        "男",
        birth_minute=33,
        birth_timezone="Asia/Shanghai",
    )

    result = calculate_destiny_analysis(person)
    calendar_context = result["calendar_context"]
    lunar_calendar = calendar_context["lunar_calendar"]
    meihua = lunar_calendar["meihua"]

    assert calendar_context["current_solar_term"]["name"] == "清明"
    assert lunar_calendar["display"] == "三月十二"
    assert meihua["base_hexagram"]["name"] == "地水师"
    assert meihua["changed_hexagram"]["name"] == "山水蒙"


def test_comprehensive_timing_returns_jieqi_grid_and_analysis_calendar():
    person = create_person_info(
        2028,
        4,
        6,
        9,
        "测试",
        "男",
        birth_minute=33,
        birth_timezone="Asia/Shanghai",
    )

    result = calculate_comprehensive_timing(
        person, analysis_year=2028, analysis_month=4
    )

    assert (
        result["calendar_context"]["lunar_calendar"]["meihua"]["base_hexagram"]["name"]
        == "地水师"
    )
    assert (
        result["analysis_calendar"]["analysis_date_context"]["current_solar_term"][
            "name"
        ]
        == "春分"
    )
    assert (
        result["analysis_calendar"]["analysis_date_context"]["next_solar_term"]["name"]
        == "清明"
    )
    assert result["liuyue_analysis"]["pillar"] == "乙卯"
    assert result["liuri_analysis"]["pillar"] == "丙辰"
    assert len(result["analysis_calendar"]["analysis_year_jieqi"]) == 24
    assert result["analysis_calendar"]["analysis_year_jieqi"][0]["name"] == "小寒"
    assert len(result["analysis_calendar"]["liuyue_timeline"]) == 12
    assert (
        result["analysis_calendar"]["liuyue_timeline"][1]["start_term"]["name"]
        == "立春"
    )
    assert (
        result["analysis_calendar"]["liuyue_timeline"][1]["liuyue"]["pillar"] == "甲寅"
    )
    assert len(result["analysis_calendar"]["jieqi_timeline"]) == 24
    qingming_node = next(
        item
        for item in result["analysis_calendar"]["jieqi_timeline"]
        if item["jieqi"]["name"] == "清明"
    )
    assert qingming_node["liuyue"]["pillar"] == "丙辰"
    assert qingming_node["liuri"]["pillar"] == "己未"


def test_build_calendar_context_marks_out_of_range_lunar_support():
    moment = datetime(2100, 2, 9, 12, 0, 0)
    pillars = BaZiCalendar.get_four_pillars(moment, timezone_name="Asia/Shanghai")

    calendar_context = build_calendar_context(
        moment,
        timezone_name="Asia/Shanghai",
        pillars=pillars,
    )

    assert calendar_context["lunar_calendar"] is None
    assert calendar_context["lunar_calendar_support"]["supported"] is False
    assert calendar_context["lunar_calendar_support"]["supported_range"] == {
        "start": "1900-01-31",
        "end": "2100-02-08",
    }


def test_zi_shi_rolls_day_pillar_to_next_civil_day():
    same_day = create_person_info(2024, 2, 4, 22, "t", "男", "北京")
    zi_shi = create_person_info(2024, 2, 4, 23, "t", "男", "北京", birth_minute=30)
    next_day = create_person_info(2024, 2, 5, 1, "t", "男", "北京")

    d_same = bazi.calculate_bazi_birth(same_day)["bazi_birth"]["four_pillars"]["day"]
    d_zi = bazi.calculate_bazi_birth(zi_shi)["bazi_birth"]["four_pillars"]["day"]
    d_next = bazi.calculate_bazi_birth(next_day)["bazi_birth"]["four_pillars"]["day"]

    assert d_zi == d_next  # 23:30 belongs to the next day's pillar
    assert d_zi != d_same  # and differs from the same civil day's earlier pillar
