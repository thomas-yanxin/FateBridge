import json
import re

import pytest

from fatebridge.services.metaphysics import (
    calculate_jinkou_analysis,
    calculate_liureng_gods,
    calculate_liureng_runyear,
    calculate_qimen_analysis,
    calculate_taiyi_analysis,
    calculate_ziwei_birth,
    calculate_ziwei_rules,
)
from fatebridge.utils.birth_input import create_person_info
from tests.fixtures.transports import mcp_text


def test_calculate_ziwei_birth_returns_twelve_palaces():
    person = create_person_info(
        birth_year=1994,
        birth_month=8,
        birth_day=23,
        birth_hour=14,
        name="张三",
        gender="男",
        birth_place="上海",
        birth_minute=30,
        birth_timezone="Asia/Shanghai",
    )

    result = calculate_ziwei_birth(person)

    assert result["analysis_type"] == "紫微斗数命盘"
    assert result["ziwei_birth"]["engine"] == "fatebridge-offline"
    assert result["ziwei_birth"]["time_algorithm"] in {"直接时间", "真太阳时"}
    assert len(result["ziwei_birth"]["palaces"]) == 12
    assert result["ziwei_birth"]["ming_gong"]["name"] == "命宫"
    assert result["ziwei_birth"]["shen_gong"]["name"] == "身宫"
    assert set(result["ziwei_birth"]["sihua"].keys()) == {
        "化禄",
        "化权",
        "化科",
        "化忌",
    }
    assert any(
        "紫微" in "、".join(palace["stars"])
        for palace in result["ziwei_birth"]["palaces"]
    )
    assert "[起盘信息]" in result["snapshot_text"]
    assert "[宫位总览]" in result["snapshot_text"]
    assert result["snapshot_export"]["export_text"] == result["snapshot_text"]


def test_calculate_ziwei_birth_supports_selected_export_sections():
    person = create_person_info(
        birth_year=1994,
        birth_month=8,
        birth_day=23,
        birth_hour=14,
        name="张三",
        gender="男",
        birth_place="上海",
        birth_minute=30,
        birth_timezone="Asia/Shanghai",
    )

    result = calculate_ziwei_birth(
        person,
        selected_sections=["宫位总览"],
    )

    assert result["snapshot_export"]["selected_sections"] == ["宫位总览"]
    assert "[宫位总览]" in result["snapshot_export"]["export_text"]
    assert "[起盘信息]" not in result["snapshot_export"]["export_text"]


def test_calculate_ziwei_rules_supports_year_stem_filter():
    result = calculate_ziwei_rules(year_stem="甲")

    assert result["analysis_type"] == "紫微规则库"
    assert result["engine"] == "fatebridge-offline"
    assert result["requested_year_stem"] == "甲"
    assert result["focused_rules"]["year_stem"] == "甲"
    assert set(result["focused_rules"]["sihua"].keys()) == {
        "化禄",
        "化权",
        "化科",
        "化忌",
    }
    assert "palace_sequence" in result["rule_catalogue"]
    assert "[规则概览]" in result["snapshot_text"]
    assert "[四化总表]" in result["snapshot_text"]
    assert "[当前天干四化]" in result["snapshot_text"]
    assert result["snapshot_export"]["export_text"] == result["snapshot_text"]


def test_calculate_ziwei_rules_supports_selected_export_sections():
    result = calculate_ziwei_rules(
        year_stem="甲",
        selected_sections=["规则概览", "当前天干四化"],
    )

    assert result["snapshot_export"]["selected_sections"] == [
        "规则概览",
        "当前天干四化",
    ]
    assert "[规则概览]" in result["snapshot_export"]["export_text"]
    assert "[当前天干四化]" in result["snapshot_export"]["export_text"]
    assert "[四化总表]" not in result["snapshot_export"]["export_text"]


