from datetime import datetime, timedelta

import pytest

from fatebridge.core.timing import TimingAnalysis
from fatebridge.services.calculation import calculate_destiny_analysis
from fatebridge.services.timing import (
    calculate_comprehensive_timing,
    calculate_dayun_analysis,
    calculate_jieqi_timeline_analysis,
    calculate_liunian_analysis,
    calculate_liuri_analysis,
    calculate_liushi_analysis,
    calculate_liuyue_analysis,
)
from fatebridge.utils.birth_input import create_person_info
from fatebridge.utils.places import resolve_birth_place_context
from fatebridge.utils.solar_time import normalize_birth_time
from fatebridge.utils.timezones import parse_timezone_name
from tests.fixtures.solar_reference import expected_solar_clock
from tests.fixtures.transports import mcp_parameters


def test_normalize_birth_time_preserves_legacy_hour_only_behavior():
    person = create_person_info(
        birth_year=1990,
        birth_month=5,
        birth_day=15,
        birth_hour=10,
        name="张三",
    )

    normalized = normalize_birth_time(person)

    assert normalized.input_datetime == datetime(1990, 5, 15, 10, 0)
    assert normalized.corrected_datetime == datetime(1990, 5, 15, 10, 0)
    assert normalized.total_correction_minutes == pytest.approx(0.0)
    assert normalized.applied is False


def test_normalize_birth_time_uses_birth_place_for_true_solar_time():
    person = create_person_info(
        birth_year=1990,
        birth_month=5,
        birth_day=15,
        birth_hour=10,
        birth_minute=30,
        birth_place="北京",
        use_true_solar_time=True,
    )

    normalized = normalize_birth_time(person)

    assert normalized.timezone == "Asia/Shanghai"
    assert normalized.longitude == pytest.approx(116.4074, abs=0.01)
    assert normalized.longitude_source == "birth_place"
    # 1990-05-15 于中国夏令时期 (CDT, UTC+9)，钟表 10:30 实际对应 CST 09:30。
    # 真太阳时修正应先脱 DST 再做 longitude + EoT 校正：
    #   09:30 + (-14.37) + 3.75 ≈ 09:19
    assert normalized.corrected_datetime.hour == 9
    assert normalized.corrected_datetime.minute == 19
    assert normalized.daylight_saving_minutes == pytest.approx(60.0, abs=0.1)
    assert normalized.total_correction_minutes == pytest.approx(-70.62, abs=0.1)
    assert normalized.applied is True


def test_normalize_birth_time_resolves_full_form_chinese_city_address():
    person = create_person_info(
        birth_year=1990,
        birth_month=5,
        birth_day=15,
        birth_hour=10,
        birth_minute=30,
        birth_place="浙江省宁波市海曙区灵桥路190号",
        use_true_solar_time=True,
    )

    normalized = normalize_birth_time(person)

    assert normalized.timezone == "Asia/Shanghai"
    assert normalized.longitude == pytest.approx(121.5503, abs=0.01)
    assert normalized.longitude_source == "birth_place"
    assert normalized.resolved_place == "海曙区"
    assert normalized.resolution_level == "county"
    assert normalized.applied is True


def test_normalize_birth_time_supports_english_city_address():
    person = create_person_info(
        birth_year=1990,
        birth_month=5,
        birth_day=15,
        birth_hour=10,
        birth_minute=30,
        birth_place="Haishu District, Ningbo, Zhejiang, China",
        use_true_solar_time=True,
    )

    normalized = normalize_birth_time(person)

    assert normalized.longitude == pytest.approx(121.5503, abs=0.01)
    assert normalized.longitude_source == "birth_place"
    assert normalized.resolved_place == "海曙区"
    assert normalized.resolution_level == "county"


def test_normalize_birth_time_supports_pinyin_city_address():
    person = create_person_info(
        birth_year=1990,
        birth_month=5,
        birth_day=15,
        birth_hour=10,
        birth_minute=30,
        birth_place="zhejiang sheng hangzhou shi xihu qu wensan lu 138 hao",
        use_true_solar_time=True,
    )

    normalized = normalize_birth_time(person)

    assert normalized.longitude == pytest.approx(120.126, abs=0.01)
    assert normalized.longitude_source == "birth_place"
    assert normalized.resolved_place == "西湖区"
    assert normalized.resolution_level == "county"


def test_normalize_birth_time_prefers_more_specific_city_match_over_province():
    person = create_person_info(
        birth_year=1990,
        birth_month=5,
        birth_day=15,
        birth_hour=10,
        birth_minute=30,
        birth_place="浙江省杭州市西湖区文三路138号",
        use_true_solar_time=True,
    )

    normalized = normalize_birth_time(person)

    assert normalized.longitude == pytest.approx(120.126, abs=0.01)
    assert normalized.longitude_source == "birth_place"
    assert normalized.resolved_place == "西湖区"
    assert normalized.resolution_level == "county"


