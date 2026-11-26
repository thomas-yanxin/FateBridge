"""Construct a Liu Ren board and assemble its calculation evidence."""

from __future__ import annotations

from typing import Any

from fatebridge.core.metaphysics.common import (
    YUE_JIANG_NAMES,
    MetaphysicsSeed,
    branch_element_text,
    ganzhi_text,
    kongwang_for_ganzhi,
    liuqin_against_day,
    stem_element_text,
    xun_head_for_ganzhi,
)
from fatebridge.core.metaphysics.liureng_auxiliary_stars import build_auxiliary_stars
from fatebridge.core.metaphysics.liureng_branch_relations import branch_relations
from fatebridge.core.metaphysics.liureng_course_conditions import (
    course_conditions_trace,
)
from fatebridge.core.metaphysics.liureng_course_layout import (
    LIURENG_GUIREN_REVERSED_EARTH,
    LIURENG_MONTH_GENERAL_BY_TERM,
    TwelveGodLayout,
)
from fatebridge.core.metaphysics.liureng_course_layout import (
    _liureng_month_general_for_term as _liureng_month_general_for_term,
)
from fatebridge.core.metaphysics.liureng_course_layout import (
    _liureng_month_general_on_hour as _liureng_month_general_on_hour,
)
from fatebridge.core.metaphysics.liureng_course_layout import twelve_god_layout
from fatebridge.core.metaphysics.liureng_cross_harmony import (
    cross_harmony,
    cross_harmony_trace,
)
from fatebridge.core.metaphysics.liureng_day_placements import (
    day_placement_patterns,
    day_placements_trace,
)
from fatebridge.core.metaphysics.liureng_emptiness import emptiness_evidence
from fatebridge.core.metaphysics.liureng_god_yin import god_yin_spirits, god_yin_trace
from fatebridge.core.metaphysics.liureng_life_stages import build_life_stages
from fatebridge.core.metaphysics.liureng_ordered_patterns import ordered_patterns_trace
from fatebridge.core.metaphysics.liureng_progression import (
    progression_trace,
    transmission_progression,
)
from fatebridge.core.metaphysics.liureng_seasonal import (
    seasonal_evidence,
    seasonal_trace,
)
from fatebridge.core.metaphysics.liureng_selection import derive_selection
from fatebridge.core.metaphysics.liureng_transmission_relations import (
    transmission_relations,
)
from fatebridge.core.metaphysics.liureng_transmissions import (
    STEM_HOUSES as DAY_STEM_HOUSE,
)
from fatebridge.core.metaphysics.liureng_year_fate import build_liureng_runyear
from fatebridge.core.metaphysics.ren_calendar import symbolic_calendar_policy
from fatebridge.core.metaphysics.ren_diurnal import resolve_diurnal
from fatebridge.core.metaphysics.ren_evidence import ruleset_metadata, xun_dun_stems
from fatebridge.core.metaphysics.ren_gods import (
    DEFAULT_GUIREN_PROFILE,
    GuirenProfile,
)
from fatebridge.utils.data import EARTHLY_BRANCHES

__all__ = [
    "DAY_STEM_HOUSE",
    "LIURENG_GUIREN_REVERSED_EARTH",
    "LIURENG_MONTH_GENERAL_BY_TERM",
    "TwelveGodLayout",
    "build_liureng_board",
    "build_liureng_runyear",
    "derive_selection",
    "twelve_god_layout",
]


def build_liureng_board(
    seed: MetaphysicsSeed,
    gender: str = "未知",
    month_general_override: str | None = None,
    is_diurnal_override: bool | None = None,
    guiren_profile: GuirenProfile = DEFAULT_GUIREN_PROFILE,
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
                "source_section": life_stages["source_title"],
                "result": life_stages,
            },
            {
                "rule_id": "liuren.named_subtypes",
                "source_section": classification["source_section"],
                "result": classification,
            },
            {
                "rule_id": "liuren.guiren_start",
                "source_section": (
                    "日贵人歌 / 夜贵人歌"
                    if guiren_profile == "tanyuan_xieji_v1"
                    else "六壬经纬·卷之一·贵神（故宫珍本丛刊419 PDF10–11）"
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
                "source_section": auxiliary_stars["source_title"],
                "result": auxiliary_stars,
            },
            {
                "rule_id": "liuren.transmission_relations",
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
                "source_section": empty_evidence["source_title"],
                "result": {
                    "day_stem_house": empty_evidence["day_stem_house"],
                    "empty_branches": empty_evidence["empty_branches"],
                    "comprehensive_judgement": None,
                },
            },
            {
                "rule_id": "liuren.branch_relations",
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
