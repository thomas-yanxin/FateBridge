"""三端（REST / MCP）代表性 payload 的单一信源。

`full_surface` 契约测试与 `golden-master` 数值锁都从这里取输入，确保两套
回归用的是同一组确定性夹具。
"""

from __future__ import annotations

from tests.fixtures.fengshui import PAYLOADS
from tests.fixtures.fengshui import payload as fengshui_payload


def _birth_payload(
    *,
    name: str = "张三",
    gender: str = "男",
    birth_place: str = "上海",
    birth_longitude: float = 121.4737,
) -> dict:
    return {
        "name": name,
        "gender": gender,
        "birth_year": 1990,
        "birth_month": 5,
        "birth_day": 15,
        "birth_hour": 10,
        "birth_minute": 30,
        "birth_timezone": "Asia/Shanghai",
        "birth_longitude": birth_longitude,
        "birth_place": birth_place,
        "use_true_solar_time": False,
    }


def astro_payload(
    *,
    name: str = "测试者",
    birth_place: str = "上海",
    birth_longitude: float = 121.4667,
    birth_latitude: float = 31.2167,
) -> dict:
    return {
        "name": name,
        "birth_year": 1990,
        "birth_month": 4,
        "birth_day": 6,
        "birth_hour": 9,
        "birth_minute": 33,
        "birth_timezone": "Asia/Shanghai",
        "birth_longitude": birth_longitude,
        "birth_latitude": birth_latitude,
        "birth_place": birth_place,
    }


def western_payload() -> dict:
    return {
        "name": "Alice",
        "birth_year": 1990,
        "birth_month": 5,
        "birth_day": 17,
        "birth_hour": 15,
        "birth_minute": 30,
        "birth_place": "上海",
        "birth_timezone": "Asia/Shanghai",
        "birth_longitude": 121.4737,
        "birth_latitude": 31.2304,
        "analysis_year": 2025,
        "analysis_month": 5,
        "analysis_day": 20,
        "pd_method": "astroapp_alchabitius",
        "pd_time_key": "Naibod",
        "pd_aspects": [0, 90, 180],
        "show_pd_bounds": True,
    }


def _mundane_payload() -> dict:
    return {
        "year": 2026,
        "ingress_term": "春分",
        "longitude": 116.4074,
        "latitude": 39.9042,
        "timezone_name": "Asia/Shanghai",
    }


def _horary_payload() -> dict:
    return {
        "question_year": 2024,
        "question_month": 6,
        "question_day": 1,
        "question_hour": 14,
        "question_minute": 30,
        "timezone_name": "Asia/Shanghai",
        "longitude": 116.4074,
        "latitude": 39.9042,
        "category": "marriage",
    }


def _election_payload() -> dict:
    return {
        "candidate_year": 2025,
        "candidate_month": 3,
        "candidate_day": 15,
        "candidate_hour": 10,
        "candidate_minute": 0,
        "timezone_name": "Asia/Shanghai",
        "longitude": 116.4074,
        "latitude": 39.9042,
        "topic_id": "marriage",
    }


def _metaphysics_payload() -> dict:
    return {
        "analysis_year": 2026,
        "analysis_month": 4,
        "analysis_day": 8,
        "analysis_hour": 9,
        "analysis_minute": 30,
        "analysis_timezone": "Asia/Shanghai",
        "analysis_longitude": 121.4737,
        "selected_sections": ["起盘信息", "九宫方盘"],
        "use_true_solar_time": False,
    }


def _compatibility_payload() -> dict:
    return {
        "person1_name": "甲",
        "person1_birth_year": 1990,
        "person1_birth_month": 5,
        "person1_birth_day": 15,
        "person1_birth_hour": 10,
        "person1_birth_minute": 30,
        "person1_gender": "男",
        "person1_birth_place": "上海",
        "person1_birth_timezone": "Asia/Shanghai",
        "person1_birth_longitude": 121.4737,
        "person2_name": "乙",
        "person2_birth_year": 1992,
        "person2_birth_month": 3,
        "person2_birth_day": 2,
        "person2_birth_hour": 8,
        "person2_birth_minute": 18,
        "person2_gender": "女",
        "person2_birth_place": "北京",
        "person2_birth_timezone": "Asia/Shanghai",
        "person2_birth_longitude": 116.4074,
        "relationship_type": "marriage",
    }


