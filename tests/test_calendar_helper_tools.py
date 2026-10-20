import json

from fatebridge.core.requests.calendar import JieqiYearRequest, NongliTimeRequest
from fatebridge.core.requests.divination import GuaMeiyiRequest
from fatebridge.services.calendar_tools import (
    calculate_jieqi_year,
    calculate_nongli_time,
)
from fatebridge.services.divination import calculate_gua_meiyi
from tests.fixtures.transports import mcp_parameters, mcp_text


def test_helper_request_models_accept_published_fields():
    jieqi_request = JieqiYearRequest(
        year=2028,
        zone="+08:00",
        lat="31n13",
        lon="121e28",
        gps_lat=31.2167,
        gps_lon=121.4667,
        jieqis=["春分", "冬至"],
        selected_sections=["查询信息", "重点节气"],
    )
    nongli_request = NongliTimeRequest(
        date="2028-04-01",
        time="09:00:00",
        zone="+08:00",
        lat="31n13",
        lon="121e28",
        gps_lat=31.2167,
        gps_lon=121.4667,
        time_alg=0,
        selected_sections=["农历上下文", "四柱上下文"],
    )
    gua_request = GuaMeiyiRequest(name=["111", "000"])

    jieqi_payload = jieqi_request.model_dump(by_alias=True)
    nongli_payload = nongli_request.model_dump(by_alias=True)

    assert jieqi_payload["gps_lat"] == 31.2167
    assert jieqi_payload["gps_lon"] == 121.4667
    assert jieqi_payload["jieqis"] == ["春分", "冬至"]
    assert jieqi_payload["selected_sections"] == ["查询信息", "重点节气"]
    assert nongli_payload["time_alg"] == 0
    assert nongli_payload["gps_lat"] == 31.2167
    assert nongli_payload["selected_sections"] == ["农历上下文", "四柱上下文"]
    assert gua_request.name == ["111", "000"]


def test_calculate_jieqi_year_returns_year_grid_and_selected_terms():
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


def test_calculate_jieqi_year_supports_selected_export_sections():
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


def test_calculate_nongli_time_returns_lunar_and_ganzhi_context():
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
    assert result["birth"] == "2028-04-01 09:01:50"
    assert result["analysis_context"]["input_datetime"] == "2028-04-01 09:00:00"
    assert result["analysis_context"]["corrected_datetime"] == "2028-04-01 09:01:50"
    assert result["analysis_context"]["effective_datetime"] == "2028-04-01 09:01:50"
    assert result["analysis_context"]["time_algorithm"] == "真太阳时"
    assert result["analysis_context"]["total_correction_minutes"] == 1.85
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
    assert "2028-04-01 09:01:50" in result["summary"]
    assert "三月初七" in result["summary"]
    assert "春分" in result["summary"]
    assert "[查询信息]" in result["snapshot_text"]
    assert "[农历上下文]" in result["snapshot_text"]
    assert "[四柱上下文]" in result["snapshot_text"]
    assert "[来源]" in result["snapshot_text"]
    assert result["snapshot_export"]["export_text"] == result["snapshot_text"]


def test_calculate_nongli_time_supports_selected_export_sections():
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


def test_calculate_nongli_time_time_alg_zero_applies_true_solar_correction():
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
    assert true_solar_result["birth"].startswith("2019-12-31 22:16:")
    assert true_solar_result["dayGanZi"] == "壬寅"
    assert true_solar_result["timeGanZi"] == "辛亥"
    assert true_solar_result["birth"] != direct_result["birth"]
    assert true_solar_result["dayGanZi"] != direct_result["dayGanZi"]
    assert true_solar_result["timeGanZi"] != direct_result["timeGanZi"]


def test_calculate_nongli_time_time_alg_zero_warns_without_longitude():
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


def test_calculate_nongli_time_supports_last_valid_offline_lunar_date():
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


def test_calculate_nongli_time_rejects_dates_after_offline_lunar_range():
    result = calculate_nongli_time(
        date="2100-02-09",
        time="12:00:00",
        zone="Asia/Shanghai",
        time_alg=1,
    )

    assert result == {
        "error": "离线农历换算仅支持公历 1900-01-31 至 2100-02-08。",
        "error_code": "validation_error",
        "status_code": 400,
        "retryable": False,
    }


def test_calculate_nongli_time_rejects_non_ce_ad_flag():
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


def test_calculate_gua_meiyi_returns_batch_meiyi_explanations():
    result = calculate_gua_meiyi(name=["111", "000"])

    assert result["analysis_type"] == "梅易卦义"
    assert result["queries"] == ["111", "000"]
    assert result["results"]["111"]["name"] == "乾"
    assert result["results"]["111"]["lookup_type"] == "trigram"
    assert "主动开创" in result["results"]["111"]["desc"]
    assert "111" not in result
    assert result["results"]["111"]["text"] == result["results"]["111"]["desc"]
    assert result["results"]["000"]["name"] == "坤"
    assert result["results"]["000"]["lookup_type"] == "trigram"
    assert "承载顺势" in result["results"]["000"]["desc"]
    assert "000" not in result
    assert "乾" in result["summary"]
    assert "坤" in result["summary"]


def test_helper_mcp_tools_return_formatted_json_strings():
    jieqi_result = json.loads(
        mcp_text(
            "jieqi_year",
            year=2028,
            zone="Asia/Shanghai",
            lat="31n13",
            lon="121e28",
            jieqis=["春分", "冬至"],
            selected_sections=["查询信息", "重点节气"],
        )
    )
    nongli_result = json.loads(
        mcp_text(
            "nongli_time",
            date="2028-04-01",
            time="09:00:00",
            zone="Asia/Shanghai",
            lon="121e28",
            selected_sections=["农历上下文"],
        )
    )
    gua_result = json.loads(mcp_text("gua_meiyi", name=["111", "000"]))

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


def test_calendar_helper_tools_expose_selected_sections_parameter():
    assert "selected_sections" in mcp_parameters("jieqi_year")["properties"]
    assert "selected_sections" in mcp_parameters("nongli_time")["properties"]


def test_nongli_rollover_uses_the_core_late_zi_rule_without_an_ignored_switch():
    late = calculate_nongli_time(date="2026-12-31", time="23:30", time_alg=1)
    early = calculate_nongli_time(date="2027-01-01", time="00:30", time_alg=1)
    assert (
        late["four_pillars"]["day"]
        == early["four_pillars"]["day"]
        == {"stem": "庚", "branch": "辰"}
    )
    assert late["dayGanZi"] == early["dayGanZi"] == "庚辰"
    assert "after23_new_day" not in NongliTimeRequest.model_fields
