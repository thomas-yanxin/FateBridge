"""Independent astronomical, calendar, and classical BaZi expert oracle suite."""

from __future__ import annotations

import gc
import json
import time
from datetime import datetime

import pytest

from fatebridge.analysis.timing_effects import TimingEffectsAnalysis
from fatebridge.application.execution import execute_with_receipt
from fatebridge.application.response_delivery import deliver_response
from fatebridge.core.almanac import (
    build_calendar_context,
    get_lunar_context,
    get_solar_terms_for_year,
)
from fatebridge.core.bazi.calendar import (
    BaZiCalendar,
    build_taixi,
    build_three_origins,
    resolve_month_duty,
    twelve_life_stage,
)
from fatebridge.core.bazi.relations import (
    check_clash_patterns,
    check_harmony_patterns,
    collect_target_branch_relations,
)
from fatebridge.core.bazi.shensha import build_shensha_profile, timing_shensha
from fatebridge.core.bazi.strength import analyze_elements_and_structure
from fatebridge.core.bazi.timing import TimingAnalysis
from fatebridge.services.bazi import calculate_bazi_birth
from fatebridge.services.timing import calculate_comprehensive_timing
from fatebridge.services.timing_periods import (
    calculate_liunian_analysis,
    calculate_liuri_analysis,
    calculate_liushi_analysis,
    calculate_liuyue_analysis,
)
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.utils.birth_input import PersonInfo
from fatebridge.utils.solar_time import normalize_birth_time

SPECS = {spec.name: spec for spec in CATALOG}


def test_solar_term_and_dst_astronomical_oracles() -> None:
    terms_2025 = {
        term.name: term.moment
        for term in get_solar_terms_for_year(2025, "Asia/Shanghai")
    }
    lichun_delta = abs(
        (
            terms_2025["立春"] - datetime.fromisoformat("2025-02-03T22:10:28+08:00")
        ).total_seconds()
    )
    lixia_delta = abs(
        (
            terms_2025["立夏"] - datetime.fromisoformat("2025-05-05T13:57:11+08:00")
        ).total_seconds()
    )
    assert lichun_delta < 5.0
    assert lixia_delta < 5.0

    person_1986 = PersonInfo(
        name="dst",
        gender="男",
        birth_year=1986,
        birth_month=5,
        birth_day=6,
        birth_hour=12,
        birth_minute=0,
        birth_timezone="Asia/Shanghai",
        birth_longitude=116.4074,
        birth_place="北京",
        use_true_solar_time=True,
    )
    norm_1986 = normalize_birth_time(person_1986)
    assert norm_1986.daylight_saving_minutes == 60.0


def test_true_solar_time_midnight_cross_and_historical_advisory() -> None:
    urumqi = PersonInfo(
        name="u",
        gender="男",
        birth_year=1990,
        birth_month=5,
        birth_day=15,
        birth_hour=0,
        birth_minute=15,
        birth_timezone="Asia/Shanghai",
        birth_longitude=87.6177,
        birth_place="乌鲁木齐",
        use_true_solar_time=True,
    )
    norm = normalize_birth_time(urumqi)
    assert norm.daylight_saving_minutes == 60.0
    assert norm.corrected_datetime.strftime("%Y-%m-%d %H:%M") == "1990-05-14 21:09"
    pillars = BaZiCalendar.get_four_pillars(
        norm.corrected_datetime,
        timezone_name="Asia/Shanghai",
        civil_datetime=norm.input_datetime,
    )
    assert {k: "".join(pillars[k]) for k in ("year", "month", "day", "hour")} == {
        "year": "庚午",
        "month": "辛巳",
        "day": "己卯",
        "hour": "乙亥",
    }

    ctx_1940 = build_calendar_context(
        datetime(1940, 7, 1, 12, 0), timezone_name="Asia/Shanghai"
    )
    assert ctx_1940["timezone_advisory"]["code"] == "historical_timezone_ambiguous"
    assert ctx_1940["timezone_advisory"]["applied_utc_offset_hours"] == 9.0


