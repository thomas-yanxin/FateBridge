"""Oracle verification for Zhongzhou, Feixing, astro_type, exact divides, and speed."""

import json
import time

import pytest

from fatebridge.application.response_delivery import deliver_response
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.services.ziwei import (
    calculate_ziwei_birth,
    calculate_ziwei_horoscope,
)
from fatebridge.utils.birth_input import create_person_info


def test_oracle_zhongzhou_school_and_astro_types() -> None:
    # Oracle 5: 1989-05-23 08:40, 己巳阴年, 男 -> 阴男
    person = create_person_info(
        birth_year=1989,
        birth_month=5,
        birth_day=23,
        birth_hour=8,
        birth_minute=40,
        birth_timezone="Asia/Shanghai",
        gender="男",
        use_true_solar_time=False,
    )
    default_chart = calculate_ziwei_birth(person)["ziwei_birth"]
    zz_chart = calculate_ziwei_birth(person, school="zhongzhou")["ziwei_birth"]

    # 命主 by year branch 巳 = 武曲, 身主 by year branch 巳 = 天机
    assert zz_chart["chart_masters"]["life"]["selection_basis"] == "natal_year_branch"
    assert zz_chart["chart_masters"]["life"]["basis_branch"] == "巳"
    assert zz_chart["chart_masters"]["life"]["star"] == "武曲"
    assert zz_chart["chart_masters"]["body"]["star"] == "天机"

    # 阴男天伤/天使互换: 天伤在疾厄宫, 天使在仆役宫
    by_name_def = {p["name"]: set(p["stars"]) for p in default_chart["palaces"]}
    by_name_zz = {p["name"]: set(p["stars"]) for p in zz_chart["palaces"]}
    assert "天伤" in by_name_def["仆役宫"] and "天使" in by_name_def["疾厄宫"]
    assert "天伤" in by_name_zz["疾厄宫"] and "天使" in by_name_zz["仆役宫"]

    # 单星截空 (己年 -> 酉), 无 截路/空亡; 另有 大耗/龙德/劫杀; 岁前称 岁破
    all_zz_stars = {s for stars in by_name_zz.values() for s in stars}
    assert "截空" in all_zz_stars
    assert "截路" not in all_zz_stars and "空亡" not in all_zz_stars
    assert {"大耗", "龙德", "劫杀"} <= all_zz_stars
    suiqian_names = [
        p["name"]
        for p in zz_chart["calendar_cycles"]["year_branch_cycles"]["suiqian"][
            "positions"
        ]
    ]
    assert "岁破" in suiqian_names and "大耗" not in suiqian_names

    # 天地人三盘: earth 以身宫为命宫, human 以福德宫为命宫
    earth = calculate_ziwei_birth(person, school="zhongzhou", astro_type="earth")[
        "ziwei_birth"
    ]
    human = calculate_ziwei_birth(person, school="zhongzhou", astro_type="human")[
        "ziwei_birth"
    ]
    assert earth["ming_gong"]["branch"] == zz_chart["shen_gong"]["branch"]
    fude_branch = next(
        p["ganzhi"][1] for p in zz_chart["palaces"] if p["name"] == "福德宫"
    )
    assert human["ming_gong"]["branch"] == fude_branch


def test_oracle_feixing_qintian_and_geng_variants() -> None:
    # Oracle 6: 1990-05-15 14:30, 庚午年, 男
    person = create_person_info(
        birth_year=1990,
        birth_month=5,
        birth_day=15,
        birth_hour=14,
        birth_minute=30,
        birth_timezone="Asia/Shanghai",
        gender="男",
        use_true_solar_time=False,
    )
    fx = calculate_ziwei_birth(person, school="feixing")["ziwei_birth"]
    assert fx["laiyin_gong"]["ganzhi"][0] == "庚"
    assert fx["laiyin_gong"]["branch"] not in ("子", "丑")
    assert fx["sihua"] == {
        "化禄": "太阳",
        "化权": "武曲",
        "化科": "太阴",
        "化忌": "天同",
    }

    liang = calculate_ziwei_birth(
        person, school="feixing", sihua_source="feixing_liang"
    )["ziwei_birth"]
    assert liang["sihua"] == {
        "化禄": "太阳",
        "化权": "武曲",
        "化科": "天府",
        "化忌": "天相",
    }

    naj = calculate_ziwei_birth(person, sihua_source="naj_ming_v1")["ziwei_birth"]
    assert naj["sihua"] == {
        "化禄": "太阳",
        "化权": "武曲",
        "化科": "天同",
        "化忌": "天相",
    }


