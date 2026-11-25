import json
from datetime import datetime
from pathlib import Path

import pytest

from fatebridge.core.almanac import get_lunar_context
from fatebridge.core.requests.calendar import NongliTimeRequest
from fatebridge.services.calendar_tools import (
    calculate_jieqi_year,
    calculate_nongli_time,
)
from fatebridge.services.divination import calculate_gua_meiyi
from tests.fixtures.solar_reference import expected_solar_clock
from tests.fixtures.transports import mcp_payload

SOLAR_LABEL_REFERENCE = json.loads(
    (
        Path(__file__).parents[1] / "data/solar_clock_labels_v1/reference.json"
    ).read_text()
)


@pytest.mark.parametrize("case", SOLAR_LABEL_REFERENCE["rows"], ids=lambda c: c["id"])
def test_solar_clock_labels_keep_independent_lunar_day_and_hour(case) -> None:
    result = calculate_nongli_time(**case["input"])
    assert "error" not in result
    expected = case["expected"]
    label = result["analysis_context"]["corrected_datetime"]
    corrected = datetime.fromisoformat(label)
    assert (corrected.date().isoformat(), corrected.hour, corrected.minute) == (
        expected["solar_date"],
        expected["solar_hour"],
        expected["solar_minute"],
    )
    calendar = result["calendar_context"]
    lunar = calendar["lunar_calendar"]
    assert calendar["solar_datetime"] == lunar["solar_datetime"] == label
    assert result["lunar_calendar"] == lunar
    assert [lunar[k] for k in ("year", "month", "day", "is_leap_month")] == [
        expected[k] for k in ("lunar_year", "lunar_month", "lunar_day", "is_leap_month")
    ]
    assert result["dayGanZi"] == expected["day_ganzhi"]
    assert result["timeGanZi"] == expected["hour_ganzhi"]
    seed = lunar["meihua"]["seed"]
    for key in (
        "year_branch",
        "hour_branch",
        "upper_number",
        "lower_number",
        "moving_line",
    ):
        assert seed[key] == expected[key]

    # The direct entry must also preserve the already corrected date; it used
    # to reinterpret a synthetic gap label during its lunar-date lookup.
    direct = get_lunar_context(
        corrected,
        timezone_name=case["input"]["zone"],
        civil_datetime=datetime.fromisoformat(
            case["independent_operands"]["civil_utc"]
        ),
    )
    assert direct is not None
    assert direct["solar_datetime"] == label
    assert [direct[k] for k in ("year", "month", "day")] == [
        expected[k] for k in ("lunar_year", "lunar_month", "lunar_day")
    ]

    # Physical seasonal boundaries still belong to the original civil instant.
    civil = calculate_nongli_time(**{**case["input"], "time_alg": 1})
    for key in ("current_solar_term", "next_solar_term", "bazi_month_boundary"):
        assert calendar[key] == civil["calendar_context"][key]


def test_calculate_jieqi_year_returns_year_grid_and_selected_terms() -> None:
    result = calculate_jieqi_year(
        year=2028,
        zone="Asia/Shanghai",
        lat="31n13",
        lon="121e28",
        jieqis=["春分", "冬至"],
    )

    assert result["analysis_type"] == "全年节气盘"
    assert result["query_context"]["year"] == 2028
    assert result["query_context"]["timezone"] == "Asia/Shanghai"
    assert len(result["jieqi_year"]) == 24
    assert result["jieqi_year"][0]["name"] == "小寒"
    assert result["jieqi_year"][-1]["name"] == "冬至"
    assert [item["name"] for item in result["selected_jieqi"]] == ["春分", "冬至"]
    assert result["year"] == 2028
    assert "jieqi24" not in result
    assert "2028年" in result["summary"]
    assert "24个节气节点" in result["summary"]
    assert "[查询信息]" in result["snapshot_text"]
    assert "[全年节气]" in result["snapshot_text"]
    assert "[重点节气]" in result["snapshot_text"]
    assert "[来源]" in result["snapshot_text"]
    assert result["snapshot_export"]["export_text"] == result["snapshot_text"]