def _relative_payload() -> dict:
    return {
        "inner": {
            **astro_payload(name="甲"),
        },
        "outer": {
            **astro_payload(
                name="乙",
                birth_place="北京",
                birth_longitude=116.4074,
                birth_latitude=39.9042,
            ),
            "birth_year": 1992,
            "birth_month": 3,
            "birth_day": 2,
            "birth_hour": 8,
            "birth_minute": 18,
        },
        "relative_mode": "Composite",
        "hsys": 0,
        "zodiacal": 0,
    }


def _relative_mcp_kwargs() -> dict:
    return {
        "inner_birth_year": 1990,
        "inner_birth_month": 4,
        "inner_birth_day": 6,
        "inner_birth_hour": 9,
        "inner_birth_minute": 33,
        "inner_birth_timezone": "Asia/Shanghai",
        "inner_birth_longitude": 121.4667,
        "inner_birth_latitude": 31.2167,
        "inner_name": "甲",
        "inner_birth_place": "上海",
        "outer_birth_year": 1992,
        "outer_birth_month": 3,
        "outer_birth_day": 2,
        "outer_birth_hour": 8,
        "outer_birth_minute": 18,
        "outer_birth_timezone": "Asia/Shanghai",
        "outer_birth_longitude": 116.4074,
        "outer_birth_latitude": 39.9042,
        "outer_name": "乙",
        "outer_birth_place": "北京",
        "relative_mode": "Composite",
        "hsys": 0,
        "zodiacal": 0,
    }


def _local_base() -> dict:
    return {
        "date": "2028-04-06",
        "time": "09:33:00",
        "zone": "+08:00",
        "lat": "31n13",
        "lon": "121e28",
    }


def _export_content() -> str:
    return "\n".join(
        [
            "[起盘信息]",
            "排盘参数",
            "",
            "[八宫详解]",
            "这里是八宫详解内容",
            "",
            "[奇门演卦]",
            "这里是奇门演卦内容",
        ]
    )