@pytest.mark.parametrize(
    "policy,expected_day,expected_hour",
    [
        ("day_rollover_at_23", "乙酉", "丙子"),
        ("night_zi_same_day_next_hour_stem", "甲申", "丙子"),
        ("night_zi_same_day_same_hour_stem", "甲申", "甲子"),
    ],
)
def test_zi_hour_policies_discriminate_day_and_hour_pillars(
    policy: str, expected_day: str, expected_hour: str
) -> None:
    dt = datetime(2025, 5, 15, 23, 30)
    pillars = BaZiCalendar.get_four_pillars(dt, "Asia/Shanghai", zi_hour_policy=policy)  # type: ignore[arg-type]
    assert "".join(pillars["year"]) == "乙巳"
    assert "".join(pillars["month"]) == "辛巳"
    assert "".join(pillars["day"]) == expected_day
    assert "".join(pillars["hour"]) == expected_hour

    person = PersonInfo(
        name="zi",
        gender="男",
        birth_year=2025,
        birth_month=5,
        birth_day=15,
        birth_hour=23,
        birth_minute=30,
        birth_timezone="Asia/Shanghai",
        use_true_solar_time=False,
    )
    res = calculate_bazi_birth(person, zi_hour_policy=policy)  # type: ignore[arg-type]
    day_p = res["bazi_birth"]["four_pillars"]["day"]
    hour_p = res["bazi_birth"]["four_pillars"]["hour"]
    assert f"{day_p['stem']}{day_p['branch']}" == expected_day
    assert f"{hour_p['stem']}{hour_p['branch']}" == expected_hour


def test_lunar_calendar_leap_and_boundary_oracles() -> None:
    d2033 = get_lunar_context(datetime(2033, 12, 22, 12, 0))
    assert d2033 is not None
    assert (d2033["year"], d2033["month"], d2033["day"], d2033["is_leap_month"]) == (
        2033,
        11,
        1,
        True,
    )
    d1933 = get_lunar_context(datetime(1933, 6, 23, 12, 0))
    assert d1933 is not None
    assert (d1933["year"], d1933["month"], d1933["day"], d1933["is_leap_month"]) == (
        1933,
        5,
        1,
        True,
    )
    d1954 = get_lunar_context(datetime(1954, 5, 3, 12, 0))
    assert d1954 is not None
    assert (d1954["year"], d1954["month"], d1954["day"], d1954["is_leap_month"]) == (
        1954,
        4,
        1,
        False,
    )
    d1978 = get_lunar_context(datetime(1978, 5, 7, 12, 0))
    assert d1978 is not None
    assert (d1978["year"], d1978["month"], d1978["day"], d1978["is_leap_month"]) == (
        1978,
        4,
        1,
        False,
    )
    c1900 = build_calendar_context(
        datetime(1900, 1, 15, 12, 0), timezone_name="Asia/Shanghai"
    )
    d1900 = c1900["lunar_calendar"]
    assert (d1900["year"], d1900["month"], d1900["day"], d1900["is_leap_month"]) == (
        1899,
        12,
        15,
        False,
    )
    assert d1900["display"] == "腊月十五"
    assert c1900["lunar_calendar_support"]["supported"] is True
    d2100 = get_lunar_context(datetime(2100, 3, 1, 12, 0))
    assert d2100 is not None and d2100["year"] == 2100 and int(d2100["month"]) >= 1


def test_child_limit_countdown_and_pre_dayun_xiaoyun() -> None:
    person = PersonInfo(
        name="kid",
        gender="男",
        birth_year=2025,
        birth_month=5,
        birth_day=15,
        birth_hour=14,
        birth_minute=30,
        birth_timezone="Asia/Shanghai",
        birth_longitude=116.4074,
        birth_place="北京",
        use_true_solar_time=False,
    )
    pillars = BaZiCalendar.get_four_pillars(
        datetime(2025, 5, 15, 14, 30), "Asia/Shanghai"
    )
    assert {k: "".join(pillars[k]) for k in ("year", "month", "day", "hour")} == {
        "year": "乙巳",
        "month": "辛巳",
        "day": "甲申",
        "hour": "辛未",
    }

    dy = TimingEffectsAnalysis.analyze_dayun_effects(
        pillars,
        datetime(2025, 5, 15, 14, 30),
        "男",
        1,
        timezone_name="Asia/Shanghai",
    )
    assert dy["status"] == "before_dayun"
    assert dy["child_limit"]["years"] == 3
    assert dy["child_limit"]["months"] == 4
    assert dy["child_limit"]["days"] == 2
    assert dy["child_limit"]["start_day_ganzhi"] == "丙午"
    assert dy["xiaoyun_info"]["direction"] == "逆行"
    assert dy["xiaoyun_info"]["pillar"] == "己巳"  # age=1 -> nominal_age=2 -> 辛未逆2步
    assert [row["pillar"] for row in dy["xiaoyun_timeline"]] == [
        "庚午",
        "己巳",
        "戊辰",
        "丁卯",
    ]

    timing_res = calculate_comprehensive_timing(
        person,
        analysis_year=2026,
        analysis_month=6,
        analysis_day=15,
        analysis_hour=12,
    )
    assert timing_res["dayun_analysis"]["status"] == "before_dayun"
    assert timing_res["dayun_analysis"]["xiaoyun"]["pillar"] == "己巳"
    assert timing_res["dayun_analysis"]["child_limit"]["start_day_ganzhi"] == "丙午"


