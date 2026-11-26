"""Natal and target leap-month policy consistency checks."""

from datetime import date, datetime

import pytest

from fatebridge.core.almanac import localize_datetime
from fatebridge.core.metaphysics.common import MetaphysicsSeed
from fatebridge.core.ziwei.chart import build_ziwei_chart
from fatebridge.services.ziwei import (
    calculate_ziwei_birth,
    calculate_ziwei_horoscope,
)
from fatebridge.utils.birth_input import create_person_info
from fatebridge.utils.civil_time import NominalClockLabel


def synthetic_seed(
    year: int, month: int = 1, day: int = 1, hour: str = "子", leap: bool = False
) -> MetaphysicsSeed:
    return MetaphysicsSeed(
        input_datetime=localize_datetime(datetime(year, 1, 1), "Asia/Shanghai"),
        clock=NominalClockLabel.from_local_datetime(datetime(year, 1, 1)),
        timezone="Asia/Shanghai",
        longitude=None,
        applied_true_solar=False,
        total_correction_minutes=0,
        pillars={"day": ("甲", "子"), "hour": ("甲", hour)},
        calendar_context={
            "lunar_calendar": {
                "year": year,
                "month": month,
                "day": day,
                "is_leap_month": leap,
            }
        },
        input_offset_visible=False,
    )


POLICIES = ("split_at_day_15", "all_current_month", "all_next_month")


def _person(civil: str):
    label = date.fromisoformat(civil)
    return create_person_info(
        birth_year=label.year,
        birth_month=label.month,
        birth_day=label.day,
        birth_hour=12,
        birth_minute=0,
        birth_timezone="Asia/Shanghai",
        use_true_solar_time=False,
        gender="男",
    )


@pytest.mark.parametrize(
    "civil,lunar,month_ordinals",
    [
        ("2023-03-06", (2023, 2, 15, False), (2, 2, 2)),
        ("2023-04-05", (2023, 2, 15, True), (2, 2, 3)),
        ("2023-04-06", (2023, 2, 16, True), (3, 2, 3)),
        ("2023-04-19", (2023, 2, 29, True), (3, 2, 3)),
        ("2023-04-20", (2023, 3, 1, False), (3, 3, 3)),
        ("2017-08-21", (2017, 6, 30, True), (7, 6, 7)),
    ],
)
def test_explicit_policies_change_only_the_placement_month_input(
    civil, lunar, month_ordinals
) -> None:
    person = _person(civil)
    expected_date = dict(zip(("year", "month", "day", "is_leap_month"), lunar))
    charts = [
        calculate_ziwei_birth(person, natal_leap_month_policy=policy)["ziwei_birth"]
        for policy in POLICIES
    ]
    for chart, policy, month in zip(charts, POLICIES, month_ordinals):
        assert chart["ruleset"]["leap_month_rule"] == policy
        assert chart["calendar_rules"]["effective_birth_month"] == month
        assert chart["lunar_date"] == expected_date
        assert chart["calendar_basis"] == charts[0]["calendar_basis"]
        assert chart["ming_gong"]["branch"] == "申酉戌亥子丑寅卯辰巳午未"[month - 1]
        assert chart["shen_gong"]["branch"] == chart["ming_gong"]["branch"]
        zuofu = next(
            p
            for p in chart["palaces"]
            if any(star["name"] == "左辅" for star in p["stars_detail"])
        )
        assert zuofu["ganzhi"][1] == "辰巳午未申酉戌亥子丑寅卯"[month - 1]
    for chart, month in zip(charts, month_ordinals):
        same_month_chart = charts[month_ordinals.index(month)]
        assert chart["palaces"] == same_month_chart["palaces"]


@pytest.mark.parametrize(
    "profile,default,month",
    [
        ("iztro_2_5_8", "split_at_day_15", 2),
        ("quanshu_v2_excerpt", "all_next_month", 3),
    ],
)
def test_omission_matches_each_profiles_original_rule(profile, default, month) -> None:
    person = _person("2023-04-05")
    chart = calculate_ziwei_birth(person, rule_profile=profile)["ziwei_birth"]
    explicit = calculate_ziwei_birth(
        person, rule_profile=profile, natal_leap_month_policy=default
    )["ziwei_birth"]
    assert chart == explicit
    assert chart["calendar_rules"]["effective_birth_month"] == month
    overridden = calculate_ziwei_birth(
        person, rule_profile=profile, natal_leap_month_policy="all_current_month"
    )["ziwei_birth"]
    assert overridden["ruleset"]["id"] == chart["ruleset"]["id"]
    assert "闰月全作下月" not in overridden["ruleset"]["overrides"]


def test_month_ordinal_thirteen_preserves_year_and_calendar_new_year_still_changes_it() -> (
    None
):
    leap_twelfth = build_ziwei_chart(
        synthetic_seed(2023, month=12, day=30, leap=True),
        "男",
        natal_leap_month_policy="all_next_month",
    )
    assert leap_twelfth["lunar_date"] == dict(
        year=2023, month=12, day=30, is_leap_month=True
    )
    assert leap_twelfth["year_stem"] == "癸"
    assert leap_twelfth["calendar_rules"]["effective_birth_month"] == 13
    assert leap_twelfth["ming_gong"]["ganzhi"] == "甲寅"


@pytest.mark.parametrize(
    "policy,expected_stems",
    [
        ("split_at_day_15", ("癸", "甲")),
        ("all_current_month", ("癸", "癸")),
        ("all_next_month", ("甲", "甲")),
    ],
)
def test_target_liuyue_respects_selected_leap_month_policy(
    policy, expected_stems
) -> None:
    # Bug 1.4 fix: 2025-08-08 is 闰六月十五, 2025-08-09 is 闰六月十六.
    person = _person("2023-04-06")
    for target_day, expected_stem in zip((8, 9), expected_stems):
        timing = calculate_ziwei_horoscope(
            person,
            natal_leap_month_policy=policy,
            analysis_year=2025,
            analysis_month=8,
            analysis_day=target_day,
            analysis_hour=12,
        )["ziwei_horoscope"]
        assert timing["ruleset"]["target_leap_month_rule"] == policy
        lunar_month = next(s for s in timing["scopes"] if s["scope"] == "流月")
        assert lunar_month["stem"] == expected_stem
        assert timing["nominal_age"] == 3