def test_normalize_birth_time_falls_back_to_province_when_city_is_unknown():
    person = create_person_info(
        birth_year=1990,
        birth_month=5,
        birth_day=15,
        birth_hour=10,
        birth_minute=30,
        # A synthetic unknown place keeps the province fallback observable.
        birth_place="河北省未收录地点",
        use_true_solar_time=True,
    )

    normalized = normalize_birth_time(person)

    assert normalized.longitude == pytest.approx(114.5149, abs=0.01)
    assert normalized.longitude_source == "birth_place"
    assert normalized.resolved_place == "河北"
    assert normalized.resolution_level == "province"


def test_normalize_birth_time_supports_english_district_address():
    person = create_person_info(
        birth_year=1990,
        birth_month=5,
        birth_day=15,
        birth_hour=10,
        birth_minute=30,
        birth_place="Lianchi District, Baoding, Hebei, China",
        use_true_solar_time=True,
    )

    normalized = normalize_birth_time(person)

    assert normalized.longitude == pytest.approx(115.491, abs=0.01)
    assert normalized.longitude_source == "birth_place"
    assert normalized.resolved_place == "莲池区"
    assert normalized.resolution_level == "county"


def test_calculate_destiny_analysis_uses_corrected_solar_time_for_hour_pillar():
    person = create_person_info(
        birth_year=2020,
        birth_month=1,
        birth_day=1,
        birth_hour=0,
        birth_minute=30,
        birth_place="乌鲁木齐",
        use_true_solar_time=True,
        name="测试",
    )

    result = calculate_destiny_analysis(person)

    assert result["person_info"]["birth_datetime"] == "2020年01月01日 00时30分"
    assert result["person_info"]["normalized_birth_datetime"] == expected_solar_clock(
        datetime(2020, 1, 1, 0, 30), "Asia/Shanghai", 87.6168
    ).strftime("%Y年%m月%d日 %H时%M分")
    assert result["person_info"]["time_adjustment"]["applied"] is True
    assert result["person_info"]["time_adjustment"]["timezone"] == "Asia/Shanghai"
    assert result["person_info"]["time_adjustment"]["longitude_source"] == "birth_place"
    assert result["person_info"]["time_adjustment"]["resolved_place"] == "乌鲁木齐"
    assert result["person_info"]["time_adjustment"]["resolution_level"] == "city"
    assert result["four_pillars"]["hour"]["branch"] == "亥"


def test_calculate_comprehensive_timing_uses_corrected_birth_time():
    person = create_person_info(
        birth_year=2020,
        birth_month=1,
        birth_day=1,
        birth_hour=0,
        birth_minute=30,
        birth_place="乌鲁木齐",
        use_true_solar_time=True,
        name="测试",
        gender="男",
    )

    result = calculate_comprehensive_timing(
        person, analysis_year=2020, analysis_month=1
    )

    assert result["personal_info"]["birth_datetime"] == "2020-01-01 00:30"
    assert result["personal_info"]["normalized_birth_datetime"] == expected_solar_clock(
        datetime(2020, 1, 1, 0, 30), "Asia/Shanghai", 87.6168
    ).strftime("%Y-%m-%d %H:%M")
    assert result["personal_info"]["time_adjustment"]["applied"] is True
    assert result["personal_info"]["time_adjustment"]["resolved_place"] == "乌鲁木齐"
    assert result["personal_info"]["time_adjustment"]["resolution_level"] == "city"
    assert result["birth_pillars"]["hour"]["branch"] == "亥"


def test_calculate_comprehensive_timing_supports_snapshot_export_and_age_override():
    person = create_person_info(
        birth_year=1990,
        birth_month=5,
        birth_day=15,
        birth_hour=10,
        birth_minute=30,
        birth_timezone="Asia/Shanghai",
        name="测试",
        gender="男",
    )

    result = calculate_comprehensive_timing(
        person,
        analysis_year=2028,
        analysis_month=4,
        analysis_day=6,
        analysis_hour=21,
        analysis_minute=55,
        analysis_age=42,
        selected_sections=["查询信息", "综合影响"],
    )
    dayun_result = calculate_dayun_analysis(person, 42)

    assert result["personal_info"]["current_age"] == 42
    assert result["personal_info"]["analysis_date"] == "2028-04-06"
    assert result["personal_info"]["analysis_datetime"] == "2028-04-06 21:55"
    assert (
        result["dayun_analysis"]["current_dayun"]
        == dayun_result["dayun_info"]["current_dayun"]
    )
    assert "[查询信息]" in result["snapshot_text"]
    assert "[大运摘要]" in result["snapshot_text"]
    assert "[流年流月流日]" in result["snapshot_text"]
    assert "[综合影响]" in result["snapshot_text"]
    assert "[来源]" in result["snapshot_text"]
    assert result["snapshot_export"]["selected_sections"] == ["查询信息", "综合影响"]
    assert "[查询信息]" in result["snapshot_export"]["export_text"]
    assert "[综合影响]" in result["snapshot_export"]["export_text"]
    assert "[大运摘要]" not in result["snapshot_export"]["export_text"]
    assert "[来源]" not in result["snapshot_export"]["export_text"]


