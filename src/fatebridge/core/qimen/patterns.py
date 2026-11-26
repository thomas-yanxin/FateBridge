"""Qimen profiles, palace relations, and pattern detection (pure structured facts)."""

from __future__ import annotations

from typing import Any

from fatebridge.core.metaphysics.common import (
    BRANCH_ELEMENTS,
    ELEMENT_CONTROLS,
    ELEMENT_GENERATES,
    MetaphysicsSeed,
    SEXAGENARY_INDEX,
    xun_head_for_ganzhi,
)
from fatebridge.core.qimen.board import (
    DEFAULT_GOD_PROFILE,
    GOD_PROFILES,
    QimenLeaders,
    compute_horse_star,
)
from fatebridge.utils.data import STEM_ELEMENTS
from fatebridge.utils.timezones import timezone_rules_metadata

DEFAULT_SEASON_PROFILE = "yanyi_vol1_verse"
RULESET_ID = "qimen_dunjia_v3"

SEASON_PROFILES: dict[str, dict[str, Any]] = {
    "yanyi_vol1_verse": {
        "title": "卷一烟波钓叟赋九星旺相",
        "section": "卷一·烟波钓叟赋",
        "states_by_relation": {
            "same_element": "相",
            "star_generates_month": "旺",
            "month_generates_star": "废",
            "star_controls_month": "休",
            "month_controls_star": "囚",
        },
    },
    "yanyi_vol3_table": {
        "title": "卷三九星旺相休囚表",
        "section": "卷三·九星旺相休囚表",
        "states_by_relation": {
            "same_element": "旺",
            "star_generates_month": "相",
            "month_generates_star": "废",
            "star_controls_month": "休",
            "month_controls_star": "囚",
        },
    },
    "yanyi_vol3_prose": {
        "title": "卷三九星旺衰正文",
        "section": "卷三·九星所属及旺衰正文",
        "states_by_relation": {
            "same_element": "旺",
            "star_generates_month": "相",
            "month_generates_star": "休",
            "star_controls_month": "死",
            "month_controls_star": "囚",
        },
    },
}

STAR_ELEMENTS: dict[str, str] = {
    "天蓬": "水",
    "天任": "土",
    "天冲": "木",
    "天辅": "木",
    "天英": "火",
    "天芮": "土",
    "天禽": "土",
    "天柱": "金",
    "天心": "金",
}

PALACE_ELEMENTS: dict[str, str] = {
    "坎": "水",
    "坤": "土",
    "震": "木",
    "巽": "木",
    "中": "土",
    "乾": "金",
    "兑": "金",
    "艮": "土",
    "离": "火",
}

DOOR_ELEMENTS: dict[str, str] = {
    "休门": "水",
    "生门": "土",
    "伤门": "木",
    "杜门": "木",
    "景门": "火",
    "死门": "土",
    "惊门": "金",
    "开门": "金",
}

PALACE_BRANCHES: dict[str, str] = {
    "坎": "子",
    "坤": "未申",
    "震": "卯",
    "巽": "辰巳",
    "中": "",
    "乾": "戌亥",
    "兑": "酉",
    "艮": "丑寅",
    "离": "午",
}

DIRECTIONS: dict[str, str] = {
    "坎": "北",
    "坤": "西南",
    "震": "东",
    "巽": "东南",
    "中": "中央",
    "乾": "西北",
    "兑": "西",
    "艮": "东北",
    "离": "南",
}

NATIVE_DOORS: dict[str, str] = {
    "坎": "休门",
    "坤": "死门",
    "震": "伤门",
    "巽": "杜门",
    "乾": "开门",
    "兑": "惊门",
    "艮": "生门",
    "离": "景门",
}

OPPOSITE_PALACE: dict[str, str] = {
    "坎": "离",
    "艮": "坤",
    "震": "兑",
    "巽": "乾",
    "离": "坎",
    "坤": "艮",
    "兑": "震",
    "乾": "巽",
    "中": "中",
}

PROSE_GATE_LABELS = {
    "door_controls_palace": "吉迫",
    "palace_controls_door": "凶迫",
    "door_generates_palace": "和",
    "palace_generates_door": "义",
    "same_element": None,
}

