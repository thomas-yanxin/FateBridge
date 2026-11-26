"""BaZi analysis dates and natal chart pillars remain independent on each surface."""

from datetime import datetime

import pytest

from fatebridge.core.calendar import BaZiCalendar
from tests.support.transports import SPECS, business, rest, surface_calls

STAMP = "2025-02-04T04:37:49.123456Z"


@pytest.mark.parametrize(
    "analysis_day,as_of,expected_date,expected_pillars,lunar_date",
    [
        (3, STAMP, "2024-02-03", ["癸卯", "乙丑", "丁酉", "庚子"], (2023, 12, 24)),
        (4, STAMP, "2024-02-04", ["癸卯", "乙丑", "戊戌", "壬子"], (2023, 12, 25)),
        (10, STAMP, "2024-02-10", ["甲辰", "丙寅", "甲辰", "甲子"], (2024, 1, 1)),
        (
            None,
            "2024-02-09T15:59:00Z",
            "2024-02-09",
            ["甲辰", "丙寅", "癸卯", "壬子"],
            (2023, 12, 30),
        ),
        (
            None,
            "2024-02-09T16:00:00Z",
            "2024-02-10",
            ["甲辰", "丙寅", "甲辰", "甲子"],
            (2024, 1, 1),
        ),
    ],
)
def test_natal_and_analysis_calendars_own_their_pillars_on_three_protocols(
    analysis_day, as_of, expected_date, expected_pillars, lunar_date, surface_calls
):
    birth = {
        "birth_year": 2000,
        "birth_month": 5,
        "birth_day": 1,
        "birth_hour": 9,
        "birth_minute": 0,
        "birth_place": "上海",
        "birth_timezone": "Asia/Shanghai",
        "use_true_solar_time": False,
        "gender": "男",
    }
    if analysis_day is not None:
        birth.update(analysis_year=2024, analysis_month=2, analysis_day=analysis_day)
    fields = [
        "bazi_birth.four_pillars",
        "bazi_birth.calendar_context.lunar_calendar",
        "bazi_birth.analysis_date",
        "bazi_birth.analysis_calendar_context",
        "bazi_birth.timing_overview.liunian.pillar",
        "bazi_birth.timing_overview.liuyue.pillar",
    ]
    controls = {
        "as_of": as_of,
        "detail": "audit",
        "fields": fields,
    }
    http, protocol, code, cli = surface_calls(
        SPECS["bazi_birth_chart"], birth, projection=controls
    )
    assert http.status_code == 200 and code == 0 and not protocol.is_error
    assert (
        business(http.json()) == business(protocol.structured_content) == business(cli)
    )
    natal = http.json()["bazi_birth"]
    assert [p["stem"] + p["branch"] for p in natal["four_pillars"].values()] == [
        "庚辰",
        "庚辰",
        "己未",
        "己巳",
    ]
    keys = ("year_jieqi_ganzhi", "month_ganzhi", "day_ganzhi", "time_ganzhi")
    assert [natal["calendar_context"]["lunar_calendar"][k] for k in keys] == [
        "庚辰",
        "庚辰",
        "己未",
        "己巳",
    ]
    context = natal["analysis_calendar_context"]
    assert natal["analysis_date"] == expected_date
    # A date-only natal query anchors at local midnight even when as_of is 23:59.
    assert context["solar_datetime"] == expected_date + " 00:00:00"
    lunar = context["lunar_calendar"]
    assert [lunar[k] for k in keys] == expected_pillars
    shared = BaZiCalendar.get_four_pillars(
        datetime.fromisoformat(expected_date), timezone_name="Asia/Shanghai"
    )
    assert ["".join(p) for p in shared.values()] == expected_pillars
    assert natal["timing_overview"]["liunian"]["pillar"] == expected_pillars[0]
    assert natal["timing_overview"]["liuyue"]["pillar"] == expected_pillars[1]
    # HKO T2024c.txt, https://www.hko.gov.hk/tc/gts/time/calendar/text/files/T2024c.txt:
    # Feb 3 = 十二月廿四; Feb 4 = 廿五 / 立春; Feb 9 = 三十; Feb 10 = 正月初一.
    # These UTC+08 daily labels certify neither exact term instants nor pillar rules.
    assert (lunar["year"], lunar["month"], lunar["day"]) == lunar_date
    if expected_date == "2024-02-04":
        assert context["next_solar_term"]["name"] == "立春"
        assert context["next_solar_term"]["datetime"].startswith(expected_date)

    # The public calendar entry must deliver the same complete calendar facts.
    controls["fields"] = ["calendar_context", "four_pillars"]
    http, protocol, code, cli = surface_calls(
        SPECS["lunar_calendar_time"],
        {
            "date": expected_date,
            "time": "00:00",
            "timezone": "Asia/Shanghai",
            "time_alg": 1,
        },
        projection=controls,
    )
    assert http.status_code == 200 and code == 0 and not protocol.is_error
    assert (
        business(http.json()) == business(protocol.structured_content) == business(cli)
    )
    assert http.json()["calendar_context"] == context
    assert [
        p["stem"] + p["branch"] for p in http.json()["four_pillars"].values()
    ] == expected_pillars