def test_fastmcp_ziwei_birth_compact_mode_can_drop_snapshot_text():
    rendered = mcp_text(
        "ziwei_birth",
        birth_year=1994,
        birth_month=8,
        birth_day=23,
        birth_hour=14,
        name="张三",
        gender="男",
        birth_place="上海",
        birth_minute=30,
        birth_timezone="Asia/Shanghai",
        compact=True,
        include_snapshot_text=False,
    )

    payload = json.loads(rendered)

    assert "snapshot_text" not in payload
    assert "snapshot_export" in payload
    assert "\n" not in rendered


def test_fastmcp_ziwei_birth_fields_projection_trims_to_subset():
    rendered = mcp_text(
        "ziwei_birth",
        birth_year=1994,
        birth_month=8,
        birth_day=23,
        birth_hour=14,
        name="张三",
        gender="男",
        birth_place="上海",
        birth_minute=30,
        birth_timezone="Asia/Shanghai",
        fields=["snapshot_export"],
    )

    payload = json.loads(rendered)

    # Only the requested key survives; run_metadata is always preserved.
    assert set(payload) <= {"snapshot_export", "run_metadata"}
    assert "snapshot_export" in payload
    assert "snapshot_text" not in payload
    assert isinstance(payload.get("run_metadata"), dict)


def test_calculate_liureng_gods_returns_core_sections():
    result = calculate_liureng_gods(
        analysis_year=2026,
        analysis_month=4,
        analysis_day=4,
        analysis_hour=21,
        analysis_minute=18,
        analysis_timezone="Asia/Shanghai",
        analysis_longitude=121.4737,
        gender="男",
        use_true_solar_time=True,
    )

    assert result["analysis_type"] == "大六壬起课"
    assert result["liureng"]["engine"] == "fatebridge-offline"
    assert result["liureng"]["month_general"]["branch"] == "戌"
    assert result["liureng"]["month_general"]["branch"]
    assert len(result["liureng"]["four_lessons"]) == 4
    assert result["liureng"]["three_transmissions"]["initial"]["branch"]
    assert result["liureng"]["overview"]
    assert "空" in result["liureng"]["kongwang"]
    assert "[四课]" in result["snapshot_text"]
    assert "[三传]" in result["snapshot_text"]
    assert result["snapshot_export"]["export_text"] == result["snapshot_text"]


def test_calculate_liureng_runyear_uses_birth_context():
    person = create_person_info(
        birth_year=1994,
        birth_month=8,
        birth_day=23,
        birth_hour=14,
        name="张三",
        gender="男",
        birth_place="上海",
        birth_minute=30,
        birth_timezone="Asia/Shanghai",
    )

    result = calculate_liureng_runyear(
        person,
        analysis_year=2026,
        analysis_month=4,
        analysis_day=4,
        analysis_hour=21,
        analysis_minute=18,
        analysis_timezone="Asia/Shanghai",
        analysis_longitude=121.4737,
    )

    assert result["analysis_type"] == "大六壬行年"
    assert result["liureng"]["engine"] == "fatebridge-offline"
    assert result["runyear"]["engine"] == "fatebridge-offline"
    assert result["runyear"]["age"] > 0
    assert len(result["runyear"]["ganzhi"]) == 2
    assert result["liureng"]["three_transmissions"]["initial"]["branch"]
    assert "[行年]" in result["snapshot_text"]
    assert result["runyear"]["ganzhi"] in result["snapshot_text"]


def test_liureng_runyear_independent_of_birth_pillars(monkeypatch):
    # 大六壬行年以「分析时刻」起课，不依赖出生四柱的构建。
    # 回归测试：曾有一处废弃的 _build_person_seed(person) 调用，会让非法出生数据
    # 误使整个行年分析报错。即便出生四柱构建失败，行年分析也应正常返回。
    import fatebridge.services.metaphysics as meta

    def _boom(*args, **kwargs):
        raise ValueError("行年分析不应依赖出生四柱")

    monkeypatch.setattr(meta, "_build_person_seed", _boom)

    person = create_person_info(
        birth_year=1994,
        birth_month=8,
        birth_day=23,
        birth_hour=14,
        name="张三",
        gender="男",
        birth_place="上海",
    )

    result = calculate_liureng_runyear(
        person,
        analysis_year=2026,
        analysis_month=4,
        analysis_day=4,
        analysis_hour=21,
        analysis_minute=18,
        analysis_timezone="Asia/Shanghai",
        analysis_longitude=121.4737,
    )

    assert "error" not in result
    assert result["analysis_type"] == "大六壬行年"
    assert result["runyear"]["engine"] == "fatebridge-offline"


