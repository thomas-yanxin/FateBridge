"""Jin Kou's own four positions, polarity use, motions and empty elements.

Rules follow named sections of the 古本 transcription, independently of
Liu Ren's lessons and transmissions. Edition limits are part of the output.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from fatebridge.core.metaphysics.jinkou_guishen import (
    GUISHEN_IDENTITIES,
    _build_guishen_mapping,
)
from fatebridge.core.metaphysics.ren_sources import JINKOU_SOURCE

from ...utils.data import EARTHLY_BRANCHES, HEAVENLY_STEMS
from .common import (
    ELEMENT_CONTROLS,
    ELEMENT_GENERATES,
    GUI_REN_SEQUENCE,
    LIURENG_GUIREN_DAY,
    LIURENG_GUIREN_NIGHT,
    SIX_CLASH_BRANCHES,
    YUE_JIANG_NAMES,
    MetaphysicsSeed,
    branch_element_text,
    ganzhi_text,
    kongwang_for_ganzhi,
    rotate_sequence,
    stem_element_text,
    xun_head_for_ganzhi,
)
from .jinkou_branch_breaks import branch_breaks, branch_breaks_trace
from .jinkou_branch_stars import branch_stars, branch_stars_trace
from .jinkou_combinations import trine_evidence
from .jinkou_definitions import definition_evidence
from .jinkou_interactions import position_interactions
from .jinkou_patterns import structural_patterns, use_evidence
from .jinkou_qi import build_jinkou_qi
from .jinkou_relations import structural_relations
from .jinkou_seasonal import seasonal_power, seasonal_power_basis
from .jinkou_stems import WUZI_DUN_START as WUZI_DUN_START
from .jinkou_stems import build_stem_relations
from .jinkou_stems import wuzidun_stem as _wuzidun_stem
from .jinkou_strength import internal_strength
from .ren_calendar import symbolic_calendar_policy
from .ren_diurnal import resolve_diurnal
from .ren_evidence import ruleset_metadata

# 十二贵神所属: inherent identities, never their occupied earth positions.


def _jinkou_pick_use_position(rows: List[Dict[str, Any]]) -> Tuple[str, str, str]:
    """阴阳次第五用: 人元 stem plus the other three inherent branches."""
    count = sum(row["polarity"] == "阳" for row in rows)
    pattern = {0: "纯阴", 1: "三阴一阳", 2: "二阴二阳", 3: "三阳一阴", 4: "纯阳"}[count]
    if count in (1, 3):
        minority = "阳" if count == 1 else "阴"
        label = next(row["label"] for row in rows if row["polarity"] == minority)
        return label, f"{pattern}，取少数{minority}位{label}为用。", pattern
    label = "贵神" if count == 4 else "将神"
    return label, f"{pattern}，依阴阳次第五用取{label}。", pattern


def _motion_evidence(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_label = {row["label"]: row for row in rows}
    definitions = [
        ("妻动", "人元", "地分", "克", "五动爻诵"),
        ("官动", "贵神", "人元", "克", "五动爻诵"),
        ("贼动", "贵神", "将神", "克", "五动爻诵"),
        ("财动", "将神", "贵神", "克", "五动爻诵"),
        ("鬼动", "地分", "人元", "克", "五动爻诵"),
        ("父母动", "地分", "人元", "生", "三动"),
        ("子孙动", "人元", "地分", "生", "三动"),
        ("兄弟动", "人元", "地分", "比和", "三动"),
    ]
    result = []
    for name, source, target, relation, section in definitions:
        left, right = by_label[source], by_label[target]
        matched = (
            ELEMENT_CONTROLS[left["element"]] == right["element"]
            if relation == "克"
            else (
                ELEMENT_GENERATES[left["element"]] == right["element"]
                if relation == "生"
                else left["element"] == right["element"]
            )
        )
        if matched:
            result.append(
                {
                    "name": name,
                    "source_position": source,
                    "target_position": target,
                    "relation": relation,
                    "source_section": section,
                    "basis": f"{source}{left['content']}({left['element']}){relation}{target}{right['content']}({right['element']})",
                    "empty_positions": [
                        r["label"]
                        for r in (left, right)
                        if r["xun_kong"] or r["si_da_kong"]
                    ],
                }
            )
    return result


def build_jinkou_board(
    seed: MetaphysicsSeed,
    liureng_board: Dict[str, Any],
    gender: str = "未知",
    di_fen: Optional[str] = None,
    runyear: Optional[Dict[str, Any]] = None,
    is_diurnal_override: Optional[bool] = None,
    natal_branch: Optional[str] = None,
    natal_branch_source: Optional[str] = None,
) -> Dict[str, Any]:
    day_stem = seed.pillars["day"][0]
    hour_branch = seed.pillars["hour"][1]
    if di_fen is not None and di_fen not in EARTHLY_BRANCHES:
        raise ValueError("di_fen 必须是一个十二地支")
    di_fen_branch = hour_branch if di_fen is None else di_fen
    diurnal = resolve_diurnal(hour_branch, is_diurnal_override)
    guiren_start, guishen_map = _build_guishen_mapping(
        day_stem, hour_branch, is_diurnal_override
    )
    guishen_name = guishen_map[di_fen_branch]
    intrinsic_ganzhi = GUISHEN_IDENTITIES[guishen_name]
    guishen_branch = intrinsic_ganzhi[1]
    # Share only the resolved month general, not lesson/style/god assignments.
    month_general = liureng_board["month_general"]
    jiangshen_branch = EARTHLY_BRANCHES[
        (
            EARTHLY_BRANCHES.index(month_general["branch"])
            + EARTHLY_BRANCHES.index(di_fen_branch)
            - EARTHLY_BRANCHES.index(hour_branch)
        )
        % 12
    ]
    jiangshen_name = YUE_JIANG_NAMES[jiangshen_branch]
    renyuan_stem = _wuzidun_stem(day_stem, di_fen_branch)
    day_ganzhi = ganzhi_text(seed.pillars["day"])
    xun_head = xun_head_for_ganzhi(day_ganzhi)
    empty = kongwang_for_ganzhi(day_ganzhi)
    empty_element = {"甲子": "水", "甲午": "水", "甲寅": "金", "甲申": "金"}.get(
        xun_head
    )
    month_branch = seed.pillars["month"][1]
    row_defs = [
        ("人元", renyuan_stem, stem_element_text(renyuan_stem), "—"),
        ("贵神", guishen_branch, branch_element_text(guishen_branch), guishen_name),
        (
            "将神",
            jiangshen_branch,
            branch_element_text(jiangshen_branch),
            jiangshen_name,
        ),
        ("地分", di_fen_branch, branch_element_text(di_fen_branch), "—"),
    ]
    rows = []
    for label, content, element, shenjiang in row_defs:
        index = (
            HEAVENLY_STEMS.index(content)
            if label == "人元"
            else EARTHLY_BRANCHES.index(content)
        )
        rows.append(
            {
                "label": label,
                "content": content,
                "shenjiang": shenjiang,
                "element": element,
                "power": seasonal_power(month_branch, element),
                "polarity": "阳" if index % 2 == 0 else "阴",
                "dun_stem": (
                    _wuzidun_stem(day_stem, content)
                    if label in ("贵神", "将神")
                    else None
                ),
                "intrinsic_ganzhi": intrinsic_ganzhi if label == "贵神" else None,
                "xun_kong": content in empty[:2] if label != "人元" else False,
                "si_da_kong": element == empty_element,
                "month_break": (
                    content == SIX_CLASH_BRANCHES[month_branch]
                    if label != "人元"
                    else False
                ),
            }
        )
    strength = internal_strength(rows)
    qi_evidence = build_jinkou_qi(
        rows, month_branch=month_branch, day_branch=seed.pillars["day"][1]
    )
    interactions = position_interactions(rows)
    stem_relations = build_stem_relations(day_stem=day_stem, rows=rows)
    use_position, use_basis, pattern = _jinkou_pick_use_position(rows)
    for row in rows:
        row["is_use"] = row["label"] == use_position
        row["seasonal_power"] = row["power"]
        row["internal_power"] = strength["powers"][row["label"]]
    patterns = structural_patterns(rows, day_ganzhi=day_ganzhi)
    definitions = definition_evidence(
        day_stem=day_stem,
        hour_branch=hour_branch,
        is_diurnal=diurnal["is_diurnal"],
        rows=rows,
    )
    use_conditions = use_evidence(rows, strength, polarity_position=use_position)
    breaks = branch_breaks(guishen_branch, jiangshen_branch, di_fen_branch)
    relations = structural_relations(
        rows,
        year_branch=seed.pillars["year"][1],
        day_branch=seed.pillars["day"][1],
        hour_branch=hour_branch,
        natal_branch=natal_branch,
        natal_branch_source=natal_branch_source,
    )
    combinations = trine_evidence(
        rows, day_branch=seed.pillars["day"][1], month_branch=month_branch
    )
    stars = branch_stars(
        year_branch=seed.pillars["year"][1],
        month_branch=month_branch,
        day_ganzhi=day_ganzhi,
        input_branches={
            "贵神": guishen_branch,
            "将神": jiangshen_branch,
            "地分": di_fen_branch,
        },
    )
    overview = {
        "di_fen": di_fen_branch,
        "di_fen_source": (
            "explicit"
            if di_fen is not None
            else "hour_branch_fallback_not_observed_direction"
        ),
        "kongwang": empty,
        "xun_head": xun_head,
        "si_da_kong": f"{empty_element}空" if empty_element else "无四大空亡",
        "board_style": "金口诀四位",
        "board_style_detail": pattern,
        "transmission_method": "四位阴阳取用（不取大六壬三传）",
        "use_position": use_position,
        "use_position_basis": use_basis,
        "yuejiang": {"branch": jiangshen_branch, "name": jiangshen_name},
        "guishen": {
            "start_branch": guiren_start,
            "branch": guishen_branch,
            "name": guishen_name,
            "earth_branch": di_fen_branch,
            "intrinsic_ganzhi": intrinsic_ganzhi,
            "direction": "逆" if guiren_start in "巳午未申酉戌" else "顺",
        },
        "month_general": dict(month_general),
        "gender": gender,
        "power_basis": seasonal_power_basis(month_branch),
        "diurnal_basis": (
            "explicit_override"
            if is_diurnal_override is not None
            else "卯至申昼、酉至寅夜的时支约定"
        ),
        "is_diurnal": diurnal["is_diurnal"],
        "diurnal_evidence": diurnal,
    }
    if runyear:
        overview["runyear"] = runyear
    return {
        "overview": overview,
        "calendar_policy": dict(
            seed.calendar_context.get("ren_calendar_policy")
            or symbolic_calendar_policy()
        ),
        "rows": rows,
        "motions": _motion_evidence(rows),
        "internal_strength": strength,
        "qi_evidence": qi_evidence,
        "position_interactions": interactions,
        "stem_relations": stem_relations,
        "patterns": patterns,
        "definition_evidence": definitions,
        "use_evidence": use_conditions,
        "relations": relations,
        "combinations": combinations,
        "branch_stars": stars,
        "branch_breaks": breaks,
        "ruleset": ruleset_metadata("jinkou"),
        "rule_trace": [
            branch_stars_trace(stars),
            {
                "rule_id": "jinkou.four_positions",
                "source_url": JINKOU_SOURCE,
                "source_section": "入式歌解 / 贵神起例 / 十二贵神所属 / 五子元遁起例",
                "result": {r["label"]: r["content"] for r in rows},
            },
            {
                "rule_id": "jinkou.polarity_use",
                "source_url": JINKOU_SOURCE,
                "source_section": "阴阳次第五用",
                "result": {"pattern": pattern, "position": use_position},
            },
            {
                "rule_id": "jinkou.internal_strength",
                "source_url": JINKOU_SOURCE,
                "source_section": "贵神休旺所主",
                "result": strength,
            },
            {
                "rule_id": "jinkou.structural_patterns",
                "source_url": patterns["source_url"],
                "source_section": patterns["source_section"],
                "result": patterns,
            },
            {
                "rule_id": "jinkou.use_conditions",
                "source_url": JINKOU_SOURCE,
                "source_section": "入式歌解 / 阴阳次第五用",
                "result": use_conditions,
            },
            {
                "rule_id": "jinkou.jingben_relations",
                "source_url": relations["source_url"],
                "source_section": relations["source_section"],
                "result": relations,
            },
            {
                "rule_id": "jinkou.empty",
                "source_url": JINKOU_SOURCE,
                "source_section": "旬中空亡 / 四大空亡",
                "result": {
                    "xun_head": xun_head,
                    "branches": empty[:2],
                    "element": empty_element,
                },
            },
            {
                "rule_id": "jinkou.trine_conditions",
                "source_url": combinations["source_url"],
                "source_section": combinations["source_section"],
                "result": combinations,
            },
            {
                "rule_id": "jinkou.month_day_qi",
                "source_url": JINKOU_SOURCE,
                "source_section": "月建旺相 / 月破休囚",
                "result": qi_evidence,
            },
            {
                "rule_id": "jinkou.position_interactions",
                "source_url": interactions["source_url"],
                "source_section": interactions["source_title"],
                "result": interactions,
            },
            {
                "rule_id": "jinkou.dun_stem_relations",
                "source_url": stem_relations["source_url"],
                "source_section": stem_relations["source_title"],
                "result": stem_relations,
            },
            {
                "rule_id": "jinkou.unresolved_definition_witnesses",
                "source_url": definitions["witnesses"][1]["scan_url"],
                "source_section": "湖社叢話第六冊p0057–p0059 / CNTS第二册PDF118–121",
                "result": {
                    "unadjudicated_ids": [
                        e["pattern_id"] for e in definitions["entries"]
                    ],
                    "adjudicated_predicate": None,
                    "complete_classical_conformance": False,
                },
            },
            branch_breaks_trace(breaks),
        ],
        "shensha": [
            {"label": "旬空", "value": empty},
            {"label": "四大空亡", "value": overview["si_da_kong"]},
            {"label": "月破", "value": SIX_CLASH_BRANCHES[month_branch]},
        ],
    }
