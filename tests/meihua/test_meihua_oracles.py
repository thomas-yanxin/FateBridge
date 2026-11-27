"""Meihua, GuaLookup (1-64), and Tongshefa oracle, party-count, and payload-budget tests."""

from __future__ import annotations

import json
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from pydantic import TypeAdapter

from fatebridge.core.divination import lookup_gua
from fatebridge.core.meihua.casting import resolve_meihua_cast_datetime
from fatebridge.core.meihua.texts import lookup_trigram_wanwu
from fatebridge.core.requests.meihua import MeihuaCasting
from fatebridge.services.divination import (
    calculate_gua_lookup,
    calculate_meihua_analysis,
    calculate_tongshefa_analysis,
)
from fatebridge.services.meihua import calculate_meihua_cast
from tests.support.transports import AS_OF, SPECS, business

ALL_12_CAST_METHODS = [
    {"method": "existing", "hexagram_code": "010111", "moving_line": 4},
    {
        "method": "sound_groups",
        "first_count": 11,
        "second_count": 1,
        "hour_branch": "子",
    },
    {"method": "object_count", "count": 9, "hour_branch": "酉"},
    {
        "method": "observed_trigrams",
        "upper_trigram": "离",
        "lower_trigram": "兑",
        "hour_branch": "辰",
    },
    {
        "method": "observed_categories",
        "subject_category": "elder_person",
        "subject_description": "单一长者",
        "single_subject_confirmed": True,
        "direction": "southeast",
        "direction_role": "toward",
        "hour_branch": "卯",
    },
    {"method": "length_zhang_chi", "zhang": 1, "chi": 8, "cun": 3},
    {"method": "length_chi_cun", "chi": 1, "cun": 8, "fen": 3, "hour_branch": "卯"},
    {"method": "text_tones", "tones": [1, 4, 3, 3, 1, 1]},
    {"method": "text_strokes", "strokes": [6, 8]},
    {
        "method": "single_character_strokes",
        "script_style": "regular",
        "left_strokes": 7,
        "right_strokes": 4,
        "total_strokes": 11,
    },
    {"method": "text_count", "character_count": 11},
    {
        "method": "lunar_time_added_count",
        "year_branch": "子",
        "lunar_month": 12,
        "lunar_day": 30,
        "hour_branch": "午",
        "added_count": 7,
    },
]


def test_meihua_time_cast_2024_05_20_14_30_oracle() -> None:
    res = calculate_meihua_analysis(
        analysis_year=2024,
        analysis_month=5,
        analysis_day=20,
        analysis_hour=14,
        analysis_minute=30,
        analysis_timezone="Asia/Shanghai",
    )
    meihua = res["meihua"]
    assert meihua["base_hexagram"]["name"] == "坎为水"
    assert meihua["changed_hexagram"]["name"] == "风水涣"
    assert meihua["mutual_hexagram"]["name"] == "山雷颐"
    assert meihua["seed"]["moving_line"] == 6
    assert meihua["body_trigram"]["name"] == "坎"
    assert meihua["use_trigram"]["name"] == "坎"
    assert meihua["body_use_relation"] == "体用比和"

    # 体党 / 用党 counts (坎水体, 坎水用 -> 本互变中3个坎水卦)
    party = meihua["party_counts"]
    assert party["trigram_counts"]["body_party"] == 3
    assert party["trigram_counts"]["use_party"] == 3
    assert party["dominant_party"] == "equal"

    # Static clause walls & counseling prose stripped
    interp = res["interpretation"]
    for removed in (
        "seasonal_qualification",
        "stage_emphasis",
        "trigram_relation_symbols",
        "internal_countercontrol",
    ):
        assert removed not in interp
    assert "evidence_scope" not in interp
    for stage in meihua["stage_relations"]:
        assert "meaning" not in stage
        assert stage["traditional_tendency"] in {"比和", "泄出", "克出", "生入", "克入"}


