import json

import pytest

from fatebridge.core.ephemeris_runtime import swe
from fatebridge.core.local_techniques.chart import (
    _build_local_chart_response,
    _normalize_date_text,
    _normalize_time_text,
)
from fatebridge.core.local_techniques.sixyao import build_sixyao_result
from fatebridge.core.requests.divination import (
    GuaLookupRequest,
    GuaMeiyiRequest,
    MeihuaAnalysisRequest,
    OtherBuRequest,
    SanShiUnitedRequest,
    SixYaoRequest,
    SuZhanRequest,
    TongSheFaRequest,
)
from fatebridge.services.divination import (
    calculate_gua_lookup,
    calculate_gua_meiyi,
    calculate_meihua_analysis,
    calculate_otherbu_analysis,
    calculate_sanshiunited_analysis,
    calculate_sixyao_analysis,
    calculate_suzhan_analysis,
    calculate_tongshefa_analysis,
)
from tests.fixtures.transports import mcp_parameters, mcp_text


def _expected_offline_engine() -> tuple[str, str]:
    if swe is not None:
        return ("ephemeris_runtime_model", "swisseph_api")
    return ("approximate_orbital_model", "fatebridge_approximate_orbital_model")


def _house_id_for_longitude(houses, longitude):
    for index, house in enumerate(houses):
        current_cusp = float(house["lon"])
        next_cusp = float(houses[(index + 1) % len(houses)]["lon"])
        span = (next_cusp - current_cusp) % 360.0 or 360.0
        distance = (float(longitude) - current_cusp) % 360.0
        if distance < span:
            return house["id"]
    return houses[0]["id"]


def _local_golden_projection():
    tongshefa_result = calculate_tongshefa_analysis(
        taiyin="巽",
        taiyang="坤",
        shaoyang="震",
        shaoyin="震",
    )
    sixyao_result = calculate_sixyao_analysis(
        date="2028-04-06",
        time="09:33:00",
        zone="+08:00",
    )
    suzhan_result = calculate_suzhan_analysis(
        date="2028-04-06",
        time="09:33:00",
        zone="+08:00",
        lat="31n13",
        lon="121e28",
        szchart=1,
        szshape=1,
        house_start_mode=2,
        doubing_su28=False,
    )
    otherbu_result = calculate_otherbu_analysis(
        date="2028-04-06",
        time="09:33:00",
        zone="+08:00",
        lat="31n13",
        lon="121e28",
        sign="Aries",
        house=6,
        planet="Sun",
        question="合作",
    )
    sanshi_result = calculate_sanshiunited_analysis(
        date="2028-04-06",
        time="09:33:00",
        zone="+08:00",
        lat="31n13",
        lon="121e28",
        qimen_options={"layout": "fly"},
        taiyi_options={"accNum": 1},
        liureng_yue="申",
        liureng_is_diurnal=False,
    )
    otherbu_sun = next(
        item
        for item in otherbu_result["diceChart"]["chart"]["objects"]
        if item["id"] == "Sun"
    )

    return {
        "tongshefa": {
            "baseLeft": tongshefa_result["tongshefa"]["baseLeft"]["name"],
            "baseRight": tongshefa_result["tongshefa"]["baseRight"]["name"],
            "main_relation": tongshefa_result["tongshefa"]["main_relation"],
            "summary": tongshefa_result["summary"],
        },
        "sixyao": {
            "current_code": sixyao_result["current_code"],
            "changed_code": sixyao_result["changed_code"],
            "moving_lines": sixyao_result["moving_lines"],
            "current_name": sixyao_result["current_hexagram"]["name"],
            "changed_name": sixyao_result["changed_hexagram"]["name"],
        },
        "suzhan": {
            "chartVariant": suzhan_result["params"]["chartVariant"],
            "houseOrientation": suzhan_result["params"]["houseOrientation"],
            "house1": suzhan_result["chart"]["houses"][0],
            "hasUranus": any(
                item["id"] == "Uranus" for item in suzhan_result["chart"]["objects"]
            ),
            "su28Count": sum(
                1 for item in suzhan_result["chart"]["objects"] if "su28" in item
            ),
        },
        "otherbu": {
            "planet": otherbu_result["planet"],
            "sign": otherbu_result["sign"],
            "house": otherbu_result["house"],
            "diceHouse1Longitude": otherbu_result["diceChart"]["params"][
                "diceHouse1Longitude"
            ],
            "sun": otherbu_sun,
        },
        "sanshiunited": {
            "qimen": {
                "ju_number": sanshi_result["qimen"]["ju_number"],
                "ju_text": sanshi_result["qimen"]["ju_text"],
                "zhifu": sanshi_result["qimen"]["zhifu"],
                "zhishi": sanshi_result["qimen"]["zhishi"],
                "layout": sanshi_result["qimen"].get("layout"),
                "reference": sanshi_result["qimen"].get("reference"),
            },
            "taiyi": {
                "main_calculation": sanshi_result["taiyi"]["core_board"][
                    "main_calculation"
                ],
                "taiyi_palace": sanshi_result["taiyi"]["taiyi_palace"],
                "big_pattern": sanshi_result["taiyi"].get("big_pattern"),
                "small_pattern": sanshi_result["taiyi"].get("small_pattern"),
            },
            "liureng": {
                "month_general": sanshi_result["liureng"]["month_general"],
                "is_diurnal": sanshi_result["liureng"]["meta"]["is_diurnal"],
            },
        },
    }


def test_meihua_request_model_accepts_analysis_fields():
    request = MeihuaAnalysisRequest(
        analysis_year=2028,
        analysis_month=4,
        analysis_day=1,
        analysis_hour=9,
        analysis_minute=0,
        analysis_timezone="Asia/Shanghai",
        question="事业推进节奏",
    )

    payload = request.model_dump()

    assert payload["analysis_year"] == 2028
    assert payload["analysis_month"] == 4
    assert payload["analysis_day"] == 1
    assert payload["analysis_hour"] == 9
    assert payload["analysis_minute"] == 0
    assert payload["analysis_timezone"] == "Asia/Shanghai"
    assert payload["question"] == "事业推进节奏"


def test_gua_lookup_request_model_accepts_fields():
    request = GuaLookupRequest(
        query="111111",
        lookup_mode="hexagram",
        selected_sections=["查询信息", "义理摘要"],
    )

    payload = request.model_dump()

    assert payload["query"] == "111111"
    assert payload["lookup_mode"] == "hexagram"
    assert payload["selected_sections"] == ["查询信息", "义理摘要"]


def test_gua_meiyi_request_model_accepts_fields():
    request = GuaMeiyiRequest(
        name=["111111", "111"],
        selected_sections=["查询概览", "批量结果"],
    )

    payload = request.model_dump()

    assert payload["name"] == ["111111", "111"]
    assert payload["selected_sections"] == ["查询概览", "批量结果"]