def test_active_structure_strength_diaohou_and_month_duty() -> None:
    # 1. 从财格: 戊日主满盘水木财官无印比根气 (乙卯无丙戊余气)
    cong_cai = {
        "year": ("壬", "子"),
        "month": ("癸", "亥"),
        "day": ("戊", "子"),
        "hour": ("乙", "卯"),
    }
    res_cc = analyze_elements_and_structure(cong_cai)
    assert res_cc["favorable_elements"]
    assert res_cc["structure_profile"]["assessment_status"] == "adjudicated"
    assert "从" in res_cc["structure_profile"]["dominant_structure"]["label"]

    # 2. 专旺格 (曲直仁寿格): 寅卯辰三会东方木局、扶身极旺无金破局
    zhuan_wang = {
        "year": ("甲", "寅"),
        "month": ("乙", "卯"),
        "day": ("甲", "辰"),
        "hour": ("癸", "亥"),
    }
    res_zw = analyze_elements_and_structure(zhuan_wang)
    assert res_zw["structure_profile"]["assessment_status"] == "adjudicated"
    assert (
        res_zw["structure_profile"]["dominant_structure"]["key"] == "zhuan_wang_qu_zhi"
    )
    assert "木" in res_zw["favorable_elements"]

    # 3. 人元司令分野 profile distinction at day 6.0 of 巳月:
    # 《三命通会》巳月: 戊7 庚5 丙18 -> day 6.0 is 戊
    # 《渊海子平》/6tail 巳月: 戊5 庚9 丙16 -> day 6.0 is 庚
    d_sanming = resolve_month_duty("巳", 6.0, day_stem="庚", profile="sanming")
    d_yuanhai = resolve_month_duty("巳", 6.0, day_stem="庚", profile="yuanhai")
    d_6tail = resolve_month_duty("巳", 6.0, day_stem="庚", profile="6tail")
    assert d_sanming["selected_stem"] == "戊"
    assert d_yuanhai["selected_stem"] == "庚"
    assert d_6tail["selected_stem"] == "庚"


def test_changsheng_schools_taixi_and_complete_shensha_separation() -> None:
    assert twelve_life_stage("戊", "寅", school="fire_earth_same_palace") == "长生"
    assert twelve_life_stage("戊", "申", school="water_earth_same_palace") == "长生"
    assert twelve_life_stage("己", "卯", school="five_element_same_stage") == "沐浴"

    pillars = {
        "year": ("庚", "午"),
        "month": ("辛", "巳"),
        "day": ("甲", "子"),
        "hour": ("庚", "寅"),  # 甲见庚寅 -> 词馆; 年干庚 -> 午为太极/天乙? 午=年支
    }
    taixi = build_taixi(pillars)
    assert taixi["pillar"] == "己丑"
    three = build_three_origins(pillars)
    shensha = build_shensha_profile(
        pillars=pillars,
        three_origins=three,
        taixi=taixi,
    )
    # 年支孤辰 anchored on year_branch (午 -> 申); check natal vs three_origins separation
    assert not any(row["label"] == "年支孤辰" for row in shensha["triggered_natal"])
    shensha_with_shen = build_shensha_profile(
        pillars={**pillars, "hour": ("庚", "申")},
        three_origins=three,
        taixi=taixi,
    )
    gu_chen = next(
        row
        for row in shensha_with_shen["triggered_natal"]
        if row["label"] == "年支孤辰"
    )
    assert gu_chen["anchor"] == "年支"
    # No 胎元/命宫/身宫/胎息 labels mixed inside triggered_natal!
    assert all(
        all(not hit.startswith(("胎元", "命宫", "身宫", "胎息")) for hit in row["hits"])
        for row in shensha["triggered_natal"]
    )
    # 词馆 requires full stem+branch (甲见庚寅, hour is 庚寅)
    assert any("词馆" in row["label"] for row in shensha["triggered_natal"])
    # 天乙贵人 checks both day stem and year stem
    assert any("天乙贵人" in row["label"] for row in shensha["natal_entries"])
    assert set(shensha["kongwang"]["by_pillar"]) == {"year", "month", "day", "hour"}


