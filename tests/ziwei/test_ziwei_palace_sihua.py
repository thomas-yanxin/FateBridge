"""Palace-stem evidence, including the reverse grouping, shares one natal chart."""

from collections import Counter

import pytest

from fatebridge.core.contracts.output_ziwei_structure import ZiweiPalaceSihuaRelations
from fatebridge.core.ziwei.ziwei_flying import palace_sihua_relations
from fatebridge.services.metaphysics import (
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
EVIDENCE = "palace_sihua_relations"
FIELD = f"ziwei_birth.{EVIDENCE}"
TRANSFORMATIONS = ("化禄", "化权", "化科", "化忌")
# Read in 禄权科忌 order from the selected natal tables.
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
    ],
)
def test_all_palace_stem_assignments_join_the_actual_natal_occurrences(
    profile, source, rule, geng, ren
):
    person = create_person_info(**BIRTH)
    chart = calculate_ziwei_birth(person, rule_profile=profile, sihua_source=source)[
        "ziwei_birth"
    ]
    evidence = chart[EVIDENCE]
    assert evidence["policy"] == "selected_natal_table_reused_for_palace_stems"
    assert evidence["sihua_rule"] == chart["ruleset"]["sihua_rule"] == rule
    assert chart["year_stem"] == "壬"
    palaces = chart["palaces"]
    assert [
        palace["ganzhi"] for palace in palaces
    ] == "癸丑 壬寅 癸卯 甲辰 乙巳 丙午 丁未 戊申 己酉 庚戌 辛亥 壬子".split()

    rows = {**DEFAULT_ROWS, "庚": geng, "壬": ren}
    expected = {}
    for transformation_index, transformation in enumerate(TRANSFORMATIONS):
        for palace in palaces:
            stem, branch = palace["ganzhi"]
            star = rows[stem].split()[transformation_index]
            expected.setdefault((transformation, star), []).append(
                dict(
                    source_palace=palace["name"],
                    source_stem=stem,
                    source_branch=branch,
                    self_transformation=any(
                        item["name"] == star for item in palace["stars_detail"]
                    ),
                )
            )

    groups = evidence["groups"]
    assert [(g["transformation"], g["target_star"]) for g in groups] == list(expected)
    assert sum(len(g["origins"]) for g in groups) == 48
    for group in groups:
        key = group["transformation"], group["target_star"]
        assert group["origins"] == expected[key]
        assert group["target_occurrences"] == [
            dict(
                palace_name=palace["name"],
                branch=palace["ganzhi"][1],
                calculation_path=f"ziwei_birth.palaces.{i}.stars_detail.{j}",
            )
            for i, palace in enumerate(palaces)
            for j, star in enumerate(palace["stars_detail"])
            if star["name"] == key[1]
        ]

    year_sihua = dict(zip(TRANSFORMATIONS, ren.split()))
    assert chart["sihua"] == year_sihua
    assert Counter(
        (star["mutagen"], star["name"])
        for palace in palaces
        for star in palace["stars_detail"]
        if star["mutagen"] is not None
    ) == Counter(year_sihua.items())


def test_reverse_groups_keep_every_occurrence_and_unlocated_assignment():
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
    assert [target["calculation_path"] for target in wealth["target_occurrences"]] == [
        "ziwei_birth.palaces.0.stars_detail.1",
        "ziwei_birth.palaces.0.stars_detail.2",
        "ziwei_birth.palaces.2.stars_detail.0",
    ]
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
    assert ZiweiPalaceSihuaRelations.model_validate(evidence).model_dump() == evidence


def test_scope_mutagens_remain_layered_by_timing_stems():
    horoscope = calculate_ziwei_horoscope(
        create_person_info(**BIRTH),
        analysis_year=2026,
        analysis_month=10,
        analysis_day=12,
        analysis_hour=10,
        analysis_timezone="Asia/Shanghai",
    )["ziwei_horoscope"]
    assert EVIDENCE not in horoscope
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