PRINTED_EXAMPLES = {
    ("开门", "震"): "吉门被迫",
    ("休门", "离"): "吉门被迫",
    ("生门", "坎"): "吉门被迫",
    ("景门", "兑"): "吉门被迫",
    ("伤门", "坤"): "凶门被迫",
    ("伤门", "艮"): "凶门被迫",
    ("杜门", "坤"): "凶门被迫",
    ("杜门", "艮"): "凶门被迫",
    ("死门", "坎"): "凶门被迫",
    ("惊门", "震"): "凶门被迫",
    ("惊门", "巽"): "凶门被迫",
}

WONDER_TOMBS = {"乙": "坤", "丙": "乾", "丁": "艮"}

PUNISHMENT_BY_HEAD: dict[str, tuple[str, str, str]] = {
    "甲子": ("戊", "卯", "震"),
    "甲戌": ("己", "未", "坤"),
    "甲申": ("庚", "寅", "艮"),
    "甲午": ("辛", "午", "离"),
    "甲辰": ("壬", "辰", "巽"),
    "甲寅": ("癸", "巳", "巽"),
}

HOUR_BRANCH_TOMBS = {
    "丙戌": {"element": "火", "polarity": "阳"},
    "壬辰": {"element": "水", "polarity": "阳"},
    "丁丑": {"element": "火", "polarity": "阴"},
    "癸未": {"element": "水", "polarity": "阴"},
    "戊戌": {"element": "土", "polarity": "阳"},
    "己丑": {"element": "土", "polarity": "阴"},
}

TIAN_XIAN_HOURS: dict[str, frozenset[str]] = {
    "甲": frozenset({"甲子", "甲戌"}),
    "己": frozenset({"甲子", "甲戌"}),
    "乙": frozenset({"甲申"}),
    "庚": frozenset({"甲申"}),
    "丙": frozenset({"甲午"}),
    "辛": frozenset({"甲午"}),
    "丁": frozenset({"甲辰"}),
    "壬": frozenset({"甲辰"}),
    "戊": frozenset({"甲寅"}),
    "癸": frozenset({"甲寅"}),
}

DE_SHI = {"乙": {"己", "辛"}, "丙": {"戊", "庚"}, "丁": {"壬", "癸"}}

STEM_KEY_PATTERNS: dict[tuple[str, str], tuple[str, str]] = {
    ("庚", "癸"): ("big_grid", "大格"),
    ("庚", "壬"): ("small_grid", "小格"),
    ("庚", "己"): ("punishment_grid", "刑格"),
    ("乙", "辛"): ("azure_dragon_flee", "青龙逃走"),
    ("辛", "乙"): ("white_tiger_rampant", "白虎猖狂"),
    ("丁", "癸"): ("vermilion_bird_river", "朱雀投江"),
    ("癸", "丁"): ("tengshe_coiling", "螣蛇夭矫"),
    ("庚", "丙"): ("taibai_enters_ying", "太白入荧"),
    ("丙", "庚"): ("ying_enters_taibai", "荧入太白"),
}

THREE_DECEPTIONS = {
    "太阴": ("true_deception", "真诈"),
    "九地": ("heavy_deception", "重诈"),
    "六合": ("rest_deception", "休诈"),
}

FIVE_JIA = (
    ("heaven_jia", "天假", "景门", frozenset("乙丙丁"), "九天"),
    ("earth_jia", "地假", "杜门", frozenset("丁己癸"), "九地"),
    ("spirit_jia", "神假", "伤门", frozenset("丁己癸"), "九地"),
    ("ghost_jia", "鬼假", "死门", frozenset("丁己癸"), "九地"),
)

GOOD_DOORS = frozenset({"开门", "休门", "生门"})

GOD_ROLES = {
    "值符": "天乙之神",
    "螣蛇": "虚诈之神",
    "太阴": "阴佑之神",
    "六合": "护卫之神",
    "白虎": "凶恶之神",
    "玄武": "小盗之神",
    "九地": "坚牢之神",
    "九天": "威武扬兵之神",
    "勾陈": "勾陈（卷四圆图）",
    "朱雀": "朱雀（卷四圆图）",
    "太常": "太常（飞盘九神）",
}


