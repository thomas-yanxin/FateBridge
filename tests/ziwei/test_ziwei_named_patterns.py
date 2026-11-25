"""Predicate checks for the selected Ming edition's named patterns."""

import pytest

from fatebridge.core.metaphysics.seed import build_analysis_seed
from fatebridge.core.metaphysics.ziwei import (
    build_ziwei_chart,
    build_ziwei_horoscope,
    build_ziwei_rules,
)


def _seed(year, month, day, hour):
    return build_analysis_seed(
        analysis_year=year, analysis_month=month, analysis_day=day, analysis_hour=hour
    )


def _rule(chart, rule_id):
    return next(
        row for row in chart["named_patterns"]["records"] if row["id"] == rule_id
    )


def _checks(row):
    return {check["id"]: check["present"] for check in row["conditions"]}


@pytest.mark.parametrize(
    "birth,palace,status",
    [
        ((2023, 1, 31, 22), "命宫", "met"),
        ((2023, 1, 31, 6), "官禄宫", "met"),
        ((2023, 1, 22, 18), "夫妻宫", "not_met"),
    ],
)
def test_sun_in_mao_allows_only_ming_or_career(birth, palace, status):
    chart = build_ziwei_chart(_seed(*birth), "男")
    sun = next(s for s in chart["named_patterns"]["stars"] if s["star"] == "太阳")
    assert (sun["natal_branch"], sun["natal_palace_name"]) == ("卯", palace)
    assert _rule(chart, "ri_chu_fu_sang")["status"] == status
    actual_palace = next(p for p in chart["palaces"] if p["name"] == palace)
    actual_sun = next(s for s in actual_palace["stars_detail"] if s["name"] == "太阳")
    assert sun["brightness"] == actual_sun["brightness"]
    assert sun["mutagen"] == actual_sun["mutagen"]


def test_branch_requirements_and_additional_tomb_condition():
    moon_chart = build_ziwei_chart(_seed(2023, 1, 31, 6), "男")
    assert moon_chart["ming_gong"]["branch"] == "亥"
    assert _rule(moon_chart, "yue_luo_hai_gong")["status"] == "met"

    wu_in_mao = build_ziwei_chart(_seed(2023, 2, 2, 22), "男")
    assert wu_in_mao["ming_gong"]["branch"] == "卯"
    assert _rule(wu_in_mao, "wu_qu_shou_yuan")["status"] == "met"
    wu_elsewhere = build_ziwei_chart(_seed(2023, 1, 23, 4), "男")
    rule = _rule(wu_elsewhere, "wu_qu_shou_yuan")
    assert rule["status"] == "not_met"
    assert _checks(rule) == {"wu_qu_in_ming": True, "wu_qu_in_other_branch": True}

    property_chart = build_ziwei_chart(_seed(2023, 1, 27, 8), "男")
    rule = _rule(property_chart, "ri_yue_zhao_bi")
    assert rule["status"] == "met"
    assert rule["conditions"] == [
        {"id": "sun_moon_in_property", "role": "required", "present": True},
        {"id": "property_in_tomb_branch", "role": "additional", "present": True},
    ]


def test_jun_chen_qing_hui_requires_same_palace_not_opposition():
    for birth, branches, status in [
        ((2023, 5, 26, 20), ("未", "未", "未"), "met"),
        ((2023, 1, 24, 20), ("辰", "辰", "戌"), "not_met"),
    ]:
        chart = build_ziwei_chart(_seed(*birth), "男")
        positions = {
            s["star"]: s["natal_branch"] for s in chart["named_patterns"]["stars"]
        }
        assert chart["ming_gong"]["branch"] == branches[0]
        assert tuple(positions[star] for star in ("紫微", "左辅", "右弼")) == branches
        assert {"天相", "武曲", "太阴"} <= positions.keys()
        rule = _rule(chart, "jun_chen_qing_hui")
        assert rule["status"] == status
        assert rule["conditions"][1] == {
            "id": "meeting_xiang_wu_yin",
            "role": "additional",
            "present": None,
        }


@pytest.mark.parametrize(
    "birth,brightness,status,in_xian",
    [
        ((2019, 2, 6, 14), {"庙"}, "met", False),
        ((2024, 2, 12, 22), {"平", "陷"}, "not_met", True),
        ((2025, 1, 30, 8), {"利", "庙"}, "not_met", False),
    ],
)
def test_quan_lu_requires_both_miao_or_wang(birth, brightness, status, in_xian):
    chart = build_ziwei_chart(_seed(*birth), "男")
    transformed = [
        s for s in chart["named_patterns"]["stars"] if s["mutagen"] in {"化禄", "化权"}
    ]
    assert {s["mutagen"] for s in transformed} == {"化禄", "化权"}
    assert {s["natal_branch"] for s in transformed} == {chart["ming_gong"]["branch"]}
    assert {s["brightness"] for s in transformed} == brightness
    rule = _rule(chart, "quan_lu_sheng_feng")
    assert rule["status"] == status
    assert _checks(rule) == {
        "quan_lu_in_ming": True,
        "quan_lu_in_miao_wang": status == "met",
        "quan_or_lu_in_xian": in_xian,
    }