def test_local_request_models_accept_alias_and_nested_fields():
    tongshefa_request = TongSheFaRequest(
        taiyin="巽",
        taiyang="坤",
        shaoyang="震",
        shaoyin="震",
    )
    sixyao_request = SixYaoRequest(
        date="2028-04-06",
        time="09:33:00",
        zone="+08:00",
        gps_lat=31.2,
        gps_lon=121.4,
        lines=[{"value": 1, "change": True}],
    )
    suzhan_request = SuZhanRequest(
        date="2028-04-06",
        time="09:33:00",
        house_start_mode=2,
        doubing_su28=False,
        hsys=0,
        zodiacal=1,
    )
    otherbu_request = OtherBuRequest(
        date="2028-04-06",
        time="09:33:00",
        sign="Aries",
        house=3,
        planet="Sun",
        hsys=0,
        zodiacal=1,
    )
    sanshiunited_request = SanShiUnitedRequest(
        date="2028-04-06",
        time="09:33:00",
        qimen_options={"layout": "fly"},
        taiyi_options={"accNum": 1},
        selected_sections=["起盘信息", "离九宫"],
        liureng_yue="辰",
        liureng_is_diurnal=True,
        use_true_solar_time=True,
    )

    sixyao_payload = sixyao_request.model_dump(by_alias=True)
    suzhan_payload = suzhan_request.model_dump(by_alias=True)
    sanshi_payload = sanshiunited_request.model_dump(by_alias=True)
    otherbu_payload = otherbu_request.model_dump(by_alias=True)

    assert tongshefa_request.shaoyin == "震"
    assert sixyao_payload["gps_lat"] == 31.2
    assert sixyao_payload["gps_lon"] == 121.4
    assert sixyao_payload["lines"][0]["change"] is True
    assert suzhan_payload["house_start_mode"] == 2
    assert suzhan_payload["doubing_su28"] is False
    assert suzhan_payload["hsys"] == 0
    assert suzhan_payload["zodiacal"] == 1
    assert otherbu_request.house == 3
    assert otherbu_payload["hsys"] == 0
    assert otherbu_payload["zodiacal"] == 1
    assert sanshiunited_request.qimen_options["layout"] == "fly"
    assert sanshiunited_request.selected_sections == ["起盘信息", "离九宫"]
    assert sanshiunited_request.liureng_is_diurnal is True
    assert sanshi_payload["liureng_is_diurnal"] is True
    assert sanshi_payload["use_true_solar_time"] is True


def test_calculate_gua_lookup_supports_hexagram_and_trigram_queries():
    hexagram_result = calculate_gua_lookup(query="111111", lookup_mode="auto")
    trigram_result = calculate_gua_lookup(query="111", lookup_mode="auto")

    assert hexagram_result["result"]["lookup_type"] == "hexagram"
    assert hexagram_result["result"]["name"] == "乾为天"
    assert hexagram_result["result"]["theme"] == "开创与自强"
    assert (
        hexagram_result["result"]["judgement"] == "局势昂扬，宜先定大方向再强力推进。"
    )
    assert "六阳纯健" in hexagram_result["result"]["image"]
    assert "立战略" in hexagram_result["result"]["favorable"]
    assert "刚愎" in hexagram_result["result"]["caution"]
    assert "主动定方向" in hexagram_result["summary"]
    assert "忌刚愎" in hexagram_result["summary"]
    assert "[查询信息]" in hexagram_result["snapshot_text"]
    assert "[卦象结构]" in hexagram_result["snapshot_text"]
    assert "[义理摘要]" in hexagram_result["snapshot_text"]
    assert "[来源]" in hexagram_result["snapshot_text"]
    assert (
        hexagram_result["snapshot_export"]["export_text"]
        == hexagram_result["snapshot_text"]
    )

    assert trigram_result["result"]["lookup_type"] == "trigram"
    assert trigram_result["result"]["name"] == "乾"
    assert trigram_result["result"]["theme"] == "主动开创"
    assert "纯阳在上" in trigram_result["result"]["image"]
    assert "立规" in trigram_result["result"]["favorable"]
    assert "刚亢" in trigram_result["result"]["caution"]
    assert "立方向" in trigram_result["summary"]
    assert "忌刚亢" in trigram_result["summary"]


def test_calculate_gua_lookup_supports_selected_export_sections():
    result = calculate_gua_lookup(
        query="111111",
        lookup_mode="auto",
        selected_sections=["查询信息", "义理摘要"],
    )

    assert result["snapshot_export"]["selected_sections"] == ["查询信息", "义理摘要"]
    assert "[查询信息]" in result["snapshot_export"]["export_text"]
    assert "[义理摘要]" in result["snapshot_export"]["export_text"]
    assert "[卦象结构]" not in result["snapshot_export"]["export_text"]
    assert "[来源]" not in result["snapshot_export"]["export_text"]


def test_calculate_gua_meiyi_returns_snapshot_export():
    result = calculate_gua_meiyi(name=["111111", "111"])

    assert result["results"]["111111"]["name"] == "乾为天"
    assert result["results"]["111"]["name"] == "乾"
    assert "[查询概览]" in result["snapshot_text"]
    assert "[批量结果]" in result["snapshot_text"]
    assert "[来源]" in result["snapshot_text"]
    assert result["snapshot_export"]["export_text"] == result["snapshot_text"]


def test_calculate_gua_meiyi_supports_selected_export_sections():
    result = calculate_gua_meiyi(
        name=["111111", "111"],
        selected_sections=["批量结果"],
    )

    assert result["snapshot_export"]["selected_sections"] == ["批量结果"]
    assert "[批量结果]" in result["snapshot_export"]["export_text"]
    assert "[查询概览]" not in result["snapshot_export"]["export_text"]
    assert "[来源]" not in result["snapshot_export"]["export_text"]


def test_fastmcp_divination_tools_expose_compact_controls():
    for tool in (
        "export_registry",
        "gua_lookup",
        "gua_meiyi",
        "meihua_analysis",
        "sanshiunited",
        "sixyao",
        "suzhan",
        "otherbu",
    ):
        properties = mcp_parameters(tool)["properties"]
        assert "compact" in properties
        assert "include_snapshot_text" in properties


def test_fastmcp_sanshiunited_compact_mode_can_drop_snapshot_text():
    rendered = mcp_text(
        "sanshiunited",
        date="2028-04-06",
        time="09:33:00",
        zone="+08:00",
        lat="31n13",
        lon="121e28",
        qimen_options={"layout": "fly"},
        taiyi_options={"accNum": 1},
        liureng_yue="申",
        liureng_is_diurnal=False,
        compact=True,
        include_snapshot_text=False,
    )

    payload = json.loads(rendered)

    assert "snapshot_text" not in payload
    assert "snapshot_export" in payload
    assert "\n" not in rendered