def test_relations_and_timing_tools_six_breaks_hidden_combos_and_fuyin_fanyin() -> None:
    pillars = {
        "year": ("甲", "子"),
        "month": ("丁", "卯"),
        "day": ("乙", "酉"),
        "hour": ("丙", "戌"),
    }
    clash = check_clash_patterns(pillars)
    assert ["子", "酉"] in clash["six_break"]  # 子酉破
    assert any(p["branches"] == ["子", "卯"] for p in clash["punishments"])  # 子卯刑
    harmony = check_harmony_patterns(
        {
            "year": ("甲", "寅"),
            "month": ("乙", "丑"),
            "day": ("丙", "午"),
            "hour": ("丁", "亥"),
        }
    )
    assert harmony["hidden_harmony"]

    # 伏吟 + 岁运并临 on 甲子
    rels_fuyin = collect_target_branch_relations(
        "子", pillars, "流年", target_stem="甲"
    )
    assert any("伏吟" in r["type"] for r in rels_fuyin)
    # 天克地冲 (反吟): 庚午 clashes 甲子
    rels_fanyin = collect_target_branch_relations(
        "午", pillars, "流年", target_stem="庚"
    )
    assert any("天克地冲" in r["type"] or "六冲" in r["type"] for r in rels_fanyin)
    assert timing_shensha(pillars, "甲", "子")

    person = PersonInfo(
        name="t",
        gender="男",
        birth_year=1990,
        birth_month=5,
        birth_day=15,
        birth_hour=10,
        birth_minute=30,
        birth_timezone="Asia/Shanghai",
        use_true_solar_time=False,
    )
    for fn in (
        lambda: calculate_liunian_analysis(person, 2026),
        lambda: calculate_liuyue_analysis(person, 2026, 5, 15),
        lambda: calculate_liuri_analysis(person, 2026, 5, 15),
        lambda: calculate_liushi_analysis(person, 2026, 5, 15, 14),
    ):
        res = fn()
        assert "error" not in res


def test_compact_payload_bloat_and_warm_latency_budgets() -> None:
    base_birth = {
        "name": "基准",
        "gender": "男",
        "birth_year": 1990,
        "birth_month": 5,
        "birth_day": 15,
        "birth_hour": 10,
        "birth_minute": 30,
        "birth_timezone": "Asia/Shanghai",
        "birth_longitude": 121.47,
        "birth_place": "上海",
        "use_true_solar_time": True,
    }
    topic_inputs = {**base_birth, "analysis_year": 2026}
    timing_inputs = {
        **topic_inputs,
        "analysis_month": 5,
        "analysis_day": 15,
        "analysis_hour": 14,
    }

    bazi_tools = [
        ("bazi_overview", base_birth),
        ("bazi_birth_chart", base_birth),
        ("bazi_career", topic_inputs),
        ("bazi_wealth", topic_inputs),
        ("bazi_marriage", topic_inputs),
        ("bazi_romance", topic_inputs),
        ("bazi_health", topic_inputs),
        ("bazi_children", topic_inputs),
        ("bazi_education", topic_inputs),
        ("bazi_personality", topic_inputs),
        ("bazi_relatives", topic_inputs),
    ]

    def _invoke(spec, raw_inputs: dict[str, object]) -> dict[str, object]:
        req = spec.request_model(**raw_inputs)
        return deliver_response(
            execute_with_receipt(spec, req),
            spec=spec,
            detail="compact",
        )

    gc.collect()
    for name, payload in bazi_tools:
        # Warm cache
        _invoke(SPECS[name], payload)
        t0 = time.perf_counter()
        res = _invoke(SPECS[name], payload)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        size_bytes = len(json.dumps(res, ensure_ascii=False).encode("utf-8"))
        assert size_bytes < 10240, f"{name} compact too large: {size_bytes}"
        assert elapsed_ms < 50.0, f"{name} too slow: {elapsed_ms:.2f}ms"

    _invoke(SPECS["bazi_timing"], timing_inputs)
    t0 = time.perf_counter()
    res_timing = _invoke(SPECS["bazi_timing"], timing_inputs)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    size_bytes = len(json.dumps(res_timing, ensure_ascii=False).encode("utf-8"))
    assert size_bytes < 15360, f"bazi_timing compact too large: {size_bytes}"
    assert elapsed_ms < 50.0, f"bazi_timing too slow: {elapsed_ms:.2f}ms"
