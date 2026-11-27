"""Construct a Liu Ren board with compact audit evidence."""

from __future__ import annotations

from typing import Any, TypedDict

from fatebridge.core.almanac import localize_datetime
from fatebridge.core.batch_cache import batch_cached, metaphysics_seed_key
from fatebridge.core.metaphysics.common import (
    ELEMENT_CONTROLS,
    ELEMENT_GENERATES,
    GUI_REN_SEQUENCE,
    SIX_CLASH_BRANCHES,
    SIX_HARM_BRANCHES,
    SIX_HARMONY_BRANCHES,
    MetaphysicsSeed,
    branch_element_text,
    ganzhi_text,
    kongwang_for_ganzhi,
    liuqin_against_day,
    rotate_sequence,
    stem_element_text,
    xun_head_for_ganzhi,
)
from fatebridge.core.metaphysics.liureng.stars import STEM_HOUSES as DAY_STEM_HOUSE
from fatebridge.core.metaphysics.liureng.stars import (
    branch_relations,
    build_auxiliary_stars,
    build_life_stages,
    cross_harmony,
    day_placement_patterns,
    emptiness_evidence,
    god_yin_spirits,
    seasonal_evidence,
)
from fatebridge.core.metaphysics.liureng.transmissions import (
    ShehaiMethod,
    classify_transmission_pattern,
    select_transmissions,
    transmission_progression,
    transmission_relations,
)
from fatebridge.core.metaphysics.ren_calendar import (
    LIURENG_MONTH_GENERAL_BY_TERM,
    MonthGeneralMode,
    compact_calendar_policy,
    compute_month_general,
    month_general_for_term,
    ruleset_metadata,
    symbolic_calendar_policy,
    xun_dun_stems,
)
from fatebridge.core.metaphysics.ren_diurnal import DiurnalMode, resolve_diurnal
from fatebridge.core.metaphysics.ren_gods import (
    DEFAULT_GUIREN_PROFILE,
    GuirenProfile,
    noble_start,
)
from fatebridge.utils.data import EARTHLY_BRANCHES, HEAVENLY_STEMS

LIURENG_GUIREN_REVERSED_EARTH = frozenset("巳午未申酉戌")


def _liureng_month_general_on_hour(
    *, hour_branch: str, month_general_branch: str
) -> dict[str, str]:
    earth_order = rotate_sequence(EARTHLY_BRANCHES, hour_branch)
    sky_order = rotate_sequence(EARTHLY_BRANCHES, month_general_branch)
    return {
        earth_branch: sky_order[index] for index, earth_branch in enumerate(earth_order)
    }


class TwelveGodLayout(TypedDict):
    sky_by_earth: dict[str, str]
    god_by_sky: dict[str, str]
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
    left_branch: str, right_branch: str, *, same_label: str = "同支"
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
    *, upper_branch: str, lower_branch: str, day_branch: str, relation: str
) -> tuple[str, str, str, str]:
    with_day = _branch_relation(upper_branch, day_branch, same_label="比和")
    with_lower = _branch_relation(upper_branch, lower_branch, same_label="伏吟")
    if with_lower == "伏吟":
        return "伏吟", "上神与下神同位，伏吟取象。", with_day, with_lower
    if with_lower == "六冲":
        return "返吟", "上神与下神相冲，取返吟往复之象。", with_day, with_lower
    if with_lower == "六害":
        return "六害", "上下见六害关系。", with_day, with_lower
    if relation == "官鬼":
        return "官鬼", "上神与日干为官鬼关系。", with_day, with_lower
    if with_lower == "六合":
        return "六合", "上下六合。", with_day, with_lower
    return "课内关系", "本课关系供取传参照。", with_day, with_lower


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
    return "下生上"