def test_calculate_meihua_analysis_returns_expected_hexagram_chain():
    result = calculate_meihua_analysis(
        analysis_year=2028,
        analysis_month=4,
        analysis_day=1,
        analysis_hour=9,
        analysis_minute=0,
        analysis_timezone="Asia/Shanghai",
        question="事业推进节奏",
    )

    meihua = result["meihua"]
    interpretation = result["interpretation"]

    assert result["analysis_context"]["lunar_display"] == "三月初七"
    assert result["analysis_context"]["current_jieqi"] == "春分"
    assert meihua["base_hexagram"]["name"] == "火天大有"
    assert meihua["changed_hexagram"]["name"] == "火风鼎"
    assert meihua["mutual_hexagram"]["name"] == "泽天夬"
    assert "opposite_hexagram" not in meihua
    assert meihua["cuo_hexagram"]["name"] == "水地比"
    assert meihua["zong_hexagram"]["name"] == "天火同人"
    assert interpretation["cuo_oracle"]["name"] == "水地比"
    assert interpretation["cuo_reading"].startswith("错卦水地比")
    assert "opposite_oracle" not in interpretation
    assert "opposite_reading" not in interpretation
    assert meihua["base_hexagram"]["judgement"] == "资源在手，宜放大优势并守住尺度。"
    assert "火在天上" in meihua["base_hexagram"]["image"]
    assert meihua["moving_palace"] == "下卦"
    assert meihua["body_trigram"]["name"] == "离"
    assert meihua["use_trigram"]["name"] == "乾"
    assert meihua["body_use_relation"] == "体克用"
    assert "体卦离、用卦乾" in meihua["body_use_summary"]
    assert interpretation["question_domain"]["label"] == "事业/项目"
    assert interpretation["moving_line_phase"]["stage"] == "起念与启动"
    assert len(interpretation["line_oracles"]) == 6
    assert sum(1 for item in interpretation["line_oracles"] if item["is_active"]) == 1
    assert interpretation["moving_line_oracle"]["position"] == "初爻"
    assert interpretation["moving_line_oracle"]["title"] == "发端位"
    assert interpretation["moving_line_oracle"]["focus"] == "起势、试探与基础"
    assert interpretation["moving_line_oracle"]["timing"] == "先小后大"
    assert interpretation["moving_line_oracle"]["changed_hexagram"]["name"] == "火风鼎"
    assert interpretation["moving_line_oracle"]["body_trigram"] == "离"
    assert interpretation["moving_line_oracle"]["use_trigram"] == "乾"
    assert "第一步踩稳" in interpretation["moving_line_oracle"]["judgement"]
    assert "试探、起步" in interpretation["moving_line_oracle"]["favorable"]
    assert "起手过满" in interpretation["moving_line_oracle"]["caution"]
    assert "里程碑先钉牢" in interpretation["moving_line_oracle"]["domain_hint"]
    assert "主动拿节奏" in interpretation["moving_line_oracle"]["body_use_adjustment"]
    assert interpretation["line_oracles"][0]["is_active"] is True
    assert interpretation["line_oracles"][-1]["changed_hexagram"]["name"] == "雷天大壮"
    assert "主动掌控" in interpretation["body_use_reading"]
    assert "火天大有" in interpretation["base_reading"]
    assert "火风鼎" in interpretation["changed_reading"]
    assert (
        interpretation["base_oracle"]["judgement"] == "资源在手，宜放大优势并守住尺度。"
    )
    assert "扩成果" in interpretation["base_oracle"]["favorable"]
    assert (
        interpretation["changed_oracle"]["judgement"]
        == "重整器局可成新局，关键在结构升级。"
    )
    assert "重组团队" in interpretation["changed_oracle"]["favorable"]
    assert "扩成果" in interpretation["action_hint"]
    assert "试探、起步" in interpretation["action_hint"]
    assert "重组团队" in interpretation["action_hint"]
    assert "骄满" in interpretation["risk_hint"]
    assert "起手过满" in interpretation["risk_hint"]
    assert "站错队" in interpretation["risk_hint"]
    assert len(interpretation["judgement_outline"]) == 7
    assert "事业/项目" in result["summary"]
    assert "起念与启动" in result["summary"]
    assert "第一步踩稳" in result["summary"]


def test_calculate_tongshefa_analysis_returns_expected_local_structure():
    result = calculate_tongshefa_analysis(
        taiyin="巽",
        taiyang="坤",
        shaoyang="震",
        shaoyin="震",
    )

    model = result["tongshefa"]

    assert result["analysis_type"] == "统摄法分析"
    assert model["baseLeft"]["name"] == "风雷益"
    assert model["baseRight"]["name"] == "地雷复"
    assert model["mutualLeft"]["name"] == "山地剥"
    assert model["mutualRight"]["name"] == "坤为地"
    assert model["oppositeLeft"]["name"] == "雷风恒"
    assert model["oppositeRight"]["name"] == "天风姤"
    assert model["main_relation"] == "思克实"
    assert "[潜藏]" in result["snapshot_text"]
    assert "[亲和]" in result["snapshot_text"]


def test_calculate_sixyao_analysis_supports_explicit_lines():
    result = calculate_sixyao_analysis(
        date="2028-04-06",
        time="09:33:00",
        zone="+08:00",
        question="合作",
        lines=[
            {"value": 1, "change": False},
            {"value": 1, "change": True},
            {"value": 1, "change": False},
            {"value": 1, "change": False},
            {"value": 1, "change": False},
            {"value": 1, "change": False},
        ],
    )

    assert result["current_code"] == "111111"
    assert result["changed_code"] == "101111"
    assert result["moving_lines"] == [2]
    assert result["current_hexagram"]["name"] == "乾为天"
    assert result["changed_hexagram"]["name"] == "天火同人"
    assert "第2爻：阳爻（动）" in result["snapshot_text"]
    assert "问题：合作" in result["snapshot_text"]


def test_calculate_sixyao_analysis_time_casts_when_no_hexagram_supplied():
    """当调用方未提供卦码 / 爻线时，六爻按起卦时刻做时间起卦（梅花口径）真实
    装卦，而不是返回一个与时刻无关的固定演示卦。"""
    result = calculate_sixyao_analysis(
        date="2028-04-06",
        time="09:33:00",
        zone="+08:00",
    )

    # 2028-04-06 09:33 +08:00 的时间起卦：本卦地水师(010000)、动6爻、之卦山水蒙(010001)。
    assert result["current_code"] == "010000"
    assert result["changed_code"] == "010001"
    assert result["moving_lines"] == [6]
    assert result["current_hexagram"]["name"] == "地水师"
    assert result["changed_hexagram"]["name"] == "山水蒙"
    assert result["cast"]["method"] == "time_meihua"
    # 2028-04-06 日干=辛，按"庚辛日起白虎"的规则，初爻六神应为白虎。
    assert result["lines"][0]["god"] == "白虎"
    assert result["lines"][5]["change"] is True
    assert "第6爻：阴爻（动）" in result["snapshot_text"]


def test_calculate_sixyao_time_cast_varies_with_moment():
    """时间起卦必须随起卦时刻变化，而非恒返回同一卦。"""
    morning = calculate_sixyao_analysis(
        date="2028-04-06", time="09:33:00", zone="+08:00"
    )
    other = calculate_sixyao_analysis(date="2025-01-01", time="23:30:00", zone="+08:00")

    assert (morning["current_code"], morning["moving_lines"]) != (
        other["current_code"],
        other["moving_lines"],
    )
    assert morning["cast"]["method"] == "time_meihua"
    assert other["cast"]["method"] == "time_meihua"


def test_calculate_sixyao_explicit_code_is_marked_manual():
    """显式提供卦码时不做时间起卦，且标记为手动起卦。"""
    result = calculate_sixyao_analysis(
        date="2028-04-06",
        time="09:33:00",
        zone="+08:00",
        gua_code="111000",
        changed_code="110000",
    )

    assert result["cast"]["method"] == "manual"
    assert result["current_code"] == "111000"
    assert result["changed_code"] == "110000"
    assert result["moving_lines"] == [3]