REST_POST_CASES = {
    "/api/cn/bazi/birth": lambda: _birth_payload(),
    "/api/cn/bazi/marriage": lambda: {
        **_birth_payload(),
        "dayun_pillar": "壬戌",
        "liunian_pillar": "丁卯",
    },
    "/api/cn/bazi/career": lambda: {
        **_birth_payload(),
        "dayun_pillar": "壬戌",
        "liunian_pillar": "丁卯",
    },
    "/api/cn/bazi/wealth": lambda: {
        **_birth_payload(),
        "dayun_pillar": "壬戌",
        "liunian_pillar": "丁卯",
    },
    "/api/cn/bazi/health": lambda: {
        **_birth_payload(),
        "dayun_pillar": "壬戌",
        "liunian_pillar": "丁卯",
    },
    "/api/cn/bazi/children": lambda: {
        **_birth_payload(),
        "dayun_pillar": "壬戌",
        "liunian_pillar": "丁卯",
    },
    "/api/cn/bazi/education": lambda: {
        **_birth_payload(),
        "dayun_pillar": "壬戌",
        "liunian_pillar": "丁卯",
    },
    "/api/cn/bazi/personality": lambda: {
        **_birth_payload(),
        "dayun_pillar": "壬戌",
        "liunian_pillar": "丁卯",
    },
    "/api/cn/bazi/relatives": lambda: {
        **_birth_payload(),
        "dayun_pillar": "壬戌",
        "liunian_pillar": "丁卯",
    },
    "/api/cn/bazi/romance": lambda: {
        **_birth_payload(),
        "dayun_pillar": "壬戌",
        "liunian_pillar": "丁卯",
    },
    "/api/compatibility": _compatibility_payload,
    "/api/timing/comprehensive": lambda: {
        **_birth_payload(),
        "analysis_year": 2028,
        "analysis_month": 4,
        "analysis_day": 6,
        "analysis_hour": 21,
        "analysis_minute": 55,
        "analysis_age": 38,
        "selected_sections": ["查询信息", "综合影响"],
    },
    "/api/timing/dayun": lambda: {
        **_birth_payload(),
        "analysis_age": 38,
        "selected_sections": ["查询信息", "大运信息"],
    },
    "/api/timing/liunian": lambda: {
        **_birth_payload(),
        "target_year": 2028,
    },
    "/api/divination/gua": lambda: {
        "query": "111111",
        "lookup_mode": "hexagram",
        "selected_sections": ["查询信息", "义理摘要"],
    },
    "/api/cn/jieqi/year": lambda: {
        "year": 2028,
        "zone": "Asia/Shanghai",
        "lat": "31n13",
        "lon": "121e28",
        "jieqis": ["春分", "冬至"],
        "selected_sections": ["查询信息", "重点节气"],
    },
    "/api/cn/nongli/time": lambda: {
        "date": "2028-04-01",
        "time": "09:00:00",
        "zone": "Asia/Shanghai",
        "lon": "121e28",
        "selected_sections": ["农历上下文", "四柱上下文"],
    },
    "/api/cn/gua/meiyi": lambda: {
        "name": ["111", "000"],
        "selected_sections": ["查询概览", "批量结果"],
    },
    "/api/export/registry": lambda: {
        "technique": "qimen",
    },
    "/api/export/parse": lambda: {
        "technique": "qimen",
        "content": _export_content(),
        "selected_sections": ["起盘信息", "八宫详解", "奇门演卦"],
    },
    "/api/knowledge/registry": lambda: {
        "domain": "astro",
        "selected_sections": ["目录概览", "astro"],
    },
    "/api/knowledge/read": lambda: {
        "domain": "astro",
        "category": "aspect",
        "aspect_degree": 90,
        "object_a": "Sun",
        "object_b": "Jupiter",
        "selected_sections": ["查询信息", "知识正文"],
    },
    "/api/divination/meihua": lambda: {
        "analysis_year": 2028,
        "analysis_month": 4,
        "analysis_day": 1,
        "analysis_hour": 9,
        "analysis_minute": 0,
        "analysis_timezone": "Asia/Shanghai",
        "question": "事业推进节奏",
    },
    "/api/divination/tongshefa": lambda: {
        "taiyin": "巽",
        "taiyang": "坤",
        "shaoyang": "震",
        "shaoyin": "震",
    },
    "/api/divination/sixyao": lambda: {
        **_local_base(),
        "gps_lat": 31.2,
        "gps_lon": 121.4,
    },
    "/api/divination/canping": lambda: {
        **_local_base(),
        "gender": "男",
        "method": "ming",
    },
    "/api/divination/heluo": lambda: {
        # mid-立夏 quarter, far from any 节气 boundary or 四立 土用 window → the
        # 节气-coupled 命运篇 stays cross-platform deterministic for the golden.
        **_local_base(),
        "date": "2000-05-15",
        "time": "09:33:00",
        "gender": "男",
    },
    "/api/divination/suzhan": lambda: {
        **_local_base(),
        "szchart": 1,
        "szshape": 1,
        "house_start_mode": 2,
        "doubing_su28": False,
    },
    "/api/compatibility/sukuyo": lambda: {
        "person1_date": "1990-06-15",
        "person1_time": "08:30:00",
        "person2_date": "1992-03-20",
        "person2_time": "14:00:00",
    },
    "/api/divination/otherbu": lambda: {
        **_local_base(),
        "sign": "Aries",
        "house": 6,
        "planet": "Sun",
        "question": "合作",
    },
    "/api/divination/sanshiunited": lambda: {
        **_local_base(),
        "qimen_options": {"layout": "fly"},
        "taiyi_options": {"accNum": 1},
        "liureng_yue": "申",
        "liureng_is_diurnal": False,
    },
    "/api/cn/ziwei/birth": lambda: {
        **_birth_payload(name="张三", gender="男"),
        "birth_year": 1994,
        "birth_month": 8,
        "birth_day": 23,
        "birth_hour": 14,
        "selected_sections": ["起盘信息", "宫位总览"],
    },
    "/api/cn/ziwei/horoscope": lambda: {
        **_birth_payload(name="张三", gender="男"),
        "birth_year": 1994,
        "birth_month": 8,
        "birth_day": 23,
        "birth_hour": 14,
        "target_year": 2026,
        "target_month": 6,
        "target_day": 19,
        "target_hour": 14,
    },
    "/api/cn/ziwei/rules": lambda: {
        "year_stem": "甲",
        "selected_sections": ["规则概览", "当前天干四化"],
    },
    "/api/cn/liureng/gods": lambda: {
        **_metaphysics_payload(),
        "gender": "男",
        "selected_sections": ["起盘信息", "三传"],
    },
    "/api/cn/liureng/runyear": lambda: {
        **_birth_payload(name="张三", gender="男"),
        "birth_year": 1994,
        "birth_month": 8,
        "birth_day": 23,
        "birth_hour": 14,
        "analysis_year": 2026,
        "analysis_month": 4,
        "analysis_day": 4,
        "analysis_hour": 21,
        "analysis_minute": 18,
        "analysis_timezone": "Asia/Shanghai",
        "analysis_longitude": 121.4737,
        "selected_sections": ["起盘信息", "行年"],
    },
    "/api/cn/qimen": lambda: {
        **_metaphysics_payload(),
        "qimen_options": {"layout": "rotating"},
    },
    "/api/cn/taiyi": lambda: {
        **_metaphysics_payload(),
        "gender": "男",
        "selected_sections": ["起盘信息", "太乙"],
    },
    "/api/cn/jinkou": lambda: {
        **_metaphysics_payload(),
        "gender": "男",
        "di_fen": "酉",
        "selected_sections": ["起盘信息", "金口诀四位"],
    },
    "/api/astro/chart": lambda: astro_payload(),
    "/api/astro/chart13": lambda: astro_payload(),
    "/api/astro/hellen": lambda: astro_payload(),
    "/api/astro/guolao": lambda: astro_payload(),
    "/api/astro/india": lambda: astro_payload(),
    "/api/astro/germany": lambda: astro_payload(),
    "/api/astro/relative": _relative_payload,
    "/api/astro/timing": western_payload,
    "/api/astro/timing/solarreturn": western_payload,
    "/api/astro/timing/lunarreturn": western_payload,
    "/api/astro/timing/transit": western_payload,
    "/api/astro/timing/solararc": western_payload,
    "/api/astro/timing/givenyear": western_payload,
    "/api/astro/timing/profection": western_payload,
    "/api/astro/timing/pd": western_payload,
    "/api/astro/timing/pdchart": western_payload,
    "/api/astro/timing/zr": western_payload,
    "/api/astro/timing/firdaria": western_payload,
    "/api/astro/timing/decennials": western_payload,
    "/api/astro/lifespan/harmonic": astro_payload,
    "/api/astro/lifespan/planetary_ages": astro_payload,
    "/api/astro/lifespan/triplicity_rulers": astro_payload,
    "/api/astro/lifespan/lunation_phase": astro_payload,
    "/api/astro/lifespan/distributions": astro_payload,
    "/api/astro/lifespan/balbillus": astro_payload,
    "/api/astro/lifespan/keypoints": astro_payload,
    "/api/astro/lifespan/yearsystem129": astro_payload,
    "/api/astro/lifespan/planetaryarc": astro_payload,
    "/api/astro/lifespan/persiandirected": astro_payload,
    "/api/astro/lifespan/agepoint": astro_payload,
    "/api/astro/lifespan/vedicprog": astro_payload,
    "/api/astro/lifespan/jaynesprog": astro_payload,
    "/api/astro/event/mundane": _mundane_payload,
    "/api/astro/event/extrareturns": astro_payload,
    "/api/astro/event/horary": _horary_payload,
    "/api/astro/event/election": _election_payload,
    "/api/timing/liuyue": lambda: {
        **_birth_payload(),
        "analysis_year": 2028,
        "analysis_month": 4,
        "analysis_day": 1,
        "selected_sections": ["查询信息", "流月信息"],
    },
    "/api/timing/liuri": lambda: {
        **_birth_payload(),
        "analysis_year": 2028,
        "analysis_month": 4,
        "analysis_day": 1,
        "analysis_hour": 9,
        "analysis_minute": 0,
        "selected_sections": ["查询信息", "流日信息"],
    },
    "/api/timing/liushi": lambda: {
        **_birth_payload(),
        "analysis_year": 2028,
        "analysis_month": 4,
        "analysis_day": 1,
        "analysis_hour": 21,
        "analysis_minute": 55,
        "selected_sections": ["查询信息", "流时信息"],
    },
    "/api/timing/jieqi": lambda: {
        **_birth_payload(),
        "target_year": 2028,
        "selected_sections": ["查询信息", "节点时间轴"],
    },
}