def test_calculate_comprehensive_timing_supports_analysis_day_boundaries():
    person = create_person_info(
        birth_year=2028,
        birth_month=4,
        birth_day=6,
        birth_hour=9,
        birth_minute=33,
        birth_timezone="Asia/Shanghai",
        name="测试",
        gender="男",
    )

    timing_result = calculate_comprehensive_timing(
        person,
        analysis_year=2028,
        analysis_month=4,
        analysis_day=6,
    )
    liuyue_result = calculate_liuyue_analysis(
        person,
        analysis_year=2028,
        analysis_month=4,
        analysis_day=6,
    )
    liuri_result = calculate_liuri_analysis(
        person,
        analysis_year=2028,
        analysis_month=4,
        analysis_day=6,
    )

    assert timing_result["personal_info"]["analysis_date"] == "2028-04-06"
    assert (
        timing_result["analysis_calendar"]["analysis_date_context"][
            "current_solar_term"
        ]["name"]
        == "清明"
    )
    assert (
        timing_result["analysis_calendar"]["analysis_date_context"]["next_solar_term"][
            "name"
        ]
        == "谷雨"
    )
    assert timing_result["liuyue_analysis"]["pillar"] == "丙辰"
    assert timing_result["liuri_analysis"]["pillar"] == "辛酉"
    assert (
        timing_result["liuyue_analysis"]["pillar"]
        == liuyue_result["liuyue_info"]["pillar"]
    )
    assert (
        timing_result["liuri_analysis"]["pillar"]
        == liuri_result["liuri_info"]["pillar"]
    )


def test_time_precision_changes_liuyue_across_qingming_boundary():
    person = create_person_info(
        birth_year=2028,
        birth_month=4,
        birth_day=6,
        birth_hour=9,
        birth_minute=33,
        birth_timezone="Asia/Shanghai",
        name="测试",
        gender="男",
    )
    qingming_node = next(
        item
        for item in TimingAnalysis.calculate_jieqi_transition_timeline(
            2028, timezone_name="Asia/Shanghai"
        )
        if item["jieqi"]["name"] == "清明"
    )

    before_result = calculate_liuyue_analysis(
        person,
        analysis_year=2028,
        analysis_month=4,
        analysis_day=4,
    )
    boundary_result = calculate_liuyue_analysis(
        person,
        analysis_year=2028,
        analysis_month=4,
        analysis_day=4,
        analysis_hour=21,
        analysis_minute=55,
    )

    assert before_result["liuyue_info"]["pillar"] == "乙卯"
    assert (
        before_result["analysis_calendar"]["analysis_date_context"][
            "current_solar_term"
        ]["name"]
        == "春分"
    )
    assert boundary_result["liuyue_info"]["pillar"] == qingming_node["liuyue"]["pillar"]
    assert (
        boundary_result["analysis_calendar"]["analysis_date_context"][
            "current_solar_term"
        ]["name"]
        == "清明"
    )
    assert (
        boundary_result["analysis_calendar"]["analysis_date_context"][
            "next_solar_term"
        ]["name"]
        == "谷雨"
    )


def test_time_precision_aligns_liuri_and_timing_with_jieqi_anchor():
    person = create_person_info(
        birth_year=2028,
        birth_month=4,
        birth_day=6,
        birth_hour=9,
        birth_minute=33,
        birth_timezone="Asia/Shanghai",
        name="测试",
        gender="男",
    )
    qingming_node = next(
        item
        for item in TimingAnalysis.calculate_jieqi_transition_timeline(
            2028, timezone_name="Asia/Shanghai"
        )
        if item["jieqi"]["name"] == "清明"
    )

    liuri_result = calculate_liuri_analysis(
        person,
        analysis_year=2028,
        analysis_month=4,
        analysis_day=4,
        analysis_hour=21,
        analysis_minute=55,
    )
    timing_result = calculate_comprehensive_timing(
        person,
        analysis_year=2028,
        analysis_month=4,
        analysis_day=4,
        analysis_hour=21,
        analysis_minute=55,
    )

    assert liuri_result["liuri_info"]["pillar"] == qingming_node["liuri"]["pillar"]
    assert (
        liuri_result["analysis_calendar"]["analysis_date_context"][
            "current_solar_term"
        ]["name"]
        == "清明"
    )
    assert timing_result["personal_info"]["analysis_datetime"] == "2028-04-04 21:55"
    assert (
        timing_result["liuyue_analysis"]["pillar"] == qingming_node["liuyue"]["pillar"]
    )
    assert timing_result["liuri_analysis"]["pillar"] == qingming_node["liuri"]["pillar"]
    assert (
        timing_result["analysis_calendar"]["analysis_date_context"][
            "current_solar_term"
        ]["name"]
        == "清明"
    )


