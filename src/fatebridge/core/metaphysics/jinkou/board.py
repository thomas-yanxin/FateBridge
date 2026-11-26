"""Jin Kou board builder decoupled from full Liuren board construction."""

from __future__ import annotations

from typing import Any

from fatebridge.core.almanac import localize_datetime
from fatebridge.core.metaphysics.common import (
    ELEMENT_CONTROLS,
    ELEMENT_GENERATES,
    GUI_REN_SEQUENCE,
    LIURENG_GUIREN_DAY,
    LIURENG_GUIREN_NIGHT,
    SIX_CLASH_BRANCHES,
    SIX_HARMONY_BRANCHES,
    YUE_JIANG_NAMES,
    MetaphysicsSeed,
    branch_element_text,
    ganzhi_text,
    kongwang_for_ganzhi,
    rotate_sequence,
    sexagenary_index_for,
    status_against_anchor,
    stem_element_text,
    xun_head_for_ganzhi,
)
from fatebridge.core.metaphysics.jinkou.patterns import (
    GUISHEN_IDENTITIES,
    branch_breaks,
    branch_stars,
    definition_evidence,
    position_interactions,
    structural_patterns,
    structural_relations,
    trine_evidence,
    use_evidence,
    wuzidun_stem,
)
from fatebridge.core.metaphysics.ren_calendar import (
    MonthGeneralMode,
    compact_calendar_policy,
    compute_month_general,
    ruleset_metadata,
    symbolic_calendar_policy,
)
from fatebridge.core.metaphysics.ren_diurnal import DiurnalMode, resolve_diurnal
from fatebridge.utils.data import EARTHLY_BRANCHES, HEAVENLY_STEMS

STEM_PAIRS = (
    ("甲己", "土"),
    ("乙庚", "金"),
    ("丙辛", "水"),
    ("丁壬", "木"),
    ("戊癸", "火"),
)
STEM_RELATIONS = (
    ("god_generates_general", "神干生将干", "贵神", "将神", "生", None),
    ("general_generates_god", "将干生神干", "将神", "贵神", "生", None),
    ("god_controls_general", "神干克将干", "贵神", "将神", "克", "贼动同类"),
    ("general_controls_god", "将干克神干", "将神", "贵神", "克", "财动同类"),
)


def _build_guishen_mapping(
    day_stem: str,
    hour_branch: str,
    is_diurnal_override: bool | None = None,
    *,
    is_diurnal: bool | None = None,
) -> tuple[str, dict[str, str]]:
    if is_diurnal is None:
        is_diurnal = resolve_diurnal(hour_branch, is_diurnal_override)["is_diurnal"]
    start = (LIURENG_GUIREN_DAY if is_diurnal else LIURENG_GUIREN_NIGHT)[day_stem]
    branches = rotate_sequence(EARTHLY_BRANCHES, start, reverse=start in "巳午未申酉戌")
    return start, dict(zip(branches, GUI_REN_SEQUENCE))


def seasonal_power(month_branch: str, element: str) -> str:
    if (
        month_branch not in EARTHLY_BRANCHES
        or element not in "木火土金水"
        or len(element) != 1
    ):
        raise ValueError("四季旺衰须使用月建支及四位实际五行")
    return status_against_anchor(branch_element_text(month_branch), element)


def seasonal_power_basis(month_branch: str) -> str:
    if month_branch not in EARTHLY_BRANCHES:
        raise ValueError("四季旺衰须使用月建支")
    return f"五行休旺：按月建{month_branch}之{branch_element_text(month_branch)}气，辰戌丑未按土旺月"


