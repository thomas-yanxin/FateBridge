"""Four named time chains without a shared clock or a new calendar policy."""

from __future__ import annotations

import hashlib
import json
import re
from fractions import Fraction
from math import lcm
from pathlib import Path
from typing import Any

from fatebridge.core.sukuyo_sources import load_source

SOURCE = Path(__file__).resolve().parents[1] / "data/sukuyo_matanga_time_sources.json"
DATA_SHA256 = "8eb31ac1e216ef247b062b7d68bd8d1b98aece3b4d97841f8a15deb00b9e5908"
FACTS_SHA256 = "f59af327f7ca99e9afe129b6f0fa2cb0a8bb1f2667ae60f4eb2fb3dc001f8ec2"
R1_SHA256 = "b7bcbf3690a64679991b5f0950ac4ebe87c5c63eb556f0415be4a7f021dcb798"
R2_SHA256 = "813fddd49bce5236fa3f76b3ee41d28dd2fe6243b4741eef6b4dc8758976418d"


def validate_matanga_data(data: dict[str, Any]) -> None:
    raw = json.dumps(
        data, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    if hashlib.sha256(raw).hexdigest() != FACTS_SHA256:
        raise ValueError("摩登伽计时链、见证映射、原字或未定控制改变，须重新核验")


def matanga_time_reference() -> dict[str, Any]:
    loaded = load_source(SOURCE)
    if loaded.sha256 != DATA_SHA256:
        raise ValueError("摩登伽计时资料身份改变，须重新冻结来源")
    data = loaded.data
    validate_matanga_data(data)
    products = {}
    for system in data["source_data"]["unit_systems"]:
        total = 1
        values = {}
        for step in system["steps"]:
            total *= step["count"]
            values["per_" + step["per"]] = total
        products[system["id"]] = values

    literal = data["source_data"]["leap_formulations"]["literal"]
    match = re.search(r"於(十九)年凡有(七)閏。(五)年(再)閏", literal)
    if match is None:
        raise ValueError("闰数条件比较没有所选原句支持")
    numbers = {"十九": 19, "七": 7, "五": 5, "再": 2}
    first = Fraction(numbers[match[2]], numbers[match[1]])
    second = Fraction(numbers[match[4]], numbers[match[3]])
    common = lcm(first.denominator, second.denominator)
    first_count, second_count = first * common, second * common
    if first_count.denominator != 1 or second_count.denominator != 1:
        raise ValueError("所选共同周期没有整数条件计数")
    return {
        **data,
        "source_bundle_sha256": loaded.sha256,
        "hash_scope": "source_data_and_edition_identity_v79",
        "before_code_reference_sha256": R1_SHA256,
        "before_edition_code_reference_sha256": R2_SHA256,
        "conditional_products": products,
        "strict_repeated_cycle_hypothesis_only": {
            "common_years": common,
            "nineteen_year_seven_intercalations": first_count.numerator,
            "five_year_two_intercalations": second_count.numerator,
            "difference": (second_count - first_count).numerator,
            "rates": [str(first), str(second)],
            "source_periodicity_or_schedule_established": False,
        },
        "same_named_units_equated": False,
        "modern_seconds_per_unit": None,
        "annual_total_literal_adjudicated": False,
        "birth_calendar_override_applied": False,
        "historical_daybreak_half_or_priority_certified": False,
    }


def matanga_time_lines(reference: dict[str, Any]) -> list[str]:
    data = reference["source_data"]
    products = reference["conditional_products"]
    cycle = reference["strict_repeated_cycle_hypothesis_only"]
    return [
        "新增直接汉译电子本比较：《摩登伽經》T1300的紡綖一尋为剎那起点，"
        "六十剎那一羅婆、三十羅婆一時、三十分一日夜；"
        f"本链条件乘积为{products['T1300_thread_chain']['per_日夜']}剎那。"
        "《舍頭諫太子二十八宿經》T1301另以切三尺縷为節起点，"
        "六十節一限、十二限一須臾、三十須臾一晝夜，"
        f"本链为{products['T1301_thread_chain']['per_晝夜']}節。"
        "两书活动比喻及单位分别保留，未换算现代秒。",
        "T1300漏刻段另以如人瞬頃名一羅婆，四羅婆一迦啅、四十迦啅一迦羅、"
        "三十迦羅一刻、二刻一分，"
        f"条件乘积为每分{products['T1300_water_chain']['per_分']}羅婆；"
        "未把本段羅婆或分与前段同名字无条件合并。"
        "T1301另列十五眴一卒、二十卒一時、三十時一須臾、三十須臾一晝夜，"
        "再接三十日一月、十二月一年；"
        f"仅按该名义链相乘为{products['T1301_blink_chain']['per_年']}眴。"
        f"所见年度原字另录‘{data['year_total_literal']['literal']}’，"
        "古代億数制及数字协调未定，不以乘积校改原字。",
        "T1300原句并列‘於十九年凡有七閏’与‘五年再閏’。"
        "仅额外假设两者都是严格重复周期，并将再作两次时，"
        f"共同{cycle['common_years']}年条件计数分别为"
        f"{cycle['nineteen_year_seven_intercalations']}和"
        f"{cycle['five_year_two_intercalations']}闰，差{cycle['difference']}；"
        "这不是原文已给严格周期或实际置闰年月，也不据此判原文必矛盾。",
        "两汉译的日初出、日中、日沒与季节性昼夜分数保留为各段语境，"
        "分名列表不自动给出全年逐日配时，更不替代T1299平明／晓时或桧尾半日、"
        "闰月复用与小月缺日补配先后的直接证据。各自listWit映射和原注、改注、"
        "app及眴／瞬复用校注分别保存；T1300的wit1指【明】，T1301的wit1指【宋】，"
        "编号不能跨文件套用，电子校记不认证亲见各版印字或传承独立性。",
    ]