def test_calculate_dayun_analysis_supports_snapshot_export():
    person = create_person_info(
        birth_year=1990,
        birth_month=5,
        birth_day=15,
        birth_hour=10,
        birth_minute=30,
        birth_timezone="Asia/Shanghai",
        name="测试",
        gender="男",
    )

    result = calculate_dayun_analysis(person, 38)

    assert "current_dayun" in result["dayun_info"]
    assert "[查询信息]" in result["snapshot_text"]
    assert "[大运信息]" in result["snapshot_text"]
    assert "[影响摘要]" in result["snapshot_text"]
    assert "[来源]" in result["snapshot_text"]
    assert result["snapshot_export"]["export_text"] == result["snapshot_text"]


def test_calculate_dayun_analysis_supports_selected_export_sections():
    person = create_person_info(
        birth_year=1990,
        birth_month=5,
        birth_day=15,
        birth_hour=10,
        birth_minute=30,
        birth_timezone="Asia/Shanghai",
        name="测试",
        gender="男",
    )

    result = calculate_dayun_analysis(
        person,
        38,
        selected_sections=["查询信息", "大运信息"],
    )

    assert result["snapshot_export"]["selected_sections"] == ["查询信息", "大运信息"]
    assert "[查询信息]" in result["snapshot_export"]["export_text"]
    assert "[大运信息]" in result["snapshot_export"]["export_text"]
    assert "[影响摘要]" not in result["snapshot_export"]["export_text"]
    assert "[来源]" not in result["snapshot_export"]["export_text"]


def test_calculate_liuri_analysis_returns_expected_pillar():
    person = create_person_info(
        birth_year=2028,
        birth_month=4,
        birth_day=6,
        birth_hour=9,
        birth_minute=33,
        birth_timezone="Asia/Shanghai",
        name="测试",
        gender="男",
    )

    result = calculate_liuri_analysis(
        person, analysis_year=2028, analysis_month=4, analysis_day=1
    )

    assert result["liuri_info"]["pillar"] == "丙辰"
    assert (
        result["analysis_calendar"]["analysis_date_context"]["current_solar_term"][
            "name"
        ]
        == "春分"
    )
    assert "[查询信息]" in result["snapshot_text"]
    assert "[流日信息]" in result["snapshot_text"]
    assert "[影响摘要]" in result["snapshot_text"]
    assert "[来源]" in result["snapshot_text"]
    assert result["snapshot_export"]["export_text"] == result["snapshot_text"]


def test_calculate_liuri_analysis_supports_selected_export_sections():
    person = create_person_info(
        birth_year=2028,
        birth_month=4,
        birth_day=6,
        birth_hour=9,
        birth_minute=33,
        birth_timezone="Asia/Shanghai",
        name="测试",
        gender="男",
    )

    result = calculate_liuri_analysis(
        person,
        analysis_year=2028,
        analysis_month=4,
        analysis_day=1,
        selected_sections=["查询信息", "流日信息"],
    )

    assert result["snapshot_export"]["selected_sections"] == ["查询信息", "流日信息"]
    assert "[查询信息]" in result["snapshot_export"]["export_text"]
    assert "[流日信息]" in result["snapshot_export"]["export_text"]
    assert "[影响摘要]" not in result["snapshot_export"]["export_text"]
    assert "[来源]" not in result["snapshot_export"]["export_text"]


def test_calculate_liushi_analysis_returns_expected_pillar():
    person = create_person_info(
        birth_year=2028,
        birth_month=4,
        birth_day=6,
        birth_hour=9,
        birth_minute=33,
        birth_timezone="Asia/Shanghai",
        name="测试",
        gender="男",
    )
    analysis_dt = datetime(2028, 4, 1, 21, 55)

    result = calculate_liushi_analysis(
        person,
        analysis_year=analysis_dt.year,
        analysis_month=analysis_dt.month,
        analysis_day=analysis_dt.day,
        analysis_hour=analysis_dt.hour,
        analysis_minute=analysis_dt.minute,
    )
    expected_liushi = TimingAnalysis.calculate_liushi(
        analysis_dt,
        timezone_name="Asia/Shanghai",
    )

    assert result["liushi_info"]["pillar"] == expected_liushi["pillar"]
    assert result["liushi_info"]["hour"] == 21
    assert (
        result["analysis_calendar"]["analysis_date_context"]["current_solar_term"][
            "name"
        ]
        == "春分"
    )
    assert "[查询信息]" in result["snapshot_text"]
    assert "[流时信息]" in result["snapshot_text"]
    assert "[影响摘要]" in result["snapshot_text"]
    assert "[来源]" in result["snapshot_text"]
    assert result["snapshot_export"]["export_text"] == result["snapshot_text"]