def test_calculate_liureng_gods_distinguishes_liuhe_style():
    # A 六合 relation is not a transmission method. Multiple thieves require
    # 涉害 after 比用, rather than unconditionally being labelled 重审.
    result = calculate_liureng_gods(
        analysis_year=2028,
        analysis_month=4,
        analysis_day=6,
        analysis_hour=9,
        analysis_minute=33,
        analysis_timezone="Asia/Shanghai",
        analysis_longitude=121.4667,
        gender="男",
    )
    first = result["liureng"]["four_lessons"][0]
    assert first["relations"]["with_lower_branch"] == "六合"
    assert first["style_hint"] == "六合"
    assert result["liureng"]["board_style"] == "涉害"


def test_calculate_liureng_gods_uses_zeike_transmission_rule():
    # Independent daliurenpython reference: 辛酉日, +5 sky offset.
    result = calculate_liureng_gods(
        analysis_year=2028,
        analysis_month=4,
        analysis_day=6,
        analysis_hour=9,
        analysis_minute=33,
        analysis_timezone="Asia/Shanghai",
        analysis_longitude=121.4667,
        gender="男",
    )
    transmissions = result["liureng"]["three_transmissions"]
    assert result["liureng"]["board_style"] == "涉害"
    assert [transmissions[k]["branch"] for k in ("initial", "middle", "final")] == [
        "未",
        "子",
        "巳",
    ]


def test_calculate_liureng_gods_uses_fanyin_transmission_rule():
    # 经典返吟条件：月将 与 占时 正好相冲。 2026-01-01 冬至期 月将=丑，故占时需落 未时
    # (丑冲未)，即 13:00-15:00。14:00 = 未时。
    result = calculate_liureng_gods(
        analysis_year=2026,
        analysis_month=1,
        analysis_day=1,
        analysis_hour=14,
        analysis_minute=0,
        analysis_timezone="Asia/Shanghai",
        analysis_longitude=121.4737,
        gender="男",
    )

    transmissions = result["liureng"]["three_transmissions"]
    assert result["liureng"]["board_style"] == "返吟"
    assert transmissions["method"] == "返吟贼克"
    # 阴日 (乙)：初=支上 (亥的上神=sky[亥]=巳)；中=初之冲=亥；末=sky[中]=巳。
    assert transmissions["initial"]["branch"] == "巳"
    assert transmissions["middle"]["branch"] == "亥"
    assert transmissions["final"]["branch"] == "巳"


def test_calculate_liureng_gods_uses_fuyin_transmission_rule():
    # 六乙日伏吟 first lesson is a genuine 下贼上 (乙木克辰土), so the
    # stem's upper god starts the chain. Initial self-punishment then moves
    # to the branch god; a self-punishing middle moves to its opposing god.
    result = calculate_liureng_gods(
        analysis_year=2026,
        analysis_month=1,
        analysis_day=1,
        analysis_hour=2,
        analysis_timezone="Asia/Shanghai",
        analysis_longitude=121.4737,
        gender="男",
    )
    transmissions = result["liureng"]["three_transmissions"]
    assert result["liureng"]["board_style"] == "伏吟"
    assert transmissions["method"] == "伏吟循刑"
    assert [transmissions[k]["branch"] for k in ("initial", "middle", "final")] == [
        "辰",
        "亥",
        "巳",
    ]


def test_calculate_liureng_gods_prefers_zeike_over_yaoke():
    # 2026-01-01 18:00 (乙亥日酉时, 月将丑) 四课上下存在 下贼上 (课4 未克卯)，
    # 依 贼克优先 于 遥克 原则，应以 重审 为课体，而非 遥克。选用课 index=4。
    result = calculate_liureng_gods(
        analysis_year=2026,
        analysis_month=1,
        analysis_day=1,
        analysis_hour=18,
        analysis_minute=0,
        analysis_timezone="Asia/Shanghai",
        analysis_longitude=121.4737,
        gender="男",
    )

    assert result["liureng"]["board_style"] == "重审"
    assert result["liureng"]["board_style_detail"] == "重审"
    assert result["liureng"]["meta"]["selected_lesson_index"] == 4