def test_calculate_sixyao_coin_casting_from_explicit_tosses():
    """真·摇钱起卦：调用方提供六掷之和（初爻→上爻），按字面=2/背面=3 装卦。
    coins=[7,8,7,9,8,6] → 少阳/少阴/少阳/老阳/少阴/老阴。"""
    result = calculate_sixyao_analysis(
        date="2028-04-06",
        time="09:33:00",
        zone="+08:00",
        coins=[7, 8, 7, 9, 8, 6],
    )

    # 值: 7→阳1, 8→阴0, 7→阳1, 9→阳1, 8→阴0, 6→阴0 → 本卦 101100。
    assert result["current_code"] == "101100"
    # 动爻: 9(老阳,第4爻) 与 6(老阴,第6爻)。翻转后 → 101001。
    assert result["changed_code"] == "101001"
    assert result["moving_lines"] == [4, 6]
    assert result["cast"]["method"] == "coin"
    assert result["cast"]["coin_source"] == "provided"
    tosses = result["cast"]["tosses"]
    assert len(tosses) == 6
    assert tosses[3]["sum"] == 9
    assert tosses[3]["yao"] == "老阳"
    assert tosses[3]["moving"] is True
    assert tosses[1]["yao"] == "少阴"
    assert tosses[1]["moving"] is False


def test_calculate_sixyao_coin_casting_random_is_seedable():
    """系统随机摇卦：同一 seed 必出同一卦（可复现），标记 coin/random。"""
    first = calculate_sixyao_analysis(
        date="2028-04-06", time="09:33:00", zone="+08:00", method="coin", seed=42
    )
    second = calculate_sixyao_analysis(
        date="2028-04-06", time="09:33:00", zone="+08:00", method="coin", seed=42
    )

    assert first["cast"]["method"] == "coin"
    assert first["cast"]["coin_source"] == "random"
    assert len(first["current_code"]) == 6
    assert set(first["current_code"]) <= {"0", "1"}
    assert first["current_code"] == second["current_code"]
    assert first["changed_code"] == second["changed_code"]
    assert first["moving_lines"] == second["moving_lines"]
    # 动爻只能落在老阴(6)/老阳(9)的掷上。
    moving_positions = {t["position"] for t in first["cast"]["tosses"] if t["moving"]}
    assert moving_positions == set(first["moving_lines"])
    for toss in first["cast"]["tosses"]:
        assert toss["sum"] in (6, 7, 8, 9)
        assert (toss["sum"] in (6, 9)) == toss["moving"]


def test_calculate_sixyao_coin_rejects_invalid_toss():
    """每掷之和必须 ∈ {6,7,8,9}（三枚铜钱），非法值经守卫返回校验错误。"""
    result = calculate_sixyao_analysis(
        date="2028-04-06",
        time="09:33:00",
        zone="+08:00",
        coins=[7, 8, 7, 9, 8, 5],
    )
    assert result["error_code"] == "validation_error"
    assert "6/7/8/9" in result["error"]


def test_calculate_sixyao_coin_requires_six_tosses():
    result = calculate_sixyao_analysis(
        date="2028-04-06",
        time="09:33:00",
        zone="+08:00",
        coins=[7, 8, 7],
    )
    assert result["error_code"] == "validation_error"


def test_build_sixyao_result_raises_on_invalid_coins():
    """核心层（无守卫）对非法摇钱输入直接 fail-loud。"""
    from fatebridge.core.local_techniques.sixyao import build_sixyao_result

    with pytest.raises(ValueError):
        build_sixyao_result(
            date="2028-04-06", time="09:33:00", zone="+08:00", coins=[7, 8, 7, 9, 8, 5]
        )


def test_sixyao_does_not_treat_the_string_zero_as_a_yang_line():
    result = calculate_sixyao_analysis(
        date="2028-04-06",
        time="09:33:00",
        zone="+08:00",
        lines=[{"value": "0", "change": False}] * 6,
    )
    assert result["error_code"] == "validation_error"
    result = calculate_sixyao_analysis(
        date="2028-04-06",
        time="09:33:00",
        zone="+08:00",
        lines=[{"value": 0, "change": False}] * 6,
    )
    assert result["current_code"] == "000000"
    assert all(line["value"] == 0 for line in result["lines"])


def test_calculate_suzhan_analysis_returns_chart_and_snapshot():
    result = calculate_suzhan_analysis(
        date="2028-04-06",
        time="09:33:00",
        zone="+08:00",
        lat="31n13",
        lon="121e28",
    )

    assert result["analysis_type"] == "宿占 / 宿盘"
    assert result["chart"]["ok"] is True
    assert result["params"]["birthLatitude"] == 31.2167
    assert result["params"]["birthLongitude"] == 121.4667
    assert len(result["chart"]["houses"]) == 12
    assert any(item["id"] == "Sun" for item in result["chart"]["objects"])
    assert any(item["id"] == "Pars Fortuna" for item in result["chart"]["objects"])
    assert "[宿盘宫位与二十八宿星曜]" in result["snapshot_text"]
    assert "宫位：House1" in result["snapshot_text"]
    assert "星曜：Sun " in result["snapshot_text"]
    assert "˚" in result["snapshot_text"]


def test_suzhan_uses_shared_local_chart_runtime():
    local_chart = _build_local_chart_response(
        date_text="2028-04-06",
        time_text="09:33:00",
        timezone_name="+08:00",
        lat="31n13",
        lon="121e28",
        hsys=8,
        zodiacal=0,
        allow_extended_hsys=True,
    )
    suzhan_result = calculate_suzhan_analysis(
        date="2028-04-06",
        time="09:33:00",
        zone="+08:00",
        lat="31n13",
        lon="121e28",
    )
    expected_precision, expected_backend = _expected_offline_engine()
    local_sun = next(
        item for item in local_chart["chart"]["objects"] if item["id"] == "Sun"
    )
    suzhan_sun = next(
        item for item in suzhan_result["chart"]["objects"] if item["id"] == "Sun"
    )

    assert local_chart["chart"]["houses"] == suzhan_result["chart"]["houses"]
    assert local_chart["chart"]["angles"] == suzhan_result["chart"]["angles"]
    assert local_sun == suzhan_sun
    assert local_chart["params"]["enginePrecision"] == expected_precision
    assert local_chart["params"]["engineBackend"] == expected_backend


def test_calculate_suzhan_analysis_exposes_runtime_engine_metadata():
    result = calculate_suzhan_analysis(
        date="2028-04-06",
        time="09:33:00",
        zone="+08:00",
        lat="31n13",
        lon="121e28",
    )
    expected_precision, expected_backend = _expected_offline_engine()

    assert result["params"]["enginePrecision"] == expected_precision
    assert result["params"]["engineBackend"] == expected_backend


def test_calculate_suzhan_analysis_applies_chart_modes_to_offline_output():
    default_result = calculate_suzhan_analysis(
        date="2028-04-06",
        time="09:33:00",
        zone="+08:00",
        lat="31n13",
        lon="121e28",
        szchart=0,
        szshape=0,
        house_start_mode=1,
        doubing_su28=True,
    )
    adjusted_result = calculate_suzhan_analysis(
        date="2028-04-06",
        time="09:33:00",
        zone="+08:00",
        lat="31n13",
        lon="121e28",
        szchart=1,
        szshape=1,
        house_start_mode=2,
        doubing_su28=False,
    )

    assert any(item["id"] == "Uranus" for item in default_result["chart"]["objects"])
    assert not any(
        item["id"] == "Uranus" for item in adjusted_result["chart"]["objects"]
    )
    assert (
        default_result["chart"]["houses"][0]["lon"]
        != adjusted_result["chart"]["houses"][0]["lon"]
    )
    assert (
        default_result["chart"]["houses"][1]["lon"]
        != adjusted_result["chart"]["houses"][1]["lon"]
    )
    assert any("su28" in item for item in default_result["chart"]["objects"])
    assert all("su28" not in item for item in adjusted_result["chart"]["objects"])
    assert default_result["snapshot_text"] != adjusted_result["snapshot_text"]


