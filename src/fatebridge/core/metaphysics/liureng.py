"""
Da Liu Ren (大六壬) board construction for the FateBridge metaphysics package.

Pure relocation from the package facade: the liu-ren-exclusive tables and
``_liureng_*`` helpers plus public ``build_liureng_board`` /
``build_liureng_runyear``. Shared 贵人/月将 tables and sexagenary/element
primitives are imported from ``.common``.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, TypedDict

from fatebridge.core.almanac import get_lunar_context, localize_datetime
from fatebridge.core.metaphysics.ren_sources import TANYUAN_SOURCE
from fatebridge.utils.birth_input import normalize_gender

from ...utils.data import EARTHLY_BRANCHES, HEAVENLY_STEMS
from .common import (
    ELEMENT_CONTROLS,
    ELEMENT_GENERATES,
    GUI_REN_SEQUENCE,
    SIX_CLASH_BRANCHES,
    SIX_HARM_BRANCHES,
    SIX_HARMONY_BRANCHES,
    YUE_JIANG_NAMES,
    MetaphysicsSeed,
    branch_element_text,
    ganzhi_text,
    kongwang_for_ganzhi,
    liuqin_against_day,
    rotate_sequence,
    sexagenary_index_for,
    sexagenary_text,
    stem_element_text,
    xun_head_for_ganzhi,
)
from .liureng_auxiliary_stars import build_auxiliary_stars
from .liureng_branch_relations import branch_relations
from .liureng_course_conditions import course_conditions_trace
from .liureng_cross_harmony import cross_harmony, cross_harmony_trace
from .liureng_day_placements import day_placement_patterns, day_placements_trace
from .liureng_emptiness import emptiness_evidence
from .liureng_god_yin import god_yin_spirits, god_yin_trace
from .liureng_life_stages import build_life_stages
from .liureng_ordered_patterns import ordered_patterns_trace
from .liureng_patterns import classify_transmission_pattern
from .liureng_progression import progression_trace, transmission_progression
from .liureng_seasonal import seasonal_evidence, seasonal_trace
from .liureng_transmission_relations import transmission_relations
from .liureng_transmissions import STEM_HOUSES as DAY_STEM_HOUSE
from .liureng_transmissions import select_transmissions
from .ren_calendar import symbolic_calendar_policy
from .ren_diurnal import resolve_diurnal
from .ren_evidence import ruleset_metadata, xun_dun_stems
from .ren_gods import (
    DEFAULT_GUIREN_PROFILE,
    TANYUAN_TRANSCRIPTION,
    GuirenProfile,
    noble_start,
)

LIURENG_MONTH_GENERAL_BY_TERM = {
    "大寒": "子",
    "立春": "子",
    "雨水": "亥",
    "惊蛰": "亥",
    "春分": "戌",
    "清明": "戌",
    "谷雨": "酉",
    "立夏": "酉",
    "小满": "申",
    "芒种": "申",
    "夏至": "未",
    "小暑": "未",
    "大暑": "午",
    "立秋": "午",
    "处暑": "巳",
    "白露": "巳",
    "秋分": "辰",
    "寒露": "辰",
    "霜降": "卯",
    "立冬": "卯",
    "小雪": "寅",
    "大雪": "寅",
    "冬至": "丑",
    "小寒": "丑",
}


LIURENG_GUIREN_REVERSED_EARTH = frozenset("巳午未申酉戌")


def _liureng_month_general_for_term(current_term: str) -> str:
    if current_term not in LIURENG_MONTH_GENERAL_BY_TERM:
        raise ValueError(f"未知节气 {current_term!r}，不能用月建代替月将")
    return LIURENG_MONTH_GENERAL_BY_TERM[current_term]


def _liureng_month_general_on_hour(
    *,
    hour_branch: str,
    month_general_branch: str,
) -> Dict[str, str]:
    earth_order = rotate_sequence(EARTHLY_BRANCHES, hour_branch)
    sky_order = rotate_sequence(EARTHLY_BRANCHES, month_general_branch)
    return {
        earth_branch: sky_order[index] for index, earth_branch in enumerate(earth_order)
    }


class TwelveGodLayout(TypedDict):
    sky_by_earth: Dict[str, str]
    god_by_sky: Dict[str, str]
    noble_start_branch: str
    noble_earth_branch: str
    is_reverse: bool


def twelve_god_layout(
    *,
    hour_branch: str,
    month_general_branch: str,
    day_stem: str,
    is_diurnal: bool,
    guiren_profile: GuirenProfile = DEFAULT_GUIREN_PROFILE,
) -> TwelveGodLayout:
    """Lay out supplied symbolic conditions without inventing a civil date.

    The normal board builder resolves calendar/diurnal conditions first, then
    uses this same layout. A source-conditioned replay cannot certify those
    upstream conditions or a Taiyi four-corner lodging rule.
    """
    if (
        hour_branch not in tuple(EARTHLY_BRANCHES)
        or month_general_branch not in tuple(EARTHLY_BRANCHES)
        or day_stem not in tuple(HEAVENLY_STEMS)
        or type(is_diurnal) is not bool
    ):
        raise ValueError("十二神将布置需要明确的时支、月将、日干与昼夜条件")
    start = noble_start(day_stem, is_diurnal, guiren_profile)
    sky = _liureng_month_general_on_hour(
        hour_branch=hour_branch, month_general_branch=month_general_branch
    )
    earth = next(branch for branch, upper in sky.items() if upper == start)
    reverse = earth in LIURENG_GUIREN_REVERSED_EARTH
    branches = rotate_sequence(EARTHLY_BRANCHES, start, reverse=reverse)
    return {
        "sky_by_earth": sky,
        "god_by_sky": dict(zip(branches, GUI_REN_SEQUENCE)),
        "noble_start_branch": start,
        "noble_earth_branch": earth,
        "is_reverse": reverse,
    }


def _branch_relation(
    left_branch: str,
    right_branch: str,
    *,
    same_label: str = "同支",
) -> str:
    if left_branch == right_branch:
        return same_label
    if SIX_HARMONY_BRANCHES.get(left_branch) == right_branch:
        return "六合"
    if SIX_CLASH_BRANCHES.get(left_branch) == right_branch:
        return "六冲"
    if SIX_HARM_BRANCHES.get(left_branch) == right_branch:
        return "六害"
    return "平"


def _liureng_judge_lesson(
    *,
    upper_branch: str,
    lower_branch: str,
    day_branch: str,
    relation: str,
) -> Tuple[str, str, str, str]:
    with_day = _branch_relation(upper_branch, day_branch, same_label="比和")
    with_lower = _branch_relation(upper_branch, lower_branch, same_label="伏吟")

    # 大六壬课体判断以"上下"关系为主：伏吟=上下同位，返吟=上下相冲，六合=上下合。
    # 上神与日支的关系只作辅参，不应单独触发 返吟/六合 类型，否则会把
    # "上下六合、上神冲日" 这种组合误判为返吟。
    if with_lower == "伏吟":
        return "伏吟", "上神与下神同位，伏吟取象。", with_day, with_lower
    if with_lower == "六冲":
        return "返吟", "上神与下神相冲，取返吟往复之象。", with_day, with_lower
    if with_lower == "六害":
        return "六害", "上下见六害关系；这不是九宗门涉害取传。", with_day, with_lower
    if relation == "官鬼":
        return "官鬼", "上神与日干为官鬼关系，不代替九宗门取传。", with_day, with_lower
    if with_lower == "六合":
        return (
            "六合",
            "上下六合；刑、破等关系另列，不据合独断成局。",
            with_day,
            with_lower,
        )
    return (
        "课内关系",
        "本课关系供取传参照，不单独决定课体或发用。",
        with_day,
        with_lower,
    )


def _liureng_upper_lower_relation(upper_branch: str, lower_branch: str) -> str:
    upper_element = branch_element_text(upper_branch)
    lower_element = (
        stem_element_text(lower_branch)
        if lower_branch in HEAVENLY_STEMS
        else branch_element_text(lower_branch)
    )
    if upper_element == lower_element:
        return "比和"
    if ELEMENT_CONTROLS[upper_element] == lower_element:
        return "上克下"
    if ELEMENT_CONTROLS[lower_element] == upper_element:
        return "下贼上"
    if ELEMENT_GENERATES[upper_element] == lower_element:
        return "上生下"
    if ELEMENT_GENERATES[lower_element] == upper_element:
        return "下生上"
    return "平"


def derive_selection(day_ganzhi: str, sky_to_earth: Dict[str, str]) -> Dict[str, Any]:
    """One domain derivation for the producer and output consistency checks."""
    day_stem, day_branch = day_ganzhi[0], day_ganzhi[1]
    day_element = stem_element_text(day_stem)
    day_stages = build_life_stages(day_stem, sky_to_earth)["stage_by_branch"]
    day_stem_house = DAY_STEM_HOUSE[day_stem]
    lesson_1_lower = day_stem_house
    lesson_1_upper = sky_to_earth[lesson_1_lower]
    lesson_2_lower = lesson_1_upper
    lesson_2_upper = sky_to_earth[lesson_2_lower]
    lesson_3_lower = day_branch
    lesson_3_upper = sky_to_earth[lesson_3_lower]
    lesson_4_lower = lesson_3_upper
    lesson_4_upper = sky_to_earth[lesson_4_lower]
    lesson_specs = [
        # (lower, upper, anchor_branch)：一/二课 以日干寄宫为 anchor；三/四课 以日支为 anchor。
        (lesson_1_lower, lesson_1_upper, day_stem_house),
        (lesson_2_lower, lesson_2_upper, day_stem_house),
        (lesson_3_lower, lesson_3_upper, day_branch),
        (lesson_4_lower, lesson_4_upper, day_branch),
    ]
    four_lessons: List[Dict[str, Any]] = []
    for lesson_index, (lower_branch, upper_branch, anchor_branch) in enumerate(
        lesson_specs, start=1
    ):
        relation = liuqin_against_day(day_element, branch_element_text(upper_branch))
        style_hint, style_basis, with_day, with_lower = _liureng_judge_lesson(
            upper_branch=upper_branch,
            lower_branch=lower_branch,
            day_branch=day_branch,
            relation=relation,
        )
        four_lessons.append(
            {
                "index": lesson_index,
                "upper_branch": upper_branch,
                "upper_day_stem_life_stage": day_stages[upper_branch],
                "lower_branch": lower_branch,
                "anchor_branch": anchor_branch,
                "text": f"{upper_branch}加{day_stem if lesson_index == 1 else lower_branch}",
                "relation": relation,
                "upper_lower_relation": _liureng_upper_lower_relation(
                    upper_branch,
                    day_stem if lesson_index == 1 else lower_branch,
                ),
                "relations": {
                    "with_day_branch": with_day,
                    "with_lower_branch": with_lower,
                },
                "style_hint": style_hint,
                "style_basis": style_basis,
                "use_candidate": False,
            }
        )

    rule_trace: List[Dict[str, Any]] = []
    (
        style,
        style_detail,
        transmission_method,
        transmission_branches,
        selected_lesson_index,
    ) = select_transmissions(
        day_stem, day_branch, sky_to_earth, four_lessons, trace=rule_trace
    )
    classification = classify_transmission_pattern(
        day_ganzhi=day_ganzhi,
        style=style,
        detail=style_detail,
        method=transmission_method,
        lessons=four_lessons,
        transmissions=transmission_branches,
        selected_lesson=selected_lesson_index,
    )
    style_detail = classification["detail"]
    transmission_method = classification["transmission_method"]
    initial_lesson = next(
        (lesson for lesson in four_lessons if lesson["index"] == selected_lesson_index),
        None,
    )
    if initial_lesson is not None:
        initial_lesson["use_candidate"] = True
    return {
        "four_lessons": four_lessons,
        "board_style": style,
        "board_style_detail": style_detail,
        "classification": classification,
        "transmission_method": transmission_method,
        "branches": transmission_branches,
        "selected_lesson_index": selected_lesson_index,
        "selected_lesson_relation": (
            initial_lesson.get("upper_lower_relation") if initial_lesson else None
        ),
        "rule_trace": rule_trace,
    }


def build_liureng_board(
    seed: MetaphysicsSeed,
    gender: str = "未知",
    month_general_override: Optional[str] = None,
    is_diurnal_override: Optional[bool] = None,
    guiren_profile: GuirenProfile = DEFAULT_GUIREN_PROFILE,
) -> Dict[str, Any]:
    lunar = seed.calendar_context.get("lunar_calendar") or {}
    current_term_name = seed.calendar_context["current_solar_term"]["name"]
    month_branch = seed.pillars["month"][1]
    day_stem = seed.pillars["day"][0]
    hour_branch = seed.pillars["hour"][1]
    day_element = stem_element_text(day_stem)
    day_ganzhi = ganzhi_text(seed.pillars["day"])
    xun_head = xun_head_for_ganzhi(day_ganzhi)
    kongwang = kongwang_for_ganzhi(day_ganzhi)

    diurnal = resolve_diurnal(hour_branch, is_diurnal_override)
    is_day = diurnal["is_diurnal"]
    if (
        month_general_override is not None
        and month_general_override not in YUE_JIANG_NAMES
    ):
        raise ValueError("month_general_override 必须是十二地支之一")
    yuejiang_branch = month_general_override or _liureng_month_general_for_term(
        current_term_name,
    )
    yuejiang_name = YUE_JIANG_NAMES[yuejiang_branch]

    layout = twelve_god_layout(
        hour_branch=hour_branch,
        month_general_branch=yuejiang_branch,
        day_stem=day_stem,
        is_diurnal=is_day,
        guiren_profile=guiren_profile,
    )
    sky_to_earth = layout["sky_by_earth"]
    guiren_start = layout["noble_start_branch"]
    guiren_earth = layout["noble_earth_branch"]
    guiren_reverse = layout["is_reverse"]
    guiren_map = layout["god_by_sky"]
    life_stages = build_life_stages(day_stem, sky_to_earth)
    day_stages = life_stages["stage_by_branch"]

    # 大六壬 classical 四课 construction:
    # 一课 下=日干寄宫, 上=sky[日干寄宫]
    # 二课 下=一课上神, 上=sky[一课上神]
    # 三课 下=日支, 上=sky[日支]
    # 四课 下=三课上神, 上=sky[三课上神]
    selection = derive_selection(day_ganzhi, sky_to_earth)
    four_lessons = selection["four_lessons"]
    style = selection["board_style"]
    style_detail = selection["board_style_detail"]
    transmission_method = selection["transmission_method"]
    transmission_branches = selection["branches"]
    selected_lesson_index = selection["selected_lesson_index"]
    rule_trace = selection["rule_trace"]
    classification = selection["classification"]
    initial_lesson = next(
        (row for row in four_lessons if row["index"] == selected_lesson_index), None
    )
    style_basis = f"依九宗门取{style}，发用为{transmission_branches[0]}。"
    style_detail_basis = f"细课体{style_detail}，取传法为{transmission_method}。"

    initial_branch = transmission_branches[0]
    transmission_labels = ["initial", "middle", "final"]
    transmission_payload: Dict[str, Any] = {"method": transmission_method}
    dun_stems = xun_dun_stems(day_ganzhi)
    earth_by_sky = {sky: earth for earth, sky in sky_to_earth.items()}
    for offset, label in enumerate(transmission_labels):
        branch = transmission_branches[offset]
        relation = liuqin_against_day(day_element, branch_element_text(branch))
        transmission_payload[label] = {
            "branch": branch,
            "relation": relation,
            "god": guiren_map[branch],
            "ganzhi": f"{dun_stems[branch]}{branch}" if branch in dun_stems else None,
            "dun_stem": dun_stems.get(branch),
            "xun_kong": branch not in dun_stems,
            "earth_branch": earth_by_sky[branch],
            "seated_kong": earth_by_sky[branch] not in dun_stems,
            "day_stem_life_stage": day_stages[branch],
            "seated_day_stem_life_stage": day_stages[earth_by_sky[branch]],
        }

    auxiliary_stars = build_auxiliary_stars(
        day_ganzhi=day_ganzhi,
        month_branch=month_branch,
        sky_by_earth=sky_to_earth,
        god_by_sky=guiren_map,
        lessons=four_lessons,
        transmissions=transmission_branches,
    )
    transmission_relationships = transmission_relations(
        day_ganzhi=day_ganzhi,
        lessons=four_lessons,
        transmissions=transmission_payload,
        month_branch=month_branch,
    )
    empty_evidence = emptiness_evidence(
        day_ganzhi=day_ganzhi,
        year_branch=seed.pillars["year"][1],
        month_branch=month_branch,
        month_general_branch=yuejiang_branch,
        hour_branch=hour_branch,
        sky_by_earth=sky_to_earth,
    )
    branch_evidence = branch_relations(
        day_ganzhi=day_ganzhi,
        year_branch=seed.pillars["year"][1],
        month_branch=month_branch,
        hour_branch=hour_branch,
        month_general_branch=yuejiang_branch,
        sky_by_earth=sky_to_earth,
        lessons=four_lessons,
        transmissions=transmission_branches,
    )

    progression = transmission_progression(day_ganzhi, transmission_branches)
    day_placements = day_placement_patterns(day_ganzhi, sky_to_earth)
    crossed_harmony = cross_harmony(day_ganzhi, sky_to_earth)
    seasonal = seasonal_evidence(
        day_ganzhi=day_ganzhi,
        month_branch=month_branch,
        sky_by_earth=sky_to_earth,
        god_by_sky=guiren_map,
    )
    god_yin = god_yin_spirits(
        day_ganzhi=day_ganzhi,
        month_branch=month_branch,
        is_diurnal=is_day,
        guiren_profile=guiren_profile,
        sky_by_earth=sky_to_earth,
        god_by_sky=guiren_map,
        lesson_uppers=[row["upper_branch"] for row in four_lessons],
        transmission_branches=transmission_branches,
    )

    overview = [
        f"月将{yuejiang_branch}({yuejiang_name})加{hour_branch}时，当前以{current_term_name}节气入局。",
        f"贵人起于{guiren_start}，{'逆' if guiren_reverse else '顺'}行布十二神将。",
        f"{style}课主导，首传落{initial_branch}，{style_basis}",
        f"细课体：{style_detail}。{style_detail_basis}",
        f"取传法：{transmission_method}。首传见{transmission_payload['initial']['relation']}，末传归{transmission_payload['final']['branch']}。",
    ]

    patterns = [
        {
            "name": f"贵人{'逆' if guiren_reverse else '顺'}行格",
            "basis": f"贵人起{guiren_start}，{'逆' if guiren_reverse else '顺'}布神将。",
        },
        {
            "name": f"{style}课",
            "basis": style_basis,
        },
    ]
    if style_detail != style:
        patterns.append(
            {
                "name": f"{style_detail}课",
                "basis": style_detail_basis,
            }
        )

    return {
        "month_general": {
            "branch": yuejiang_branch,
            "name": yuejiang_name,
        },
        "calendar_policy": dict(
            seed.calendar_context.get("ren_calendar_policy")
            or symbolic_calendar_policy()
        ),
        "board_style": style,
        "board_style_detail": style_detail,
        "classification": classification,
        "board_order": "天盘顺布",
        "guiren_order": "逆" if guiren_reverse else "顺",
        "ruleset": ruleset_metadata("liureng", guiren_profile=guiren_profile),
        "rule_trace": rule_trace
        + [
            god_yin_trace(god_yin),
            seasonal_trace(seasonal),
            progression_trace(progression),
            {
                "rule_id": "liuren.tanyuan_life_stages",
                "source_url": life_stages["source_url"],
                "source_section": life_stages["source_title"],
                "result": life_stages,
            },
            {
                "rule_id": "liuren.named_subtypes",
                "source_url": classification["source_url"],
                "source_section": classification["source_section"],
                "result": classification,
            },
            {
                "rule_id": "liuren.guiren_start",
                "source_url": (
                    TANYUAN_TRANSCRIPTION
                    if guiren_profile == "tanyuan_xieji_v1"
                    else None
                ),
                "source_section": (
                    "日贵人歌 / 夜贵人歌"
                    if guiren_profile == "tanyuan_xieji_v1"
                    else "所选通行昼夜表"
                ),
                "result": {
                    "profile": guiren_profile,
                    "is_diurnal": is_day,
                    "start_branch": guiren_start,
                    "earth_branch": guiren_earth,
                    "direction": "逆" if guiren_reverse else "顺",
                },
            },
            {
                "rule_id": "liuren.transmissions.result",
                "source_section": "九宗门",
                "result": {
                    "style": style,
                    "detail": style_detail,
                    "branches": transmission_branches,
                    "source_lesson": selected_lesson_index,
                },
            },
            {
                "rule_id": "liuren.tanyuan_auxiliary_stars",
                "source_url": auxiliary_stars["source_url"],
                "source_section": auxiliary_stars["source_title"],
                "result": auxiliary_stars,
            },
            {
                "rule_id": "liuren.transmission_relations",
                "source_url": transmission_relationships["source_url"],
                "source_section": "探原·论三传 / 论十二天将 / 论合",
                "result": {
                    "matched_rule_ids": transmission_relationships["matched_rule_ids"],
                    "god_spirit_wars": [
                        r["war"] for r in transmission_relationships["rows"]
                    ],
                    "comprehensive_judgement": None,
                },
            },
            ordered_patterns_trace(transmission_relationships["named_structures"]),
            course_conditions_trace(transmission_relationships["course_conditions"]),
            day_placements_trace(day_placements),
            {
                "rule_id": "liuren.empty_scope",
                "source_url": empty_evidence["source_url"],
                "source_section": empty_evidence["source_title"],
                "result": {
                    "day_stem_house": empty_evidence["day_stem_house"],
                    "empty_branches": empty_evidence["empty_branches"],
                    "comprehensive_judgement": None,
                },
            },
            {
                "rule_id": "liuren.branch_relations",
                "source_url": branch_evidence["source_url"],
                "source_section": branch_evidence["source_title"],
                "result": {
                    "row_count": len(branch_evidence["rows"]),
                    "annotated_harmony_rows": [
                        r["id"]
                        for r in branch_evidence["rows"]
                        if r["facts"]["harmony_annotation"] is not None
                    ],
                    "comprehensive_judgement": None,
                },
            },
            cross_harmony_trace(crossed_harmony),
        ],
        "kongwang": kongwang,
        "xun_head": xun_head,
        "month_building_element": branch_element_text(month_branch),
        "life_stages": life_stages,
        "auxiliary_stars": auxiliary_stars,
        "guiren_system": (
            "探原·协纪辨方昼夜贵人"
            if guiren_profile == "tanyuan_xieji_v1"
            else "六壬通行昼夜贵人表"
        ),
        "four_lessons": four_lessons,
        "three_transmissions": transmission_payload,
        "transmission_relations": transmission_relationships,
        "transmission_progression": progression,
        "seasonal_evidence": seasonal,
        "god_yin": god_yin,
        "emptiness_evidence": empty_evidence,
        "branch_relations": branch_evidence,
        "day_placement_patterns": day_placements,
        "cross_harmony": crossed_harmony,
        "patterns": patterns,
        "overview": overview,
        "twelve_board": [
            {
                "earth_branch": branch,
                "sky_branch": sky_to_earth[branch],
                "god": guiren_map[sky_to_earth[branch]],
            }
            for branch in EARTHLY_BRANCHES
        ],
        "meta": {
            "guiren_profile": guiren_profile,
            "current_term": current_term_name,
            "month_general_basis": (
                "explicit_override"
                if month_general_override is not None
                else "中气换将"
            ),
            "lunar_display": lunar.get("display"),
            "questioner_gender": gender,
            "is_diurnal": is_day,
            "diurnal_evidence": diurnal,
            "selected_lesson_index": (
                initial_lesson["index"] if initial_lesson else None
            ),
            "selected_lesson_relation": (
                initial_lesson.get("upper_lower_relation") if initial_lesson else None
            ),
            "guiren_earth_branch": guiren_earth,
            "diurnal_basis": (
                "explicit_override"
                if is_diurnal_override is not None
                else "卯至申昼、酉至寅夜的时支约定"
            ),
        },
    }


def build_liureng_runyear(
    seed: MetaphysicsSeed,
    gender: str,
    birth_year: int,
    *,
    birth_lunar_year: int,
    age_reference_timezone: Optional[str] = None,
) -> Dict[str, Any]:
    # 虚岁 changes at lunar new year, not Gregorian Jan 1 or 立春.
    # Both endpoints need one civil calendar. The service supplies the birth
    # zone, retaining its existing natal-year anchor. Changing the display zone
    # of an unchanged analysis instant cannot change age or produce age zero.
    age_zone = age_reference_timezone or seed.timezone
    analysis_civil = localize_datetime(seed.input_datetime, seed.timezone)
    target_civil = localize_datetime(analysis_civil, age_zone)
    target_lunar = get_lunar_context(target_civil, timezone_name=age_zone)
    if target_lunar is None:
        raise ValueError("行年需要分析日期的农历年")
    target_lunar_year = target_lunar["year"]
    if not isinstance(target_lunar_year, int):
        raise ValueError("行年需要有效的农历年")
    age = target_lunar_year - birth_lunar_year + 1
    if birth_lunar_year not in (birth_year - 1, birth_year) or age < 1:
        raise ValueError("行年分析日期不能早于出生年")
    normalized_gender = normalize_gender(gender)
    basis = {
        "age": age,
        "gender": gender,
        "age_basis": "农历年差加一；正月初一换岁",
        "rule_id": "liuren.runyear_bingyin_renshen",
        "source_url": TANYUAN_SOURCE,
        "source_section": "大六壬探原·卷上推演篇·年命",
        "birth_lunar_year": birth_lunar_year,
        "age_calendar": {
            "policy": "one_timezone_lunar_year_age_v1",
            "timezone": age_zone,
            "analysis_civil_datetime": target_civil.isoformat(),
            "birth_lunar_year": birth_lunar_year,
            "analysis_lunar_year": target_lunar_year,
            "year_boundary": "正月初一00:00",
            "scope": "虚岁两端统一民用时区后按农历年差加一；分析课盘仍使用其本身时区和所选日时钟，未据此裁定原典全球时区规则。",
        },
    }
    if normalized_gender == "未知":
        return {
            **basis,
            "ganzhi": None,
            "status": "not_calculated",
            "reason": "未提供男女行年分支，不默认套用男式",
        }
    if normalized_gender == "女":
        start_index = sexagenary_index_for("壬申")
        direction = -1
    else:
        start_index = sexagenary_index_for("丙寅")
        direction = 1
    runyear_ganzhi = sexagenary_text(start_index + direction * (age - 1))
    return {**basis, "ganzhi": runyear_ganzhi, "status": "calculated"}
