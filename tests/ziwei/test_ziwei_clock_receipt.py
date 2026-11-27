"""HKO civil-date anchors, day_divide rollover, and nominal_age alignment."""

from datetime import datetime

import pytest

from fatebridge.services.ziwei import (
    calculate_ziwei_birth,
    calculate_ziwei_horoscope,
)
from fatebridge.utils.birth_input import create_person_info

CNY_EVE = dict(year=2023, month=12, day=30, is_leap_month=False)
CNY = dict(year=2024, month=1, day=1, is_leap_month=False)
EVE_BIRTH = dict(
    birth_year=2024,
    birth_month=2,
    birth_day=9,
    birth_hour=23,
    birth_minute=30,
    birth_timezone="Asia/Shanghai",
    gender="男",
    use_true_solar_time=False,
)
EVE_TARGET = dict(
    analysis_year=2024,
    analysis_month=2,
    analysis_day=9,
    analysis_hour=23,
    analysis_minute=30,
    analysis_timezone="Asia/Shanghai",
)


@pytest.mark.parametrize(
    "policy,placement,lunar,year_stem,ziwei_branch,boundary",
    [
        ("current", "2024-02-09 23:30:00", CNY_EVE, "癸", "亥", "00:00"),
        ("forward", "2024-02-10 00:00:00", CNY, "甲", "酉", "23:00"),
    ],
)
def test_new_year_eve_chart_and_flows_share_the_placement_date(
    policy, placement, lunar, year_stem, ziwei_branch, boundary
) -> None:
    person = create_person_info(**EVE_BIRTH)
    birth = calculate_ziwei_birth(person, day_divide=policy)
    chart = birth["ziwei_birth"]
    horoscope = calculate_ziwei_horoscope(person, **EVE_TARGET, day_divide=policy)[
        "ziwei_horoscope"
    ]
    clocks = horoscope["calendar_basis"]
    assert clocks["birth"] == chart["calendar_basis"]
    assert chart["lunar_date"] == lunar
    assert chart["year_stem"] == year_stem
    assert chart["hour_branch"] == "子"
    assert "rule_trace" not in chart
    for receipt in clocks["birth"], clocks["target"]:
        assert receipt["day_divide"] == policy
        assert receipt["placement_clock"] == "civil"
        assert receipt["placement_datetime"] == placement
        assert receipt["civil_datetime"] == "2024-02-09 23:30:00"
        assert receipt["civil_instant_utc"] == "2024-02-09T15:30:00+00:00"
        assert receipt["apparent_solar_datetime"] is None
        assert receipt["placement_lunar_date"] == lunar
        assert (
            receipt["civil_date_lunar_date"]
            == receipt["reference_lunar_date"]
            == CNY_EVE
        )
        assert receipt["day_boundary"] == f"{boundary}_in_selected_clock"
        assert receipt["late_zi_rollover_applied"] is (policy == "forward")
        assert receipt["date_shift_days"] == (policy == "forward")

    lunar_display = birth["analysis_context"]["lunar_display"]
    assert lunar_display.endswith("初一" if policy == "forward" else "三十")
    assert horoscope["scopes"][2]["stem"] == year_stem
    age = horoscope["nominal_age_calendar"]
    assert age["birth_placement_lunar_year"] == lunar["year"]
    assert age["target_lunar_year"] == lunar["year"]
    assert horoscope["nominal_age"] == age["nominal_age"] == 1

    # Query 10.5h later on CNY Day 1: forward=age 1, current=age 2 (Bug 1.2 fix!)
    new_year = {
        **EVE_TARGET,
        "analysis_day": 10,
        "analysis_hour": 10,
        "analysis_minute": 0,
    }
    after = calculate_ziwei_horoscope(person, **new_year, day_divide=policy)[
        "ziwei_horoscope"
    ]
    assert after["nominal_age"] == (1 if policy == "forward" else 2)
    assert after["nominal_age_calendar"]["target_lunar_date"] == CNY


def test_forward_day_divide_rolls_target_nominal_age_and_xiaoxian_together() -> None:
    person = create_person_info(
        birth_year=1990,
        birth_month=5,
        birth_day=15,
        birth_hour=12,
        birth_minute=0,
        birth_timezone="Asia/Shanghai",
        gender="男",
        use_true_solar_time=False,
    )
    h = calculate_ziwei_horoscope(
        person,
        analysis_year=2024,
        analysis_month=2,
        analysis_day=9,
        analysis_hour=23,
        analysis_minute=30,
        analysis_timezone="Asia/Shanghai",
        day_divide="forward",
    )["ziwei_horoscope"]
    liunian = next(s for s in h["scopes"] if s["scope"] == "流年")
    assert liunian["palace_ganzhi"].endswith("辰")
    assert liunian["stem"] == "甲"
    assert h["nominal_age"] == 35
    # 小限 at age 35 for 午年男 (start 辰 + 34 % 12 = +10 -> 寅)
    xiaoxian = next(s for s in h["scopes"] if s["scope"] == "小限")
    assert xiaoxian["branch"] == "寅"