def validate_profiles(god_profile: str, season_profile: str) -> None:
    for name, value, profiles in (
        ("god_profile", god_profile, GOD_PROFILES),
        ("season_profile", season_profile, SEASON_PROFILES),
    ):
        if not isinstance(value, str) or value not in profiles:
            raise ValueError(f"{name}仅支持：{', '.join(profiles)}")


def god_evidence(god: str) -> dict[str, Any]:
    return {
        "god": god,
        "section": "卷三·天乙直符吉凶神说" if god not in {"勾陈", "朱雀"} else "卷四·阴阳二遁圆图",
        "traditional_role": GOD_ROLES.get(god, god),
    }


def star_season_relation(star_element: str, month_element: str) -> str:
    if star_element == month_element:
        return "same_element"
    if ELEMENT_GENERATES[star_element] == month_element:
        return "star_generates_month"
    if ELEMENT_GENERATES[month_element] == star_element:
        return "month_generates_star"
    if ELEMENT_CONTROLS[star_element] == month_element:
        return "star_controls_month"
    return "month_controls_star"


def star_season_state(
    star_element: str, month_element: str, profile: str = DEFAULT_SEASON_PROFILE
) -> str:
    validate_profiles(DEFAULT_GOD_PROFILE, profile)
    return str(
        SEASON_PROFILES[profile]["states_by_relation"][
            star_season_relation(star_element, month_element)
        ]
    )


def gate_palace_relation(door: str, trigram: str) -> dict[str, Any]:
    door_element = DOOR_ELEMENTS[door]
    palace_element = PALACE_ELEMENTS[trigram]
    if door_element == palace_element:
        relation = "same_element"
    elif ELEMENT_CONTROLS[door_element] == palace_element:
        relation = "door_controls_palace"
    elif ELEMENT_CONTROLS[palace_element] == door_element:
        relation = "palace_controls_door"
    elif ELEMENT_GENERATES[door_element] == palace_element:
        relation = "door_generates_palace"
    else:
        relation = "palace_generates_door"
    return {
        "door": door,
        "trigram": trigram,
        "door_element": door_element,
        "palace_element": palace_element,
        "relation": relation,
        "verse_door_pressure": relation == "door_controls_palace",
        "palace_restricts_door": relation == "palace_controls_door",
        "prose_label": PROSE_GATE_LABELS[relation],
    }


def _source_disagreements(
    board: dict[str, Any], leader: QimenLeaders
) -> list[dict[str, Any]]:
    """Retain attested printed discrepancies without altering computed layout."""
    result: list[dict[str, Any]] = []
    ju = board["ju_text"]
    hour = board["time_ganzhi"]
    for number, at_hour, printed_gua, case_id in (
        (9, "庚辰", "坎", "vol4-yin9-gengchen-door"),
        (4, "癸亥", "离", "vol4-yin4-guihai-door"),
    ):
        if (
            ju.startswith(f"阴遁{'一二三四五六七八九'[number - 1]}局")
            and hour == at_hour
            and leader["raw_door_gong"] != printed_gua
        ):
            result.append(
                {
                    "case_id": case_id,
                    "field": "raw_door_gong",
                    "source_value": printed_gua,
                    "computed_value": leader["raw_door_gong"],
                    "status": "unresolved_print_rule_disagreement",
                }
            )
    if ju.startswith("阴遁三局") and hour == "壬辰":
        palace = next(p for p in board["palaces"] if p["trigram"] == "离")
        if palace["door"] != "杜门":
            result.append(
                {
                    "case_id": "de-shi-yin3-renchen",
                    "field": "door",
                    "source_value": "杜门",
                    "computed_value": palace["door"],
                    "status": "unresolved_scan_rule_disagreement",
                }
            )
    if ju.startswith("阳遁五局") and hour == "壬申":
        geng = next(p for p in board["palaces"] if "庚" in p["heaven_stems"])
        if geng["trigram"] != "离":
            result.append(
                {
                    "case_id": "vol2-yang5-renshen-geng-palace",
                    "field": "heaven_geng_palace",
                    "source_value": "离",
                    "computed_value": geng["trigram"],
                    "status": "unresolved_scan_rule_disagreement",
                }
            )
    return result


