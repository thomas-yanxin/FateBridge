from datetime import datetime, timedelta

import pytest

from fatebridge.core.bazi.timing import TimingAnalysis
from fatebridge.services.bazi import calculate_bazi_overview
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
from fatebridge.utils.places import (
    KNOWN_BIRTH_PLACE_ENTRIES,
    resolve_birth_place_context,
)
from fatebridge.utils.solar_time import normalize_birth_time
from fatebridge.utils.timezones import parse_timezone_name


def test_normalize_birth_time_preserves_legacy_hour_only_behavior() -> None:
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


def test_normalize_birth_time_uses_birth_place_for_true_solar_time() -> None:
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


def test_normalize_birth_time_resolves_full_form_chinese_city_address() -> None:
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


def test_normalize_birth_time_supports_english_city_address() -> None:
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


def test_normalize_birth_time_supports_pinyin_city_address() -> None:
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


def test_normalize_birth_time_prefers_more_specific_city_match_over_province() -> None:
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


def test_normalize_birth_time_falls_back_to_province_when_city_is_unknown() -> None:
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


def test_normalize_birth_time_supports_english_district_address() -> None:
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


def test_calculate_destiny_analysis_uses_corrected_solar_time_for_hour_pillar() -> None:
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

    result = calculate_bazi_overview(person)

    assert result["person_info"]["birth_datetime"] == "2020年01月01日 00时30分"
    assert (
        result["person_info"]["normalized_birth_datetime"] == "2019年12月31日 22时17分"
    )
    assert result["person_info"]["time_adjustment"]["applied"] is True
    assert result["person_info"]["time_adjustment"]["timezone"] == "Asia/Shanghai"
    assert result["person_info"]["time_adjustment"]["longitude_source"] == "birth_place"
    assert result["person_info"]["time_adjustment"]["resolved_place"] == "乌鲁木齐"
    assert result["person_info"]["time_adjustment"]["resolution_level"] == "city"
    assert result["four_pillars"]["hour"]["branch"] == "亥"


def test_calculate_comprehensive_timing_uses_corrected_birth_time() -> None:
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

    assert result["person_info"]["birth_datetime"] == "2020-01-01 00:30"
    assert result["person_info"]["normalized_birth_datetime"] == "2019-12-31 22:17"
    assert result["person_info"]["time_adjustment"]["applied"] is True
    assert result["person_info"]["time_adjustment"]["resolved_place"] == "乌鲁木齐"
    assert result["person_info"]["time_adjustment"]["resolution_level"] == "city"
    assert result["four_pillars"]["hour"]["branch"] == "亥"


def test_calculate_comprehensive_timing_supports_age_override() -> None:
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
    )
    dayun_result = calculate_dayun_analysis(person, 42)

    assert result["person_info"]["current_age"] == 42
    assert result["person_info"]["analysis_date"] == "2028-04-06"
    assert result["person_info"]["analysis_datetime"] == "2028-04-06 21:55"
    assert (
        result["dayun"]["current_dayun"]
        == dayun_result["dayun"]["current_dayun"]
    )


def test_calculate_comprehensive_timing_supports_analysis_day_boundaries() -> None:
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

    assert timing_result["person_info"]["analysis_date"] == "2028-04-06"
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
    assert timing_result["liuyue"]["pillar"] == "丙辰"
    assert timing_result["liuri"]["pillar"] == "辛酉"
    assert (
        timing_result["liuyue"]["pillar"]
        == liuyue_result["liuyue"]["pillar"]
    )
    assert (
        timing_result["liuri"]["pillar"]
        == liuri_result["liuri"]["pillar"]
    )


def test_time_precision_changes_liuyue_across_qingming_boundary() -> None:
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

    assert before_result["liuyue"]["pillar"] == "乙卯"
    assert (
        before_result["analysis_calendar"]["analysis_date_context"][
            "current_solar_term"
        ]["name"]
        == "春分"
    )
    assert boundary_result["liuyue"]["pillar"] == qingming_node["liuyue"]["pillar"]
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


def test_time_precision_aligns_liuri_and_timing_with_jieqi_anchor() -> None:
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

    assert liuri_result["liuri"]["pillar"] == qingming_node["liuri"]["pillar"]
    assert (
        liuri_result["analysis_calendar"]["analysis_date_context"][
            "current_solar_term"
        ]["name"]
        == "清明"
    )
    assert timing_result["person_info"]["analysis_datetime"] == "2028-04-04 21:55"
    assert (
        timing_result["liuyue"]["pillar"] == qingming_node["liuyue"]["pillar"]
    )
    assert timing_result["liuri"]["pillar"] == qingming_node["liuri"]["pillar"]
    assert (
        timing_result["analysis_calendar"]["analysis_date_context"][
            "current_solar_term"
        ]["name"]
        == "清明"
    )


def test_calculate_dayun_analysis_returns_current_dayun() -> None:
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

    assert "current_dayun" in result["dayun"]


def test_calculate_liuri_analysis_returns_expected_pillar() -> None:
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

    assert result["liuri"]["pillar"] == "丙辰"
    assert (
        result["analysis_calendar"]["analysis_date_context"]["current_solar_term"][
            "name"
        ]
        == "春分"
    )


def test_calculate_liushi_analysis_returns_expected_pillar() -> None:
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

    assert result["liushi"]["pillar"] == expected_liushi["pillar"]
    assert result["liushi"]["hour"] == 21
    assert (
        result["analysis_calendar"]["analysis_date_context"]["current_solar_term"][
            "name"
        ]
        == "春分"
    )