def test_supplied_seconds_do_not_create_hypothetical_minute_endpoints() -> None:
    person = create_person_info(
        **{**EVE_BIRTH, "birth_hour": 22, "birth_minute": 59, "birth_second": 30}
    )
    basis = calculate_ziwei_birth(person)["ziwei_birth"]["calendar_basis"]
    assert basis["placement_datetime"] == "2024-02-09 22:59:30"
    sensitivity = basis["time_input"]["minute_sensitivity"]
    assert sensitivity["birth_seconds_supplied"] is True
    assert sensitivity["base_second"] == 30
    assert "endpoint_seconds" not in sensitivity
    assert "crosses_hour_branch" not in sensitivity


def test_unknown_gender_still_reports_a_knowable_pre_decade_status() -> None:
    person = create_person_info(**{**EVE_BIRTH, "gender": "未知"})
    h = calculate_ziwei_horoscope(person, **EVE_TARGET)["ziwei_horoscope"]
    assert h["nominal_age"] == 1
    decade, small_limit, *independent = h["scopes"]
    assert decade["status"] == "not_started"
    assert decade["branch"] is decade["mutagen"] is None
    assert small_limit["status"] == "unavailable"
    assert all(len(scope["palace_map"]) == 12 for scope in independent)


@pytest.mark.parametrize(
    "solar_day,before,after,effective_months",
    [
        (5, (2, 15, True), (2, 16, True), (2, 3)),
        (19, (2, 29, True), (3, 1, False), (3, 3)),
    ],
)
def test_rollover_resolves_the_actual_lunar_month_and_leap_day(
    solar_day, before, after, effective_months
) -> None:
    person = create_person_info(
        **{**EVE_BIRTH, "birth_year": 2023, "birth_month": 4, "birth_day": solar_day}
    )
    for policy, (month, day, leap), effective in zip(
        ("current", "forward"), (before, after), effective_months
    ):
        chart = calculate_ziwei_birth(person, day_divide=policy)["ziwei_birth"]
        expected = dict(year=2023, month=month, day=day, is_leap_month=leap)
        assert (
            chart["lunar_date"]
            == chart["calendar_basis"]["placement_lunar_date"]
            == expected
        )
        assert chart["calendar_rules"]["effective_birth_month"] == effective


@pytest.mark.parametrize("policy", ["current", "forward"])
@pytest.mark.parametrize(
    "civil_day,hour,minute,longitude,solar_day",
    [(9, 23, 55, 130.0, 10), (10, 0, 10, 118.0, 9)],
)
def test_solar_date_crossing_and_late_zi_are_distinct(
    policy, civil_day, hour, minute, longitude, solar_day
) -> None:
    person = create_person_info(
        **{
            **EVE_BIRTH,
            "birth_day": civil_day,
            "birth_hour": hour,
            "birth_minute": minute,
            "birth_longitude": longitude,
            "use_true_solar_time": True,
        }
    )
    chart = calculate_ziwei_birth(person, day_divide=policy)["ziwei_birth"]
    receipt = chart["calendar_basis"]
    assert receipt["placement_clock"] == "apparent_solar"
    assert (
        receipt["time_input"]["minute_sensitivity"]["clock_stage"]
        == "after_normalization_before_day_divide"
    )
    corrected = datetime.fromisoformat(receipt["apparent_solar_datetime"])
    assert corrected.day == solar_day
    assert receipt["civil_datetime"].startswith(f"2024-02-{civil_day:02d} ")
    rolled = solar_day == 9 and policy == "forward"
    assert receipt["late_zi_rollover_applied"] is rolled
    assert receipt["placement_datetime"] == (
        "2024-02-10 00:00:00"
        if rolled
        else corrected.isoformat(sep=" ", timespec="seconds")
    )
    assert receipt["date_shift_days"] == solar_day + int(rolled) - civil_day
    assert receipt["civil_date_lunar_date"] == (CNY if civil_day == 10 else CNY_EVE)
    assert (
        chart["lunar_date"]
        == receipt["placement_lunar_date"]
        == (CNY if solar_day == 10 or rolled else CNY_EVE)
    )


def test_target_civil_year_is_distinct_from_birth_zone_age_clock() -> None:
    birth = {**EVE_BIRTH, "birth_hour": 22}
    target = {
        **EVE_TARGET,
        "analysis_day": 10,
        "analysis_hour": 0,
        "analysis_timezone": "+09:00",
    }
    for policy, expected_age in (("current", 1), ("forward", 2)):
        h = calculate_ziwei_horoscope(
            create_person_info(**birth), **target, day_divide=policy
        )["ziwei_horoscope"]
        receipt = h["calendar_basis"]["target"]
        assert (
            receipt["civil_date_lunar_date"] == receipt["placement_lunar_date"] == CNY
        )
        assert receipt["reference_lunar_date"] == CNY_EVE
        assert h["scopes"][2]["stem"] == "甲"
        age = h["nominal_age_calendar"]
        assert age["target_civil_lunar_year"] == 2024
        assert age["target_datetime"] == "2024-02-09 23:30:00+08:00"
        assert age["timezone"] == birth["birth_timezone"]
        assert h["nominal_age"] == expected_age