def derive_selection(
    day_ganzhi: str,
    sky_to_earth: dict[str, str],
    *,
    shehai_method: ShehaiMethod = "depth_first",
    harm_include_terminal: bool = False,
) -> dict[str, Any]:
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
        (lesson_1_lower, lesson_1_upper, day_stem_house),
        (lesson_2_lower, lesson_2_upper, day_stem_house),
        (lesson_3_lower, lesson_3_upper, day_branch),
        (lesson_4_lower, lesson_4_upper, day_branch),
    ]
    four_lessons: list[dict[str, Any]] = []
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

    rule_trace: list[dict[str, Any]] = []
    (
        style,
        style_detail,
        transmission_method,
        transmission_branches,
        selected_lesson_index,
    ) = select_transmissions(
        day_stem,
        day_branch,
        sky_to_earth,
        four_lessons,
        shehai_method=shehai_method,
        harm_include_terminal=harm_include_terminal,
        trace=rule_trace,
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


def _liureng_board_cache_key(
    seed: MetaphysicsSeed,
    gender: str = "未知",
    month_general_override: str | None = None,
    is_diurnal_override: bool | None = None,
    guiren_profile: GuirenProfile = DEFAULT_GUIREN_PROFILE,
    *,
    shehai_method: ShehaiMethod = "depth_first",
    harm_include_terminal: bool = False,
    diurnal_mode: DiurnalMode = "clock",
    month_general_mode: MonthGeneralMode = "solar_term",
    latitude: float | None = None,
    longitude: float | None = None,
) -> tuple[object, ...]:
    return (
        metaphysics_seed_key(seed),
        gender,
        month_general_override,
        is_diurnal_override,
        guiren_profile,
        shehai_method,
        harm_include_terminal,
        diurnal_mode,
        month_general_mode,
        latitude,
        longitude,
    )


@batch_cached(
    "liuren.build_liureng_board",
    _liureng_board_cache_key,
    copy_result=True,
)
def build_liureng_board(
    seed: MetaphysicsSeed,
    gender: str = "未知",
    month_general_override: str | None = None,
    is_diurnal_override: bool | None = None,
    guiren_profile: GuirenProfile = DEFAULT_GUIREN_PROFILE,
    *,
    shehai_method: ShehaiMethod = "depth_first",
    harm_include_terminal: bool = False,
    diurnal_mode: DiurnalMode = "clock",
    month_general_mode: MonthGeneralMode = "solar_term",
    latitude: float | None = None,
    longitude: float | None = None,
) -> dict[str, Any]:
    lunar = seed.calendar_context.get("lunar_calendar") or {}
    current_term_name = seed.calendar_context["current_solar_term"]["name"]
    month_branch = seed.pillars["month"][1]
    day_stem = seed.pillars["day"][0]
    hour_branch = seed.pillars["hour"][1]
    day_element = stem_element_text(day_stem)
    day_ganzhi = ganzhi_text(seed.pillars["day"])
    xun_head = xun_head_for_ganzhi(day_ganzhi)
    kongwang = kongwang_for_ganzhi(day_ganzhi)

    instant_for_astro = localize_datetime(seed.input_datetime, seed.timezone)
    diurnal = resolve_diurnal(
        hour_branch,
        is_diurnal_override,
        diurnal_mode=diurnal_mode,
        instant=instant_for_astro,
        latitude=latitude,
        longitude=seed.longitude if longitude is None else longitude,
    )
    is_day = diurnal["is_diurnal"]
    general_info = compute_month_general(
        seed,
        month_general_mode=month_general_mode,
        month_general_override=month_general_override,
    )
    yuejiang_branch = general_info["branch"]
    yuejiang_name = general_info["name"]

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

    selection = derive_selection(
        day_ganzhi,
        sky_to_earth,
        shehai_method=shehai_method,
        harm_include_terminal=harm_include_terminal,
    )
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
    transmission_payload: dict[str, Any] = {"method": transmission_method}
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
    for pname in classification.get("named_patterns", []):
        patterns.append(
            {
                "name": pname,
                "basis": f"三传{''.join(transmission_branches)}结构命中{pname}",
            }
        )

    raw_policy = seed.calendar_context.get("ren_calendar_policy")
    board_policy = (
        dict(raw_policy) if raw_policy is not None else symbolic_calendar_policy()
    )
    if raw_policy is not None and general_info["basis"] != "中气换将":
        board_policy["month_general_boundary"] = general_info["basis"]

    return {
        "month_general": {
            "branch": yuejiang_branch,
            "name": yuejiang_name,
        },
        "calendar_policy": board_policy,
        "board_style": style,
        "board_style_detail": style_detail,
        "classification": classification,
        "board_order": "天盘顺布",
        "guiren_order": "逆" if guiren_reverse else "顺",
        "ruleset": ruleset_metadata("liureng", guiren_profile=guiren_profile),
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
            "month_general_basis": general_info["basis"],
            "month_general_mode": month_general_mode,
            "lunar_display": lunar.get("display"),
            "questioner_gender": gender,
            "is_diurnal": is_day,
            "diurnal_mode": diurnal_mode,
            "diurnal_evidence": diurnal,
            "shehai_method": shehai_method,
            "harm_include_terminal": harm_include_terminal,
            "selected_lesson_index": (
                initial_lesson["index"] if initial_lesson else None
            ),
            "selected_lesson_relation": (
                initial_lesson.get("upper_lower_relation") if initial_lesson else None
            ),
            "guiren_earth_branch": guiren_earth,
            "guiren_start_branch": guiren_start,
            "diurnal_basis": (
                "explicit_override"
                if is_diurnal_override is not None
                else (
                    "sunrise_sunset_ephemeris"
                    if diurnal["astronomical_boundary_computed"]
                    else "卯至申昼、酉至寅夜的时支约定"
                )
            ),
        },
    }


__all__ = [
    "DAY_STEM_HOUSE",
    "LIURENG_GUIREN_REVERSED_EARTH",
    "LIURENG_MONTH_GENERAL_BY_TERM",
    "TwelveGodLayout",
    "_liureng_month_general_for_term",
    "_liureng_month_general_on_hour",
    "_liureng_upper_lower_relation",
    "build_liureng_board",
    "compact_calendar_policy",
    "compute_month_general",
    "derive_selection",
    "twelve_god_layout",
]

_liureng_month_general_for_term = month_general_for_term
