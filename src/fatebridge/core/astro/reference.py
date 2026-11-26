"""Chart convention tables, physical constants and approximation parameters."""

from __future__ import annotations

from typing import Any

from fatebridge.core.astro import runtime

PHYSICAL_BODIES = (
    "Sun",
    "Moon",
    "Mercury",
    "Venus",
    "Mars",
    "Jupiter",
    "Saturn",
    "Uranus",
    "Neptune",
    "Pluto",
)


# 本质尊贵 (essential dignity)。仅古典七曜有庙旺落陷之分；天王 / 海王 / 冥王及
# 交点等无古典本质尊贵，dignity 记为 None。
# 入庙(domicile)：行星所主之宫；入旺(exaltation)：曜升之宫；
# 落陷(detriment)：庙之对宫；失势(fall)：旺之对宫。
DIGNITY_LABELS_ZH = {
    "rulership": "庙",
    "exaltation": "旺",
    "detriment": "陷",
    "fall": "弱",
    "no_major_dignity": "无主要庙旺落陷",
}


NAKSHATRAS = [
    "Ashwini",
    "Bharani",
    "Krittika",
    "Rohini",
    "Mrigashira",
    "Ardra",
    "Punarvasu",
    "Pushya",
    "Ashlesha",
    "Magha",
    "Purva Phalguni",
    "Uttara Phalguni",
    "Hasta",
    "Chitra",
    "Swati",
    "Vishakha",
    "Anuradha",
    "Jyeshtha",
    "Mula",
    "Purva Ashadha",
    "Uttara Ashadha",
    "Shravana",
    "Dhanishta",
    "Shatabhisha",
    "Purva Bhadrapada",
    "Uttara Bhadrapada",
    "Revati",
]


SU28 = [
    "角宿",
    "亢宿",
    "氐宿",
    "房宿",
    "心宿",
    "尾宿",
    "箕宿",
    "斗宿",
    "牛宿",
    "女宿",
    "虚宿",
    "危宿",
    "室宿",
    "壁宿",
    "奎宿",
    "娄宿",
    "胃宿",
    "昴宿",
    "毕宿",
    "觜宿",
    "参宿",
    "井宿",
    "鬼宿",
    "柳宿",
    "星宿",
    "张宿",
    "翼宿",
    "轸宿",
]


PLANET_SEQUENCE = [*PHYSICAL_BODIES, "North Node"]


# 月亮交点（虚点）。元素 / 模式平衡按行星本体统计，不计交点。
NODE_BODIES = frozenset({"North Node", "South Node"})


# 元素 / 模式平衡的统计口径说明（随盘面输出，供解读时标明基准）。
BALANCE_BASIS = "行星本体计入；月亮交点（虚点）不计入元素/模式统计"


PLANET_SWISSEPH_IDS = (
    {
        "Sun": runtime.swe.SUN,
        "Moon": runtime.swe.MOON,
        "Mercury": runtime.swe.MERCURY,
        "Venus": runtime.swe.VENUS,
        "Mars": runtime.swe.MARS,
        "Jupiter": runtime.swe.JUPITER,
        "Saturn": runtime.swe.SATURN,
        "Uranus": runtime.swe.URANUS,
        "Neptune": runtime.swe.NEPTUNE,
        "Pluto": runtime.swe.PLUTO,
        "North Node": runtime.swe.MEAN_NODE,
    }
    if runtime.swe is not None
    else {}
)

EXTRA_BODY_SWISSEPH_IDS = (
    {
        "Chiron": getattr(runtime.swe, "CHIRON", 15),
        "Lilith": getattr(runtime.swe, "MEAN_APOG", 12),
        "Ceres": getattr(runtime.swe, "CERES", 17),
        "Pallas": getattr(runtime.swe, "PALLAS", 18),
        "Juno": getattr(runtime.swe, "JUNO", 19),
        "Vesta": getattr(runtime.swe, "VESTA", 20),
        "True Node": runtime.swe.TRUE_NODE,
    }
    if runtime.swe is not None
    else {}
)

STATION_SPEED_THRESHOLDS: dict[str, float] = {
    "Mercury": 0.1,
    "Venus": 0.1,
    "Mars": 0.05,
    "Jupiter": 0.02,
    "Saturn": 0.015,
    "Uranus": 0.008,
    "Neptune": 0.005,
    "Pluto": 0.004,
    "Chiron": 0.005,
    "Ceres": 0.02,
    "Pallas": 0.02,
    "Juno": 0.02,
    "Vesta": 0.02,
}


TRADITIONAL_PLANETS = list(PHYSICAL_BODIES[:7])


# 顺序敏感的 ``TRADITIONAL_PLANETS`` 用于 ``list(...)`` 与有序推导；成员判断
# (``x in ...``) 另用此 frozenset，避免对 list 做线性扫描。两者内容一致。
TRADITIONAL_PLANET_IDS = frozenset(TRADITIONAL_PLANETS)


ASPECTS = [
    ("conjunction", 0.0),
    ("sextile", 60.0),
    ("square", 90.0),
    ("trine", 120.0),
    ("opposition", 180.0),
]

MINOR_ASPECTS = [
    ("semisextile", 30.0),
    ("semisquare", 45.0),
    ("quintile", 72.0),
    ("sesquiquadrate", 135.0),
    ("quincunx", 150.0),
]