def test_year_divide_exact_horoscope_divide_exact_and_age_divide_birthday() -> None:
    # 2002-02-08 10:00 (post-Lichun 壬午, pre-CNY 辛巳)
    person = create_person_info(
        birth_year=2002,
        birth_month=2,
        birth_day=8,
        birth_hour=10,
        birth_minute=0,
        birth_timezone="Asia/Shanghai",
        gender="男",
        use_true_solar_time=False,
    )
    normal = calculate_ziwei_birth(person, year_divide="normal")["ziwei_birth"]
    exact = calculate_ziwei_birth(person, year_divide="exact")["ziwei_birth"]
    assert normal["year_stem"] == "辛"
    assert exact["year_stem"] == "壬"

    # age_divide="birthday": born 1990-05-15 (lunar 四月廿一), query 2024-02-10 (CNY 1, before birthday)
    p2 = create_person_info(
        birth_year=1990,
        birth_month=5,
        birth_day=15,
        birth_hour=12,
        birth_minute=0,
        birth_timezone="Asia/Shanghai",
        gender="男",
        use_true_solar_time=False,
    )
    h_normal = calculate_ziwei_horoscope(
        p2,
        analysis_year=2024,
        analysis_month=2,
        analysis_day=10,
        analysis_hour=12,
        age_divide="normal",
    )["ziwei_horoscope"]
    h_bday = calculate_ziwei_horoscope(
        p2,
        analysis_year=2024,
        analysis_month=2,
        analysis_day=10,
        analysis_hour=12,
        age_divide="birthday",
    )["ziwei_horoscope"]
    assert h_normal["nominal_age"] == 35
    assert h_bday["nominal_age"] == 34

    # horoscope_divide="exact" on 2023-04-05 12:00 (post-Qingming 丙辰 vs lunar leap 2 乙卯)
    h_exact = calculate_ziwei_horoscope(
        p2,
        analysis_year=2023,
        analysis_month=4,
        analysis_day=5,
        analysis_hour=12,
        horoscope_divide="exact",
    )["ziwei_horoscope"]
    liuyue = next(s for s in h_exact["scopes"] if s["scope"] == "流月")
    assert liuyue["flowing_star_basis"]["stem"] == "丙"
    assert liuyue["flowing_star_basis"]["branch"] == "辰"


def test_warm_latency_and_payload_budgets() -> None:
    person = create_person_info(
        birth_year=1994,
        birth_month=8,
        birth_day=23,
        birth_hour=14,
        birth_minute=30,
        birth_timezone="Asia/Shanghai",
        gender="男",
        use_true_solar_time=False,
    )
    calculate_ziwei_birth(person)
    t0 = time.perf_counter()
    for _ in range(20):
        b = calculate_ziwei_birth(person)
    birth_ms = (time.perf_counter() - t0) / 20 * 1000

    calculate_ziwei_horoscope(
        person, analysis_year=2026, analysis_month=6, analysis_day=19, analysis_hour=14
    )
    t1 = time.perf_counter()
    for _ in range(20):
        h = calculate_ziwei_horoscope(
            person,
            analysis_year=2026,
            analysis_month=6,
            analysis_day=19,
            analysis_hour=14,
        )
    timing_ms = (time.perf_counter() - t1) / 20 * 1000

    assert birth_ms < 3.0
    assert timing_ms < 5.0
    by_name = {spec.name: spec for spec in CATALOG}
    assert (
        len(
            json.dumps(
                deliver_response(b, spec=by_name["ziwei_birth_chart"]),
                ensure_ascii=False,
            ).encode()
        )
        <= 10240
    )
    assert (
        len(
            json.dumps(
                deliver_response(h, spec=by_name["ziwei_timing"]),
                ensure_ascii=False,
            ).encode()
        )
        <= 10240
    )
    assert len(json.dumps(h, ensure_ascii=False).encode()) < 20480