def internal_strength(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if len(rows) != 4 or {r["label"] for r in rows} != {"人元", "贵神", "将神", "地分"}:
        raise ValueError("课内旺衰需要四个不同的四位")
    if any(row["element"] not in ELEMENT_CONTROLS for row in rows):
        raise ValueError("四位五行无效")
    elements = list(dict.fromkeys(row["element"] for row in rows))
    relations = []
    for i, left in enumerate(rows):
        for j, right in enumerate(rows):
            if i == j:
                continue
            a, b = left["element"], right["element"]
            rel = (
                "克"
                if ELEMENT_CONTROLS[a] == b
                else (
                    "生"
                    if ELEMENT_GENERATES[a] == b
                    else "比和" if a == b and i < j else None
                )
            )
            if rel:
                relations.append(
                    {
                        "source_position": left["label"],
                        "target_position": right["label"],
                        "source_element": a,
                        "target_element": b,
                        "relation": rel,
                    }
                )
    candidates = [
        e
        for e in elements
        if not any(ELEMENT_CONTROLS[other] == e for other in elements)
    ]
    anchor = candidates[0] if len(candidates) == 1 else None
    return {
        "method": "guben_uncontrolled_phase_excerpt_v1",
        "status": "resolved_excerpt" if anchor else "ambiguous_excerpt",
        "anchor_element": anchor,
        "candidate_elements": candidates,
        "candidate_positions": [r["label"] for r in rows if r["element"] in candidates],
        "has_control": any(r["relation"] == "克" for r in relations),
        "relations": relations,
        "powers": {
            r["label"]: status_against_anchor(anchor, r["element"]) if anchor else None
            for r in rows
        },
        "basis": (
            "四位内仅此五行不受其余五行克制，定为课内旺神。"
            if anchor
            else "四位内不受克五行不唯一，保留全部候选。"
        ),
    }


def build_jinkou_qi(
    rows: list[dict[str, Any]], *, month_branch: str, day_branch: str
) -> dict[str, Any]:
    general = next(row for row in rows if row["label"] == "将神")
    branch = general["content"]
    offset = (
        EARTHLY_BRANCHES.index(branch) - EARTHLY_BRANCHES.index(month_branch)
    ) % 12
    label = {0: "建旺", 1: "进气相", 2: "进气相", 6: "月破", 11: "退气"}.get(offset)
    day_element = branch_element_text(day_branch)
    general_element = branch_element_text(branch)
    building_checks = [
        {
            "position": pos,
            "branch": next(r for r in rows if r["label"] == pos)["content"],
            "month_building_branch": month_branch,
            "matched": next(r for r in rows if r["label"] == pos)["content"]
            == month_branch,
        }
        for pos in ("贵神", "将神")
    ]
    return {
        "ruleset_id": "jinkou_yuejian_richen_excerpt_v1",
        "source_section": "月建旺相 / 月破休囚",
        "month_building_branch": month_branch,
        "jiangshen_branch": branch,
        "month_offset": offset,
        "month_qi_label": label,
        "month_qi_status": "matched_excerpt" if label else "not_classified_by_excerpt",
        "day_branch": day_branch,
        "day_element": day_element,
        "jiangshen_element": general_element,
        "day_generates_general": ELEMENT_GENERATES[day_element] == general_element,
        "month_building_checks": building_checks,
        "basis": f"月建{month_branch}、将神{branch}相距{offset}支（{label or '平'}）；日支{day_branch}({day_element}){'生' if ELEMENT_GENERATES[day_element] == general_element else '未生'}将神({general_element})。",
    }


def build_stem_relations(
    *, day_stem: str, rows: list[dict[str, Any]]
) -> dict[str, Any]:
    nodes = {}
    for row in rows[1:3]:
        branch = row["content"]
        expected = wuzidun_stem(day_stem, branch)
        nodes[row["label"]] = {
            "position": row["label"],
            "name": row["shenjiang"],
            "branch": branch,
            "branch_element": row["element"],
            "dun_stem": expected,
            "dun_ganzhi": expected + branch,
            "dun_element": stem_element_text(expected),
            "branch_xun_kong": row["xun_kong"],
            "branch_si_da_kong": row["si_da_kong"],
        }
    intrinsic = rows[1]["intrinsic_ganzhi"]
    evaluations = []
    relation = "两干比和"
    motion_analogue: str | None = None
    for rule_id, name, source, target, phase_rel, analogue in STEM_RELATIONS:
        a, b = nodes[source]["dun_element"], nodes[target]["dun_element"]
        matched = (ELEMENT_GENERATES if phase_rel == "生" else ELEMENT_CONTROLS)[a] == b
        evaluations.append({"id": rule_id, "relation": name, "matched": matched})
        if matched:
            relation, motion_analogue = name, analogue
    left_gz, right_gz = nodes["贵神"]["dun_ganzhi"], nodes["将神"]["dun_ganzhi"]
    pair = next(
        (
            (p, e)
            for p, e in STEM_PAIRS
            if frozenset(p) == frozenset((left_gz[0], right_gz[0]))
        ),
        None,
    )
    left_xun, right_xun = xun_head_for_ganzhi(left_gz), xun_head_for_ganzhi(right_gz)
    return {
        "ruleset_id": "jinkou_jingben_dun_stem_relations_v1",
        "source_title": "校正京本金口诀·五子元遁干元类",
        "day_stem": day_stem,
        "god": nodes["贵神"],
        "general": nodes["将神"],
        "guishen_intrinsic_ganzhi": intrinsic,
        "relation": relation,
        "motion_analogue": motion_analogue,
        "rule_evaluations": evaluations,
        "pair_facts": {
            "left_ganzhi": left_gz,
            "right_ganzhi": right_gz,
            "stem_harmony_matched": pair is not None,
            "canonical_stem_pair": list(pair[0]) if pair else None,
            "candidate_element": pair[1] if pair else None,
            "branch_harmony_matched": SIX_HARMONY_BRANCHES[left_gz[1]] == right_gz[1],
            "left_ganzhi_xun_head": left_xun,
            "right_ganzhi_xun_head": right_xun,
            "same_ganzhi_xun": left_xun == right_xun,
        },
        "complete_classical_conformance": True,
    }


def _jinkou_pick_use_position(rows: list[dict[str, Any]]) -> tuple[str, str, str]:
    count = sum(row["polarity"] == "阳" for row in rows)
    pattern = {0: "纯阴", 1: "三阴一阳", 2: "二阴二阳", 3: "三阳一阴", 4: "纯阳"}[count]
    if count in (1, 3):
        minority = "阳" if count == 1 else "阴"
        label = next(row["label"] for row in rows if row["polarity"] == minority)
        return label, f"{pattern}，取少数{minority}位{label}为用。", pattern
    label = "贵神" if count == 4 else "将神"
    return label, f"{pattern}，依阴阳次第五用取{label}。", pattern


def _motion_evidence(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
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


def _resolve_month_general(
    seed: MetaphysicsSeed,
    liureng_or_month_general: dict[str, Any] | str | None,
    *,
    month_general_mode: MonthGeneralMode = "solar_term",
    month_general_override: str | None = None,
) -> dict[str, Any]:
    if liureng_or_month_general is None:
        return compute_month_general(
            seed,
            month_general_mode=month_general_mode,
            month_general_override=month_general_override,
        )
    if isinstance(liureng_or_month_general, str):
        if liureng_or_month_general not in YUE_JIANG_NAMES:
            raise ValueError("month_general 必须是十二地支之一")
        return {
            "branch": liureng_or_month_general,
            "name": YUE_JIANG_NAMES[liureng_or_month_general],
            "basis": "explicit_month_general",
        }
    if isinstance(liureng_or_month_general, dict):
        if "month_general" in liureng_or_month_general:
            mg = liureng_or_month_general["month_general"]
            return {
                "branch": mg["branch"],
                "name": mg["name"],
                "basis": "supplied_board",
            }
        overview = liureng_or_month_general.get("overview")
        if isinstance(overview, dict) and "month_general" in overview:
            mg = overview["month_general"]
            return {
                "branch": mg["branch"],
                "name": mg["name"],
                "basis": "supplied_jinkou_board",
            }
        if "branch" in liureng_or_month_general and "name" in liureng_or_month_general:
            return dict(liureng_or_month_general)
    raise ValueError("无法从输入解析月将")


def build_jinkou_board(
    seed: MetaphysicsSeed,
    liureng_or_month_general: dict[str, Any] | str | None = None,
    gender: str = "未知",
    di_fen: str | None = None,
    runyear: dict[str, Any] | None = None,
    is_diurnal_override: bool | None = None,
    natal_branch: str | None = None,
    natal_branch_source: str | None = None,
    *,
    diurnal_mode: DiurnalMode = "clock",
    month_general_mode: MonthGeneralMode = "solar_term",
    month_general_override: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    _is_child_course: bool = False,
) -> dict[str, Any]:
    day_stem = seed.pillars["day"][0]
    hour_branch = seed.pillars["hour"][1]
    if di_fen is not None and di_fen not in EARTHLY_BRANCHES:
        raise ValueError("di_fen 必须是一个十二地支")
    di_fen_branch = hour_branch if di_fen is None else di_fen
    instant_for_astro = localize_datetime(seed.input_datetime, seed.timezone)
    diurnal = resolve_diurnal(
        hour_branch,
        is_diurnal_override,
        diurnal_mode=diurnal_mode,
        instant=instant_for_astro,
        latitude=latitude,
        longitude=seed.longitude if longitude is None else longitude,
    )
    guiren_start, guishen_map = _build_guishen_mapping(
        day_stem, hour_branch, is_diurnal_override, is_diurnal=diurnal["is_diurnal"]
    )
    guishen_name = guishen_map[di_fen_branch]
    intrinsic_ganzhi = GUISHEN_IDENTITIES[guishen_name]
    guishen_branch = intrinsic_ganzhi[1]
    month_general = _resolve_month_general(
        seed,
        liureng_or_month_general,
        month_general_mode=month_general_mode,
        month_general_override=month_general_override,
    )
    jiangshen_branch = EARTHLY_BRANCHES[
        (
            EARTHLY_BRANCHES.index(month_general["branch"])
            + EARTHLY_BRANCHES.index(di_fen_branch)
            - EARTHLY_BRANCHES.index(hour_branch)
        )
        % 12
    ]
    jiangshen_name = YUE_JIANG_NAMES[jiangshen_branch]
    renyuan_stem = wuzidun_stem(day_stem, di_fen_branch)
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
                "seasonal_power": seasonal_power(month_branch, element),
                "polarity": "阳" if index % 2 == 0 else "阴",
                "dun_stem": (
                    wuzidun_stem(day_stem, content)
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
        row["internal_power"] = strength["powers"][row["label"]]
    patterns = structural_patterns(
        rows,
        day_ganzhi=day_ganzhi,
        hour_branch=hour_branch,
        is_diurnal=diurnal["is_diurnal"],
    )
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
    overview: dict[str, Any] = {
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
        "month_general": {
            "branch": month_general["branch"],
            "name": month_general["name"],
        },
        "gender": gender,
        "power_basis": seasonal_power_basis(month_branch),
        "diurnal_mode": diurnal_mode,
        "diurnal_basis": (
            "explicit_override"
            if is_diurnal_override is not None
            else (
                "sunrise_sunset_ephemeris"
                if diurnal["astronomical_boundary_computed"]
                else "卯至申昼、酉至寅夜的时支约定"
            )
        ),
        "is_diurnal": diurnal["is_diurnal"],
        "diurnal_evidence": diurnal,
    }
    if runyear:
        overview["runyear"] = runyear

    # Never duplicate full solar_term_dependencies or top-level board blocks inside rule_trace.
    raw_policy = seed.calendar_context.get("ren_calendar_policy")
    calendar_policy = compact_calendar_policy(raw_policy)
    if _is_child_course and "solar_term_dependencies" in calendar_policy:
        calendar_policy.pop("solar_term_dependencies", None)

    return {
        "overview": overview,
        "calendar_policy": calendar_policy,
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
            {
                "rule_id": "jinkou.four_positions",
                "source_section": "入式歌解 / 贵神起例 / 五子元遁",
                "result": {r["label"]: r["content"] for r in rows},
            },
            {
                "rule_id": "jinkou.polarity_use",
                "source_section": "阴阳次第五用",
                "result": {"pattern": pattern, "position": use_position},
            },
            {
                "rule_id": "jinkou.jingben_relations",
                "source_section": relations["source_section"],
                "result": {"si_jue": {"natal": relations["si_jue"]["natal"]}},
            },
        ],
        "shensha": [
            {"label": "旬空", "value": empty},
            {"label": "四大空亡", "value": overview["si_da_kong"]},
            {"label": "月破", "value": SIX_CLASH_BRANCHES[month_branch]},
        ],
    }