def test_calculate_liureng_gods_bazhuan_day_still_prefers_direct_clash():
    # 甲寅日 is an 八专 day, but 酉金克甲木 in the first lesson takes
    # precedence over the no-clash 八专 method.
    result = calculate_liureng_gods(
        analysis_year=2026,
        analysis_month=2,
        analysis_day=9,
        analysis_hour=10,
        analysis_timezone="Asia/Shanghai",
        analysis_longitude=121.4737,
        gender="男",
    )
    assert result["liureng"]["board_style_detail"] == "元首"
    assert result["liureng"]["meta"]["selected_lesson_relation"] == "上克下"


def test_calculate_liureng_gods_remote_clash_precedes_bieze():
    result = calculate_liureng_gods(
        analysis_year=2026,
        analysis_month=1,
        analysis_day=2,
        analysis_hour=10,
        analysis_timezone="Asia/Shanghai",
        analysis_longitude=121.4737,
        gender="男",
    )
    assert result["liureng"]["board_style"] == "遥克"
    assert result["liureng"]["board_style_detail"] == "弹射"
    assert [
        result["liureng"]["three_transmissions"][k]["branch"]
        for k in ("initial", "middle", "final")
    ] == ["申", "辰", "子"]


def test_calculate_liureng_gods_marks_zhongshen_detail():
    # 重审课 = 下贼上。 2026-01-06 09:00 (庚辰日巳时) 月将=丑。四课中 课2 上子下辰为下贼上
    # (辰土克子水)，发用从 课2，整体课体为 "重审"。
    result = calculate_liureng_gods(
        analysis_year=2026,
        analysis_month=1,
        analysis_day=6,
        analysis_hour=9,
        analysis_minute=0,
        analysis_timezone="Asia/Shanghai",
        analysis_longitude=121.4737,
        gender="男",
    )

    assert result["liureng"]["board_style_detail"] == "重审"
    assert result["liureng"]["meta"]["selected_lesson_relation"] == "下贼上"
    assert any(pattern["name"] == "重审课" for pattern in result["liureng"]["patterns"])


def test_calculate_liureng_gods_first_lesson_uses_stem_element():
    result = calculate_liureng_gods(
        analysis_year=2026,
        analysis_month=1,
        analysis_day=3,
        analysis_hour=0,
        analysis_minute=0,
        analysis_timezone="Asia/Shanghai",
        analysis_longitude=121.4737,
        gender="男",
    )

    assert result["liureng"]["board_style_detail"] == "重审"
    assert result["liureng"]["meta"]["selected_lesson_relation"] == "下贼上"
    assert any(pattern["name"] == "重审课" for pattern in result["liureng"]["patterns"])


def test_calculate_qimen_analysis_returns_nine_palaces():
    result = calculate_qimen_analysis(
        analysis_year=2026,
        analysis_month=4,
        analysis_day=4,
        analysis_hour=21,
        analysis_minute=18,
        analysis_timezone="Asia/Shanghai",
        analysis_longitude=121.4737,
        use_true_solar_time=True,
    )

    assert result["analysis_type"] == "奇门遁甲"
    assert result["qimen"]["dun_type"] in {"阳遁", "阴遁"}
    assert len(result["qimen"]["palaces"]) == 9
    assert result["qimen"]["zhifu"]["star"]
    assert result["qimen"]["zhishi"]["door"]
    assert result["qimen"]["palaces"][0]["door_hexagram"]["name"]
    assert (
        result["qimen"]["palaces"][0]["content_palace"]
        == result["qimen"]["palaces"][0]["name"]
    )
    assert (
        result["qimen"]["palaces"][0]["content_trigram"]
        == result["qimen"]["palaces"][0]["trigram"]
    )
    assert "[八宫详解]" in result["snapshot_text"]
    assert "[九宫方盘]" in result["snapshot_text"]
    assert "[奇门演卦]" in result["snapshot_text"]
    assert result["snapshot_export"]["export_text"] == result["snapshot_text"]
    assert "离九宫" in result["snapshot_export"]["section_titles_detected"]