def test_calculate_jieqi_year_supports_selected_export_sections() -> None:
    result = calculate_jieqi_year(
        year=2028,
        zone="Asia/Shanghai",
        jieqis=["春分", "冬至"],
        selected_sections=["查询信息", "重点节气"],
    )

    assert result["snapshot_export"]["selected_sections"] == ["查询信息", "重点节气"]
    assert "[查询信息]" in result["snapshot_export"]["export_text"]
    assert "[重点节气]" in result["snapshot_export"]["export_text"]
    assert "[全年节气]" not in result["snapshot_export"]["export_text"]
    assert "[来源]" not in result["snapshot_export"]["export_text"]


def test_jieqi_year_keeps_exact_events_when_local_clock_is_unspecified() -> None:
    vostok = calculate_jieqi_year(year=1994, zone="Antarctica/Vostok")
    utc = calculate_jieqi_year(year=1994, zone="UTC")
    local_fields = {
        "datetime",
        "datetime_with_offset",
        "date_key",
        "day_ganzhi",
        "utc_offset_seconds",
        "fold",
    }
    assert len(vostok["jieqi_year"]) == len(utc["jieqi_year"]) == 24
    for term, control in zip(vostok["jieqi_year"], utc["jieqi_year"], strict=True):
        assert term["name"] == control["name"]
        assert term["civil_point"] == control["civil_point"]
        # IANA tzdb has no Vostok civil clock during the 1994 closure.
        utc_label = control["datetime_with_offset"]
        if "1994-01-31T17:00:00+00:00" <= utc_label < "1994-11-01T00:00:00+00:00":
            assert term["datetime_utc"] == utc_label
            assert local_fields.isdisjoint(term)
        else:
            assert local_fields.issubset(term)
            assert "datetime_utc" not in term
    assert sum("datetime_utc" in term for term in vostok["jieqi_year"]) == 18
    assert "当地钟时未定义" in vostok["snapshot_text"]


@pytest.mark.local_data
def test_calculate_nongli_time_returns_lunar_and_ganzhi_context() -> None:
    result = calculate_nongli_time(
        date="2028-04-01",
        time="09:00:00",
        zone="Asia/Shanghai",
        lon="121e28",
    )

    assert result["analysis_type"] == "农历换算"
    assert result["input_context"]["date"] == "2028-04-01"
    assert result["input_context"]["time"] == "09:00:00"
    assert result["input_context"]["timezone"] == "Asia/Shanghai"
    expected = expected_solar_clock(
        datetime(2028, 4, 1, 9), "Asia/Shanghai", 121 + 28 / 60
    )
    actual = datetime.fromisoformat(result["birth"])
    assert abs((actual - expected).total_seconds()) <= 5
    assert result["analysis_context"]["input_datetime"] == "2028-04-01 09:00:00"
    assert result["analysis_context"]["corrected_datetime"] == result["birth"]
    assert result["analysis_context"]["effective_datetime"] == result["birth"]
    assert result["analysis_context"]["time_algorithm"] == "真太阳时"
    correction = (actual - datetime(2028, 4, 1, 9)).total_seconds() / 60
    assert (
        abs(result["analysis_context"]["total_correction_minutes"] - correction) <= 0.02
    )
    assert result["yearJieqi"] == "戊申"
    assert result["monthGanZi"] == "乙卯"
    assert result["dayGanZi"] == "丙辰"
    assert result["timeGanZi"] == "癸巳"
    assert "year" not in result and "time" not in result
    assert result["month"] == "三月"
    assert result["day"] == "初七"
    assert result["monthInt"] == 3
    assert result["dayInt"] == 7
    assert result["leap"] is False
    assert result["lunar_calendar"]["display"] == "三月初七"
    assert result["lunar_calendar"]["jieqi"] == "春分"
    assert set(result["four_pillars"]) == {"year", "month", "day", "hour"}
    assert result["calendar_context"]["current_solar_term"]["name"] == "春分"
    assert result["birth"] in result["summary"]
    assert "三月初七" in result["summary"]
    assert "春分" in result["summary"]
    assert "[查询信息]" in result["snapshot_text"]
    assert "[农历上下文]" in result["snapshot_text"]
    assert "[四柱上下文]" in result["snapshot_text"]
    assert "[来源]" in result["snapshot_text"]
    assert result["snapshot_export"]["export_text"] == result["snapshot_text"]