def test_calculate_liushi_analysis_supports_selected_export_sections():
    person = create_person_info(
        birth_year=2028,
        birth_month=4,
        birth_day=6,
        birth_hour=9,
        birth_minute=33,
        birth_timezone="Asia/Shanghai",
        name="测试",
        gender="男",
    )

    result = calculate_liushi_analysis(
        person,
        analysis_year=2028,
        analysis_month=4,
        analysis_day=1,
        analysis_hour=21,
        analysis_minute=55,
        selected_sections=["查询信息", "流时信息"],
    )

    assert result["snapshot_export"]["selected_sections"] == ["查询信息", "流时信息"]
    assert "[查询信息]" in result["snapshot_export"]["export_text"]
    assert "[流时信息]" in result["snapshot_export"]["export_text"]
    assert "[影响摘要]" not in result["snapshot_export"]["export_text"]
    assert "[来源]" not in result["snapshot_export"]["export_text"]


def test_calculate_liunian_analysis_supports_snapshot_export():
    person = create_person_info(
        birth_year=2028,
        birth_month=4,
        birth_day=6,
        birth_hour=9,
        birth_minute=33,
        birth_timezone="Asia/Shanghai",
        name="测试",
        gender="男",
    )

    result = calculate_liunian_analysis(
        person,
        2028,
    )

    assert result["liunian_info"]["pillar"] == "戊申"
    assert "[查询信息]" in result["snapshot_text"]
    assert "[流年信息]" in result["snapshot_text"]
    assert "[影响摘要]" in result["snapshot_text"]
    assert "[来源]" in result["snapshot_text"]
    assert result["snapshot_export"]["export_text"] == result["snapshot_text"]


def test_calculate_liunian_analysis_supports_selected_export_sections():
    person = create_person_info(
        birth_year=2028,
        birth_month=4,
        birth_day=6,
        birth_hour=9,
        birth_minute=33,
        birth_timezone="Asia/Shanghai",
        name="测试",
        gender="男",
    )

    result = calculate_liunian_analysis(
        person,
        2028,
        selected_sections=["查询信息", "流年信息"],
    )

    assert result["snapshot_export"]["selected_sections"] == ["查询信息", "流年信息"]
    assert "[查询信息]" in result["snapshot_export"]["export_text"]
    assert "[流年信息]" in result["snapshot_export"]["export_text"]
    assert "[影响摘要]" not in result["snapshot_export"]["export_text"]
    assert "[来源]" not in result["snapshot_export"]["export_text"]


def test_calculate_liuyue_analysis_returns_expected_pillar():
    person = create_person_info(
        birth_year=2028,
        birth_month=4,
        birth_day=6,
        birth_hour=9,
        birth_minute=33,
        birth_timezone="Asia/Shanghai",
        name="测试",
        gender="男",
    )

    result = calculate_liuyue_analysis(
        person, analysis_year=2028, analysis_month=4, analysis_day=1
    )

    assert result["liuyue_info"]["pillar"] == "乙卯"
    assert result["liuyue_info"]["solar_term_window"]["start_term"]["name"] == "惊蛰"
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
    assert result["liunian_info"]["pillar"] == "戊申"
    assert "[查询信息]" in result["snapshot_text"]
    assert "[流月信息]" in result["snapshot_text"]
    assert "[流年联动]" in result["snapshot_text"]
    assert "[影响摘要]" in result["snapshot_text"]
    assert "[来源]" in result["snapshot_text"]
    assert result["snapshot_export"]["export_text"] == result["snapshot_text"]


def test_calculate_liuyue_analysis_supports_selected_export_sections():
    person = create_person_info(
        birth_year=2028,
        birth_month=4,
        birth_day=6,
        birth_hour=9,
        birth_minute=33,
        birth_timezone="Asia/Shanghai",
        name="测试",
        gender="男",
    )

    result = calculate_liuyue_analysis(
        person,
        analysis_year=2028,
        analysis_month=4,
        analysis_day=1,
        selected_sections=["查询信息", "流月信息"],
    )

    assert result["snapshot_export"]["selected_sections"] == ["查询信息", "流月信息"]
    assert "[查询信息]" in result["snapshot_export"]["export_text"]
    assert "[流月信息]" in result["snapshot_export"]["export_text"]
    assert "[流年联动]" not in result["snapshot_export"]["export_text"]
    assert "[影响摘要]" not in result["snapshot_export"]["export_text"]