def test_metaphysics_true_solar_time_includes_equation_of_time():
    result = calculate_qimen_analysis(
        analysis_year=2026,
        analysis_month=4,
        analysis_day=4,
        analysis_hour=21,
        analysis_minute=18,
        analysis_timezone="Asia/Shanghai",
        analysis_longitude=121.4737,
        use_true_solar_time=True,
    )

    # Direct Swiss Ephemeris 2.10.03 reference, outside FateBridge's helpers:
    # jd_ut=2461135.0541666667 (13:18 UTC), time_equ=-2.935413924 min,
    # longitude=+5.8948 min, total=+2.959386076 min. The old 2.51 value came
    # from a date-only sinusoidal approximation. This is a library integration
    # reference, not an independent astronomical accuracy certificate.
    assert result["analysis_context"]["time_algorithm"] == "真太阳时"
    assert result["analysis_context"]["corrected_datetime"].startswith(
        "2026-04-04 21:20:"
    )
    assert result["analysis_context"]["total_correction_minutes"] == pytest.approx(
        2.959386076, abs=0.05
    )
    assert result["four_pillars"] == {
        "year": {"stem": "丙", "branch": "午"},
        "month": {"stem": "辛", "branch": "卯"},
        "day": {"stem": "戊", "branch": "申"},
        "hour": {"stem": "癸", "branch": "亥"},
    }
    assert result["qimen"]["ju_text"] == "阳遁六局下元"
    assert result["qimen"]["yuan"] == "下元"
    assert result["qimen"]["fu_tou"] == "甲辰"
    assert result["qimen"]["day_xun_head"] == "甲辰"
    assert result["qimen"]["xun_head"] == "甲寅"
    assert result["qimen"]["day_kongwang"] == "寅卯空"
    assert result["qimen"]["kongwang"] == "子丑空"
    assert result["qimen"]["zhifu"] == {
        "star": "天芮",
        "palace": "坤二宫",
        "trigram": "坤",
        "content_palace": "坤二宫",
        "content_trigram": "坤",
        "code": "芮",
    }
    assert result["qimen"]["zhishi"] == {
        "door": "死门",
        "palace": "坤二宫",
        "trigram": "坤",
        "content_palace": "坤二宫",
        "content_trigram": "坤",
        "code": "死",
    }
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
    assert "值符：天芮在坤二宫" in result["snapshot_text"]


def test_calculate_qimen_analysis_applies_qimen_options_and_snapshot_text():
    default_result = calculate_qimen_analysis(
        analysis_year=2028,
        analysis_month=4,
        analysis_day=6,
        analysis_hour=9,
        analysis_minute=33,
        analysis_timezone="Asia/Shanghai",
        analysis_longitude=121.4737,
    )
    optioned_result = calculate_qimen_analysis(
        analysis_year=2028,
        analysis_month=4,
        analysis_day=6,
        analysis_hour=9,
        analysis_minute=33,
        analysis_timezone="Asia/Shanghai",
        analysis_longitude=121.4737,
        qimen_options={"ju_method": "chaibu"},
    )

    assert optioned_result["qimen"]["ju_method"] == "chaibu"
    assert optioned_result["qimen"]["ju_term"] == "清明"
    assert optioned_result["qimen"]["ju_number"] == 7
    assert default_result["qimen"]["ju_number"] == 6
    assert optioned_result["snapshot_text"] != default_result["snapshot_text"]
    assert "[九宫方盘]" in optioned_result["snapshot_text"]
    assert "定局所用节气：清明" in optioned_result["snapshot_text"]