def test_calculate_suzhan_analysis_supports_offline_house_system_and_zodiacal_modes():
    tropical_equal_result = calculate_suzhan_analysis(
        date="2028-04-06",
        time="09:33:00",
        zone="+08:00",
        lat="31n13",
        lon="121e28",
        szchart=0,
        hsys=8,
        zodiacal=0,
    )
    sidereal_whole_result = calculate_suzhan_analysis(
        date="2028-04-06",
        time="09:33:00",
        zone="+08:00",
        lat="31n13",
        lon="121e28",
        szchart=0,
        hsys=0,
        zodiacal=1,
    )

    tropical_sun = next(
        item
        for item in tropical_equal_result["chart"]["objects"]
        if item["id"] == "Sun"
    )
    sidereal_sun = next(
        item
        for item in sidereal_whole_result["chart"]["objects"]
        if item["id"] == "Sun"
    )

    assert tropical_equal_result["params"]["houseSystemResolved"] == "equal"
    assert tropical_equal_result["params"]["zodiacMode"] == "tropical"
    assert sidereal_whole_result["params"]["houseSystemResolved"] == "whole_sign"
    assert sidereal_whole_result["params"]["zodiacMode"] == "sidereal"
    assert sidereal_whole_result["params"]["zodiacLabelZh"] == "恒星黄道，岁差:Lahiri"
    assert sidereal_whole_result["params"]["ayanamsha"] > 0
    assert (
        tropical_equal_result["chart"]["houses"][0]["lon"]
        != sidereal_whole_result["chart"]["houses"][0]["lon"]
    )
    assert tropical_sun["lon"] != sidereal_sun["lon"]
    assert tropical_sun["sign"] != sidereal_sun["sign"]


def test_calculate_suzhan_analysis_supports_extended_offline_house_systems():
    placidus_result = calculate_suzhan_analysis(
        date="2028-04-06",
        time="09:33:00",
        zone="+08:00",
        lat="31n13",
        lon="121e28",
        szchart=0,
        hsys=3,
        zodiacal=0,
    )
    sripati_result = calculate_suzhan_analysis(
        date="2028-04-06",
        time="09:33:00",
        zone="+08:00",
        lat="31n13",
        lon="121e28",
        szchart=0,
        hsys=7,
        zodiacal=0,
    )

    placidus_sun = next(
        item for item in placidus_result["chart"]["objects"] if item["id"] == "Sun"
    )
    sripati_sun = next(
        item for item in sripati_result["chart"]["objects"] if item["id"] == "Sun"
    )
    placidus_houses = placidus_result["chart"]["houses"]
    sripati_houses = sripati_result["chart"]["houses"]
    placidus_spans = [
        round((placidus_houses[(index + 1) % 12]["lon"] - house["lon"]) % 360.0, 4)
        for index, house in enumerate(placidus_houses)
    ]
    sripati_spans = [
        round((sripati_houses[(index + 1) % 12]["lon"] - house["lon"]) % 360.0, 4)
        for index, house in enumerate(sripati_houses)
    ]

    assert placidus_result["params"]["houseSystemResolved"] == "placidus"
    assert sripati_result["params"]["houseSystemResolved"] == "sripati"
    assert any(span != 30.0 for span in placidus_spans)
    assert any(span != 30.0 for span in sripati_spans)
    assert (
        _house_id_for_longitude(placidus_houses, placidus_sun["lon"])
        == placidus_sun["house"]
    )
    assert (
        _house_id_for_longitude(sripati_houses, sripati_sun["lon"])
        == sripati_sun["house"]
    )
    assert placidus_houses[0]["lon"] != sripati_houses[0]["lon"]


def test_calculate_suzhan_analysis_rejects_unsupported_offline_modes():
    invalid_hsys_result = calculate_suzhan_analysis(
        date="2028-04-06",
        time="09:33:00",
        zone="+08:00",
        lat="31n13",
        lon="121e28",
        hsys=9,
    )
    invalid_zodiac_result = calculate_suzhan_analysis(
        date="2028-04-06",
        time="09:33:00",
        zone="+08:00",
        lat="31n13",
        lon="121e28",
        zodiacal=2,
    )

    assert invalid_hsys_result == {
        "error": "核心星盘离线模式暂仅支持 hsys=0..8（整宫制、Alcabitus、Regiomontanus、Placidus、Koch、Vehlow Equal、Polich Page、Sripati、天顶为10宫中点等宫制）。",
        "error_code": "validation_error",
        "status_code": 400,
        "retryable": False,
    }
    assert invalid_zodiac_result == {
        "error": "核心星盘离线模式暂仅支持 zodiacal=0(回归黄道) 或 zodiacal=1(恒星黄道/Lahiri)。",
        "error_code": "validation_error",
        "status_code": 400,
        "retryable": False,
    }


def test_calculate_otherbu_analysis_supports_traditional_mode():
    result = calculate_otherbu_analysis(
        date="2028-04-06",
        time="09:33:00",
        zone="+08:00",
        lat="31n13",
        lon="121e28",
        tradition=True,
        sign="Aries",
        house=0,
        planet="Sun",
        question="合作",
    )

    natal_objects = result["chart"]["chart"]["objects"]
    dice_sun = next(
        item for item in result["diceChart"]["chart"]["objects"] if item["id"] == "Sun"
    )

    assert result["analysis_type"] == "西洋游戏 / 占星骰子"
    assert result["sign"] == "Aries"
    assert result["planet"] == "Sun"
    assert dice_sun["house"] == "House1"
    assert dice_sun["sign"] == "Aries"
    assert not any(item["id"] == "Uranus" for item in natal_objects)
    assert "Sun主核心意志" in result["interpretation"]["summary"]
    assert "星座：Aries" in result["snapshot_text"]
    assert "问题：合作" in result["snapshot_text"]
    assert "[骰子盘宫位与星体]" in result["snapshot_text"]
    assert "[天象盘宫位与星体]" in result["snapshot_text"]