def test_calculate_liunian_analysis_returns_expected_pillar() -> None:
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

    assert result["liunian"]["pillar"] == "戊申"


def test_calculate_liuyue_analysis_returns_expected_pillar() -> None:
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

    assert result["liuyue"]["pillar"] == "乙卯"
    assert result["liuyue"]["solar_term_window"]["start_term"]["name"] == "惊蛰"
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
    assert result["liunian"]["pillar"] == "戊申"


def test_calculate_jieqi_timeline_analysis_returns_qingming_node() -> None:
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

    result = calculate_jieqi_timeline_analysis(person, analysis_year=2028)

    assert len(result["jieqi_timeline"]) == 24
    qingming_node = next(
        item for item in result["jieqi_timeline"] if item["jieqi"]["name"] == "清明"
    )
    assert qingming_node["analysis_anchor"] == "2028-04-04 14:04:00"
    assert qingming_node["liuyue"]["pillar"] == "丙辰"
    assert qingming_node["liuri"]["pillar"] == "己未"


def test_liuyue_timeline_anchor_is_minute_safe_and_replayable() -> None:
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
    assert liuyue_result["liuyue"]["pillar"] == qingming_month["liuyue"]["pillar"]
    assert (
        liuyue_result["liuyue"]["solar_term_window"]["start_term"]["name"]
        == "清明"
    )


def test_jieqi_timeline_anchor_is_minute_safe_and_replayable() -> None:
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
        else:
            pass

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

        assert liuyue_result["liuyue"]["pillar"] == item["liuyue"]["pillar"]
        assert liuri_result["liuri"]["pillar"] == item["liuri"]["pillar"]
        assert timing_result["liuyue"]["pillar"] == item["liuyue"]["pillar"]
        assert timing_result["liuri"]["pillar"] == item["liuri"]["pillar"]


def test_comprehensive_timing_matches_specialized_timing_tools() -> None:
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
        timing_result["dayun"]["current_dayun"]
        == dayun_result["dayun"]["current_dayun"]
    )
    assert (
        timing_result["dayun"]["start_age"]
        == dayun_result["dayun"]["start_age"]
    )
    assert (
        timing_result["dayun"]["dayun_age"]
        == dayun_result["dayun"]["dayun_age"]
    )
    assert (
        timing_result["liunian"]["pillar"]
        == liunian_result["liunian"]["pillar"]
    )
    assert (
        timing_result["liuyue"]["pillar"]
        == liuyue_result["liuyue"]["pillar"]
    )
    assert (
        timing_result["liuri"]["pillar"]
        == liuri_result["liuri"]["pillar"]
    )
    assert (
        timing_result["liushi"]["pillar"]
        == liushi_result["liushi"]["pillar"]
    )


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
def test_parse_timezone_name_accepts_offset_forms(value: str, expected_hours) -> None:
    assert _offset_hours(parse_timezone_name(value)) == pytest.approx(expected_hours)


def test_parse_timezone_name_accepts_iana_name() -> None:
    # IANA names still win over the numeric-offset shortcut.
    assert parse_timezone_name("Asia/Shanghai").utcoffset(
        datetime(2001, 1, 1, 12)
    ) == timedelta(hours=8)


@pytest.mark.parametrize("value", ["garbage", "1e3", "inf", "nan", "Asia/Nowhere"])
def test_parse_timezone_name_rejects_invalid_with_actionable_message(
    value: str,
) -> None:
    with pytest.raises(ValueError) as excinfo:
        parse_timezone_name(value)
    message = str(excinfo.value)
    # The error must name the accepted formats so callers can self-correct.
    assert "Asia/Shanghai" in message
    assert "+08:00" in message or "UTC+8" in message
    assert "bare offset" in message


def test_normalize_birth_time_accepts_bare_integer_timezone() -> None:
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


def test_resolve_birth_place_resolves_prefecture_city_district_form() -> None:
    # A catalogued district now resolves beyond its parent city.
    resolution = resolve_birth_place_context("咸阳市秦都区")
    assert resolution.canonical_name == "秦都区"
    assert resolution.longitude == pytest.approx(108.705, abs=0.01)
    assert resolution.level == "county"


def test_normalize_birth_time_resolves_newly_catalogued_prefecture_city() -> None:
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


def test_resolve_birth_place_context_returns_latitude() -> None:
    # Latitude must travel with longitude so the astrology engine can build a
    # chart from a place name alone (same coverage as the BaZi true-solar path).
    shanghai = resolve_birth_place_context("上海")
    assert shanghai.longitude == pytest.approx(121.4737, abs=0.01)
    assert shanghai.latitude == pytest.approx(31.2304, abs=0.01)

    # A prefecture-level city that previously had longitude but no latitude.
    nantong = resolve_birth_place_context("南通")
    assert nantong.longitude == pytest.approx(120.8943, abs=0.01)
    assert nantong.latitude is not None


def test_every_catalogued_place_has_latitude() -> None:
    # Drift guard: a place may not be half-resolved (longitude without latitude).
    # If this fails, a new make_birth_place_entry is missing its latitude.

    missing = [
        entry["canonical_name"]
        for entry in KNOWN_BIRTH_PLACE_ENTRIES
        if entry.get("latitude") is None
    ]
    assert missing == [], f"places missing latitude: {missing}"


def test_normalize_birth_time_unknown_place_errors_actionably() -> None:
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