RELATIVE_MODE_LABELS_ZH = {
    "compare": "比较盘",
    "composite": "组合盘",
    "influence": "影响盘",
    "timespace": "时空中点盘",
    "marks": "马克斯盘",
}


RELATIVE_ZODIACAL_LABELS_ZH = {
    0: "回归黄道",
    1: "恒星黄道，岁差:Lahiri",
}


RELATIVE_HOUSE_SYSTEM_SPECS: dict[int, dict[str, Any]] = {
    0: {
        "key": "whole_sign",
        "label_zh": "整宫制",
        "swisseph_code": b"W",
    },
    1: {
        "key": "alcabitus",
        "label_zh": "Alcabitus",
        "swisseph_code": b"B",
    },
    2: {
        "key": "regiomontanus",
        "label_zh": "Regiomontanus",
        "swisseph_code": b"R",
    },
    3: {
        "key": "placidus",
        "label_zh": "Placidus",
        "swisseph_code": b"P",
    },
    4: {
        "key": "koch",
        "label_zh": "Koch",
        "swisseph_code": b"K",
    },
    5: {
        "key": "vehlow_equal",
        "label_zh": "Vehlow Equal",
        "swisseph_code": b"V",
    },
    6: {
        "key": "polich_page",
        "label_zh": "Polich Page",
        "swisseph_code": b"T",
    },
    7: {
        "key": "sripati",
        "label_zh": "Sripati",
        "swisseph_code": b"S",
    },
    8: {
        "key": "equal_mc",
        "label_zh": "天顶为第10宫宫头的等宫制",
        "swisseph_code": b"D",
    },
    9: {
        "key": "equal",
        "label_zh": "等宫制（上升起点）",
        "swisseph_code": b"E",
        "public_code": None,
    },
}


RELATIVE_MODE_NUMERIC_MAP = {
    0: "compare",
    1: "composite",
    2: "influence",
    3: "timespace",
    4: "marks",
}


RELATIVE_MODE_EXACT_ALIASES = {
    "Comp": "compare",
    "Composite": "composite",
    "Synastry": "influence",
    "TimeSpace": "timespace",
    "Marks": "marks",
}


RELATIVE_MODE_FALLBACK_ALIASES = {
    "compare": "compare",
    "comparison": "compare",
    "comp": "compare",
    "比较盘": "compare",
    "组合盘": "composite",
    "composite": "composite",
    "influence": "influence",
    "synastry": "influence",
    "影响盘": "influence",
    "timespace": "timespace",
    "time space": "timespace",
    "时空中点盘": "timespace",
    "marks": "marks",
    "马克斯盘": "marks",
}


CORE_CHART_DEFAULT_HOUSE_SYSTEMS = {
    # Placidus is the de-facto default of modern Western (tropical) astrology
    # software, so the natal chart matches what users see elsewhere.  chart13's
    # equal-from-MC default is intentional (its 13-sign frame is not quadrant
    # native), and the traditional charts stay whole-sign by tradition.
    "chart": "placidus",
    "chart13": "equal_mc",
    "hellen_chart": "whole_sign",
    "guolao_chart": "whole_sign",
    "india_chart": "whole_sign",
}


CORE_CHART_DEFAULT_HOUSE_LABELS_ZH = {
    "equal": "等宫制（上升起点）",
    "equal_mc": "天顶为第10宫宫头的等宫制",
    "placidus": "Placidus",
    "whole_sign": "整宫制",
}


CORE_CHART_DEFAULT_ZODIACAL = {
    "chart": 0,
    "chart13": 0,
    "hellen_chart": 0,
    "guolao_chart": 0,
    "india_chart": 1,
}


DEFAULT_PLANET_ORBS = {
    "Sun": 10.0,
    "Moon": 10.0,
    "Mercury": 7.0,
    "Venus": 7.0,
    "Mars": 7.5,
    "Jupiter": 9.0,
    "Saturn": 9.0,
    "Uranus": 5.0,
    "Neptune": 5.0,
    "Pluto": 5.0,
}


# 关系取向（婚姻/恋爱）的解读侧重：强调宫位 + 关键星体，并据此过滤 synastry 相位。
RELATIONSHIP_FOCUS_DEFS: dict[str, dict[str, Any]] = {
    "marriage": {
        "label_zh": "婚姻",
        "houses": [7],
        "bodies": ["Sun", "Moon", "Venus", "Saturn"],
        "note": "婚姻取向：重点观察第7宫（夫妻宫）与日/月/金星/土星之间的 synastry 相位。",
    },
    "romance": {
        "label_zh": "恋爱",
        "houses": [5],
        "bodies": ["Sun", "Moon", "Venus", "Mars"],
        "note": "恋爱取向：重点观察第5宫（恋爱宫）与日/月/金星/火星之间的 synastry 相位。",
    },
}


RELATIONSHIP_FOCUS_ALIASES = {
    "marriage": "marriage",
    "marry": "marriage",
    "婚姻": "marriage",
    "结婚": "marriage",
    "romance": "romance",
    "romantic": "romance",
    "dating": "romance",
    "love": "romance",
    "恋爱": "romance",
    "戀愛": "romance",
    "general": "general",
    "泛": "general",
    "none": "general",
    "": "general",
}
