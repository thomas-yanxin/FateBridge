"""Palace-stem flying SiHua matrix, 来因宫, and 自化/忌冲 checks."""

import pytest

from fatebridge.core.ziwei.flying import build_flying_sihua, palace_sihua_relations
from fatebridge.services.ziwei import (
    calculate_ziwei_birth,
    calculate_ziwei_horoscope,
)
from fatebridge.utils.birth_input import create_person_info

BIRTH = dict(
    birth_year=1992,
    birth_month=8,
    birth_day=15,
    birth_hour=14,
    birth_minute=30,
    birth_timezone="Asia/Shanghai",
    use_true_solar_time=False,
    gender="男",
)
TRANSFORMATIONS = ("化禄", "化权", "化科", "化忌")
DEFAULT_ROWS = {
    "甲": "廉贞 破军 武曲 太阳",
    "乙": "天机 天梁 紫微 太阴",
    "丙": "天同 天机 文昌 廉贞",
    "丁": "太阴 天同 天机 巨门",
    "戊": "贪狼 太阴 右弼 天机",
    "己": "武曲 贪狼 天梁 文曲",
    "庚": "太阳 武曲 太阴 天同",
    "辛": "巨门 太阳 文曲 文昌",
    "壬": "天梁 紫微 左辅 武曲",
    "癸": "破军 巨门 太阴 贪狼",
}


@pytest.mark.parametrize(
    "profile,source,rule,geng,ren",
    [
        (
            "iztro_2_5_8",
            "rule_profile",
            "iztro_2_5_8",
            "太阳 武曲 太阴 天同",
            "天梁 紫微 左辅 武曲",
        ),
        (
            "quanshu_v2_excerpt",
            "rule_profile",
            "quanshu_v2_transcription",
            "太阳 武曲 太阴 天同",
            "天梁 紫微 天府 武曲",
        ),
        (
            "iztro_2_5_8",
            "naj_ming_v1",
            "naj_ming_v1",
            "太阳 武曲 天同 天相",
            "天梁 紫微 天府 武曲",
        ),
        (
            "iztro_2_5_8",
            "feixing_liang",
            "feixing_liang",
            "太阳 武曲 天府 天相",
            "天梁 紫微 左辅 武曲",
        ),
    ],
)
def test_flying_sihua_matrix_and_laiyin_palace(
    profile, source, rule, geng, ren
) -> None:
    person = create_person_info(**BIRTH)
    chart = calculate_ziwei_birth(person, rule_profile=profile, sihua_source=source)[
        "ziwei_birth"
    ]
    assert chart["year_stem"] == "壬"
    laiyin = chart["laiyin_gong"]
    assert laiyin["ganzhi"][0] == "壬"
    assert laiyin["branch"] not in ("子", "丑")
    assert laiyin["name"] == "父母宫"
    assert laiyin["ganzhi"] == "壬寅"

    flying = chart["flying_sihua"]
    assert flying["sihua_rule"] == rule
    assert flying["laiyin_gong"] == laiyin
    assert len(flying["matrix"]) == 12
    assert sum(1 for row in flying["matrix"] if row.get("is_original_palace")) == 1

    ren_sihua = dict(zip(TRANSFORMATIONS, ren.split()))
    assert chart["sihua"] == ren_sihua
    # Verify 父母宫 (壬寅) transforms match selected 壬 row
    fumu = next(row for row in flying["matrix"] if row["palace"] == "父母宫")
    for tr, star in ren_sihua.items():
        assert fumu["transforms"][tr].startswith(f"{star}->")
    assert fumu["lu_to_ji"] is not None
    assert fumu["ji_to_ji"] is not None
    assert fumu["ji_clash"] is not None