def test_calculate_qimen_analysis_supports_selected_export_sections():
    result = calculate_qimen_analysis(
        analysis_year=2028,
        analysis_month=4,
        analysis_day=6,
        analysis_hour=9,
        analysis_minute=33,
        analysis_timezone="Asia/Shanghai",
        analysis_longitude=121.4737,
        selected_sections=["起盘信息", "九宫方盘", "离九宫"],
    )

    assert "[八宫详解]" in result["snapshot_text"]
    assert result["snapshot_export"]["selected_sections"] == [
        "起盘信息",
        "九宫方盘",
        "离九宫",
    ]
    assert "[起盘信息]" in result["snapshot_export"]["export_text"]
    assert "[九宫方盘]" in result["snapshot_export"]["export_text"]
    assert "[离九宫]" in result["snapshot_export"]["export_text"]
    assert "[八宫详解]" not in result["snapshot_export"]["export_text"]


def test_calculate_taiyi_analysis_returns_sixteen_palaces():
    result = calculate_taiyi_analysis(
        analysis_year=2026,
        analysis_month=4,
        analysis_day=4,
        analysis_hour=21,
        analysis_minute=18,
        analysis_timezone="Asia/Shanghai",
        analysis_longitude=121.4737,
        gender="男",
        use_true_solar_time=True,
    )

    assert result["analysis_type"] == "太乙神数"
    assert result["taiyi"]["style_label"]
    # 金镜年计核心：724年的积年1937281逐年加一，2026年为1938583，55局。
    # 完整主客算独立验收见 test_taiyi_accuracy.py；软件同源一致不认证原典。
    assert result["taiyi"]["taiyi_palace"] == "艮"
    assert result["taiyi"]["wenchang_palace"] == "申"
    assert len(result["taiyi"]["palace_marks"]) == 16
    assert result["taiyi"]["core_board"]["main_calculation"] == "陽遁五十五局"
    assert result["taiyi"]["core_board"]["kook_number"] == 55
    assert result["taiyi"]["core_board"]["shiji"] == "艮"
    assert "[太乙盘]" in result["snapshot_text"]
    assert "[十六宫标记]" in result["snapshot_text"]
    assert result["snapshot_export"]["export_text"] == result["snapshot_text"]


def test_calculate_liureng_gods_supports_selected_export_sections():
    result = calculate_liureng_gods(
        analysis_year=2026,
        analysis_month=4,
        analysis_day=4,
        analysis_hour=21,
        analysis_minute=18,
        analysis_timezone="Asia/Shanghai",
        analysis_longitude=121.4737,
        gender="男",
        selected_sections=["起盘信息", "三传", "概览"],
    )

    assert result["snapshot_export"]["selected_sections"] == [
        "起盘信息",
        "三传",
        "概览",
    ]
    assert "[起盘信息]" in result["snapshot_export"]["export_text"]
    assert "[三传]" in result["snapshot_export"]["export_text"]
    assert "[概览]" in result["snapshot_export"]["export_text"]
    assert "[四课]" not in result["snapshot_export"]["export_text"]


def test_calculate_taiyi_analysis_supports_selected_export_sections():
    result = calculate_taiyi_analysis(
        analysis_year=2026,
        analysis_month=4,
        analysis_day=4,
        analysis_hour=21,
        analysis_minute=18,
        analysis_timezone="Asia/Shanghai",
        analysis_longitude=121.4737,
        gender="男",
        selected_sections=["起盘信息", "十六宫标记"],
    )

    assert result["snapshot_export"]["selected_sections"] == ["起盘信息", "十六宫标记"]
    assert "[起盘信息]" in result["snapshot_export"]["export_text"]
    assert "[十六宫标记]" in result["snapshot_export"]["export_text"]
    assert "[太乙盘]" not in result["snapshot_export"]["export_text"]


