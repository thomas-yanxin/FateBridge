"""ZiBai (Annual/Monthly/Daily/Hourly + 煞位), BaZhai (64-cell/MingGua/三要), JinSuo (8+24)."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core.fengshui.bazhai import bazhai, minggua, sectors, yangzhai_sanyao
from fatebridge.core.fengshui.jinsuo import jinsuo, jinsuo_24_mountains
from fatebridge.core.fengshui.models import (
    AnnualRequest,
    BazhaiRequest,
    JinsuoRequest,
    MingguaRequest,
    MonthlyRequest,
    Placement,
)
from fatebridge.core.fengshui.zibai import (
    annual_stars,
    daily_stars,
    hourly_stars,
    monthly_stars,
)

MONTHLY_FIXTURE = Path(__file__).parent / "fixtures" / "monthly-integrity-v1.json"

# 《八宅明镜》大游年歌 64-cell oracle: sitting -> {palace_dir: star_name}
BAZHAI_64_ORACLE: dict[str, dict[str, str]] = {
    "坎": {
        "N": "伏位",
        "NE": "五鬼",
        "E": "天医",
        "SE": "生气",
        "S": "延年",
        "SW": "绝命",
        "W": "祸害",
        "NW": "六煞",
    },
    "艮": {
        "N": "五鬼",
        "NE": "伏位",
        "E": "六煞",
        "SE": "绝命",
        "S": "祸害",
        "SW": "生气",
        "W": "延年",
        "NW": "天医",
    },
    "震": {
        "N": "天医",
        "NE": "六煞",
        "E": "伏位",
        "SE": "延年",
        "S": "生气",
        "SW": "祸害",
        "W": "绝命",
        "NW": "五鬼",
    },
    "巽": {
        "N": "生气",
        "NE": "绝命",
        "E": "延年",
        "SE": "伏位",
        "S": "天医",
        "SW": "五鬼",
        "W": "六煞",
        "NW": "祸害",
    },
    "离": {
        "N": "延年",
        "NE": "祸害",
        "E": "生气",
        "SE": "天医",
        "S": "伏位",
        "SW": "六煞",
        "W": "五鬼",
        "NW": "绝命",
    },
    "坤": {
        "N": "绝命",
        "NE": "生气",
        "E": "祸害",
        "SE": "五鬼",
        "S": "六煞",
        "SW": "伏位",
        "W": "天医",
        "NW": "延年",
    },
    "兑": {
        "N": "祸害",
        "NE": "延年",
        "E": "绝命",
        "SE": "六煞",
        "S": "五鬼",
        "SW": "天医",
        "W": "伏位",
        "NW": "生气",
    },
    "乾": {
        "N": "六煞",
        "NE": "天医",
        "E": "五鬼",
        "SE": "祸害",
        "S": "绝命",
        "SW": "延年",
        "W": "生气",
        "NW": "伏位",
    },
}


@pytest.mark.parametrize(
    "year,expected_center", [(2024, 3), (2025, 2), (2026, 1), (2027, 9)]
)
def test_annual_zibai_and_afflictions(year: int, expected_center: int) -> None:
    res = annual_stars(AnnualRequest(effective_year=year))
    assert res["status"] == "complete"
    assert res["center_star_number"] == expected_center
    if year == 2026:
        aff = res["annual_afflictions"]
        assert aff["year_branch"] == "午"
        assert aff["taisui"] == {"branch": "午", "direction": "S"}
        assert aff["suipo"] == {"branch": "子", "direction": "N"}
        assert aff["sansha"]["direction"] == "N"
        assert aff["wuhuang"]["direction"] == "S"
        assert aff["erhei"]["direction"] == "NW"


def test_monthly_zibai_36_centers_and_lichun_rollover() -> None:
    fixture = json.loads(MONTHLY_FIXTURE.read_text(encoding="utf-8"))
    branch_to_year = {
        "子": 2020,
        "丑": 2021,
        "寅": 2022,
        "卯": 2023,
        "辰": 2024,
        "巳": 2025,
        "午": 2026,
        "未": 2027,
        "申": 2028,
        "酉": 2029,
        "戌": 2030,
        "亥": 2031,
    }
    for group in fixture["printed_center_columns"]:
        for branch in group["branches"]:
            yr = branch_to_year[branch]
            for month_num, expected_center in enumerate(group["centers"], start=1):
                res = monthly_stars(
                    MonthlyRequest(
                        effective_solar_year=yr, solar_month_number=month_num
                    )
                )
                assert res["center_star_number"] == expected_center
                for d, offset in fixture["palace_offsets"].items():
                    assert (
                        res["palaces"][d]["monthly_star_number"]
                        == (expected_center + offset - 1) % 9 + 1
                    )

    jan10 = monthly_stars(
        MonthlyRequest(query_at=datetime.fromisoformat("2027-01-10T12:00:00+08:00"))
    )
    assert jan10["time_context"]["effective_solar_year"] == 2026
    assert jan10["time_context"]["solar_month_number"] == 12
    assert jan10["center_star_number"] == 6


def test_daily_and_hourly_zibai_oracles() -> None:
    # §6 #6: 2026-02-04T12:00:00+08:00 (between 立春 & 雨水 -> [冬至, 雨水), 己酉 day index=45)
    t1 = datetime.fromisoformat("2026-02-04T12:00:00+08:00")
    d1 = daily_stars(t1, "Asia/Shanghai")
    assert d1["day_ganzhi"] == "己酉"
    assert d1["segment"]["anchor_term"] == "冬至"
    assert d1["segment"]["jiazi_anchor_star"] == 1
    assert d1["segment"]["progression_direction"] == "ascending"
    assert d1["center_star_number"] == 1  # wrap9(1 + 45) == 1
    assert d1["palaces"]["NW"]["daily_star_number"] == 2

    # 己酉 -> 酉 ∈ {子午卯酉} after 冬至 -> 子=1 ascending; 12:00 = 午(idx=6) -> 7
    h1 = hourly_stars(t1, "Asia/Shanghai")
    assert h1["day_branch"] == "酉" and h1["hour_branch"] == "午"
    assert h1["zi_anchor_star"] == 1 and h1["center_star_number"] == 7

    # 2026-02-06T12:00:00+08:00 is 辛亥 day -> 亥 ∈ {寅申巳亥} after 冬至 -> 子=7 ascending
    t2 = datetime.fromisoformat("2026-02-06T12:00:00+08:00")
    h2 = hourly_stars(t2, "Asia/Shanghai")
    assert h2["day_branch"] == "亥" and h2["zi_anchor_star"] == 7
    assert h2["progression_direction"] == "ascending"
    assert h2["center_star_number"] == 4  # wrap9(7 + 6) == 4

    # Summer solstice yin_dun descending check (2026-07-15T12:00:00+08:00)
    t3 = datetime.fromisoformat("2026-07-15T12:00:00+08:00")
    d3 = daily_stars(t3, "Asia/Shanghai")
    assert d3["segment"]["dun_half"] == "yin_dun"
    assert d3["segment"]["progression_direction"] == "descending"
    h3 = hourly_stars(t3, "Asia/Shanghai")
    assert h3["dun_half"] == "yin_dun" and h3["progression_direction"] == "descending"


def test_bazhai_all_64_cells_and_minggua_and_sanyao() -> None:
    # §6 #7: Verify all 64 cells against 《八宅明镜》大游年歌
    for base, expected_map in BAZHAI_64_ORACLE.items():
        computed = sectors(base, "house", "house_sitting_trigram")
        for direction, expected_star in expected_map.items():
            assert computed[direction]["star"]["name"] == expected_star

    # MingGua 1990-05-15 male -> 坎1 East; female -> 艮8 West; raw 5 substitution
    m1990 = minggua(MingguaRequest(birth_date="1990-05-15", gender="male"))
    assert m1990["candidates"][0]["trigram"] == "坎"
    assert m1990["candidates"][0]["palace_number"] == 1
    assert m1990["candidates"][0]["group"] == "east"

    m_five_male = minggua(MingguaRequest(birth_year=1995, gender="male"))
    assert m_five_male["candidates"][0]["substitution"] is True
    assert m_five_male["candidates"][0]["trigram"] == "坤"
    m_five_female = minggua(MingguaRequest(birth_year=1999, gender="female"))
    assert m_five_female["candidates"][0]["substitution"] is True
    assert m_five_female["candidates"][0]["trigram"] == "艮"

    # 阳宅三要: East 4-house coherence (坎/离/震/巽)
    sanyao = yangzhai_sanyao(
        "坎",
        [
            Placement(
                object_id="door", purpose="door", location_direction="SE"
            ),  # 巽木
            Placement(object_id="bed", purpose="bed", location_direction="N"),  # 坎水
            Placement(
                object_id="stove", purpose="stove", location_direction="E"
            ),  # 震木
        ],
    )
    assert sanyao is not None
    assert sanyao["complete_sanyao"] is True
    assert sanyao["east_west_coherence"] == "east_four_coherent"
    assert sanyao["relations"]["door_to_master"]["younian_star"]["name"] == "生气"
    assert sanyao["relations"]["door_to_master"]["element_label"] == "主生门"

    full = bazhai(
        BazhaiRequest.model_validate(
            {
                "house": {
                    "facing_degrees": 135.0,
                },  # sitting 乾, defaults north_reference="magnetic"
                "occupants": [
                    {
                        "birth_year": 1990,
                        "gender": "male",
                    }
                ],
                "placements": [
                    {
                        "purpose": "door",
                        "location_direction": "NE",
                    },
                    {"purpose": "bed", "location_direction": "SW"},
                ],
            }
        )
    )
    assert full["house"]["north_reference"] == "magnetic"
    assert full["house"]["sitting_trigram"] == "乾"
    assert full["occupants"][0]["subject_id"] == "occupant_1"
    assert full["yangzhai_sanyao"]["east_west_coherence"] == "west_four_coherent"


def test_jinsuo_8_palaces_and_24_mountains() -> None:
    m24 = jinsuo_24_mountains()
    assert len(m24) == 24
    for m in ("子", "癸", "壬", "未", "坤", "申", "甲", "卯", "乙", "辰", "巽", "巳"):
        assert m24[m]["preferred_classification"] == "sand"
    for m in ("戌", "乾", "亥", "庚", "酉", "辛", "丑", "艮", "寅", "丙", "午", "丁"):
        assert m24[m]["preferred_classification"] == "water"

    res = jinsuo(
        JinsuoRequest.model_validate(
            {
                "features": [
                    {
                        "object_id": "east_hill",
                        "mountain": "甲",
                        "classification": "sand",
                        "classification_basis": "measured",
                        "evidence": "甲山有实山",
                    },
                    {
                        "object_id": "south_pond",
                        "mountain": "午",
                        "classification": "water",
                        "classification_basis": "user_confirmed",
                        "evidence": "午方见水池",
                    },
                ]
            }
        )
    )
    assert res["status"] == "complete"
    assert all(f["finding"] == "matches_preference" for f in res["feature_findings"])

    with pytest.raises(ValidationError):
        JinsuoRequest.model_validate(
            {
                "features": [
                    {
                        "object_id": "bad",
                        "direction": "S",
                        "mountain": "甲",
                        "classification": "sand",
                        "classification_basis": "measured",
                        "evidence": "mismatch",
                    }
                ]
            }
        )