def test_calculate_jieqi_timeline_analysis_returns_qingming_node():
    person = create_person_info(
        birth_year=2028,
        birth_month=4,
        birth_day=6,
        birth_hour=9,
        birth_minute=33,
        birth_timezone="Asia/Shanghai",
        name="测试",
        gender="男",
    )

    result = calculate_jieqi_timeline_analysis(person, target_year=2028)

    assert len(result["jieqi_timeline"]) == 24
    qingming_node = next(
        item for item in result["jieqi_timeline"] if item["jieqi"]["name"] == "清明"
    )
    assert qingming_node["analysis_anchor"] == "2028-04-04 14:04:00"
    assert qingming_node["liuyue"]["pillar"] == "丙辰"
    assert qingming_node["liuri"]["pillar"] == "己未"
    assert "[查询信息]" in result["snapshot_text"]
    assert "[年度节气]" in result["snapshot_text"]
    assert "[节点时间轴]" in result["snapshot_text"]
    assert "[来源]" in result["snapshot_text"]
    assert result["snapshot_export"]["export_text"] == result["snapshot_text"]


def test_calculate_jieqi_timeline_analysis_supports_selected_export_sections():
    person = create_person_info(
        birth_year=2028,
        birth_month=4,
        birth_day=6,
        birth_hour=9,
        birth_minute=33,
        birth_timezone="Asia/Shanghai",
        name="测试",
        gender="男",
    )

    result = calculate_jieqi_timeline_analysis(
        person,
        target_year=2028,
        selected_sections=["查询信息", "节点时间轴"],
    )

    assert result["snapshot_export"]["selected_sections"] == ["查询信息", "节点时间轴"]
    assert "[查询信息]" in result["snapshot_export"]["export_text"]
    assert "[节点时间轴]" in result["snapshot_export"]["export_text"]
    assert "[年度节气]" not in result["snapshot_export"]["export_text"]
    assert "[来源]" not in result["snapshot_export"]["export_text"]


def test_liuyue_timeline_anchor_is_minute_safe_and_replayable():
    person = create_person_info(
        birth_year=2028,
        birth_month=4,
        birth_day=6,
        birth_hour=9,
        birth_minute=33,
        birth_timezone="Asia/Shanghai",
        name="测试",
        gender="男",
    )

    timeline = TimingAnalysis.calculate_liuyue_timeline(
        2028, timezone_name="Asia/Shanghai"
    )

    for item in timeline:
        anchor = datetime.strptime(item["analysis_anchor"], "%Y-%m-%d %H:%M:%S")
        start_term = datetime.fromisoformat(item["start_term"]["datetime"])
        assert anchor.second == 0
        assert timedelta(0) < anchor - start_term <= timedelta(minutes=1)

    qingming_month = next(
        item for item in timeline if item["start_term"]["name"] == "清明"
    )
    anchor = datetime.strptime(qingming_month["analysis_anchor"], "%Y-%m-%d %H:%M:%S")
    liuyue_result = calculate_liuyue_analysis(
        person,
        analysis_year=anchor.year,
        analysis_month=anchor.month,
        analysis_day=anchor.day,
        analysis_hour=anchor.hour,
        analysis_minute=anchor.minute,
    )

    assert qingming_month["analysis_anchor"] == "2028-04-04 14:04:00"
    assert liuyue_result["liuyue_info"]["pillar"] == qingming_month["liuyue"]["pillar"]
    assert (
        liuyue_result["liuyue_info"]["solar_term_window"]["start_term"]["name"]
        == "清明"
    )


def test_jieqi_timeline_anchor_is_minute_safe_and_replayable():
    person = create_person_info(
        birth_year=2028,
        birth_month=4,
        birth_day=6,
        birth_hour=9,
        birth_minute=33,
        birth_timezone="Asia/Shanghai",
        name="测试",
        gender="男",
    )

    timeline = TimingAnalysis.calculate_jieqi_transition_timeline(
        2028, timezone_name="Asia/Shanghai"
    )
    sample_names = {"清明", "立秋", "冬至"}

    for item in timeline:
        anchor = datetime.strptime(item["analysis_anchor"], "%Y-%m-%d %H:%M:%S")
        term = datetime.fromisoformat(item["jieqi"]["datetime"])
        assert anchor.second == 0
        assert timedelta(0) < anchor - term <= timedelta(minutes=1)

        if item["jieqi"]["name"] not in sample_names:
            continue

        liuyue_result = calculate_liuyue_analysis(
            person,
            analysis_year=anchor.year,
            analysis_month=anchor.month,
            analysis_day=anchor.day,
            analysis_hour=anchor.hour,
            analysis_minute=anchor.minute,
        )
        liuri_result = calculate_liuri_analysis(
            person,
            analysis_year=anchor.year,
            analysis_month=anchor.month,
            analysis_day=anchor.day,
            analysis_hour=anchor.hour,
            analysis_minute=anchor.minute,
        )
        timing_result = calculate_comprehensive_timing(
            person,
            analysis_year=anchor.year,
            analysis_month=anchor.month,
            analysis_day=anchor.day,
            analysis_hour=anchor.hour,
            analysis_minute=anchor.minute,
        )

        assert liuyue_result["liuyue_info"]["pillar"] == item["liuyue"]["pillar"]
        assert liuri_result["liuri_info"]["pillar"] == item["liuri"]["pillar"]
        assert timing_result["liuyue_analysis"]["pillar"] == item["liuyue"]["pillar"]
        assert timing_result["liuri_analysis"]["pillar"] == item["liuri"]["pillar"]