def test_calculate_otherbu_analysis_supports_offline_house_system_and_zodiacal_modes():
    tropical_equal_result = calculate_otherbu_analysis(
        date="2028-04-06",
        time="09:33:00",
        zone="+08:00",
        lat="31n13",
        lon="121e28",
        sign="Aries",
        house=6,
        planet="Sun",
        hsys=8,
        zodiacal=0,
    )
    sidereal_whole_result = calculate_otherbu_analysis(
        date="2028-04-06",
        time="09:33:00",
        zone="+08:00",
        lat="31n13",
        lon="121e28",
        sign="Aries",
        house=6,
        planet="Sun",
        hsys=0,
        zodiacal=1,
    )

    tropical_sun = next(
        item
        for item in tropical_equal_result["chart"]["chart"]["objects"]
        if item["id"] == "Sun"
    )
    sidereal_sun = next(
        item
        for item in sidereal_whole_result["chart"]["chart"]["objects"]
        if item["id"] == "Sun"
    )

    assert tropical_equal_result["chart"]["params"]["houseSystemResolved"] == "equal"
    assert tropical_equal_result["chart"]["params"]["zodiacMode"] == "tropical"
    assert (
        sidereal_whole_result["chart"]["params"]["houseSystemResolved"] == "whole_sign"
    )
    assert sidereal_whole_result["chart"]["params"]["zodiacMode"] == "sidereal"
    assert (
        sidereal_whole_result["chart"]["params"]["zodiacLabelZh"]
        == "恒星黄道，岁差:Lahiri"
    )
    assert sidereal_whole_result["chart"]["params"]["ayanamsha"] > 0
    assert (
        tropical_equal_result["chart"]["chart"]["houses"][0]["lon"]
        != sidereal_whole_result["chart"]["chart"]["houses"][0]["lon"]
    )
    assert tropical_sun["lon"] != sidereal_sun["lon"]
    assert tropical_sun["sign"] != sidereal_sun["sign"]


def test_calculate_otherbu_analysis_exposes_runtime_engine_metadata():
    result = calculate_otherbu_analysis(
        date="2028-04-06",
        time="09:33:00",
        zone="+08:00",
        lat="31n13",
        lon="121e28",
        sign="Aries",
        house=6,
        planet="Sun",
    )
    expected_precision, expected_backend = _expected_offline_engine()

    assert result["chart"]["params"]["enginePrecision"] == expected_precision
    assert result["chart"]["params"]["engineBackend"] == expected_backend
    assert result["diceChart"]["params"]["enginePrecision"] == expected_precision
    assert result["diceChart"]["params"]["engineBackend"] == expected_backend


def test_calculate_otherbu_analysis_supports_extended_offline_house_systems():
    placidus_result = calculate_otherbu_analysis(
        date="2028-04-06",
        time="09:33:00",
        zone="+08:00",
        lat="31n13",
        lon="121e28",
        sign="Aries",
        house=6,
        planet="Sun",
        hsys=3,
        zodiacal=0,
    )
    sripati_result = calculate_otherbu_analysis(
        date="2028-04-06",
        time="09:33:00",
        zone="+08:00",
        lat="31n13",
        lon="121e28",
        sign="Aries",
        house=6,
        planet="Sun",
        hsys=7,
        zodiacal=0,
    )

    placidus_sun = next(
        item
        for item in placidus_result["chart"]["chart"]["objects"]
        if item["id"] == "Sun"
    )
    sripati_sun = next(
        item
        for item in sripati_result["chart"]["chart"]["objects"]
        if item["id"] == "Sun"
    )
    placidus_houses = placidus_result["chart"]["chart"]["houses"]
    sripati_houses = sripati_result["chart"]["chart"]["houses"]
    placidus_spans = [
        round((placidus_houses[(index + 1) % 12]["lon"] - house["lon"]) % 360.0, 4)
        for index, house in enumerate(placidus_houses)
    ]
    sripati_spans = [
        round((sripati_houses[(index + 1) % 12]["lon"] - house["lon"]) % 360.0, 4)
        for index, house in enumerate(sripati_houses)
    ]

    assert placidus_result["chart"]["params"]["houseSystemResolved"] == "placidus"
    assert sripati_result["chart"]["params"]["houseSystemResolved"] == "sripati"
    assert any(span != 30.0 for span in placidus_spans)
    assert any(span != 30.0 for span in sripati_spans)
    assert (
        _house_id_for_longitude(placidus_houses, placidus_sun["lon"])
        == placidus_sun["house"]
    )
    assert (
        _house_id_for_longitude(sripati_houses, sripati_sun["lon"])
        == sripati_sun["house"]
    )
    assert placidus_houses[0]["lon"] != sripati_houses[0]["lon"]


def test_calculate_otherbu_analysis_rejects_unsupported_offline_modes():
    invalid_hsys_result = calculate_otherbu_analysis(
        date="2028-04-06",
        time="09:33:00",
        zone="+08:00",
        lat="31n13",
        lon="121e28",
        hsys=9,
    )
    invalid_zodiac_result = calculate_otherbu_analysis(
        date="2028-04-06",
        time="09:33:00",
        zone="+08:00",
        lat="31n13",
        lon="121e28",
        zodiacal=2,
    )

    assert invalid_hsys_result == {
        "error": "核心星盘离线模式暂仅支持 hsys=0..8（整宫制、Alcabitus、Regiomontanus、Placidus、Koch、Vehlow Equal、Polich Page、Sripati、天顶为10宫中点等宫制）。",
        "error_code": "validation_error",
        "status_code": 400,
        "retryable": False,
    }
    assert invalid_zodiac_result == {
        "error": "核心星盘离线模式暂仅支持 zodiacal=0(回归黄道) 或 zodiacal=1(恒星黄道/Lahiri)。",
        "error_code": "validation_error",
        "status_code": 400,
        "retryable": False,
    }


def test_calculate_otherbu_analysis_keeps_dice_chart_house_geometry_consistent():
    result = calculate_otherbu_analysis(
        date="2028-04-06",
        time="09:33:00",
        zone="+08:00",
        lat="31n13",
        lon="121e28",
        sign="Aries",
        house=6,
        planet="Sun",
    )

    dice_sun = next(
        item for item in result["diceChart"]["chart"]["objects"] if item["id"] == "Sun"
    )
    actual_house = _house_id_for_longitude(
        result["diceChart"]["chart"]["houses"], dice_sun["lon"]
    )

    assert dice_sun["house"] == "House7"
    assert actual_house == "House7"
    assert dice_sun["house"] == actual_house


def test_calculate_sanshiunited_analysis_returns_local_aggregation():
    result = calculate_sanshiunited_analysis(
        date="2028-04-06",
        time="09:33:00",
        zone="+08:00",
        lat="31n13",
        lon="121e28",
    )

    assert result["analysis_type"] == "三式合一"
    assert result["qimen"]["dun_type"] == "阳遁"
    assert result["qimen"]["ju_number"] == 6
    assert result["taiyi"]["core_board"]["main_calculation"] == "陽遁五十七局"
    # 贵人乘午，实际落地盘丑，应按地盘位置顺布。
    assert result["liureng"]["patterns"][0]["name"] == "贵人顺行格"
    assert "subresults" in result
    assert "qimen" in result["subresults"]
    assert result["subresults"]["qimen"]["pan"] == result["qimen"]
    assert result["subresults"]["taiyi"]["pan"] == result["taiyi"]
    assert result["subresults"]["liureng_gods"]["liureng"] == result["liureng"]
    assert "[太乙十六宫]" in result["snapshot_text"]
    assert "[六壬小局]" in result["snapshot_text"]
    assert "[八宫详解]" in result["snapshot_text"]
    assert result["snapshot_export"]["export_text"] == result["snapshot_text"]
    assert "离九宫" in result["snapshot_export"]["section_titles_detected"]
    assert result["qimen"]["zhifu"]["star"] == "天任"
    assert result["qimen"]["zhifu"]["palace"] == "坤二宫"
    assert result["qimen"]["zhishi"]["door"] == "生门"
    assert result["qimen"]["zhishi"]["palace"] == "艮八宫"
    assert "值符：天任在坤二宫" in result["snapshot_text"]
    assert "艮八宫：天盘干：癸" in result["snapshot_text"]
    zhifu_palace = next(
        palace
        for palace in result["qimen"]["palaces"]
        if palace["name"] == result["qimen"]["zhifu"]["palace"]
    )
    zhishi_palace = next(
        palace
        for palace in result["qimen"]["palaces"]
        if palace["name"] == result["qimen"]["zhishi"]["palace"]
    )
    assert zhifu_palace["star"] == result["qimen"]["zhifu"]["star"]
    assert zhishi_palace["door"] == result["qimen"]["zhishi"]["door"]