def test_calculate_nongli_time_supports_selected_export_sections() -> None:
    result = calculate_nongli_time(
        date="2028-04-01",
        time="09:00:00",
        zone="Asia/Shanghai",
        lon="121e28",
        selected_sections=["农历上下文", "四柱上下文"],
    )

    assert result["snapshot_export"]["selected_sections"] == [
        "农历上下文",
        "四柱上下文",
    ]
    assert "[农历上下文]" in result["snapshot_export"]["export_text"]
    assert "[四柱上下文]" in result["snapshot_export"]["export_text"]
    assert "[查询信息]" not in result["snapshot_export"]["export_text"]
    assert "[来源]" not in result["snapshot_export"]["export_text"]


@pytest.mark.local_data
def test_calculate_nongli_time_time_alg_zero_applies_true_solar_correction() -> None:
    direct_result = calculate_nongli_time(
        date="2020-01-01",
        time="00:30:00",
        zone="Asia/Shanghai",
        gps_lon=87.6168,
        time_alg=1,
    )
    true_solar_result = calculate_nongli_time(
        date="2020-01-01",
        time="00:30:00",
        zone="Asia/Shanghai",
        gps_lon=87.6168,
        time_alg=0,
    )

    assert direct_result["birth"] == "2020-01-01 00:30:00"
    assert direct_result["dayGanZi"] == "癸卯"
    assert direct_result["timeGanZi"] == "壬子"
    expected = expected_solar_clock(
        datetime(2020, 1, 1, 0, 30), "Asia/Shanghai", 87.6168
    )
    assert (
        abs(
            (
                datetime.fromisoformat(true_solar_result["birth"]) - expected
            ).total_seconds()
        )
        <= 5
    )
    assert true_solar_result["dayGanZi"] == "壬寅"
    assert true_solar_result["timeGanZi"] == "辛亥"
    assert true_solar_result["birth"] != direct_result["birth"]
    assert true_solar_result["dayGanZi"] != direct_result["dayGanZi"]
    assert true_solar_result["timeGanZi"] != direct_result["timeGanZi"]


def test_calculate_nongli_time_time_alg_zero_warns_without_longitude() -> None:
    result = calculate_nongli_time(
        date="2020-01-01",
        time="00:30:00",
        zone="Asia/Shanghai",
        time_alg=0,
    )

    assert result["birth"] == "2020-01-01 00:30:00"
    assert result["dayGanZi"] == "癸卯"
    assert result["timeGanZi"] == "壬子"
    assert result["warnings"] == [
        "time_alg=0 需要 lon 或 gps_lon 才能计算真太阳时，已回退为直接时间。"
    ]


def test_calculate_nongli_time_retains_last_legacy_lunar_date() -> None:
    result = calculate_nongli_time(
        date="2100-02-08",
        time="12:00:00",
        zone="Asia/Shanghai",
        time_alg=1,
    )

    assert result["analysis_type"] == "农历换算"
    assert result["birth"] == "2100-02-08 12:00:00"
    assert result["nongli"] == "二零九九年腊月三十"
    assert result["monthInt"] == 12
    assert result["dayInt"] == 30
    assert result["lunar_calendar"]["display"] == "腊月三十"


