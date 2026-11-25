"""三端（REST / MCP）代表性 payload 的单一信源。

`full_surface` 契约测试与 `golden-master` 数值锁都从这里取输入，确保两套
回归用的是同一组确定性夹具。
"""

from __future__ import annotations

from tests.fixtures.fengshui import PAYLOADS
from tests.fixtures.fengshui import payload as fengshui_payload

# At 2000-01-01 12:00 UTC, the independent plane-normal norm is 1.24e-16.
J2000_UNRESOLVED_ASC_SITE = {
    "birth_latitude": -66.5623231709126,
    "birth_longitude": 169.54144401512139,
}


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


def relationship_payload() -> dict:
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
    "/api/bazi/compare-sources": lambda: {
        "year_pillar": "甲子",
        "month_pillar": "丙寅",
        "day_pillar": "甲子",
        "hour_pillar": "甲子",
    },
    "/api/human-design/chart": lambda: {
        "birth_year": 1990,
        "birth_month": 4,
        "birth_day": 6,
        "birth_hour": 9,
        "birth_minute": 33,
        "birth_timezone": "Asia/Shanghai",
    },
    "/api/bazi/birth-chart": _birth_payload,
    "/api/bazi/overview": _birth_payload,
    "/api/bazi/marriage": lambda: {
        **_birth_payload(),
        "dayun_pillar": "壬戌",
        "liunian_pillar": "丁卯",
    },
    "/api/bazi/career": lambda: {
        **_birth_payload(),
        "dayun_pillar": "壬戌",
        "liunian_pillar": "丁卯",
    },
    "/api/bazi/wealth": lambda: {
        **_birth_payload(),
        "dayun_pillar": "壬戌",
        "liunian_pillar": "丁卯",
    },
    "/api/bazi/health": lambda: {
        **_birth_payload(),
        "dayun_pillar": "壬戌",
        "liunian_pillar": "丁卯",
    },
    "/api/bazi/children": lambda: {
        **_birth_payload(),
        "dayun_pillar": "壬戌",
        "liunian_pillar": "丁卯",
    },
    "/api/bazi/education": lambda: {
        **_birth_payload(),
        "dayun_pillar": "壬戌",
        "liunian_pillar": "丁卯",
    },
    "/api/bazi/personality": lambda: {
        **_birth_payload(),
        "dayun_pillar": "壬戌",
        "liunian_pillar": "丁卯",
    },
    "/api/bazi/relatives": lambda: {
        **_birth_payload(),
        "dayun_pillar": "壬戌",
        "liunian_pillar": "丁卯",
    },
    "/api/bazi/romance": lambda: {
        **_birth_payload(),
        "dayun_pillar": "壬戌",
        "liunian_pillar": "丁卯",
    },
    "/api/bazi/compatibility": _compatibility_payload,
    "/api/bazi/timing": lambda: {
        **_birth_payload(),
        "analysis_year": 2028,
        "analysis_month": 4,
        "analysis_day": 6,
        "analysis_hour": 21,
        "analysis_minute": 55,
        "analysis_age": 38,
        "selected_sections": ["查询信息", "综合影响"],
    },
    "/api/bazi/timing/luck-cycles": lambda: {
        **_birth_payload(),
        "analysis_age": 38,
        "selected_sections": ["查询信息", "大运信息"],
    },
    "/api/bazi/timing/yearly": lambda: {
        **_birth_payload(),
        "target_year": 2028,
    },
    "/api/divination/gua": lambda: {
        "query": "111111",
        "lookup_mode": "hexagram",
        "selected_sections": ["查询信息", "经文"],
    },
    "/api/calendar/solar-terms": lambda: {
        "year": 2028,
        "zone": "Asia/Shanghai",
        "lat": "31n13",
        "lon": "121e28",
        "jieqis": ["春分", "冬至"],
        "selected_sections": ["查询信息", "重点节气"],
    },
    "/api/calendar/lunar-time": lambda: {
        "date": "2028-04-01",
        "time": "09:00:00",
        "zone": "Asia/Shanghai",
        "lon": "121e28",
        "selected_sections": ["农历上下文", "四柱上下文"],
    },
    "/api/divination/gua/meanings": lambda: {
        "name": ["111", "000"],
        "selected_sections": ["查询概览", "批量结果"],
    },
    "/api/export/formats": lambda: {
        "technique": "qimen",
    },
    "/api/export/parse": lambda: {
        "technique": "qimen",
        "content": _export_content(),
        "selected_sections": ["起盘信息", "八宫详解", "奇门演卦"],
    },
    "/api/knowledge/catalog": lambda: {
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
    "/api/divination/meihua/time-cast": lambda: {
        "analysis_year": 2028,
        "analysis_month": 4,
        "analysis_day": 1,
        "analysis_hour": 9,
        "analysis_minute": 0,
        "analysis_timezone": "Asia/Shanghai",
        "question": "事业推进节奏",
    },
    "/api/divination/meihua/cast": lambda: {
        "casting": {
            "method": "sound_groups",
            "first_count": 1,
            "second_count": 5,
            "hour_branch": "酉",
        },
        "question": "虚构声音起卦验收",
    },
    "/api/divination/combine-four-gua": lambda: {
        "taiyin": "巽",
        "taiyang": "坤",
        "shaoyang": "震",
        "shaoyin": "震",
    },
    "/api/divination/liuyao": lambda: {
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
    "/api/divination/astrology-dice/interpret": lambda: {
        **_local_base(),
        "sign": "Aries",
        "house": 6,
        "planet": "Sun",
        "question": "合作",
    },
    "/api/divination/sanshi": lambda: {
        **_local_base(),
        "qimen_options": {"layout": "direct"},
        "taiyi_options": {},
        "liureng_yue": "申",
        "liureng_is_diurnal": False,
    },
    "/api/ziwei/birth-chart": lambda: {
        **_birth_payload(name="张三", gender="男"),
        "birth_year": 1994,
        "birth_month": 8,
        "birth_day": 23,
        "birth_hour": 14,
        "selected_sections": ["起盘信息", "宫位总览"],
    },
    "/api/ziwei/timing": lambda: {
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
    "/api/ziwei/rules": lambda: {
        "year_stem": "甲",
        "selected_sections": ["规则概览", "当前天干四化"],
    },
    "/api/liuren/chart": lambda: {
        **_metaphysics_payload(),
        "gender": "男",
        "selected_sections": ["起盘信息", "三传"],
    },
    "/api/liuren/timing/yearly": lambda: {
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
    "/api/qimen": lambda: {
        **_metaphysics_payload(),
        "qimen_options": {"layout": "rotating"},
    },
    "/api/taiyi": lambda: {
        **_metaphysics_payload(),
        "gender": "男",
        "selected_sections": ["起盘信息", "太乙"],
    },
    "/api/jinkou": lambda: {
        **_metaphysics_payload(),
        "gender": "男",
        "di_fen": "酉",
        "selected_sections": ["起盘信息", "金口诀四位"],
    },
    "/api/astrology/chart": lambda: astro_payload(),
    "/api/astrology/thirteen-sector-chart": lambda: astro_payload(),
    "/api/astrology/hellenistic-chart": lambda: astro_payload(),
    "/api/astrology/guolao-chart": lambda: astro_payload(),
    "/api/astrology/vedic-chart": lambda: astro_payload(),
    "/api/astrology/vimshottari-dasha": lambda: {
        **astro_payload(),
        "analysis_year": 2026,
        "analysis_month": 10,
        "analysis_day": 22,
    },
    "/api/astrology/hamburg-midpoint-chart": lambda: astro_payload(),
    "/api/astrology/relationship-chart": relationship_payload,
    "/api/astrology/timing": western_payload,
    "/api/astrology/timing/solar-return": western_payload,
    "/api/astrology/timing/lunar-return": western_payload,
    "/api/astrology/timing/transit-chart": western_payload,
    "/api/astrology/timing/solar-arc": western_payload,
    "/api/astrology/timing/chart-for-year": western_payload,
    "/api/astrology/timing/profection": western_payload,
    "/api/astrology/timing/primary-directions": western_payload,
    "/api/astrology/timing/primary-directions-chart": western_payload,
    "/api/astrology/timing/zodiacal-releasing": western_payload,
    "/api/astrology/timing/firdaria": western_payload,
    "/api/astrology/timing/decennials": western_payload,
    "/api/astrology/harmonic-chart": astro_payload,
    "/api/astrology/timing/planetary-ages": astro_payload,
    "/api/astrology/timing/triplicity-ruler-periods": astro_payload,
    "/api/astrology/timing/lunar-phase-progressions": astro_payload,
    "/api/astrology/timing/bounds-directions": astro_payload,
    "/api/astrology/timing/balbillus-periods": astro_payload,
    "/api/astrology/timing/numeric-aspect-periods": astro_payload,
    "/api/astrology/timing/planetary-periods-129-years": astro_payload,
    "/api/astrology/timing/planetary-arc-directions": astro_payload,
    "/api/astrology/timing/persian-directions": astro_payload,
    "/api/astrology/timing/age-point": astro_payload,
    "/api/astrology/timing/sidereal-progressions": astro_payload,
    "/api/astrology/timing/declination-progressions": astro_payload,
    "/api/astrology/events/mundane-ingress-chart": _mundane_payload,
    "/api/astrology/events/planetary-returns": astro_payload,
    "/api/astrology/events/horary-chart": _horary_payload,
    "/api/astrology/events/evaluate-election-time": _election_payload,
    "/api/bazi/timing/monthly": lambda: {
        **_birth_payload(),
        "analysis_year": 2028,
        "analysis_month": 4,
        "analysis_day": 1,
        "selected_sections": ["查询信息", "流月信息"],
    },
    "/api/bazi/timing/daily": lambda: {
        **_birth_payload(),
        "analysis_year": 2028,
        "analysis_month": 4,
        "analysis_day": 1,
        "analysis_hour": 9,
        "analysis_minute": 0,
        "selected_sections": ["查询信息", "流日信息"],
    },
    "/api/bazi/timing/hourly": lambda: {
        **_birth_payload(),
        "analysis_year": 2028,
        "analysis_month": 4,
        "analysis_day": 1,
        "analysis_hour": 21,
        "analysis_minute": 55,
        "selected_sections": ["查询信息", "流时信息"],
    },
    "/api/calendar/solar-term-timeline": lambda: {
        **_birth_payload(),
        "target_year": 2028,
        "selected_sections": ["查询信息", "节点时间轴"],
    },
    "/api/psychometrics/ipip-big-five": lambda: {
        "action": "score",
        "responses": {str(i): (i % 5) + 1 for i in range(1, 51)},
        "include_item_breakdown": True,
    },
}

REST_GET_CASES = {
    "/health": lambda body: body["status"] == "healthy",
    "/ready": lambda body: body["status"] == "ready",
    "/metrics": lambda body: body is None,
    "/api/tools": lambda body: body["counts"]["total"] >= 1
    and isinstance(body["tools"], list),
}

MCP_CASES = {
    "compare_bazi_sources": (
        "compare_bazi_sources",
        lambda: {
            "year_pillar": "甲子",
            "month_pillar": "丙寅",
            "day_pillar": "甲子",
            "hour_pillar": "甲子",
        },
    ),
    "bazi_overview": ("bazi_overview", _birth_payload),
    "bazi_birth_chart": ("bazi_birth_chart", _birth_payload),
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
    "bazi_compatibility": ("bazi_compatibility", _compatibility_payload),
    "bazi_timing": (
        "bazi_timing",
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
    "bazi_luck_cycles": (
        "bazi_luck_cycles",
        lambda: {
            **_birth_payload(),
            "analysis_age": 38,
            "selected_sections": ["查询信息", "大运信息"],
        },
    ),
    "bazi_yearly_timing": (
        "bazi_yearly_timing",
        lambda: {**_birth_payload(), "target_year": 2028},
    ),
    "bazi_monthly_timing": (
        "bazi_monthly_timing",
        lambda: {
            **_birth_payload(),
            "analysis_year": 2028,
            "analysis_month": 4,
            "analysis_day": 1,
            "selected_sections": ["查询信息", "流月信息"],
        },
    ),
    "thirteen_sector_chart": ("thirteen_sector_chart", astro_payload),
    "hellenistic_chart": ("hellenistic_chart", astro_payload),
    "guolao_chart": ("guolao_chart", astro_payload),
    "vedic_chart": ("vedic_chart", astro_payload),
    "vimshottari_dasha": (
        "vimshottari_dasha",
        lambda: {
            **astro_payload(),
            "analysis_year": 2026,
            "analysis_month": 10,
            "analysis_day": 22,
        },
    ),
    "human_design": (
        "human_design",
        lambda: {
            "birth_year": 1990,
            "birth_month": 4,
            "birth_day": 6,
            "birth_hour": 9,
            "birth_minute": 33,
            "birth_timezone": "Asia/Shanghai",
        },
    ),
    "hamburg_midpoint_chart": ("hamburg_midpoint_chart", astro_payload),
    "export_formats": ("export_formats", lambda: {"technique": "qimen"}),
    "export_parse": (
        "export_parse",
        lambda: {
            "technique": "qimen",
            "content": _export_content(),
            "selected_sections": ["起盘信息", "八宫详解", "奇门演卦"],
        },
    ),
    "knowledge_catalog": (
        "knowledge_catalog",
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
    "solar_terms_for_year": (
        "solar_terms_for_year",
        lambda: {
            "year": 2028,
            "zone": "Asia/Shanghai",
            "lat": "31n13",
            "lon": "121e28",
            "jieqis": ["春分", "冬至"],
            "selected_sections": ["查询信息", "重点节气"],
        },
    ),
    "lunar_calendar_time": (
        "lunar_calendar_time",
        lambda: {
            "date": "2028-04-01",
            "time": "09:00:00",
            "zone": "Asia/Shanghai",
            "lon": "121e28",
            "selected_sections": ["农历上下文", "四柱上下文"],
        },
    ),
    "gua_meanings": (
        "gua_meanings",
        lambda: {"name": ["111", "000"], "selected_sections": ["查询概览", "批量结果"]},
    ),
    "gua_lookup": (
        "gua_lookup",
        lambda: {
            "query": "111111",
            "lookup_mode": "hexagram",
            "selected_sections": ["查询信息", "经文"],
        },
    ),
    "meihua_cast": (
        "meihua_cast",
        lambda: {
            "casting": {
                "method": "sound_groups",
                "first_count": 1,
                "second_count": 5,
                "hour_branch": "酉",
            }
        },
    ),
    "meihua_time_cast": (
        "meihua_time_cast",
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
    "combine_four_gua": (
        "combine_four_gua",
        lambda: {
            "taiyin": "巽",
            "taiyang": "坤",
            "shaoyang": "震",
            "shaoyin": "震",
        },
    ),
    "liuyao": ("liuyao", lambda: {**_local_base(), "gps_lat": 31.2, "gps_lon": 121.4}),
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
    "interpret_astrology_dice": (
        "interpret_astrology_dice",
        lambda: {
            **_local_base(),
            "gps_lat": 31 + 13 / 60,
            "gps_lon": 121 + 28 / 60,
            "sign": "Aries",
            "house": 6,
            "planet": "Sun",
            "question": "合作",
        },
    ),
    "sanshi_combined_chart": (
        "sanshi_combined_chart",
        lambda: {
            **_local_base(),
            "gps_lat": 31.2,
            "gps_lon": 121.4,
            "qimen_options": {"layout": "direct"},
            "taiyi_options": {},
            "liureng_yue": "申",
            "liureng_is_diurnal": False,
        },
    ),
    "ziwei_birth_chart": (
        "ziwei_birth_chart",
        lambda: {
            **_birth_payload(name="张三", gender="男"),
            "birth_year": 1994,
            "birth_month": 8,
            "birth_day": 23,
            "birth_hour": 14,
            "selected_sections": ["起盘信息", "宫位总览"],
        },
    ),
    "ziwei_timing": (
        "ziwei_timing",
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
    "liuren_chart": (
        "liuren_chart",
        lambda: {
            **_metaphysics_payload(),
            "gender": "男",
            "selected_sections": ["起盘信息", "三传"],
        },
    ),
    "liuren_yearly_timing": (
        "liuren_yearly_timing",
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
    "bazi_daily_timing": (
        "bazi_daily_timing",
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
    "bazi_hourly_timing": (
        "bazi_hourly_timing",
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
    "solar_term_timeline": (
        "solar_term_timeline",
        lambda: {
            **_birth_payload(),
            "target_year": 2028,
            "selected_sections": ["查询信息", "节点时间轴"],
        },
    ),
    "astrology_chart": ("astrology_chart", astro_payload),
    "relationship_chart": ("relationship_chart", relationship_payload),
    "western_timing": ("western_timing", western_payload),
    "solar_return": ("solar_return", western_payload),
    "lunar_return": ("lunar_return", western_payload),
    "transit_chart": ("transit_chart", western_payload),
    "solar_arc": ("solar_arc", western_payload),
    "chart_for_year": ("chart_for_year", western_payload),
    "profection": ("profection", western_payload),
    "primary_directions": ("primary_directions", western_payload),
    "primary_directions_chart": ("primary_directions_chart", western_payload),
    "zodiacal_releasing": ("zodiacal_releasing", western_payload),
    "firdaria": ("firdaria", western_payload),
    "decennials": ("decennials", western_payload),
    "harmonic_chart": ("harmonic_chart", astro_payload),
    "planetary_ages": ("planetary_ages", astro_payload),
    "triplicity_ruler_periods": ("triplicity_ruler_periods", astro_payload),
    "lunar_phase_progressions": ("lunar_phase_progressions", astro_payload),
    "bounds_directions": ("bounds_directions", astro_payload),
    "balbillus_periods": ("balbillus_periods", astro_payload),
    "numeric_aspect_periods": ("numeric_aspect_periods", astro_payload),
    "planetary_periods_129_years": ("planetary_periods_129_years", astro_payload),
    "planetary_arc_directions": ("planetary_arc_directions", astro_payload),
    "persian_directions": ("persian_directions", astro_payload),
    "age_point": ("age_point", astro_payload),
    "sidereal_progressions": ("sidereal_progressions", astro_payload),
    "declination_progressions": ("declination_progressions", astro_payload),
    "mundane_ingress_chart": ("mundane_ingress_chart", _mundane_payload),
    "planetary_returns": ("planetary_returns", astro_payload),
    "horary_chart": ("horary_chart", _horary_payload),
    "evaluate_election_time": ("evaluate_election_time", _election_payload),
    "ipip_big_five": (
        "ipip_big_five",
        lambda: {
            "action": "score",
            "responses": {str(i): (i % 5) + 1 for i in range(1, 51)},
            "include_item_breakdown": True,
        },
    ),
}

# Residential foundation tools participate in full-surface and golden coverage.
for _fengshui_name in PAYLOADS:
    _tool_name = (
        "xuankong_house_chart" if _fengshui_name == "xuankong_natal" else _fengshui_name
    )
    REST_POST_CASES["/api/fengshui/" + _tool_name.replace("_", "-")] = (
        lambda name=_fengshui_name: fengshui_payload(name)
    )
    MCP_CASES[f"fengshui_{_tool_name}"] = (
        f"fengshui_{_tool_name}",
        lambda name=_fengshui_name: fengshui_payload(name),
    )