def test_calculate_jinkou_analysis_returns_four_positions():
    result = calculate_jinkou_analysis(
        analysis_year=2026,
        analysis_month=4,
        analysis_day=4,
        analysis_hour=21,
        analysis_minute=18,
        analysis_timezone="Asia/Shanghai",
        analysis_longitude=121.4737,
        gender="男",
        di_fen="酉",
        use_true_solar_time=True,
    )

    assert result["analysis_type"] == "金口诀"
    assert result["liureng"]["engine"] == "fatebridge-offline"
    assert result["jinkou"]["engine"] == "fatebridge-offline"
    assert result["liureng"]["month_general"]["branch"] == "戌"
    assert result["jinkou"]["overview"]["di_fen"] == "酉"
    assert result["jinkou"]["overview"]["yuejiang"]["branch"] == "申"
    # 金口诀戊日夜贵未：未贵、午蛇……酉太阴，不能借用大六壬天盘。
    assert result["jinkou"]["overview"]["guishen"]["name"] == "太阴"
    assert result["jinkou"]["overview"]["guishen"]["branch"] == "酉"
    assert result["jinkou"]["overview"]["board_style"] == "金口诀四位"
    assert result["jinkou"]["overview"]["use_position"] in {
        "人元",
        "贵神",
        "将神",
        "地分",
    }
    assert len(result["jinkou"]["rows"]) == 4
    assert result["jinkou"]["overview"]["yuejiang"]["name"]
    assert result["jinkou"]["overview"]["guishen"]["name"]
    assert result["jinkou"]["shensha"]
    assert "[金口诀速览]" in result["snapshot_text"]
    assert "[金口诀四位]" in result["snapshot_text"]
    assert "[四位神煞]" in result["snapshot_text"]
    assert result["snapshot_export"]["export_text"] == result["snapshot_text"]


def test_calculate_jinkou_analysis_does_not_borrow_liureng_transmission_rule():
    result = calculate_jinkou_analysis(
        analysis_year=2026,
        analysis_month=1,
        analysis_day=2,
        analysis_hour=10,
        analysis_minute=0,
        analysis_timezone="Asia/Shanghai",
        analysis_longitude=121.4737,
        gender="男",
        di_fen="巳",
    )

    assert result["liureng"]["board_style_detail"] == "弹射"
    assert result["jinkou"]["overview"]["board_style_detail"] == "三阴一阳"
    # 丙子日巳时巳位：癸 / 天空戌 / 大吉丑 / 巳，唯一阳位是贵神。
    assert result["jinkou"]["overview"]["use_position"] == "贵神"
    assert all(
        item["label"] not in {"课体", "取传"} for item in result["jinkou"]["shensha"]
    )


def test_calculate_jinkou_analysis_supports_selected_export_sections():
    result = calculate_jinkou_analysis(
        analysis_year=2026,
        analysis_month=4,
        analysis_day=4,
        analysis_hour=21,
        analysis_minute=18,
        analysis_timezone="Asia/Shanghai",
        analysis_longitude=121.4737,
        gender="男",
        di_fen="酉",
        selected_sections=["起盘信息", "金口诀四位"],
    )

    assert result["snapshot_export"]["selected_sections"] == ["起盘信息", "金口诀四位"]
    assert "[起盘信息]" in result["snapshot_export"]["export_text"]
    assert "[金口诀四位]" in result["snapshot_export"]["export_text"]
    assert "[四位神煞]" not in result["snapshot_export"]["export_text"]


def test_ziwei_birth_palaces_have_stars_detail():
    person = create_person_info(
        birth_year=1994,
        birth_month=8,
        birth_day=23,
        birth_hour=14,
        name="张三",
        gender="男",
        birth_place="上海",
        birth_minute=30,
        birth_timezone="Asia/Shanghai",
    )

    result = calculate_ziwei_birth(person)
    palaces = result["ziwei_birth"]["palaces"]

    for palace in palaces:
        # additive: legacy `stars` list is preserved unchanged
        assert "stars" in palace
        assert "stars_detail" in palace
        # a star-less palace must still carry stars_detail as an empty list
        assert isinstance(palace["stars_detail"], list)
        assert len(palace["stars_detail"]) == len(palace["stars"])
        for legacy, detail in zip(palace["stars"], palace["stars_detail"]):
            assert legacy == detail["label"]
            assert set(detail.keys()) == {"name", "label", "brightness", "mutagen"}

    # at least one major star must carry a non-null brightness
    all_details = [d for p in palaces for d in p["stars_detail"]]
    assert any(d["brightness"] is not None for d in all_details)

    # mutagen parsing: any 化X suffix in legacy stars surfaces in detail.mutagen
    for palace in palaces:
        for detail in palace["stars_detail"]:
            if detail["mutagen"] is not None:
                assert detail["label"] == f"{detail['name']}{detail['mutagen']}"
                assert detail["mutagen"] in {"化禄", "化权", "化科", "化忌"}


