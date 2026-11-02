"""Source-scoped Qimen evidence; rule matches never assert real-world events."""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict

from fatebridge.core.almanac import (
    _solar_terms_for_context_year,
    get_solar_terms_for_year,
    localize_datetime,
)
from fatebridge.core.metaphysics.common import (
    BRANCH_ELEMENTS,
    ELEMENT_CONTROLS,
    MetaphysicsSeed,
)
from fatebridge.core.qimen_calendar_stems import (
    match_calendar_stems,
    resolve_calendar_stems,
)
from fatebridge.core.qimen_combinations import build_combinations
from fatebridge.core.qimen_five_jia import build_five_jia
from fatebridge.core.qimen_gate_relations import (
    DOOR_ELEMENTS,
    PALACE_ELEMENTS,
    gate_palace_relation,
)
from fatebridge.core.qimen_profiles import (
    DEFAULT_GOD_PROFILE,
    DEFAULT_SEASON_PROFILE,
    describe_profiles,
    god_evidence,
    star_season_relation,
    star_season_state,
)
from fatebridge.core.qimen_punishment import palace_punishment
from fatebridge.core.qimen_stem_context import build_stem_context
from fatebridge.core.qimen_three_deceptions import build_three_deceptions
from fatebridge.core.qimen_time_conditions import build_hour_branch_tomb
from fatebridge.core.qimen_tombs import palace_wonder_tombs
from fatebridge.core.solar_model_policy import solar_context_input_years
from fatebridge.utils.timezones import timezone_rules_metadata

