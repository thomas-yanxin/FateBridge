"""Natal month placement is independent of date conversion and target month rules."""

from datetime import date, datetime

import pytest

from fatebridge.core.almanac import localize_datetime
from fatebridge.core.metaphysics.common import MetaphysicsSeed
from fatebridge.core.metaphysics.ziwei import build_ziwei_chart
from fatebridge.services.metaphysics import (
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
        # HKO UTC+08 date labels. The readings use the same physical moment.
        ("2023-03-06", (2023, 2, 15, False), (2, 2, 2)),
        ("2023-04-05", (2023, 2, 15, True), (2, 2, 3)),
        ("2023-04-06", (2023, 2, 16, True), (3, 2, 3)),
        ("2023-04-19", (2023, 2, 29, True), (3, 2, 3)),
        ("2023-04-20", (2023, 3, 1, False), (3, 3, 3)),
        # In 2017 the two adjacent ordinary months have only 29 days each.
        ("2017-08-21", (2017, 6, 30, True), (7, 6, 7)),
    ],
)
def test_explicit_policies_change_only_the_placement_month_input(
    civil, lunar, month_ordinals
):
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
        assert chart["year_stem"] == ("癸" if lunar[0] == 2023 else "丁")
        assert chart["calendar_basis"] == charts[0]["calendar_basis"]
        trace = {step["rule_id"]: step for step in chart["rule_trace"]}
        assert trace["ziwei_tianfu_placement"]["inputs"]["lunar_day"] == lunar[2]
        source = trace["wuhu_dun_nayin_ju"]["outputs"]["source_comparison"]
        assert source["source_frames"] == [73, 74]
        assert source["matches_source_chain"] == (month == lunar[1] + int(lunar[3]))
        assert source["compared_rules_applied"] is False
        # Noon gives the same 命/身 branch. 左辅 starts at 辰 for month 1.
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
def test_omission_matches_each_profiles_original_rule(profile, default, month):
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
    assert overridden["ruleset"]["version"] == chart["ruleset"]["version"]
    assert "本命身命闰月全作下月" not in overridden["ruleset"]["overrides"]


def test_month_ordinal_thirteen_preserves_year_and_calendar_new_year_still_changes_it():
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
    for civil, year, stem, month in [
        ("2024-02-09", 2023, "癸", 12),
        ("2024-02-10", 2024, "甲", 1),
    ]:
        chart = calculate_ziwei_birth(
            _person(civil), natal_leap_month_policy="all_next_month"
        )["ziwei_birth"]
        assert chart["lunar_date"]["year"] == year
        assert chart["year_stem"] == stem
        assert chart["calendar_rules"]["effective_birth_month"] == month


@pytest.mark.parametrize("target_day,month_stem", [(8, "癸"), (9, "甲")])
def test_timing_uses_the_natal_choice_and_target_keeps_day_15_split(
    target_day, month_stem
):
    person = _person("2023-04-06")
    for policy, doujun in zip(POLICIES, ("酉", "戌", "酉")):
        birth = calculate_ziwei_birth(person, natal_leap_month_policy=policy)[
            "ziwei_birth"
        ]
        timing = calculate_ziwei_horoscope(
            person,
            natal_leap_month_policy=policy,
            analysis_year=2025,
            analysis_month=8,
            analysis_day=target_day,
            analysis_hour=12,
        )["ziwei_horoscope"]
        natal = timing["natal_prerequisites"]
        assert timing["ruleset"]["leap_month_rule"] == policy
        assert natal["ruleset"]["leap_month_rule"] == policy
        assert natal["lunar_date"] == birth["lunar_date"]
        assert natal["rule_trace"] == birth["rule_trace"][:3]
        assert timing["source_comparison"]["doujun"]["actual_branch"] == doujun
        lunar_month = next(s for s in timing["scopes"] if s["scope"] == "流月")
        assert lunar_month["stem"] == month_stem
        assert timing["nominal_age"] == 3