def test_comprehensive_timing_matches_specialized_timing_tools():
    person = create_person_info(
        birth_year=1990,
        birth_month=5,
        birth_day=15,
        birth_hour=10,
        birth_minute=30,
        birth_timezone="Asia/Shanghai",
        name="测试",
        gender="男",
    )

    timing_result = calculate_comprehensive_timing(
        person,
        analysis_year=2028,
        analysis_month=4,
        analysis_day=6,
        analysis_age=42,
    )
    dayun_result = calculate_dayun_analysis(person, 42)
    liunian_result = calculate_liunian_analysis(person, 2028)
    liuyue_result = calculate_liuyue_analysis(
        person,
        analysis_year=2028,
        analysis_month=4,
        analysis_day=6,
    )
    liuri_result = calculate_liuri_analysis(
        person,
        analysis_year=2028,
        analysis_month=4,
        analysis_day=6,
    )
    liushi_result = calculate_liushi_analysis(
        person,
        analysis_year=2028,
        analysis_month=4,
        analysis_day=6,
        analysis_hour=0,
        analysis_minute=0,
    )

    assert (
        timing_result["dayun_analysis"]["current_dayun"]
        == dayun_result["dayun_info"]["current_dayun"]
    )
    assert (
        timing_result["dayun_analysis"]["start_age"]
        == dayun_result["dayun_info"]["start_age"]
    )
    assert (
        timing_result["dayun_analysis"]["dayun_age"]
        == dayun_result["dayun_info"]["dayun_age"]
    )
    assert (
        timing_result["liunian_analysis"]["pillar"]
        == liunian_result["liunian_info"]["pillar"]
    )
    assert (
        timing_result["liuyue_analysis"]["pillar"]
        == liuyue_result["liuyue_info"]["pillar"]
    )
    assert (
        timing_result["liuri_analysis"]["pillar"]
        == liuri_result["liuri_info"]["pillar"]
    )
    assert (
        timing_result["liushi_analysis"]["pillar"]
        == liushi_result["liushi_info"]["pillar"]
    )


def test_fastmcp_tools_expose_birth_time_precision_arguments():
    analyze_properties = mcp_parameters("analyze_destiny")["properties"]
    compatibility_properties = mcp_parameters("two_person_compatibility")["properties"]
    timing_properties = mcp_parameters("timing_analysis")["properties"]
    dayun_properties = mcp_parameters("dayun_analysis")["properties"]
    liunian_properties = mcp_parameters("liunian_analysis")["properties"]
    liuyue_properties = mcp_parameters("liuyue_analysis")["properties"]
    liuri_properties = mcp_parameters("liuri_analysis")["properties"]
    liushi_properties = mcp_parameters("liushi_analysis")["properties"]
    jieqi_properties = mcp_parameters("jieqi_timeline_analysis")["properties"]

    assert "birth_minute" in analyze_properties
    assert "birth_timezone" in analyze_properties
    assert "birth_longitude" in analyze_properties
    assert "use_true_solar_time" in analyze_properties

    assert "person1_birth_minute" in compatibility_properties
    assert "person2_birth_minute" in compatibility_properties
    assert "person1_birth_timezone" in compatibility_properties
    assert "person2_birth_timezone" in compatibility_properties
    assert "person1_birth_longitude" in compatibility_properties
    assert "person2_birth_longitude" in compatibility_properties
    assert "use_true_solar_time" in timing_properties
    assert "analysis_day" in timing_properties
    assert "analysis_hour" in timing_properties
    assert "analysis_minute" in timing_properties
    assert "selected_sections" in timing_properties
    assert "selected_sections" in dayun_properties
    assert "selected_sections" in liunian_properties
    assert "analysis_year" in liuyue_properties
    assert "analysis_month" in liuyue_properties
    assert "analysis_day" in liuyue_properties
    assert "analysis_hour" in liuyue_properties
    assert "analysis_minute" in liuyue_properties
    assert "selected_sections" in liuyue_properties
    assert "analysis_year" in liuri_properties
    assert "analysis_month" in liuri_properties
    assert "analysis_day" in liuri_properties
    assert "analysis_hour" in liuri_properties
    assert "analysis_minute" in liuri_properties
    assert "selected_sections" in liuri_properties
    assert "analysis_year" in liushi_properties
    assert "analysis_month" in liushi_properties
    assert "analysis_day" in liushi_properties
    assert "analysis_hour" in liushi_properties
    assert "analysis_minute" in liushi_properties
    assert "selected_sections" in liushi_properties
    assert "target_year" in jieqi_properties
    assert "selected_sections" in jieqi_properties