def test_calculate_sanshiunited_analysis_respects_liureng_overrides():
    result = calculate_sanshiunited_analysis(
        date="2028-04-06",
        time="09:33:00",
        zone="+08:00",
        lat="31n13",
        lon="121e28",
        liureng_yue="申",
        liureng_is_diurnal=False,
    )

    assert result["liureng"]["month_general"]["branch"] == "申"
    assert result["liureng"]["meta"]["is_diurnal"] is False


def test_calculate_sanshiunited_analysis_applies_qimen_and_taiyi_options():
    default_result = calculate_sanshiunited_analysis(
        date="2028-04-06",
        time="09:33:00",
        zone="+08:00",
        lat="31n13",
        lon="121e28",
    )
    optioned_result = calculate_sanshiunited_analysis(
        date="2028-04-06",
        time="09:33:00",
        zone="+08:00",
        lat="31n13",
        lon="121e28",
        qimen_options={"layout": "fly"},
        taiyi_options={"accNum": 1},
    )

    assert optioned_result["qimen"] != default_result["qimen"]
    assert optioned_result["qimen"]["palaces"] != default_result["qimen"]["palaces"]
    assert optioned_result["taiyi"] != default_result["taiyi"]
    assert (
        optioned_result["taiyi"]["taiyi_palace"]
        != default_result["taiyi"]["taiyi_palace"]
    )
    assert optioned_result["subresults"]["qimen"]["pan"] == optioned_result["qimen"]
    assert optioned_result["subresults"]["taiyi"]["pan"] == optioned_result["taiyi"]
    assert optioned_result["snapshot_text"] != default_result["snapshot_text"]
    assert "内容来源：" in optioned_result["snapshot_text"]
    assert (
        "坎一宫：天盘干：丁；地盘干：己；八神：螣蛇；九星：天冲；八门：惊门；内容来源：兑七宫 / 兑"
        in optioned_result["snapshot_text"]
    )
    optioned_zhifu_palace = next(
        palace
        for palace in optioned_result["qimen"]["palaces"]
        if palace["name"] == optioned_result["qimen"]["zhifu"]["palace"]
    )
    optioned_zhishi_palace = next(
        palace
        for palace in optioned_result["qimen"]["palaces"]
        if palace["name"] == optioned_result["qimen"]["zhishi"]["palace"]
    )
    assert optioned_result["qimen"]["zhifu"]["star"] == optioned_zhifu_palace["star"]
    assert (
        optioned_result["qimen"]["zhifu"]["trigram"] == optioned_zhifu_palace["trigram"]
    )
    assert (
        optioned_result["qimen"]["zhifu"]["content_palace"]
        == optioned_zhifu_palace["content_palace"]
    )
    assert (
        optioned_result["qimen"]["zhifu"]["content_trigram"]
        == optioned_zhifu_palace["content_trigram"]
    )
    assert optioned_result["qimen"]["zhifu"]["code"]
    assert optioned_result["qimen"]["zhishi"]["door"] == optioned_zhishi_palace["door"]
    assert (
        optioned_result["qimen"]["zhishi"]["trigram"]
        == optioned_zhishi_palace["trigram"]
    )
    assert (
        optioned_result["qimen"]["zhishi"]["content_palace"]
        == optioned_zhishi_palace["content_palace"]
    )
    assert (
        optioned_result["qimen"]["zhishi"]["content_trigram"]
        == optioned_zhishi_palace["content_trigram"]
    )
    assert optioned_result["qimen"]["zhishi"]["code"]
    assert optioned_zhifu_palace["content_palace"]
    assert optioned_zhifu_palace["content_trigram"]
    assert any(
        palace["content_palace"] != palace["name"]
        or palace["content_trigram"] != palace["trigram"]
        for palace in optioned_result["qimen"]["palaces"]
    )
    assert optioned_result["qimen"]["palaces"][0]["trigram"] == "坎"


def test_calculate_sanshiunited_analysis_supports_selected_export_sections():
    result = calculate_sanshiunited_analysis(
        date="2028-04-06",
        time="09:33:00",
        zone="+08:00",
        lat="31n13",
        lon="121e28",
        selected_sections=["起盘信息", "太乙", "离九宫"],
    )

    assert result["snapshot_export"]["selected_sections"] == [
        "起盘信息",
        "太乙",
        "离九宫",
    ]
    assert "[起盘信息]" in result["snapshot_export"]["export_text"]
    assert "[太乙]" in result["snapshot_export"]["export_text"]
    assert "[离九宫]" in result["snapshot_export"]["export_text"]
    assert "[概览]" not in result["snapshot_export"]["export_text"]
    assert "[八宫详解]" not in result["snapshot_export"]["export_text"]


def test_calculate_sanshiunited_analysis_supports_true_solar_time():
    # 三式默认已开真太阳时；显式关掉得到钟表时间基线，与开启态对比。
    default_result = calculate_sanshiunited_analysis(
        date="2026-04-04",
        time="23:50:00",
        zone="+08:00",
        gps_lat=39.9,
        gps_lon=73.0,
        use_true_solar_time=False,
    )
    true_solar_result = calculate_sanshiunited_analysis(
        date="2026-04-04",
        time="23:50:00",
        zone="+08:00",
        gps_lat=39.9,
        gps_lon=73.0,
        use_true_solar_time=True,
    )

    assert true_solar_result["analysis_context"]["time_algorithm"] == "真太阳时"
    assert true_solar_result["analysis_context"]["longitude"] == 73.0
    assert true_solar_result["analysis_context"]["total_correction_minutes"] != 0
    assert (
        true_solar_result["analysis_context"]["corrected_datetime"]
        != true_solar_result["analysis_context"]["input_datetime"]
    )
    assert "真太阳时" in true_solar_result["snapshot_text"]
    assert true_solar_result["snapshot_text"] != default_result["snapshot_text"]
    assert (
        true_solar_result["sources"]["four_pillars"]["hour"]
        != default_result["sources"]["four_pillars"]["hour"]
    )