def test_meihua_party_counts_and_true_solar_time_helper() -> None:
    cast_res = calculate_meihua_cast(
        casting={"method": "existing", "hexagram_code": "111101", "moving_line": 1}
    )
    # 111101 = 火天大有, moving line 1 (下卦乾动): 体=离(火), 用=乾(金)
    # 本: 离(火), 乾(金); 互: 兑(金), 乾(金); 变(火风鼎): 离(火), 巽(木)
    # 体党(火, 木生火): 离×2 + 巽×1 = 3; 用党(金, 土生金): 乾×2 + 兑×1 = 3
    party = cast_res["meihua"]["party_counts"]
    assert party["body_element"] == "火"
    assert party["use_element"] == "金"
    assert party["trigram_counts"]["body_party"] == 3
    assert party["trigram_counts"]["use_party"] == 3
    assert party["line_counts"]["yang_lines"] == 5
    assert party["line_counts"]["yin_lines"] == 1

    dt = datetime(2024, 5, 20, 14, 30, tzinfo=ZoneInfo("Asia/Shanghai"))
    civil_dt, civil_meta = resolve_meihua_cast_datetime(dt, use_true_solar_time=False)
    assert civil_dt == dt and civil_meta["true_solar_time_applied"] is False
    solar_dt, solar_meta = resolve_meihua_cast_datetime(
        dt, longitude=116.4, use_true_solar_time=True
    )
    assert solar_meta["true_solar_time_applied"] is True
    assert solar_dt != dt
    with pytest.raises(ValueError):
        resolve_meihua_cast_datetime(dt, use_true_solar_time=True, longitude=None)


@pytest.mark.parametrize("casting", ALL_12_CAST_METHODS, ids=lambda p: p["method"])
def test_all_12_meihua_casting_methods_and_budget(casting: dict[str, object]) -> None:
    TypeAdapter(MeihuaCasting).validate_python(casting)
    calculate_meihua_cast(casting=casting)
    t0 = time.perf_counter()
    res = calculate_meihua_cast(casting=casting)
    dt_ms = (time.perf_counter() - t0) * 1000
    size_bytes = len(json.dumps(res, ensure_ascii=False).encode("utf-8"))
    assert "error" not in res
    assert res["meihua"]["party_counts"]["trigram_counts"]["body_party"] >= 1
    assert size_bytes < 25_000
    assert dt_ms < 15.0


def test_trigram_wanwu_lookup() -> None:
    qian = lookup_trigram_wanwu("乾")
    assert qian["element"] == "金" and qian["direction"] == "西北"
    with pytest.raises(ValueError):
        lookup_trigram_wanwu("未知")


def test_gua_lookup_king_wen_1_to_64_and_relations() -> None:
    res = calculate_gua_lookup(queries=["1", "64", "#11", "第13卦"])
    q1 = res["results"]["1"]
    assert q1["name"] == "乾为天"
    assert q1["mutual_hexagram"]["name"] == "乾为天"
    assert q1["cuo_hexagram"]["name"] == "坤为地"
    assert q1["zong_hexagram"]["name"] == "乾为天"
    assert q1["bagong"] == {
        "palace": "乾",
        "palace_element": "金",
        "position": "本宫",
        "shi_line": 6,
        "ying_line": 3,
    }
    q64 = res["results"]["64"]
    assert q64["name"] == "火水未济"
    assert q64["cuo_hexagram"]["name"] == "水火既济"
    assert q64["zong_hexagram"]["name"] == "水火既济"
    assert q64["bagong"]["palace"] == "离"
    assert res["results"]["#11"]["name"] == "地天泰"
    assert res["results"]["第13卦"]["name"] == "天火同人"

    with pytest.raises(ValueError):
        lookup_gua("0")
    with pytest.raises(ValueError):
        lookup_gua("65")
    assert calculate_gua_lookup(queries=["0"])["error_code"] == "validation_error"


def test_tongshefa_lower_mutual_opposite_relations_and_transports(
    surface_calls,
) -> None:
    payload = {"taiyin": "巽", "taiyang": "坤", "shaoyang": "震", "shaoyin": "震"}
    res = calculate_tongshefa_analysis(**payload)
    model = res["tongshefa"]
    assert model["main_relation"] == "思克实"
    assert model["lower_relation"] == "思同实"
    assert model["mutual_relations"] == {"upper": "思同实", "lower": "思同实"}
    assert model["opposite_relations"] == {"upper": "实克思", "lower": "思同实"}

    http, mcp, code, cli = surface_calls(
        SPECS["combine_four_gua"],
        payload,
        rest_as_of=AS_OF,
    )
    assert http.status_code == 200 and code == 0 and not mcp.is_error
    assert business(http.json()) == business(cli) == business(mcp.structured_content)