def _offset_hours(tzinfo) -> float:
    delta = tzinfo.utcoffset(datetime(2001, 1, 1, 12))
    assert delta is not None
    return delta.total_seconds() / 3600.0


@pytest.mark.parametrize(
    "value, expected_hours",
    [
        ("8", 8.0),  # bare unsigned hour offset — the natural input that used to fail
        ("+8", 8.0),
        ("-5", -5.0),
        ("5.5", 5.5),  # India-style half-hour offset
        ("+08:00", 8.0),
        ("UTC+8", 8.0),
        ("GMT+8", 8.0),
    ],
)
def test_parse_timezone_name_accepts_offset_forms(value, expected_hours):
    assert _offset_hours(parse_timezone_name(value)) == pytest.approx(expected_hours)


def test_parse_timezone_name_accepts_iana_name():
    # IANA names still win over the numeric-offset shortcut.
    assert parse_timezone_name("Asia/Shanghai").utcoffset(
        datetime(2001, 1, 1, 12)
    ) == timedelta(hours=8)


@pytest.mark.parametrize("value", ["garbage", "1e3", "inf", "nan", "Asia/Nowhere"])
def test_parse_timezone_name_rejects_invalid_with_actionable_message(value):
    with pytest.raises(ValueError) as excinfo:
        parse_timezone_name(value)
    message = str(excinfo.value)
    # The error must name the accepted formats so callers can self-correct.
    assert "Asia/Shanghai" in message
    assert "+08:00" in message or "UTC+8" in message
    assert "bare offset" in message


def test_normalize_birth_time_accepts_bare_integer_timezone():
    # End-to-end: the bare "8" that previously raised now drives correction.
    person = create_person_info(
        birth_year=1988,
        birth_month=8,
        birth_day=8,
        birth_hour=8,
        birth_minute=8,
        birth_longitude=120.0,
        birth_timezone="8",
        use_true_solar_time=True,
    )
    normalized = normalize_birth_time(person)
    assert normalized.applied is True


def test_resolve_birth_place_resolves_prefecture_city_district_form():
    # A catalogued district now resolves beyond its parent city.
    resolution = resolve_birth_place_context("咸阳市秦都区")
    assert resolution.canonical_name == "秦都区"
    assert resolution.longitude == pytest.approx(108.705, abs=0.01)
    assert resolution.level == "county"


def test_normalize_birth_time_resolves_newly_catalogued_prefecture_city():
    person = create_person_info(
        birth_year=1988,
        birth_month=8,
        birth_day=8,
        birth_hour=8,
        birth_minute=8,
        birth_place="咸阳市秦都区",
        use_true_solar_time=True,
    )
    normalized = normalize_birth_time(person)
    assert normalized.applied is True
    assert normalized.longitude_source == "birth_place"
    assert normalized.resolved_place == "秦都区"
    assert normalized.longitude == pytest.approx(108.705, abs=0.01)


def test_resolve_birth_place_context_returns_latitude():
    # Latitude must travel with longitude so the astrology engine can build a
    # chart from a place name alone (same coverage as the BaZi true-solar path).
    shanghai = resolve_birth_place_context("上海")
    assert shanghai.longitude == pytest.approx(121.4737, abs=0.01)
    assert shanghai.latitude == pytest.approx(31.2304, abs=0.01)

    # A prefecture-level city that previously had longitude but no latitude.
    nantong = resolve_birth_place_context("南通")
    assert nantong.longitude == pytest.approx(120.8943, abs=0.01)
    assert nantong.latitude is not None


def test_every_catalogued_place_has_latitude():
    # Drift guard: a place may not be half-resolved (longitude without latitude).
    # If this fails, a new make_birth_place_entry is missing its latitude.
    from fatebridge.utils.places import KNOWN_BIRTH_PLACE_ENTRIES

    missing = [
        entry["canonical_name"]
        for entry in KNOWN_BIRTH_PLACE_ENTRIES
        if entry.get("latitude") is None
    ]
    assert missing == [], f"places missing latitude: {missing}"


def test_normalize_birth_time_unknown_place_errors_actionably():
    person = create_person_info(
        birth_year=1988,
        birth_month=8,
        birth_day=8,
        birth_hour=8,
        birth_place="火星基地",
        use_true_solar_time=True,
    )
    with pytest.raises(ValueError) as excinfo:
        normalize_birth_time(person)
    message = str(excinfo.value)
    assert "火星基地" in message  # names the unrecognized place
    assert "birth_longitude" in message  # tells the caller how to fix it