def enrich_qimen_evidence(
    board: dict[str, Any], *, seed: MetaphysicsSeed, leader: QimenLeaders
) -> dict[str, Any]:
    """Attach structured palace states, horse star, void palaces, and Qimen patterns."""
    month_branch = seed.pillars["month"][1]
    month_element = BRANCH_ELEMENTS[month_branch][0].value
    god_profile = board.setdefault("god_profile", DEFAULT_GOD_PROFILE)
    season_profile = board.setdefault("season_profile", DEFAULT_SEASON_PROFILE)
    validate_profiles(god_profile, season_profile)

    horse = compute_horse_star(board["time_ganzhi"])
    board["horse_star"] = horse
    hour_void_chars = set(board["kongwang"][:2])
    day_void_chars = set(board["day_kongwang"][:2])
    hour_void_palaces: list[str] = []
    day_void_palaces: list[str] = []

    patterns: list[dict[str, Any]] = []
    for index, palace in enumerate(board["palaces"]):
        trigram = palace["trigram"]
        palace["direction"] = DIRECTIONS[trigram]
        palace["element"] = PALACE_ELEMENTS[trigram]
        branches = PALACE_BRANCHES[trigram]
        h_void = [b for b in branches if b in hour_void_chars]
        d_void = [b for b in branches if b in day_void_chars]
        if h_void:
            hour_void_palaces.append(palace["name"])
        if d_void:
            day_void_palaces.append(palace["name"])
        palace["hour_void_branches"] = h_void
        palace["day_void_branches"] = d_void
        palace["is_horse_palace"] = trigram == horse["trigram"]

        if trigram == "中" and board.get("layout") != "fei":
            continue

        door = palace["door"]
        star = palace["star"]
        gate_rel = gate_palace_relation(door, trigram) if door else None
        palace["door_palace_relation"] = gate_rel["relation"] if gate_rel else None
        palace["door_pressure"] = bool(gate_rel and gate_rel["verse_door_pressure"])
        palace["star_season_state"] = (
            star_season_state(STAR_ELEMENTS[star], month_element, season_profile)
            if star
            else None
        )

        # Wonder tombs (三奇入墓)
        tombs = [s for s in palace["heaven_stems"] if WONDER_TOMBS.get(s) == trigram]
        palace["wonder_tombs"] = tombs
        for sky in tombs:
            patterns.append(
                {
                    "rule_id": "wonder_tomb",
                    "name": "三奇入墓",
                    "palace": palace["name"],
                    "facts": {"heaven_stem": sky, "trigram": trigram},
                }
            )

        # Six-instrument punishment (六仪击刑)
        punished = [
            {"xun_head": h, "hidden_stem": s, "punished_branch": b}
            for h, (s, b, t) in PUNISHMENT_BY_HEAD.items()
            if s in palace["heaven_stems"] and t == trigram
        ]
        palace["punishments"] = [r["hidden_stem"] for r in punished]
        for r in punished:
            patterns.append(
                {
                    "rule_id": "six_instrument_punishment",
                    "name": "六仪击刑",
                    "palace": palace["name"],
                    "facts": {
                        "heaven_stem": r["hidden_stem"],
                        "trigram": trigram,
                        "instrument_xun_head": r["xun_head"],
                        "punished_branch": r["punished_branch"],
                    },
                }
            )

        if gate_rel and gate_rel["verse_door_pressure"]:
            patterns.append(
                {
                    "rule_id": "door_pressure",
                    "name": "门迫",
                    "palace": palace["name"],
                    "facts": {
                        "door": door,
                        "door_element": gate_rel["door_element"],
                        "palace_element": gate_rel["palace_element"],
                    },
                }
            )

        # Stem-pair & combination patterns
        _append_palace_patterns(
            patterns,
            palace=palace,
            leader=leader,
            day_ganzhi=board["day_ganzhi"],
            time_ganzhi=board["time_ganzhi"],
        )

    board["void_palaces"] = {"hour": hour_void_palaces, "day": day_void_palaces}
    board["hidden_stems_palace_map"] = {
        p["name"]: p["hidden_stem"] for p in board["palaces"]
    }

    # Global structure checks (伏吟, 反吟, 五不遇时, 天显时格)
    outer = [p for p in board["palaces"] if p["trigram"] != "中"]
    day_stem, hour_stem = board["day_ganzhi"][0], board["time_ganzhi"][0]
    stems_order = "甲乙丙丁戊己庚辛壬癸"
    five_not_meet = (
        ELEMENT_CONTROLS[STEM_ELEMENTS[hour_stem][0].value]
        == STEM_ELEMENTS[day_stem][0].value
        and stems_order.index(hour_stem) % 2 == stems_order.index(day_stem) % 2
    )
    tian_xian = board["time_ganzhi"] in TIAN_XIAN_HOURS[day_stem]
    board["structure"] = {
        "hour_branch_tomb": board["time_ganzhi"] in HOUR_BRANCH_TOMBS,
        "stars_fuyin": all(p["heaven_origin_trigram"] == p["trigram"] for p in outer),
        "stars_fanyin": all(
            p["heaven_origin_trigram"] == OPPOSITE_PALACE[p["trigram"]] for p in outer
        ),
        "doors_fuyin": all(p["door"] == NATIVE_DOORS[p["trigram"]] for p in outer),
        "doors_fanyin": all(
            p["door"] == NATIVE_DOORS[OPPOSITE_PALACE[p["trigram"]]] for p in outer
        ),
        "stems_fuyin": all(p["heaven_stem"] == p["earth_stem"] for p in outer),
        "stems_fanyin": all(
            p["heaven_origin_trigram"] == OPPOSITE_PALACE[p["trigram"]]
            and p["heaven_stem"] != p["earth_stem"]
            for p in outer
        ),
        "five_not_meet": five_not_meet,
        "tian_xian_time": tian_xian,
    }
    if five_not_meet:
        patterns.append(
            {
                "rule_id": "five_not_meet",
                "name": "五不遇时",
                "palace": "全局",
                "facts": {"day_ganzhi": board["day_ganzhi"], "time_ganzhi": board["time_ganzhi"]},
            }
        )
    if tian_xian:
        patterns.append(
            {
                "rule_id": "tian_xian_time",
                "name": "天显时格",
                "palace": "全局",
                "facts": {"day_ganzhi": board["day_ganzhi"], "time_ganzhi": board["time_ganzhi"]},
            }
        )

    board["patterns"] = patterns
    board["stem_context"] = {
        "day": {
            "ganzhi": board["day_ganzhi"],
            "literal_stem": day_stem,
            "xun_head": board["day_xun_head"],
        },
        "hour": {
            "ganzhi": board["time_ganzhi"],
            "literal_stem": hour_stem,
            "effective_stem": leader["zhifu_heaven_stem"]
            if hour_stem == "甲"
            else hour_stem,
            "xun_head": leader["xun_head"],
        },
    }
    board["source_disagreements"] = _source_disagreements(board, leader)
    board["rule_profiles"] = {
        "god": {"id": god_profile, "title": GOD_PROFILES[god_profile]["title"]},
        "season": {
            "id": season_profile,
            "title": SEASON_PROFILES[season_profile]["title"],
        },
        "lodging": {"id": board.get("lodging_policy", "kun2")},
    }
    board["rulesets"] = [
        {
            "id": RULESET_ID,
            "version": "3.0.0",
            "title": "时家奇门（转盘/飞盘、置闰/拆补/茅山、寄宫可选）",
            "classical_author": "明·程道生等",
            "classical_conformance": "implemented",
            "ju_method": board["ju_method"],
        }
    ]
    board["calendar_policy"] = {
        "timezone": seed.timezone,
        "timezone_rules": timezone_rules_metadata(seed.timezone),
        "civil_datetime": seed.input_isoformat(),
        "corrected_datetime": seed.clock_isoformat(),
        "hour_clock": "apparent_solar" if seed.applied_true_solar else "civil",
        "day_boundary": "23:00",
        "ju_term": board["ju_term"],
        "ju_method": board["ju_method"],
        "solar_term_provider": seed.calendar_context["current_solar_term"].get(
            "resolution_provider", "unknown"
        ),
    }
    board["rule_trace"] = [
        {
            "rule_id": "ju_resolution",
            "inputs": {"day_ganzhi": board["day_ganzhi"], "ju_method": board["ju_method"]},
            "outputs": {
                "ju_term": board["ju_term"],
                "dun_type": board["dun_type"],
                "ju_number": board["ju_number"],
                "yuan": board["yuan"],
            },
        },
        {
            "rule_id": "leaders",
            "inputs": {"time_ganzhi": board["time_ganzhi"], "layout": board["layout"]},
            "outputs": {
                "zhifu_star": board["zhifu"]["star"],
                "zhifu_palace": board["zhifu"]["palace"],
                "zhishi_door": board["zhishi"]["door"],
                "zhishi_palace": board["zhishi"]["palace"],
                "horse_star": horse,
            },
        },
        {
            "rule_id": "structure",
            "inputs": {"month_branch": month_branch, "kongwang": board["kongwang"]},
            "outputs": board["structure"],
        },
    ]
    board["assessment"] = {
        "calculation_scope": f"time_qimen_{board['layout']}_{board['ju_method']}",
        "classical_conformance": "implemented",
    }
    return board