def test_reverse_groups_keep_every_occurrence_and_unlocated_assignment() -> None:
    evidence = palace_sihua_relations(
        [
            ("命宫", "甲寅", ["武曲", "廉贞", "廉贞"]),
            ("父母宫", "甲子", []),
            ("福德宫", "乙卯", ["廉贞"]),
        ],
        {
            "甲": dict(zip(TRANSFORMATIONS, ["廉贞", "破军", "武曲", "太阳"])),
            "乙": dict(zip(TRANSFORMATIONS, ["廉贞", "天梁", "紫微", "太阴"])),
        },
        sihua_rule="fixture",
    )
    groups = evidence["groups"]
    wealth = groups[0]
    assert wealth["transformation"] == "化禄"
    assert wealth["target_star"] == "廉贞"
    assert [
        (row["source_branch"], row["self_transformation"]) for row in wealth["origins"]
    ] == [
        ("寅", True),
        ("子", False),
        ("卯", True),
    ]
    missing = groups[1]
    assert (missing["transformation"], missing["target_star"]) == ("化权", "破军")
    assert missing["target_occurrences"] == []
    assert [row["self_transformation"] for row in missing["origins"]] == [None, None]


def test_inward_and_outward_self_transformations_and_ji_clash() -> None:
    palaces = [
        {"name": "命宫", "ganzhi": "甲寅", "stars_detail": [{"name": "廉贞"}]},
        {"name": "迁移宫", "ganzhi": "甲申", "stars_detail": [{"name": "太阳"}]},
        {"name": "父母宫", "ganzhi": "乙卯", "stars_detail": [{"name": "武曲"}]},
        {"name": "夫妻宫", "ganzhi": "丙辰", "stars_detail": [{"name": "天机"}]},
        {"name": "子女宫", "ganzhi": "丁巳", "stars_detail": [{"name": "太阴"}]},
        {"name": "财帛宫", "ganzhi": "戊午", "stars_detail": [{"name": "贪狼"}]},
        {"name": "疾厄宫", "ganzhi": "己未", "stars_detail": [{"name": "天同"}]},
        {"name": "仆役宫", "ganzhi": "庚酉", "stars_detail": [{"name": "巨门"}]},
        {"name": "官禄宫", "ganzhi": "辛戌", "stars_detail": [{"name": "文昌"}]},
        {"name": "田宅宫", "ganzhi": "壬亥", "stars_detail": [{"name": "天梁"}]},
        {"name": "福德宫", "ganzhi": "癸子", "stars_detail": [{"name": "破军"}]},
        {"name": "兄弟宫", "ganzhi": "甲丑", "stars_detail": [{"name": "文曲"}]},
    ]
    rules = {
        stem: dict(zip(TRANSFORMATIONS, row.split()))
        for stem, row in DEFAULT_ROWS.items()
    }
    res = build_flying_sihua(palaces, rules, year_stem="甲", sihua_rule="iztro_2_5_8")
    ming = next(r for r in res["matrix"] if r["palace"] == "命宫")
    qianyi = next(r for r in res["matrix"] if r["palace"] == "迁移宫")
    # 命宫甲干廉贞化禄在命宫 -> 离心自化; 甲太阳化忌在迁移(申) -> 冲命宫(寅)
    assert "化禄" in ming["outward_self"]
    assert ming["ji_clash"] == "迁移宫(申)冲命宫(寅)"
    # 迁移宫甲干廉贞化禄入对宫命宫 -> 命宫向心自化
    assert any("迁移宫:化禄(廉贞)" == item for item in ming["inward_self"])
    assert any("命宫:化忌(太阳)" == item for item in qianyi["inward_self"])


def test_scope_mutagens_remain_layered_by_timing_stems() -> None:
    horoscope = calculate_ziwei_horoscope(
        create_person_info(**BIRTH),
        analysis_year=2026,
        analysis_month=10,
        analysis_day=12,
        analysis_hour=10,
        analysis_timezone="Asia/Shanghai",
    )["ziwei_horoscope"]
    assert [(scope["scope"], scope["stem"]) for scope in horoscope["scopes"]] == [
        ("大限", "甲"),
        ("小限", "戊"),
        ("流年", "丙"),
        ("流月", "戊"),
        ("流日", "己"),
        ("流时", "己"),
    ]
    for scope in horoscope["scopes"]:
        assert scope["mutagen"] == dict(
            zip(TRANSFORMATIONS, DEFAULT_ROWS[scope["stem"]].split())
        )