def test_local_offline_golden_samples_match_current_contract():
    assert _local_golden_projection() == {
        "tongshefa": {
            "baseLeft": "风雷益",
            "baseRight": "地雷复",
            "main_relation": "思克实",
            "summary": "已运行本地统摄法算法。本卦：左风雷益，右地雷复。主关系：思克实。",
        },
        "sixyao": {
            "current_code": "010000",
            "changed_code": "010001",
            "moving_lines": [6],
            "current_name": "地水师",
            "changed_name": "山水蒙",
        },
        "suzhan": {
            "chartVariant": "guolao_chart",
            "houseOrientation": "reverse",
            "house1": {
                "id": "House1",
                "lon": 60.0,
                "sign": "Gemini",
                "sign_zh": "双子座",
            },
            "hasUranus": False,
            "su28Count": 0,
        },
        "otherbu": {
            "planet": "Sun",
            "sign": "Aries",
            "house": 6,
            "diceHouse1Longitude": 180.0,
            "sun": {
                "id": "Sun",
                "house": "House7",
                "sign": "Aries",
                "signlon": 15.0,
                "lon": 15.0,
                "su28": "亢",
            },
        },
        "sanshiunited": {
            "qimen": {
                "ju_number": 6,
                "ju_text": "阳遁六局下元",
                "zhifu": {
                    "star": "天任",
                    "palace": "中五宫",
                    "trigram": "中",
                    "content_palace": "坤二宫",
                    "content_trigram": "坤",
                    "code": "任",
                },
                "zhishi": {
                    "door": "生门",
                    "palace": "坤二宫",
                    "trigram": "坤",
                    "content_palace": "艮八宫",
                    "content_trigram": "艮",
                    "code": "生",
                },
                "layout": "fly",
                "reference": "门迫逢旺，先阻后成。",
            },
            "taiyi": {
                "main_calculation": "陽遁五十七局（积数+1）",
                "taiyi_palace": "寅",
                "big_pattern": "龙德扶身格",
                "small_pattern": "六合入局",
            },
            "liureng": {
                "month_general": {"branch": "申", "name": "传送"},
                "is_diurnal": False,
            },
        },
    }


def test_fastmcp_meihua_tool_exposes_parameters():
    properties = mcp_parameters("meihua_analysis")["properties"]

    assert "analysis_year" in properties
    assert "analysis_month" in properties
    assert "analysis_day" in properties
    assert "analysis_hour" in properties
    assert "analysis_minute" in properties
    assert "analysis_timezone" in properties
    assert "question" in properties


def test_fastmcp_gua_lookup_tool_exposes_parameters():
    properties = mcp_parameters("gua_lookup")["properties"]

    assert "query" in properties
    assert "lookup_mode" in properties
    assert "selected_sections" in properties


def test_fastmcp_gua_meiyi_tool_exposes_parameters():
    properties = mcp_parameters("gua_meiyi")["properties"]

    assert "name" in properties
    assert "selected_sections" in properties


def test_fastmcp_local_tools_expose_parameters():
    assert "taiyin" in mcp_parameters("tongshefa")["properties"]
    assert "taiyang" in mcp_parameters("tongshefa")["properties"]

    sixyao_properties = mcp_parameters("sixyao")["properties"]
    assert "date" in sixyao_properties
    assert "time" in sixyao_properties
    assert "gua_code" in sixyao_properties
    assert "changed_code" in sixyao_properties
    assert "lines" in sixyao_properties

    suzhan_properties = mcp_parameters("suzhan")["properties"]
    assert "szchart" in suzhan_properties
    assert "szshape" in suzhan_properties
    assert "house_start_mode" in suzhan_properties
    assert "hsys" in suzhan_properties
    assert "zodiacal" in suzhan_properties

    otherbu_properties = mcp_parameters("otherbu")["properties"]
    assert "tradition" in otherbu_properties
    assert "sign" in otherbu_properties
    assert "house" in otherbu_properties
    assert "planet" in otherbu_properties
    assert "hsys" in otherbu_properties
    assert "zodiacal" in otherbu_properties

    sanshi_properties = mcp_parameters("sanshiunited")["properties"]
    assert "qimen_options" in sanshi_properties
    assert "taiyi_options" in sanshi_properties
    assert "selected_sections" in sanshi_properties
    assert "liureng_yue" in sanshi_properties
    assert "liureng_is_diurnal" in sanshi_properties
    assert "use_true_solar_time" in sanshi_properties


def test_tongshefa_hex_always_enriches_every_hexagram():
    """_hex 必须对全部 64 卦都填上 theme/judgement/image，不再静默吞错。

    回归历史 bug：_hex 用 ``except ValueError: pass`` 兜底 lookup，
    一旦卦码构造出错就静默产出缺 theme 的残卦。binary_code 由合法八卦拼成
    恒合法，lookup 永不抛错，故此处验证 64 卦全部被成功补全。
    """
    from fatebridge.core.local_techniques import tongshefa as _t

    names = ["乾", "兑", "离", "震", "巽", "坎", "艮", "坤"]
    built = 0
    for upper_name in names:
        for lower_name in names:
            hexagram = _t._hex(_t._bagua(upper_name), _t._bagua(lower_name))
            # 三个增益键必须存在且非空——证明 lookup 一定被成功消费。
            assert hexagram["theme"], hexagram["name"]
            assert hexagram["judgement"], hexagram["name"]
            assert hexagram["image"], hexagram["name"]
            built += 1
    assert built == 64


@pytest.mark.parametrize("lunar_day", range(1, 9))
@pytest.mark.parametrize("hour_branch", "子丑寅卯辰巳午未")
def test_meihua_uses_distinct_cuo_and_zong_fields(lunar_day, hour_branch):
    from fatebridge.core.divination import (
        build_meihua_interpretation,
        derive_meihua_hexagram,
    )

    meihua = derive_meihua_hexagram(
        year_branch="子", lunar_month=1, lunar_day=lunar_day, hour_branch=hour_branch
    )
    base_lines = meihua["base_hexagram"]["lines"]
    assert meihua["cuo_hexagram"]["lines"] == [1 - bit for bit in base_lines]
    assert meihua["zong_hexagram"]["lines"] == list(reversed(base_lines))
    assert "opposite_hexagram" not in meihua
    interpretation = build_meihua_interpretation(meihua)
    cuo_name = meihua["cuo_hexagram"]["name"]
    assert interpretation["cuo_reading"].startswith(f"错卦{cuo_name}")
    assert interpretation["cuo_oracle"]["name"] == cuo_name


def test_normalize_date_text_zero_pads_single_digits() -> None:
    # Both slash and dash separators, padded or not, must normalize.
    assert _normalize_date_text("2026/4/23") == "2026-04-23"
    assert _normalize_date_text("2026/04/23") == "2026-04-23"
    assert _normalize_date_text("2026-4-23") == "2026-04-23"
    assert _normalize_date_text("2026-04-23") == "2026-04-23"
    # Non-matching inputs pass through unchanged so callers get a useful
    # fromisoformat error message rather than silently corrupted data.
    assert _normalize_date_text("not-a-date") == "not-a-date"


def test_normalize_time_text_zero_pads_hours_and_seconds() -> None:
    assert _normalize_time_text("9:15") == "09:15:00"
    assert _normalize_time_text("9:5:3") == "09:05:03"
    assert _normalize_time_text("") == "00:00:00"
    assert _normalize_time_text("12:00:00") == "12:00:00"


def test_sixyao_moving_lines_honor_supplied_codes() -> None:
    """If caller passes gua_code and changed_code but no lines, the change
    flags must be derived from the codes (not from the placeholder seed,
    which would report lines 3 and 6 as moving for any request)."""
    result = build_sixyao_result(
        date="2026/04/23",
        time="12:00",
        zone="+08:00",
        lat="31n13",
        lon="121e28",
        question="audit",
        gua_code="111000",
        changed_code="110000",
    )
    assert result["moving_lines"] == [3]
    # Line 6 (上爻) had a hardcoded change=True in the old default seed — it
    # must now correctly report no change.
    assert result["lines"][5]["change"] is False
    assert "is_fuyin_line" not in result["lines"][5]
