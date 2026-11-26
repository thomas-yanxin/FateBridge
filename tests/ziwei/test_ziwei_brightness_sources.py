"""Brightness table verification against iztro 2.5.8 and classical sources."""

import pytest

from fatebridge.core.ziwei.tables import lookup_star_brightness
from fatebridge.services.ziwei import (
    calculate_ziwei_birth,
    calculate_ziwei_horoscope,
    calculate_ziwei_rules,
)
from fatebridge.utils.birth_input import create_person_info

BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
QS = "ziwei_doushu_qs"
CLASSICAL = "quanshu_v2_selected_table"
REVISION = "a857a4fc2c2950cf27c8e4818c77a7090ad1c434"
BIRTH = dict(
    birth_year=1992,
    birth_month=8,
    birth_day=15,
    birth_hour=14,
    birth_minute=30,
    birth_timezone="Asia/Shanghai",
    gender="男",
    use_true_solar_time=False,
)
TARGET = dict(analysis_year=2026, analysis_month=10, analysis_day=12, analysis_hour=10)


def test_iztro_and_classical_brightness_labels() -> None:
    # Bug 1.1 fixes: 太阳@酉="平", 太阴@酉="旺", 七杀@酉="旺"
    assert lookup_star_brightness("太阳", "酉") == "平"
    assert lookup_star_brightness("太阴", "酉") == "旺"
    assert lookup_star_brightness("七杀", "酉") == "旺"
    assert lookup_star_brightness("左辅", "子") is None

    assert lookup_star_brightness("太阴", "寅", brightness_source=CLASSICAL) == "旺"
    assert lookup_star_brightness("太阳", "酉", brightness_source=CLASSICAL) == "平"
    assert lookup_star_brightness("禄存", "子", brightness_source=CLASSICAL) == "庙"
    assert lookup_star_brightness("禄存", "丑", brightness_source=CLASSICAL) is None
    assert lookup_star_brightness("左辅", "子", brightness_source=CLASSICAL) is None
    assert lookup_star_brightness("天刑", "子", brightness_source=CLASSICAL) is None


@pytest.mark.parametrize(
    "variant,star,expected",
    [
        ("qs", "太阳", "陷不旺庙旺旺旺得得平不陷"),
        ("qs", "左辅", "旺庙庙陷庙平旺庙平陷庙不"),
        ("qs", "天钺", "··旺··旺·旺庙庙··"),
        ("xd1", "太阴", "庙庙不陷陷陷陷平利旺旺庙"),
        ("zz", "太阴", "庙庙闲陷闲陷陷平平旺旺庙"),
        ("xd2", "紫微", "闲庙庙旺闲旺庙庙旺平陷旺"),
        ("xd2", "天钺", "庙旺庙庙庙庙庙旺庙庙庙庙"),
    ],
)
def test_pinned_software_labels(variant, star, expected) -> None:
    source = f"ziwei_doushu_{variant}"
    assert [
        lookup_star_brightness(star, branch, brightness_source=source)
        for branch in BRANCHES
    ] == [None if grade == "·" else grade for grade in expected]


def test_source_specific_aliases_and_blanks_do_not_fall_back() -> None:
    for star in ("截空", "副截", "截路", "空亡"):
        assert lookup_star_brightness(star, "子", brightness_source=QS) == "陷"
        assert lookup_star_brightness(star, "亥", brightness_source=QS) is None
    assert lookup_star_brightness("旬空", "酉", brightness_source=QS) == "庙"
    assert lookup_star_brightness("副旬", "酉", brightness_source=QS) == "庙"
    assert lookup_star_brightness("天空", "子", brightness_source=QS) == "陷"
    assert lookup_star_brightness("地空", "子", brightness_source=QS) == "平"
    assert lookup_star_brightness("月德", "子", brightness_source=QS) is None
    assert lookup_star_brightness("禄存", "丑", brightness_source=QS) is None
    assert lookup_star_brightness("擎羊", "卯", brightness_source=QS) == "陷"
    assert lookup_star_brightness("qingyangMin", "卯") == "陷"


def _remove_brightness(value):
    if isinstance(value, dict):
        return {
            k: _remove_brightness(v)
            for k, v in value.items()
            if k
            not in {
                "brightness",
                "brightness_source",
                "brightness_rule",
                "brightness_table",
                "natal_brightness",
                "natal_star_brightness",
            }
        }
    if isinstance(value, list):
        return [_remove_brightness(item) for item in value]
    return value


@pytest.mark.parametrize("profile", ["iztro_2_5_8", "quanshu_v2_excerpt"])
def test_birth_and_horoscope_change_only_brightness_facts(profile) -> None:
    person = create_person_info(**BIRTH)
    omitted = calculate_ziwei_birth(person, rule_profile=profile)["ziwei_birth"]
    inherited = calculate_ziwei_birth(
        person, rule_profile=profile, brightness_source="rule_profile"
    )["ziwei_birth"]
    selected = calculate_ziwei_birth(
        person, rule_profile=profile, brightness_source=QS
    )["ziwei_birth"]
    assert inherited == omitted
    assert "brightness_table" not in inherited["ruleset"]
    assert _remove_brightness(inherited) == _remove_brightness(selected)
    assert selected != inherited
    source = selected["ruleset"]["brightness_table"]
    assert (
        source
        == calculate_ziwei_rules(brightness_source=QS)["rule_catalogue"]["ruleset"][
            "brightness_table"
        ]
    )
    assert source["id"] == QS
    assert source["source_kind"] == "software_compatibility"
    assert source["version"] == REVISION
    assert REVISION in source["source_url"]
    assert source["branch_order"] == list(BRANCHES)
    assert source["grade_scale"] == list("庙旺得利平不陷")
    stars = {s["name"]: s for p in selected["palaces"] for s in p["stars_detail"]}
    assert all(s["brightness_source"] == QS for s in stars.values())
    assert stars["左辅"]["brightness"] == "庙"
    assert stars["月德"]["brightness"] is None

    default_timing = calculate_ziwei_horoscope(person, **TARGET, rule_profile=profile)[
        "ziwei_horoscope"
    ]
    selected_timing = calculate_ziwei_horoscope(
        person, **TARGET, rule_profile=profile, brightness_source=QS
    )["ziwei_horoscope"]
    assert _remove_brightness(default_timing) == _remove_brightness(selected_timing)
    assert selected_timing["ruleset"]["brightness_table"] == source
    for scope in selected_timing["scopes"]:
        for link in scope["mutagen_natal_links"]:
            expected_b = stars[link["star"]]["brightness"]
            if expected_b is None:
                assert "natal_star_brightness" not in link
            else:
                assert link["natal_star_brightness"] == expected_b


def test_brightness_selector_is_independent_of_the_base_ruleset() -> None:
    rules = calculate_ziwei_rules(
        rule_profile="quanshu_v2_excerpt", brightness_source="iztro_2_5_8"
    )["rule_catalogue"]["ruleset"]
    assert rules["id"] == "quanshu_v2_excerpt"
    assert rules["brightness_rule"] == "iztro_2_5_8"
    assert rules["sihua_rule"] == "quanshu_v2_transcription"
    assert rules["brightness_table"]["branch_order"] == list("寅卯辰巳午未申酉戌亥子丑")