REST_GET_CASES = {
    "/health": lambda body: body["status"] == "healthy",
    "/ready": lambda body: body["status"] == "ready",
    "/metrics": lambda body: body is None,
    "/api/tools": lambda body: body["counts"]["total"] >= 1
    and isinstance(body["tools"], list),
    "/api/scenarios": lambda body: body["schema_version"] == "1.0"
    and isinstance(body["scenarios"], list),
}

MCP_CASES = {
    "analyze_destiny": ("analyze_destiny", _birth_payload),
    "bazi_birth": ("bazi_birth", _birth_payload),
    "bazi_marriage": (
        "bazi_marriage",
        lambda: {**_birth_payload(), "dayun_pillar": "壬戌", "liunian_pillar": "丁卯"},
    ),
    "bazi_career": (
        "bazi_career",
        lambda: {**_birth_payload(), "dayun_pillar": "壬戌", "liunian_pillar": "丁卯"},
    ),
    "bazi_wealth": (
        "bazi_wealth",
        lambda: {**_birth_payload(), "dayun_pillar": "壬戌", "liunian_pillar": "丁卯"},
    ),
    "bazi_health": (
        "bazi_health",
        lambda: {**_birth_payload(), "dayun_pillar": "壬戌", "liunian_pillar": "丁卯"},
    ),
    "bazi_children": (
        "bazi_children",
        lambda: {**_birth_payload(), "dayun_pillar": "壬戌", "liunian_pillar": "丁卯"},
    ),
    "bazi_education": (
        "bazi_education",
        lambda: {**_birth_payload(), "dayun_pillar": "壬戌", "liunian_pillar": "丁卯"},
    ),
    "bazi_personality": (
        "bazi_personality",
        lambda: {**_birth_payload(), "dayun_pillar": "壬戌", "liunian_pillar": "丁卯"},
    ),
    "bazi_relatives": (
        "bazi_relatives",
        lambda: {**_birth_payload(), "dayun_pillar": "壬戌", "liunian_pillar": "丁卯"},
    ),
    "bazi_romance": (
        "bazi_romance",
        lambda: {**_birth_payload(), "dayun_pillar": "壬戌", "liunian_pillar": "丁卯"},
    ),
    "two_person_compatibility": ("two_person_compatibility", _compatibility_payload),
    "timing_analysis": (
        "timing_analysis",
        lambda: {
            **_birth_payload(),
            "analysis_year": 2028,
            "analysis_month": 4,
            "analysis_day": 6,
            "analysis_hour": 21,
            "analysis_minute": 55,
            "analysis_age": 38,
            "selected_sections": ["查询信息", "综合影响"],
        },
    ),
    "dayun_analysis": (
        "dayun_analysis",
        lambda: {
            **_birth_payload(),
            "analysis_age": 38,
            "selected_sections": ["查询信息", "大运信息"],
        },
    ),
    "liunian_analysis": (
        "liunian_analysis",
        lambda: {**_birth_payload(), "target_year": 2028},
    ),
    "liuyue_analysis": (
        "liuyue_analysis",
        lambda: {
            **_birth_payload(),
            "analysis_year": 2028,
            "analysis_month": 4,
            "analysis_day": 1,
            "selected_sections": ["查询信息", "流月信息"],
        },
    ),
    "astro_chart13": ("astro_chart13", astro_payload),
    "astro_hellen_chart": ("astro_hellen_chart", astro_payload),
    "astro_guolao_chart": ("astro_guolao_chart", astro_payload),
    "astro_india_chart": ("astro_india_chart", astro_payload),
    "astro_germany_chart": ("astro_germany_chart", astro_payload),
    "export_registry": ("export_registry", lambda: {"technique": "qimen"}),
    "export_parse": (
        "export_parse",
        lambda: {
            "technique": "qimen",
            "content": _export_content(),
            "selected_sections": ["起盘信息", "八宫详解", "奇门演卦"],
        },
    ),
    "knowledge_registry": (
        "knowledge_registry",
        lambda: {"domain": "astro", "selected_sections": ["目录概览", "astro"]},
    ),
    "knowledge_read": (
        "knowledge_read",
        lambda: {
            "domain": "astro",
            "category": "aspect",
            "aspect_degree": 90,
            "object_a": "Sun",
            "object_b": "Jupiter",
            "selected_sections": ["查询信息", "知识正文"],
        },
    ),
    "jieqi_year": (
        "jieqi_year",
        lambda: {
            "year": 2028,
            "zone": "Asia/Shanghai",
            "lat": "31n13",
            "lon": "121e28",
            "jieqis": ["春分", "冬至"],
            "selected_sections": ["查询信息", "重点节气"],
        },
    ),
    "nongli_time": (
        "nongli_time",
        lambda: {
            "date": "2028-04-01",
            "time": "09:00:00",
            "zone": "Asia/Shanghai",
            "lon": "121e28",
            "selected_sections": ["农历上下文", "四柱上下文"],
        },
    ),
    "gua_meiyi": (
        "gua_meiyi",
        lambda: {"name": ["111", "000"], "selected_sections": ["查询概览", "批量结果"]},
    ),
    "gua_lookup": (
        "gua_lookup",
        lambda: {
            "query": "111111",
            "lookup_mode": "hexagram",
            "selected_sections": ["查询信息", "义理摘要"],
        },
    ),
    "meihua_analysis": (
        "meihua_analysis",
        lambda: {
            "analysis_year": 2028,
            "analysis_month": 4,
            "analysis_day": 1,
            "analysis_hour": 9,
            "analysis_minute": 0,
            "analysis_timezone": "Asia/Shanghai",
            "question": "事业推进节奏",
        },
    ),
    "tongshefa": (
        "tongshefa",
        lambda: {
            "taiyin": "巽",
            "taiyang": "坤",
            "shaoyang": "震",
            "shaoyin": "震",
        },
    ),
    "sixyao": ("sixyao", lambda: {**_local_base(), "gps_lat": 31.2, "gps_lon": 121.4}),
    "canping": (
        "canping",
        lambda: {**_local_base(), "gender": "男", "method": "ming"},
    ),
    "heluo": (
        "heluo",
        lambda: {
            **_local_base(),
            "date": "2000-05-15",
            "time": "09:33:00",
            "gender": "男",
        },
    ),
    "suzhan": (
        "suzhan",
        lambda: {
            **_local_base(),
            "gps_lat": 31.2,
            "gps_lon": 121.4,
            "szchart": 1,
            "szshape": 1,
            "house_start_mode": 2,
            "doubing_su28": False,
        },
    ),
    "sukuyo_compatibility": (
        "sukuyo_compatibility",
        lambda: {
            "person1_date": "1990-06-15",
            "person1_time": "08:30:00",
            "person2_date": "1992-03-20",
            "person2_time": "14:00:00",
        },
    ),
    "otherbu": (
        "otherbu",
        lambda: {
            **_local_base(),
            "gps_lat": 31.2,
            "gps_lon": 121.4,
            "sign": "Aries",
            "house": 6,
            "planet": "Sun",
            "question": "合作",
        },
    ),
    "sanshiunited": (
        "sanshiunited",
        lambda: {
            **_local_base(),
            "gps_lat": 31.2,
            "gps_lon": 121.4,
            "qimen_options": {"layout": "fly"},
            "taiyi_options": {"accNum": 1},
            "liureng_yue": "申",
            "liureng_is_diurnal": False,
        },
    ),
    "ziwei_birth": (
        "ziwei_birth",
        lambda: {
            **_birth_payload(name="张三", gender="男"),
            "birth_year": 1994,
            "birth_month": 8,
            "birth_day": 23,
            "birth_hour": 14,
            "selected_sections": ["起盘信息", "宫位总览"],
        },
    ),
    "ziwei_horoscope": (
        "ziwei_horoscope",
        lambda: {
            **_birth_payload(name="张三", gender="男"),
            "birth_year": 1994,
            "birth_month": 8,
            "birth_day": 23,
            "birth_hour": 14,
            "target_year": 2026,
            "target_month": 6,
            "target_day": 19,
            "target_hour": 14,
        },
    ),
    "ziwei_rules": (
        "ziwei_rules",
        lambda: {"year_stem": "甲", "selected_sections": ["规则概览", "当前天干四化"]},
    ),
    "liureng_gods": (
        "liureng_gods",
        lambda: {
            **_metaphysics_payload(),
            "gender": "男",
            "selected_sections": ["起盘信息", "三传"],
        },
    ),
    "liureng_runyear": (
        "liureng_runyear",
        lambda: {
            **_birth_payload(name="张三", gender="男"),
            "birth_year": 1994,
            "birth_month": 8,
            "birth_day": 23,
            "birth_hour": 14,
            "analysis_year": 2026,
            "analysis_month": 4,
            "analysis_day": 4,
            "analysis_hour": 21,
            "analysis_minute": 18,
            "analysis_timezone": "Asia/Shanghai",
            "analysis_longitude": 121.4737,
            "selected_sections": ["起盘信息", "行年"],
        },
    ),
    "qimen": (
        "qimen",
        lambda: {**_metaphysics_payload(), "qimen_options": {"layout": "rotating"}},
    ),
    "taiyi": (
        "taiyi",
        lambda: {
            **_metaphysics_payload(),
            "gender": "男",
            "selected_sections": ["起盘信息", "太乙"],
        },
    ),
    "jinkou": (
        "jinkou",
        lambda: {
            **_metaphysics_payload(),
            "gender": "男",
            "di_fen": "酉",
            "selected_sections": ["起盘信息", "金口诀四位"],
        },
    ),
    "liuri_analysis": (
        "liuri_analysis",
        lambda: {
            **_birth_payload(),
            "analysis_year": 2028,
            "analysis_month": 4,
            "analysis_day": 1,
            "analysis_hour": 9,
            "analysis_minute": 0,
            "selected_sections": ["查询信息", "流日信息"],
        },
    ),
    "liushi_analysis": (
        "liushi_analysis",
        lambda: {
            **_birth_payload(),
            "analysis_year": 2028,
            "analysis_month": 4,
            "analysis_day": 1,
            "analysis_hour": 21,
            "analysis_minute": 55,
            "selected_sections": ["查询信息", "流时信息"],
        },
    ),
    "jieqi_timeline_analysis": (
        "jieqi_timeline_analysis",
        lambda: {
            **_birth_payload(),
            "target_year": 2028,
            "selected_sections": ["查询信息", "节点时间轴"],
        },
    ),
    "astro_chart": ("astro_chart", astro_payload),
    "astro_relative_chart": ("astro_relative_chart", _relative_mcp_kwargs),
    "western_timing_analysis": ("western_timing_analysis", western_payload),
    "solarreturn": ("solarreturn", western_payload),
    "lunarreturn": ("lunarreturn", western_payload),
    "transit": ("transit", western_payload),
    "solararc": ("solararc", western_payload),
    "givenyear": ("givenyear", western_payload),
    "profection": ("profection", western_payload),
    "pd": ("pd", western_payload),
    "pdchart": ("pdchart", western_payload),
    "zr": ("zr", western_payload),
    "firdaria": ("firdaria", western_payload),
    "decennials": ("decennials", western_payload),
    "astro_harmonic": ("astro_harmonic", astro_payload),
    "astro_planetary_ages": ("astro_planetary_ages", astro_payload),
    "astro_triplicity_rulers": ("astro_triplicity_rulers", astro_payload),
    "astro_lunation_phase": ("astro_lunation_phase", astro_payload),
    "astro_distributions": ("astro_distributions", astro_payload),
    "astro_balbillus": ("astro_balbillus", astro_payload),
    "astro_keypoints": ("astro_keypoints", astro_payload),
    "astro_yearsystem129": ("astro_yearsystem129", astro_payload),
    "astro_planetaryarc": ("astro_planetaryarc", astro_payload),
    "astro_persiandirected": ("astro_persiandirected", astro_payload),
    "astro_agepoint": ("astro_agepoint", astro_payload),
    "astro_vedicprog": ("astro_vedicprog", astro_payload),
    "astro_jaynesprog": ("astro_jaynesprog", astro_payload),
    "astro_mundane": ("astro_mundane", _mundane_payload),
    "astro_extrareturns": ("astro_extrareturns", astro_payload),
    "astro_horary": ("astro_horary", _horary_payload),
    "astro_election": ("astro_election", _election_payload),
}

# Residential foundation tools participate in full-surface and golden coverage.
for _fengshui_name in PAYLOADS:
    REST_POST_CASES[f"/api/fengshui/{_fengshui_name}"] = (
        lambda name=_fengshui_name: fengshui_payload(name)
    )
    MCP_CASES[f"fengshui_{_fengshui_name}"] = (
        f"fengshui_{_fengshui_name}",
        lambda name=_fengshui_name: fengshui_payload(name),
    )