def test_calculate_nongli_time_rejects_dates_after_offline_lunar_range() -> None:
    result = calculate_nongli_time(
        date="2101-01-01",
        time="12:00:00",
        zone="Asia/Shanghai",
        time_alg=1,
    )

    assert result == {
        "error": "离线农历换算仅支持公历 1900-01-01 至 2100-12-31。",
        "error_code": "validation_error",
        "status_code": 400,
        "retryable": False,
    }


def test_calculate_nongli_time_rejects_non_ce_ad_flag() -> None:
    result = calculate_nongli_time(
        date="2028-04-01",
        time="09:00:00",
        zone="Asia/Shanghai",
        lon="121e28",
        ad=0,
    )

    assert result == {
        "error": "离线农历换算当前仅支持公元日期（ad=1）。",
        "error_code": "validation_error",
        "status_code": 400,
        "retryable": False,
    }


@pytest.mark.parametrize("time_alg", [-1, 2])
def test_calculate_nongli_time_rejects_unsupported_clock_mode(time_alg) -> None:
    result = calculate_nongli_time(
        date="2024-02-10",
        time="00:00:00",
        zone="Asia/Hong_Kong",
        lon="0e00",
        time_alg=time_alg,
    )

    assert result == {
        "error": "time_alg 仅支持 0（真太阳时）或 1（直接时间）。",
        "error_code": "validation_error",
        "status_code": 400,
        "retryable": False,
    }


def test_calculate_gua_meiyi_returns_batch_trigram_structures() -> None:
    result = calculate_gua_meiyi(name=["111", "000"])

    assert result["analysis_type"] == "梅易卦义"
    assert result["queries"] == ["111", "000"]
    assert result["results"]["111"]["name"] == "乾"
    assert result["results"]["111"]["lookup_type"] == "trigram"
    assert result["results"]["111"]["lines"] == [1, 1, 1]
    assert "111" not in result
    assert result["results"]["000"]["name"] == "坤"
    assert result["results"]["000"]["lookup_type"] == "trigram"
    assert result["results"]["000"]["lines"] == [0, 0, 0]
    assert "000" not in result
    assert "乾" in result["summary"]
    assert "坤" in result["summary"]


def test_helper_mcp_tools_return_structured_results() -> None:
    jieqi_result = mcp_payload(
        "solar_terms_for_year",
        year=2028,
        zone="Asia/Shanghai",
        lat="31n13",
        lon="121e28",
        jieqis=["春分", "冬至"],
        selected_sections=["查询信息", "重点节气"],
    )
    nongli_result = mcp_payload(
        "lunar_calendar_time",
        date="2028-04-01",
        time="09:00:00",
        zone="Asia/Shanghai",
        lon="121e28",
        selected_sections=["农历上下文"],
    )
    gua_result = mcp_payload("gua_meanings", name=["111", "000"])

    assert jieqi_result["analysis_type"] == "全年节气盘"
    assert jieqi_result["selected_jieqi"][0]["name"] == "春分"
    assert jieqi_result["snapshot_export"]["selected_sections"] == [
        "查询信息",
        "重点节气",
    ]
    assert nongli_result["analysis_type"] == "农历换算"
    assert nongli_result["lunar_calendar"]["display"] == "三月初七"
    assert nongli_result["snapshot_export"]["selected_sections"] == ["农历上下文"]
    assert gua_result["analysis_type"] == "梅易卦义"
    assert gua_result["results"]["111"]["name"] == "乾"


def test_nongli_rollover_uses_the_core_late_zi_rule_without_an_ignored_switch() -> None:
    late = calculate_nongli_time(date="2026-12-31", time="23:30", time_alg=1)
    early = calculate_nongli_time(date="2027-01-01", time="00:30", time_alg=1)
    assert (
        late["four_pillars"]["day"]
        == early["four_pillars"]["day"]
        == {"stem": "庚", "branch": "辰"}
    )
    assert late["dayGanZi"] == early["dayGanZi"] == "庚辰"
    assert "after23_new_day" not in NongliTimeRequest.model_fields