def test_ziwei_snapshot_text_annotates_brightness():
    person = create_person_info(
        birth_year=1994,
        birth_month=8,
        birth_day=23,
        birth_hour=14,
        name="张三",
        gender="男",
        birth_place="上海",
        birth_minute=30,
        birth_timezone="Asia/Shanghai",
    )

    result = calculate_ziwei_birth(person)
    snapshot = result["snapshot_text"]

    # brightness must render as `star(brightness)` — a brightness char in
    # parentheses immediately after a star name (e.g. "紫微(庙)", "廉贞化禄(利)"),
    # not merely somewhere in the text.
    assert re.search(r"[一-鿿]+\([庙旺得利平不陷]\)", snapshot)


def test_ziwei_horoscope_request_requires_target_datetime():
    from fatebridge.core.requests.metaphysics import ZiweiHoroscopeRequest

    req = ZiweiHoroscopeRequest(
        gender="男",
        birth_year=1994,
        birth_month=8,
        birth_day=23,
        birth_hour=14,
        target_year=2026,
        target_month=6,
        target_day=19,
        target_hour=14,
    )
    payload = req.model_dump()
    assert payload["target_year"] == 2026
    assert payload["target_month"] == 6
    assert payload["target_day"] == 19
    assert payload["target_hour"] == 14

    import pytest as _pytest
    from pydantic import ValidationError

    with _pytest.raises(ValidationError):
        ZiweiHoroscopeRequest(  # missing target_* → invalid
            gender="男",
            birth_year=1994,
            birth_month=8,
            birth_day=23,
            birth_hour=14,
        )


def test_calculate_ziwei_horoscope_returns_six_scopes_and_snapshot():
    from fatebridge.services.metaphysics import calculate_ziwei_horoscope

    person = create_person_info(
        birth_year=1994,
        birth_month=8,
        birth_day=23,
        birth_hour=14,
        gender="男",
    )
    result = calculate_ziwei_horoscope(
        person,
        target_year=2026,
        target_month=6,
        target_day=19,
        target_hour=14,
    )
    assert result["analysis_type"] == "紫微斗数运限"
    h = result["ziwei_horoscope"]
    assert h["engine"] == "fatebridge-offline"
    assert h["nominal_age"] == 2026 - 1994 + 1  # 虚岁 drives 大限 selection
    assert {s["scope"] for s in h["scopes"]} == {
        "大限",
        "小限",
        "流年",
        "流月",
        "流日",
        "流时",
    }
    assert "[起盘信息]" in result["snapshot_text"]
    assert "[流年]" in result["snapshot_text"]
    assert result["snapshot_export"]["export_text"] == result["snapshot_text"]


def test_calculate_ziwei_horoscope_supports_selected_sections():
    from fatebridge.services.metaphysics import calculate_ziwei_horoscope

    person = create_person_info(
        birth_year=1994,
        birth_month=8,
        birth_day=23,
        birth_hour=14,
        gender="男",
    )
    result = calculate_ziwei_horoscope(
        person,
        target_year=2026,
        target_month=6,
        target_day=19,
        target_hour=14,
        selected_sections=["流年"],
    )
    assert result["snapshot_export"]["selected_sections"] == ["流年"]
    assert "[流年]" in result["snapshot_export"]["export_text"]
    assert "[起盘信息]" not in result["snapshot_export"]["export_text"]


def test_ziwei_horoscope_registered_on_all_surfaces():
    from fatebridge.services.tool_catalog import mcp_specs, rest_specs

    assert any(getattr(s, "key", None) == "ziwei_horoscope" for s in rest_specs())
    assert any(getattr(s, "mcp_name", None) == "ziwei_horoscope" for s in mcp_specs())