def _append_palace_patterns(
    patterns: list[dict[str, Any]],
    *,
    palace: dict[str, Any],
    leader: QimenLeaders,
    day_ganzhi: str,
    time_ganzhi: str,
) -> None:
    trigram = palace["trigram"]
    door = palace["door"]
    god = palace["god"]
    pname = palace["name"]
    hidden_head = leader["zhifu_heaven_stem"]
    native_host = (
        leader["lodged_gong"] if leader["source_gong"] == "中" else leader["source_gong"]
    )
    day_stem = day_ganzhi[0]
    hour_stem = hidden_head if time_ganzhi[0] == "甲" else time_ganzhi[0]

    for sky in palace["heaven_stems"]:
        for earth in palace["earth_stems"]:
            facts = {"heaven_stem": sky, "earth_stem": earth, "door": door}
            if (sky, earth) in STEM_KEY_PATTERNS:
                rule_id, name = STEM_KEY_PATTERNS[(sky, earth)]
                patterns.append(
                    {"rule_id": rule_id, "name": name, "palace": pname, "facts": facts}
                )
            ground_head = earth == hidden_head and trigram == native_host
            moving_head = sky == hidden_head and trigram == leader["star_gong"]
            if sky == "丙" and ground_head:
                patterns.append(
                    {
                        "rule_id": "flying_bird_enters_cave",
                        "name": "飞鸟跌穴",
                        "palace": pname,
                        "facts": facts,
                    }
                )
            if moving_head and earth == "丙":
                patterns.append(
                    {
                        "rule_id": "dragon_returns_head",
                        "name": "青龙返首",
                        "palace": pname,
                        "facts": facts,
                    }
                )
            if sky == "庚" and ground_head:
                patterns.append(
                    {
                        "rule_id": "hidden_palace",
                        "name": "天乙伏宫格",
                        "palace": pname,
                        "facts": facts,
                    }
                )
            if moving_head and earth == "庚":
                patterns.append(
                    {
                        "rule_id": "flying_palace",
                        "name": "天乙飞宫格",
                        "palace": pname,
                        "facts": facts,
                    }
                )
            if earth in DE_SHI.get(sky, set()):
                patterns.append(
                    {
                        "rule_id": "wonders_de_shi",
                        "name": "三奇得使",
                        "palace": pname,
                        "facts": facts,
                    }
                )
            if sky == "丙" and earth == "丁" and door == "生门":
                patterns.append(
                    {"rule_id": "heaven_dun", "name": "天遁", "palace": pname, "facts": facts}
                )
            if sky == "乙" and earth == "己" and door == "开门":
                patterns.append(
                    {"rule_id": "earth_dun", "name": "地遁", "palace": pname, "facts": facts}
                )
            if sky == "乙" and earth in {"辛", "己"} and door in GOOD_DOORS:
                if sky == "乙" and earth == "辛":
                    patterns.append(
                        {"rule_id": "cloud_dun", "name": "云遁", "palace": pname, "facts": facts}
                    )
            if sky == "乙" and earth == "癸" and door == "休门":
                patterns.append(
                    {"rule_id": "dragon_dun", "name": "龙遁", "palace": pname, "facts": facts}
                )
            if day_stem != "甲":
                if sky == "庚" and earth == day_stem:
                    patterns.append(
                        {
                            "rule_id": "hidden_day_stem",
                            "name": "伏干格",
                            "palace": pname,
                            "facts": facts,
                        }
                    )
                if sky == day_stem and earth == "庚":
                    patterns.append(
                        {
                            "rule_id": "flying_day_stem",
                            "name": "飞干格",
                            "palace": pname,
                            "facts": facts,
                        }
                    )
            if sky == "庚" and earth == hour_stem:
                patterns.append(
                    {
                        "rule_id": "hour_stem_block",
                        "name": "时格",
                        "palace": pname,
                        "facts": facts,
                    }
                )

        # Nine Duns (人/神/鬼/风/云/龙/虎遁) + 三诈 + 五假
        if sky == "丁" and door == "休门" and god == "太阴":
            patterns.append(
                {
                    "rule_id": "human_dun",
                    "name": "人遁",
                    "palace": pname,
                    "facts": {"heaven_stem": "丁", "door": door, "god": god},
                }
            )
        if sky == "丙" and door == "生门" and god == "九天":
            patterns.append(
                {
                    "rule_id": "spirit_dun",
                    "name": "神遁",
                    "palace": pname,
                    "facts": {"heaven_stem": "丙", "door": door, "god": god},
                }
            )
        if sky in {"乙", "丁"} and door == "杜门" and god == "九地":
            patterns.append(
                {
                    "rule_id": "ghost_dun",
                    "name": "鬼遁",
                    "palace": pname,
                    "facts": {"heaven_stem": sky, "door": door, "god": god},
                }
            )
        if sky == "乙" and door in GOOD_DOORS and trigram == "巽":
            patterns.append(
                {
                    "rule_id": "wind_dun",
                    "name": "风遁",
                    "palace": pname,
                    "facts": {"heaven_stem": "乙", "door": door, "trigram": trigram},
                }
            )
        if sky == "乙" and door == "休门" and trigram == "坎":
            patterns.append(
                {
                    "rule_id": "dragon_dun",
                    "name": "龙遁",
                    "palace": pname,
                    "facts": {"heaven_stem": "乙", "door": door, "trigram": trigram},
                }
            )
        if (
            (sky == "乙" and door in {"休门", "生门"} and trigram == "艮")
            or (sky == "庚" and door == "开门" and trigram == "兑")
        ):
            patterns.append(
                {
                    "rule_id": "tiger_dun",
                    "name": "虎遁",
                    "palace": pname,
                    "facts": {"heaven_stem": sky, "door": door, "trigram": trigram},
                }
            )

    # 三诈 & 五假
    wonders = [s for s in palace["heaven_stems"] if s in "乙丙丁"]
    if wonders and door in GOOD_DOORS and god in THREE_DECEPTIONS:
        rule_id, name = THREE_DECEPTIONS[god]
        patterns.append(
            {
                "rule_id": rule_id,
                "name": name,
                "palace": pname,
                "facts": {"heaven_wonder_stems": wonders, "door": door, "god": god},
            }
        )
    for rule_id, name, wanted_door, stems, wanted_god in FIVE_JIA:
        eligible = [s for s in palace["heaven_stems"] if s in stems]
        if door == wanted_door and god == wanted_god and eligible:
            patterns.append(
                {
                    "rule_id": rule_id,
                    "name": name,
                    "palace": pname,
                    "facts": {
                        "qualifying_heaven_stems": eligible,
                        "door": door,
                        "god": god,
                    },
                }
            )
    if trigram == leader["door_gong"] and "丁" in palace["earth_stems"]:
        patterns.append(
            {
                "rule_id": "jade_maiden_gate",
                "name": "玉女守门",
                "palace": pname,
                "facts": {"earth_stem": "丁", "door": door, "hour_ganzhi": time_ganzhi},
            }
        )