def test_sun_moon_flanks_do_not_discharge_unknown_qualifications():
    chart = build_ziwei_chart(_seed(2023, 1, 22, 14), "男")
    row = _rule(chart, "ri_yue_jia_ming")
    assert row["status"] == "source_undetermined"
    assert _checks(row) == {
        "sun_moon_flank_ming": True,
        "auspicious_star_in_ming": None,
        "void_in_ming": None,
    }
    other = build_ziwei_chart(_seed(2023, 1, 22, 0), "男")
    assert _rule(other, "ri_yue_jia_ming")["status"] == "not_met"


@pytest.mark.parametrize(
    "birth,lunar_month,hour_branch,ming,positions,matched",
    [
        ((1990, 9, 28, 4), 8, "寅", "未", ("申", "午"), True),
        ((1990, 11, 26, 8), 10, "辰", "未", ("午", "申"), True),
        ((1990, 9, 28, 6), 8, "卯", "午", ("未", "未"), False),
        ((1990, 9, 28, 8), 8, "辰", "巳", ("午", "申"), False),
    ],
)
def test_chang_qu_flanking_is_geometry_only(
    birth, lunar_month, hour_branch, ming, positions, matched
):
    chart = build_ziwei_chart(_seed(*birth), "男")
    evidence = chart["named_patterns"]
    assert (chart["lunar_date"]["month"], chart["hour_branch"]) == (
        lunar_month,
        hour_branch,
    )
    actual = {s["star"]: s["natal_branch"] for s in evidence["stars"]}
    assert (actual["文昌"], actual["文曲"]) == positions
    assert evidence["chang_qu_flank"]["ming_branch"] == ming
    assert evidence["chang_qu_flank"]["matched"] is matched
    if matched:
        assert evidence["chang_qu_flank"]["adjacent_branches"] == ["午", "申"]
    assert "wen_xing_an_gong" not in {r["id"] for r in evidence["records"]}
    assert len(chart["ming_structural_conditions"]["records"]) == 5


def test_limit_evidence_uses_target_lunar_year_and_existing_indices():
    born = _seed(1990, 9, 28, 4)
    chart = build_ziwei_chart(born, "男")
    for day, year, branch in [(9, 2023, "卯"), (10, 2024, "辰")]:
        result = build_ziwei_horoscope(
            chart=chart,
            gender="男",
            target_seed=_seed(2024, 2, day, 12),
            birth_seed=born,
        )
        evidence = result["named_pattern_limit_evidence"]
        assert (evidence["target_lunar_year"], evidence["annual_branch"]) == (
            year,
            branch,
        )
        assert evidence["records"][0]["status"] == "source_undetermined"
        actual_indices = {scope["scope"]: scope["branch"] for scope in result["scopes"]}
        for row in evidence["limit_indices"]:
            limit_branch = actual_indices[row["scope"]]
            assert row["branch"] == limit_branch
            assert row["natal_lucun_same_palace"] is (
                limit_branch == evidence["natal_lucun_branch"]
            )
            assert row["natal_tianma_same_palace"] is (
                limit_branch == evidence["natal_tianma_branch"]
            )

    same_palace = build_ziwei_horoscope(
        chart=chart,
        gender="男",
        target_seed=_seed(2030, 6, 1, 12),
        birth_seed=born,
    )["named_pattern_limit_evidence"]
    assert same_palace["limit_indices"][1] == {
        "scope": "小限",
        "branch": "申",
        "natal_lucun_same_palace": True,
        "natal_tianma_same_palace": True,
    }
    assert same_palace["records"][0]["status"] == "source_undetermined"

    unknown = build_ziwei_horoscope(
        chart=build_ziwei_chart(born, "未知"),
        gender="未知",
        target_seed=_seed(2024, 2, 10, 12),
        birth_seed=born,
    )["named_pattern_limit_evidence"]
    assert unknown["annual_branch"] == "辰"
    assert all(
        row["branch"] is None and row["natal_lucun_same_palace"] is None
        for row in unknown["limit_indices"]
    )


def test_catalogue_keeps_ming_facsimiles_and_transcript_separate():
    catalogue = build_ziwei_rules()["rule_catalogue"]["named_patterns"]
    assert [
        (source["url"].rsplit("/", 1)[-1], source["kind"])
        for source in catalogue["sources"]
    ] == [
        ("4468520", "facsimile"),
        ("4469314", "facsimile"),
        ("index.php?oldid=7913704", "transcript"),
    ]
    definitions = {row["id"]: row for row in catalogue["rules"]}
    assert definitions["yue_luo_hai_gong"]["aliases"] == ["月朗天门"]
    assert definitions["ri_yue_zhao_bi"]["frame"] == 71
    assert definitions["jun_chen_qing_hui"]["frame"] == 72
    assert definitions["feng_yun_ji_hui"]["frame"] == 73
    assert definitions["wen_xing_an_gong"]["scope"] == "catalogue_only"