SOURCE = "https://zh.wikisource.org/w/index.php?oldid=625946"
RULESET_ID = "qimen_rotating_kun2_v2"
SCAN_SOURCE = "https://ourartnet.com/King_James/Hushulei/047.pdf"
STAR_ELEMENTS = {
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
PALACE_BRANCHES = {
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
DIRECTIONS = {
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
NATIVE_DOORS = {
    "坎": "休门",
    "坤": "死门",
    "震": "伤门",
    "巽": "杜门",
    "乾": "开门",
    "兑": "惊门",
    "艮": "生门",
    "离": "景门",
}
OPPOSITE = {
    "坎": "离",
    "艮": "坤",
    "震": "兑",
    "巽": "乾",
    "离": "坎",
    "坤": "艮",
    "兑": "震",
    "乾": "巽",
}
STEM_PATTERNS = {
    ("庚", "癸"): (
        "大格",
        "天盘庚加地盘癸，原文称大格；传统描述阻隔，不直接断言现实失物不可得或某人不在。",
    ),
    ("庚", "壬"): (
        "小格",
        "天盘庚加地盘壬，原文又称伏格；传统描述阻隔，不与伏吟或伏宫格混为同一规则。",
    ),
    ("庚", "己"): ("刑格", "传统上提示推进受阻；不能据此断定现实损失。"),
    ("乙", "辛"): ("青龙逃走", "传统上提示退避与牵制；不能据此断定现实失败。"),
    ("辛", "乙"): ("白虎猖狂", "传统上提示冲突与失序；需核实实际约束。"),
    ("丁", "癸"): ("朱雀投江", "传统上提示表达或文书受阻；可检查信息传递。"),
    ("癸", "丁"): ("螣蛇夭矫", "传统上提示纠缠与变动；可复核尚未确认的信息。"),
    ("庚", "丙"): ("太白入荧", "古籍用于主客进退判断；不直接转成现代事件结论。"),
    ("丙", "庚"): ("荧入太白", "古籍用于主客进退判断；不直接转成现代事件结论。"),
}


def _source_disagreements(
    board: Dict[str, Any], leader: Dict[str, str]
) -> list[dict[str, Any]]:
    """Retain printed conflicts; they never override a calculated palace."""
    result: list[dict[str, Any]] = []
    ju = board["ju_text"]
    hour = board["time_ganzhi"]
    for number, at_hour, printed_gua, page, case_id in [
        (9, "庚辰", "坎", 67, "vol4-yin9-gengchen-door"),
        (4, "癸亥", "离", 69, "vol4-yin4-guihai-door"),
    ]:
        if (
            ju.startswith(f"阴遁{'一二三四五六七八九'[number - 1]}局")
            and hour == at_hour
        ):
            if leader["raw_door_gong"] != printed_gua:
                result.append(
                    {
                        "case_id": case_id,
                        "field": "raw_door_gong",
                        "source": SCAN_SOURCE,
                        "source_section": "卷四·直使加时宫数表",
                        "source_scan_page": page,
                        "source_value": printed_gua,
                        "computed_value": leader["raw_door_gong"],
                        "status": "unresolved_print_rule_disagreement",
                        "evidence_paths": [
                            "qimen.rule_trace.0.outputs.raw_door_gong",
                            "qimen.zhishi.trigram",
                        ],
                    }
                )
    if ju.startswith("阴遁三局") and hour == "壬辰":
        palace = next(p for p in board["palaces"] if p["trigram"] == "离")
        if palace["door"] != "杜门":
            result.append(
                {
                    "case_id": "de-shi-yin3-renchen",
                    "field": "door",
                    "source": SCAN_SOURCE,
                    "source_section": "卷二·三奇得使",
                    "source_scan_page": 19,
                    "source_value": "杜门",
                    "computed_value": palace["door"],
                    "status": "unresolved_scan_rule_disagreement",
                    "supporting_source": {
                        "section": "卷四·阴三局数表甲申旬",
                        "scan_page": 70,
                        "raw_star_palace": 8,
                        "raw_door_palace": 2,
                        "leader_door": "休门",
                        "scope": "卷四值使宫数支持当前移门结果，仍不消除卷二门名冲突",
                    },
                    "evidence_paths": [
                        "qimen.palaces.8.door",
                        "qimen.rule_trace.0.outputs",
                    ],
                }
            )
    if ju.startswith("阳遁五局") and hour == "壬申":
        geng = next(p for p in board["palaces"] if "庚" in p["heaven_stems"])
        if geng["trigram"] != "离":
            result.append(
                {
                    "case_id": "vol2-yang5-renshen-geng-palace",
                    "field": "heaven_geng_palace",
                    "source": SCAN_SOURCE,
                    "source_section": "卷二·伏干格",
                    "source_scan_page": 31,
                    "source_value": "离",
                    "computed_value": geng["trigram"],
                    "status": "unresolved_scan_rule_disagreement",
                    "supporting_source": {
                        "title": "古今图书集成·艺术典第705卷·释天乙伏干格",
                        "source": "https://zh.wikisource.org/w/index.php?title=Page:Gujin_Tushu_Jicheng,_Volume_478_(1700-1725).djvu/127&oldid=1899797",
                        "source_value": "坤",
                        "scope": "另一引文写二宫；不能消除所选遁甲演义影印写九宫的差异，日甲身份另待核",
                    },
                    "evidence_paths": ["qimen.palaces", "qimen.stem_context.day"],
                }
            )
    return result


def enrich_qimen_evidence(
    board: Dict[str, Any], *, seed: MetaphysicsSeed, leader: Dict[str, str]
) -> Dict[str, Any]:
    month_branch = seed.pillars["month"][1]
    month_element = BRANCH_ELEMENTS[month_branch][0].value
    board.setdefault("god_profile", DEFAULT_GOD_PROFILE)
    board.setdefault("season_profile", DEFAULT_SEASON_PROFILE)
    profiles = describe_profiles(board["god_profile"], board["season_profile"])
    board["rule_profiles"] = profiles
    board["rulesets"] = [
        {
            "id": RULESET_ID,
            "version": "2.12.0",
            "title": "时家转盘，天禽及中干寄坤二",
            "author": "FateBridge contributors",
            "classical_author": "明·程道生",
            "source": SOURCE,
            "source_kind": "online_transcription_with_selected_scan_comparison",
            "scan_collation": {
                "source": SCAN_SOURCE,
                "source_sha256": "58f7596ff01debe06f447ecbd3a67be4b95a5ab45df98defb04c943f1537f8d3",
                "pages": [
                    7,
                    16,
                    17,
                    18,
                    19,
                    20,
                    25,
                    26,
                    29,
                    31,
                    32,
                    33,
                    34,
                    37,
                    38,
                    48,
                    49,
                    62,
                    63,
                    64,
                    65,
                    66,
                    67,
                    68,
                    69,
                    70,
                    71,
                ],
                "scope": "卷二组合、三诈完整命名与缺项语境、旬首依赖例局；卷四十八局1080时值符值使宫数及表头星门；卷一、三旺相异文与卷三正文、卷四四幅圆图八神；非全盘各层或全书校勘",
                "bibliographic_authentication": "not_completed",
                "unresolved_case_ids": [
                    "de-shi-yin3-renchen",
                    "vol4-yin9-gengchen-door",
                    "vol4-yin4-guihai-door",
                    "vol2-yang5-renshen-geng-palace",
                ],
            },
            "sections": [
                "卷一·时家奇门",
                "卷一·八门九星逐时移宫诀",
                "卷一·烟波钓叟赋",
                "卷一·超神接气置闰诀",
                "卷三·九星所属及旺衰正文／九星旺相休囚表／天乙直符吉凶神说",
                "卷二·五不遇／三奇入墓／六仪击刑／门迫宫迫／三奇凶格",
                "卷二·飞鸟跌穴／青龙回首／大隔／小隔／伏宫格／飞宫格",
                "卷二·三奇入墓·时干支入墓六时",
                "卷二·三诈五假·三诈完整组合及缺项释读范围",
                "卷二·三诈五假·五假四类完整组合与人假未决身份",
                "卷四·阴阳二遁十八局值符值使逐时宫数表",
            ],
            "classical_conformance": "partial_excerpt",
            "ju_method": board["ju_method"],
            "conventions": [
                "23:00子初换日",
                "门迫布尔按歌诀门克宫；正文吉迫、凶迫、和、义为另列关系名，不当现实吉凶",
                "中五寄坤二，天禽随天芮，寄干单列",
                f"八神采用{profiles['god']['title']}；九星旺衰采用{profiles['season']['title']}",
                "拆补法为另列现代约定，不宣称全书原法",
                "置闰阈值统一为民用日期超前达到9日；未穷尽历史异说",
                "奇门演卦为软件派生，未据原典验收",
                "三诈按天盘奇、门、所选八神同宫完整组合命名；缺项吉凶不采纳，人遁重叠不算独立印证",
                "五假按明确门干神组合命名天、地、神、鬼四类；丁己癸不称三奇，人假六合身份未决，己候选未采纳",
            ],
            "unresolved": [
                "只完成第三方托管影印所列页面的选取观察；部分馆藏书目已核，所选PDF的馆藏对应及全书校勘未完成",
                "本书八神名称、九星旺衰存在章内和章节差异；按所选口径逐项呈现，未据此判全书一致",
                "卷二阴三局壬辰得使例写杜门临九，规则推得开门，保留原文冲突未解决",
                "卷四阴九庚辰直使原文坎一与规则坤二不符；阴四癸亥原文离九与规则艮八不符，均保留未解决",
                "卷二阳五壬申伏干例写天柱庚临离九，当前共转规则得坤二；另一古籍引文写二宫，原典差异继续保留",
                "置闰锚点及九日阈值的历代异说未穷尽独立验收",
                "本命行年、三遁异文、全书其余格局未实现；三奇入墓按卷二王璋所列口径",
                "三奇入墓段首乙丙丁临六宫戌句与王璋明确列举的释读及优先关系待核；仅展示字面候选对照，不自动采纳",
                "日甲伏干、飞干仅列日甲本身藏仪与时旬藏仪两种候选，未采纳任一候选；岁格年界不同时及岁干、月朔干为甲时亦保留未决",
                "月朔干取现代民用农历本月初一的日干，非八字月干；只支持已列离线历表范围，未复原古历或合朔时刻",
                "时干支入墓仅按卷二正文六组字面时柱判断，不借甲的藏仪替代；天盘时干落墓宫未在此规则判定",
                "六仪击刑保留广义六仪落刑宫匹配为暂定取法，并列本时直符窄读；正文未明写仅本旬，同段卯时例能区分两法，范围尚未裁定",
                "三诈歌诀得二亦吉与正文门合太阴无奇不利的释读优先未决；十分七分不作概率",
                "五假人假句的六合与九天层次及身份未决；另段己为六合仅支持未采纳候选，不改字作六壬，不以未命名当不存在",
                "新增四个旬首格只核对所列甲子旬原例；其余五旬按本时旬首及现行寄宫规则推算，未独立完成原例验收",
                "现代时区、定气及真太阳时为工程约定，不等于复原古代平气历",
            ],
            "real_world_efficacy": "not_tested",
        }
    ]
    # The annual schedule is selected by the original civil input year and
    # already covers corrected/late-Zi dates across New Year. Observe that
    # window and the actual effective label years under the selected model.
    # Do not also request the previous year of a corrected prior-year label:
    # that is outside the schedule's dependencies and can request1798.
    context_year = localize_datetime(seed.input_datetime, seed.timezone).year
    effective_clock = localize_datetime(seed.corrected_datetime, seed.timezone)
    effective_date = effective_clock.date() + timedelta(
        days=int(effective_clock.hour == 23)
    )
    grid_years = sorted(
        {context_year - 1, context_year, effective_clock.year, effective_date.year}
    )
    low, high = solar_context_input_years(context_year)
    providers = sorted(
        {
            term.resolution_provider
            for year in grid_years
            for term in (
                _solar_terms_for_context_year(year, seed.timezone, context_year)
                if low <= context_year <= high and not low <= year <= high
                else get_solar_terms_for_year(year, seed.timezone)
            )
        }
    )
    board["calendar_policy"] = {
        "solar_time_adjustment": (
            dict(seed.solar_time_adjustment)
            if seed.applied_true_solar and seed.solar_time_adjustment is not None
            else {
                "applied": seed.applied_true_solar,
                "status": (
                    "missing_seed_adjustment_provenance"
                    if seed.applied_true_solar
                    else "not_applied"
                ),
                "total_correction_minutes": seed.total_correction_minutes,
            }
        ),
        "timezone": seed.timezone,
        "timezone_rules": timezone_rules_metadata(seed.timezone),
        "civil_datetime": seed.input_datetime.isoformat(),
        "corrected_datetime": seed.corrected_datetime.isoformat(),
        "hour_clock": "apparent_solar" if seed.applied_true_solar else "civil",
        "day_boundary": "23:00",
        "xun_scope": "hour",
        "astronomical_term": seed.calendar_context["current_solar_term"],
        "ju_term": board["ju_term"],
        "ju_method": board["ju_method"],
        "solar_term_providers": providers,
        "term_grid_years_observed": grid_years,
        "precision_status": (
            "astronomical" if providers == ["swisseph"] else "approximate"
        ),
        "rule_change_granularity": (
            "five_day_yuan_at_23:00"
            if board["ju_method"] == "zhirun"
            else "solar_term_instant_and_futou_day"
        ),
    }
    trace = [
        {
            "rule_id": "leaders",
            "source": SOURCE,
            "section": "卷一·时家奇门／烟波钓叟赋",
            "inputs": {
                "day_ganzhi": board["day_ganzhi"],
                "time_ganzhi": board["time_ganzhi"],
                "ju_text": board["ju_text"],
            },
            "outputs": dict(leader),
        }
    ]
    trace.append(
        {
            "rule_id": "solar_time_adjustment",
            "source": "https://www.astro.com/swisseph/swephprg.htm",
            "section": "现代均时差与钟表标签修正，非原典历法认证",
            "outputs": dict(board["calendar_policy"]["solar_time_adjustment"]),
            "evidence_paths": ["qimen.calendar_policy.solar_time_adjustment"],
        }
    )
    trace.append(
        {
            "rule_id": "ju_resolution",
            "source": SOURCE,
            "section": "卷一·超神接气置闰诀；拆补为另列现代约定",
            "inputs": {
                "day_ganzhi": board["day_ganzhi"],
                "ju_method": board["ju_method"],
                "civil_term": seed.calendar_context["current_solar_term"]["name"],
            },
            "outputs": board.get("ju_decision", {}),
        }
    )
    trace.append(
        {
            "rule_id": "chapter_profiles",
            "source": SOURCE,
            "section": f"{profiles['god']['section']}；{profiles['season']['section']}；{profiles['wonder_tomb']['section']}；{profiles['six_instrument_punishment']['section']}；{profiles['door_palace_relation']['section']}",
            "inputs": {
                "god_profile": board["god_profile"],
                "season_profile": board["season_profile"],
                "dun_type": leader["dun_type"],
                "zhifu_trigram": leader["star_gong"],
            },
            "outputs": profiles,
            "evidence_paths": [
                "qimen.god_profile",
                "qimen.season_profile",
                "qimen.rule_profiles",
            ],
        }
    )
    patterns = []
    for index, palace in enumerate(board["palaces"]):
        trigram = palace["trigram"]
        palace["direction"] = DIRECTIONS[trigram]
        palace["element"] = PALACE_ELEMENTS[trigram]
        if trigram == "中":
            palace["evidence"] = {
                "status": "hosted_in_kun2",
                "note": "中宫保留地盘干；无独立八门八神，天禽与寄干在芮星宫列出。",
            }
            continue
        path = f"qimen.palaces.{index}"
        door = palace["door"]
        void = [
            branch
            for branch in PALACE_BRANCHES[trigram]
            if branch in board["kongwang"][:2]
        ]
        gate_relation = gate_palace_relation(door, trigram)
        door_pressure = gate_relation["verse_door_pressure"]
        evidence = {
            "wonder_tomb": palace_wonder_tombs(trigram, palace["heaven_stems"]),
            "six_instrument_punishment": palace_punishment(
                board["time_ganzhi"], trigram, palace["heaven_stems"]
            ),
            "hour_void_branches": void,
            "hour_void_scope": (
                "full"
                if len(void) == len(PALACE_BRANCHES[trigram])
                else "partial" if void else "none"
            ),
            "door_element": DOOR_ELEMENTS[door],
            "door_palace_relation": gate_relation,
            "door_pressure": door_pressure,
            "palace_restricts_door": gate_relation["palace_restricts_door"],
            "star_element": STAR_ELEMENTS[palace["star"]],
            "star_season_state": star_season_state(
                STAR_ELEMENTS[palace["star"]], month_element, board["season_profile"]
            ),
            "star_season_profile": board["season_profile"],
            "star_season_source_section": profiles["season"]["section"],
            "star_season_relation": star_season_relation(
                STAR_ELEMENTS[palace["star"]], month_element
            ),
            "god_interpretation": god_evidence(palace["god"]),
            "season_month_branch": month_branch,
            "season_month_element": month_element,
        }
        palace["evidence"] = evidence
        trace.append(
            {
                "rule_id": "palace_relations",
                "source": SOURCE,
                "section": f"门宫关系：卷一·烟波钓叟赋及卷二·门迫宫迫；九星旺衰：{profiles['season']['section']}；神义：{evidence['god_interpretation']['section']}；六仪击刑：{profiles['six_instrument_punishment']['section']}",
                "evidence_paths": [
                    path + ".door",
                    path + ".star",
                    path + ".trigram",
                    path + ".god",
                    path + ".heaven_stems",
                    "qimen.time_ganzhi",
                    "qimen.rule_profiles",
                    "four_pillars.month.branch",
                ],
                "outputs": dict(evidence),
            }
        )

        def match(rule_id: str, name: str, facts: Dict[str, Any], meaning: str) -> None:
            patterns.append(
                {
                    "rule_id": rule_id,
                    "name": name,
                    "palace": palace["name"],
                    "evidence_paths": [path],
                    "facts": facts,
                    "traditional_meaning": meaning,
                    "source": SOURCE,
                    "section": "卷二·"
                    + {
                        "door_pressure": "门迫宫迫",
                        "six_instrument_punishment": "六仪击刑",
                        "wonder_tomb": "三奇入墓",
                    }.get(
                        rule_id,
                        {
                            "朱雀投江": "朱雀入江",
                            "螣蛇夭矫": "螣蛇跃蹻",
                            "大格": "大隔",
                            "小格": "小隔并岁隔月隔日隔时隔",
                        }.get(name, name),
                    ),
                    "layer": "traditional_rule_match",
                }
            )
            if name in {"大格", "小格"}:
                patterns[-1]["source_scan_pages"] = [29]

        if door_pressure:
            match(
                "door_pressure",
                "门迫",
                {
                    "door": door,
                    "door_element": DOOR_ELEMENTS[door],
                    "palace_element": palace["element"],
                },
                "按歌诀门克宫称门迫；同段正文称此关系吉迫，名称不代表全盘或现实吉利，仍须合看实际条件。",
            )
            patterns[-1]["source_scan_pages"] = [34]
            patterns[-1]["qualification"] = {
                "condition": "按歌诀核实际门五行克宫五行；正文关系名另外保留",
                "condition_observed": True,
                "blocking_rule_names": [],
                "same_palace_conflicts": [],
                "source_disagreements": [],
                "door_palace_evidence": dict(gate_relation),
                "overall_judgment": "requires_whole_board",
                "outcome_inference_allowed": False,
            }
        for sky in palace["heaven_stems"]:
            if sky in evidence["wonder_tomb"]["selected_matched_stems"]:
                match(
                    "wonder_tomb",
                    "三奇入墓",
                    {"heaven_stem": sky, "trigram": trigram},
                    "按本书卷二王璋所列乙临坤、丙临乾、丁临艮的口径；传统上提示力量受限，不断现实灾祸。",
                )
                patterns[-1]["source_scan_pages"] = [33]
                patterns[-1]["qualification"] = {
                    "condition": "按已固定的卷二王璋列举核实际天盘奇及主干、寄干；不自动改用段首字面候选",
                    "condition_observed": True,
                    "blocking_rule_names": [],
                    "same_palace_conflicts": [],
                    "source_disagreements": [],
                    "tomb_evidence": dict(evidence["wonder_tomb"]),
                    "overall_judgment": "requires_whole_board",
                    "outcome_inference_allowed": False,
                }
            punishment = evidence["six_instrument_punishment"]
            if any(r["hidden_stem"] == sky for r in punishment["geometric_matches"]):
                instrument = next(
                    r
                    for r in punishment["geometric_matches"]
                    if r["hidden_stem"] == sky
                )
                match(
                    "six_instrument_punishment",
                    "六仪击刑",
                    {
                        "heaven_stem": sky,
                        "trigram": trigram,
                        "instrument_xun_head": instrument["xun_head"],
                        "hour_xun_head": punishment["xun_head"],
                        "punished_branch": instrument["punished_branch"],
                    },
                    "按暂定广义取法，此六仪落所刑之宫；其自身六甲身份与本时旬首分别列出，范围未裁定，不断现实灾祸。",
                )
                patterns[-1]["source_scan_pages"] = [33, 34]
                patterns[-1]["qualification"] = {
                    "condition": "按暂定广义取法核六仪落刑宫；本时直符窄读另列，原文范围未裁定",
                    "condition_observed": True,
                    "blocking_rule_names": [],
                    "same_palace_conflicts": [],
                    "source_disagreements": [],
                    "punishment_evidence": dict(punishment),
                    "punishment_instrument_identity": dict(instrument),
                    "overall_judgment": "requires_whole_board",
                    "outcome_inference_allowed": False,
                }
            for earth in palace["earth_stems"]:
                if (sky, earth) in STEM_PATTERNS:
                    name, meaning = STEM_PATTERNS[(sky, earth)]
                    match(
                        "stem_pair",
                        name,
                        {"heaven_stem": sky, "earth_stem": earth},
                        meaning,
                    )
    outer = [palace for palace in board["palaces"] if palace["trigram"] != "中"]
    hour_branch_tomb = build_hour_branch_tomb(board["time_ganzhi"], source=SOURCE)
    board["structure"] = {
        "hour_branch_tomb": hour_branch_tomb["matched"],
        "stars_fuyin": all(p["heaven_origin_trigram"] == p["trigram"] for p in outer),
        "stars_fanyin": all(
            p["heaven_origin_trigram"] == OPPOSITE[p["trigram"]] for p in outer
        ),
        "doors_fuyin": all(p["door"] == NATIVE_DOORS[p["trigram"]] for p in outer),
        "doors_fanyin": all(
            p["door"] == NATIVE_DOORS[OPPOSITE[p["trigram"]]] for p in outer
        ),
    }
    from fatebridge.utils.data import STEM_ELEMENTS

    day, hour = board["day_ganzhi"][0], board["time_ganzhi"][0]
    # 五不遇 uses same-polarity 七杀, not every instance of 时干克日干.
    stems = "甲乙丙丁戊己庚辛壬癸"
    board["structure"]["five_not_meet"] = (
        ELEMENT_CONTROLS[STEM_ELEMENTS[hour][0].value] == STEM_ELEMENTS[day][0].value
        and stems.index(hour) % 2 == stems.index(day) % 2
    )
    trace.append(
        {
            "rule_id": "structure",
            "source": SOURCE,
            "section": "卷二·五不遇／伏吟格／反吟格",
            "inputs": {"day_stem": day, "hour_stem": hour},
            "outputs": dict(board["structure"]),
        }
    )
    board["source_disagreements"] = _source_disagreements(board, leader)
    for pattern in patterns:
        if pattern["rule_id"] in {
            "wonder_tomb",
            "six_instrument_punishment",
            "door_pressure",
        }:
            pattern["qualification"]["source_disagreements"] = list(
                board["source_disagreements"]
            )
    day_hour_context, stem_patterns = build_stem_context(
        board, leader=leader, source=SOURCE
    )
    calendar_stems = resolve_calendar_stems(seed)
    calendar_patterns = match_calendar_stems(
        board, calendar_stems, leader=leader, source=SOURCE
    )
    stem_context = {
        **day_hour_context,
        **calendar_stems,
        "hour_branch_tomb": hour_branch_tomb,
        "year_and_lunar_month_start_rules": "literal_non_jia_with_explicit_unresolved_boundaries",
    }
    board["stem_context"] = stem_context
    trace.append(
        {
            "rule_id": "hour_branch_tomb",
            "source": SOURCE,
            "section": hour_branch_tomb["source_section"],
            "inputs": {"literal_hour_ganzhi": board["time_ganzhi"]},
            "outputs": hour_branch_tomb,
            "evidence_paths": [
                "qimen.time_ganzhi",
                "qimen.stem_context.hour_branch_tomb",
                "qimen.structure.hour_branch_tomb",
            ],
        }
    )
    patterns.extend([*stem_patterns, *calendar_patterns])
    trace.append(
        {
            "rule_id": "day_hour_stem_identity",
            "source": SOURCE,
            "section": "卷二·伏干格／飞干格／小隔并岁隔月隔日隔时隔",
            "inputs": {
                "day_ganzhi": board["day_ganzhi"],
                "hour_ganzhi": board["time_ganzhi"],
            },
            "outputs": day_hour_context,
            "evidence_paths": ["qimen.stem_context"],
        }
    )
    trace.append(
        {
            "rule_id": "calendar_stem_anchors",
            "source": SOURCE,
            "section": "卷二·小隔并岁隔月隔日隔时隔·岁格／月格",
            "inputs": {
                "civil_datetime": seed.input_datetime.isoformat(),
                "timezone": seed.timezone,
            },
            "outputs": calendar_stems,
            "evidence_paths": [
                "qimen.stem_context.year",
                "qimen.stem_context.lunar_month_start",
            ],
        }
    )
    trace.extend(
        {
            "rule_id": p["rule_id"],
            "source": p["source"],
            "section": p["section"],
            "evidence_paths": p["evidence_paths"],
            "outputs": {"facts": p["facts"], "qualification": p["qualification"]},
        }
        for p in [*stem_patterns, *calendar_patterns]
    )
    combinations = build_combinations(
        board, leader=leader, source=SOURCE, existing_patterns=patterns
    )
    patterns.extend(combinations)
    three_deceptions = build_three_deceptions(board, patterns)
    patterns.extend(three_deceptions)
    five_jia = build_five_jia(board, patterns)
    patterns.extend(five_jia)
    trace.append(
        {
            "rule_id": "five_jia_contexts",
            "source": SOURCE,
            "section": "卷二·三诈五假·五假",
            "inputs": {
                "profile_id": profiles["five_jia"]["id"],
                "layers": "actual_heaven_stems_door_selected_god",
            },
            "outputs": {
                "matched_names": [
                    {"palace": p["palace"], "rule_id": p["rule_id"]} for p in five_jia
                ],
                "human_jia_identity_resolved": False,
                "human_jia_formal_match": None,
            },
            "evidence_paths": [
                "qimen.rule_profiles.five_jia",
                *[
                    f"qimen.palaces.{i}.evidence.five_jia"
                    for i, p in enumerate(board["palaces"])
                    if p["trigram"] != "中"
                ],
            ],
        }
    )
    trace.append(
        {
            "rule_id": "three_deceptions_contexts",
            "source": SOURCE,
            "section": "卷二·三诈五假·三诈",
            "inputs": {
                "profile_id": profiles["three_deceptions"]["id"],
                "layers": "actual_heaven_stems_door_selected_god",
            },
            "outputs": {
                "matched_names": [
                    {"palace": p["palace"], "rule_id": p["rule_id"]}
                    for p in three_deceptions
                ],
                "partial_priority_unresolved_palaces": [
                    p["name"]
                    for p in board["palaces"]
                    if p.get("evidence", {})
                    .get("three_deceptions", {})
                    .get("prose_partial_case")
                    == "door_and_taiyin_without_wonder_priority_unresolved"
                ],
            },
            "evidence_paths": [
                "qimen.rule_profiles.three_deceptions",
                *[
                    f"qimen.palaces.{i}.evidence.three_deceptions"
                    for i, p in enumerate(board["palaces"])
                    if p["trigram"] != "中"
                ],
            ],
        }
    )
    trace.extend(
        {
            "rule_id": p["rule_id"],
            "source": p["source"],
            "section": p["section"],
            "evidence_paths": p["evidence_paths"],
            "outputs": {"facts": p["facts"], "qualification": p["qualification"]},
        }
        for p in [*combinations, *three_deceptions, *five_jia]
    )
    board["patterns"] = patterns
    board["rule_trace"] = trace
    board["assessment"] = {
        "calculation_scope": "time_qimen_rotating_board",
        "classical_conformance": "partial_excerpt",
        "interpretation_status": "rule_evidence_only",
        "real_world_efficacy": "not_tested",
        "authority_certified": False,
        "score": None,
    }
    return board
