"""Position-aware BaZi evidence shared by birth and the nine topic services.

This layer checks observable prerequisites, never certifies 成格 or converts a
star count into strength. Source principles and project formalizations are
identified separately. It does not change the existing strength/scoring model.
"""

from __future__ import annotations

from copy import deepcopy
from itertools import combinations
from typing import Any, Dict, List, Mapping, Optional, Tuple

from fatebridge.core.bureau_season import build_bureau_season_reference
from fatebridge.core.classical import (
    determine_monthly_structure,
    seasonal_climate_god,
    twelve_life_stage,
)
from fatebridge.core.classical_candidate_selection import SOURCE as CANDIDATE_SOURCE
from fatebridge.core.classical_candidate_selection import build_candidate_selection
from fatebridge.core.classical_force import SOURCE as FORCE_SOURCE
from fatebridge.core.classical_force import build_force_components
from fatebridge.core.classical_from_child import SOURCE as FROM_CHILD_SOURCE
from fatebridge.core.classical_from_child import build_from_child_reference
from fatebridge.core.classical_passage import SOURCE as PASSAGE_SOURCE
from fatebridge.core.classical_passage import build_passage_evidence
from fatebridge.core.classical_roots import build_classical_root_profile
from fatebridge.core.classical_routes import SOURCE as ROUTES_SOURCE
from fatebridge.core.classical_routes import build_classical_routes, star_id
from fatebridge.core.element_presence import build_element_presence
from fatebridge.core.hidden_carriers import (
    build_natal_hidden_carriers,
    describe_temporal_hidden_carrier,
    hidden_target_reference,
)
from fatebridge.core.month_duty_reference import build_month_duty_reference
from fatebridge.core.passage_relations import build_passage_relation_context
from fatebridge.core.star_occurrences import build_star_occurrences
from fatebridge.core.timing_carriers import SCOPE as CARRIER_SCOPE
from fatebridge.core.timing_carriers import SOURCE as CARRIER_SOURCE
from fatebridge.core.timing_carriers import describe_timing_carrier
from fatebridge.utils.data import (
    BRANCH_COMBINATIONS,
    BRANCH_CONFLICTS,
    BRANCH_HARMS,
    BRANCH_SEASONAL_COMBINATIONS,
    BRANCH_SELF_PUNISHMENTS,
    BRANCH_THREE_PUNISHMENTS,
    BRANCH_TRIPLE_COMBINATIONS,
    DESTRUCTION_CYCLE,
    STEM_ELEMENTS,
    TenGod,
    get_ten_god,
    iter_pillar_gods,
)

Pillars = Mapping[str, Tuple[str, str]]
ORDER = ("year", "month", "day", "hour")
SOURCE_URL = (
    "https://upload.wikimedia.org/wikipedia/commons/f/fe/"
    "NLC416-11jh010455-35296_%E5%AD%90%E5%B9%B3%E7%9C%9F%E8%A9%AE.pdf"
)
RULESETS = [
    {
        "id": "ziping_prerequisites_v1",
        "title": "沈孝瞻《秘本子平真诠》正文（上海世界图书馆发行，国图藏本）",
        "source_url": SOURCE_URL,
        "source_sha256": "71402a780b0351b54edf121a51bc4a4a4ce5896496c35b954563ee06f1a6f620",
        "locators": {
            "storage_clash": "论墓库刑冲之说 PDF43–45",
            "roots": "论十干得时不旺失时不弱，PDF22–23／印刷13–14",
            "month_command": "论用神，PDF26–27／印刷17–18",
            "formation": "论用神成败救应，PDF28–30／印刷19–21",
            "positions": "论正官，PDF65–67／印刷56–58",
            "food_wealth": "论食神，PDF76–78／印刷67–69",
            "hurt_seal": "论伤官，PDF82–85／印刷73–76",
        },
        "scope": "原典原则的有限前提审查；具体布尔判据为本项目形式化，不是全流派裁决。",
    },
    {
        "id": "fatebridge_position_topic_v1",
        "title": "FateBridge 星位、关系与九专题取证约定 v1",
        "scope": "透藏、同字根／同五行根、位置距离、主题选星及时间触点；不认证合化、吉凶或现实结果。",
    },
    dict(ROUTES_SOURCE),
    dict(FORCE_SOURCE),
    dict(CANDIDATE_SOURCE),
    dict(PASSAGE_SOURCE),
]


def _roots(stem: str, pillars: Pillars) -> List[Dict[str, Any]]:
    from fatebridge.utils.data import BRANCH_HIDDEN_STEMS

    return [
        {
            "pillar": name,
            "branch": pillars[name][1],
            "stem": hidden,
            "hidden_rank": rank,
            "kind": "same_stem" if hidden == stem else "same_element",
        }
        for name in ORDER
        for rank, hidden in enumerate(BRANCH_HIDDEN_STEMS[pillars[name][1]])
        if STEM_ELEMENTS[hidden][0] == STEM_ELEMENTS[stem][0]
    ]


def _growth_roots(stem: str, pillars: Pillars) -> List[Dict[str, Any]]:
    return [
        {
            "pillar": n,
            "branch": pillars[n][1],
            "stage": twelve_life_stage(stem, pillars[n][1]),
            "kind": "growth_phase_reference",
            "source_ref": "ziping_prerequisites_v1:roots",
        }
        for n in ORDER
        if twelve_life_stage(stem, pillars[n][1]) in ("长生", "临官", "帝旺")
    ]


def _pair_relations(left: str, right: str, pillars: Pillars) -> List[Dict[str, Any]]:
    a, b = pillars[left], pillars[right]
    kinds = []
    for name, table in (
        ("六合", BRANCH_COMBINATIONS),
        ("六冲", BRANCH_CONFLICTS),
        ("六害", BRANCH_HARMS),
    ):
        if table.get(a[1]) == b[1]:
            kinds.append(("branch", name))
    if a[1] == b[1] and a[1] in BRANCH_SELF_PUNISHMENTS:
        kinds.append(("branch", "自刑"))
    if {a[1], b[1]} == {"子", "卯"}:
        kinds.append(("branch", "子卯刑"))
    if frozenset((a[0], b[0])) in {
        frozenset(pair) for pair in ("甲己", "乙庚", "丙辛", "丁壬", "戊癸")
    }:
        kinds.append(("stem", "天干五合"))
    return [
        {
            "kind": kind,
            "level": level,
            "positions": [left, right],
            "characters": [
                a[0 if level == "stem" else 1],
                b[0 if level == "stem" else 1],
            ],
            "distance": (
                abs(ORDER.index(left) - ORDER.index(right))
                if left in ORDER and right in ORDER
                else None
            ),
            "effect_status": "relation_only",
        }
        for level, kind in kinds
    ]


def _group_relations(pillars: Pillars) -> List[Dict[str, Any]]:
    groups = []
    for kind, table in (
        ("三合", BRANCH_TRIPLE_COMBINATIONS),
        ("三会", BRANCH_SEASONAL_COMBINATIONS),
        ("三刑", {"".join(g): None for g in BRANCH_THREE_PUNISHMENTS if len(g) == 3}),
    ):
        for branches, bureau in table.items():
            if set(branches) <= {b for _, b in pillars.values()}:
                groups.append(
                    {
                        "kind": kind,
                        "branches": list(branches),
                        "positions": [
                            n for n, (_, b) in pillars.items() if b in branches
                        ],
                        "bureau": bureau,
                        "effect_status": "relation_only",
                    }
                )
    return groups


def build_natal_evidence(
    pillars: Pillars, strength: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Build position and prerequisite evidence without consulting an oracle."""
    supplied = strength or {}
    assessment = supplied.get("assessment", {})
    strength = {
        "strength_level": supplied.get("strength_level"),
        "method_id": assessment.get("method_id"),
        "status": assessment.get("status"),
        "requires_special_structure_review": assessment.get(
            "requires_special_structure_review"
        ),
        "candidate_strengths": assessment.get("sensitivity", {}).get(
            "candidate_strengths", []
        ),
        "root_effect_policy": assessment.get("root_effect_policy"),
        "root_qualifications": deepcopy(assessment.get("root_qualifications")),
        "stem_energy_accounting": deepcopy(assessment.get("stem_energy_accounting")),
        "clash_comparison": deepcopy(assessment.get("clash_comparison")),
        "threshold_arithmetic": deepcopy(assessment.get("threshold_arithmetic")),
        "storage_movement_effects": (
            deepcopy([e for e in assessment["relations"] if "storage_effect" in e])
            if "relations" in assessment
            else None
        ),
    }
    day = pillars["day"][0]
    gods: Dict[str, List[Dict[str, Any]]] = {g.value: [] for g in TenGod}
    for entry in iter_pillar_gods({n: pillars[n] for n in ORDER}, day):
        gods[entry.ten_god.value].append(
            {
                "pillar": entry.pillar,
                "stem": entry.char,
                "branch": entry.branch,
                "location": entry.location,
                "evidence_id": star_id(entry.pillar, entry.location, entry.char),
                "roots": _roots(entry.char, pillars),
                "growth_phase_roots": _growth_roots(entry.char, pillars),
            }
        )
    stems = [
        {
            "pillar": name,
            "stem": pillars[name][0],
            "ten_god": get_ten_god(day, pillars[name][0]).value,
            "is_day_master": name == "day",
            "roots": _roots(pillars[name][0], pillars),
            "life_stages": {
                n: twelve_life_stage(pillars[name][0], pillars[n][1]) for n in ORDER
            },
            "growth_phase_roots": _growth_roots(pillars[name][0], pillars),
        }
        for name in ORDER
    ]
    relations = [
        r for a, b in combinations(ORDER, 2) for r in _pair_relations(a, b, pillars)
    ]
    groups = _group_relations(pillars)
    monthly = determine_monthly_structure(dict(pillars), day)
    lu = dict(zip("甲乙丙丁戊己庚辛壬癸", "寅卯巳午巳午申酉亥子"))
    blade = dict(zip("甲丙戊庚壬", "卯午午酉子"))
    branch = pillars["month"][1]
    month_candidates = [
        {
            **candidate,
            "visible_in": [
                n
                for n in ("year", "month", "hour")
                if pillars[n][0] == candidate["stem"]
            ],
        }
        for candidate in monthly["hidden_stems"]
    ]
    month = {
        "month_branch": branch,
        "label": monthly["label"],
        "selection_rule": monthly["selection_rule"],
        "selection_method": monthly["method_id"],
        "legacy_label": monthly["legacy_label"],
        "candidates": month_candidates,
        "selected_god": monthly["structure_god"],
        "lu_seat": branch == lu[day],
        "yang_blade_seat": branch == blade.get(day),
        "legacy_blade_qualification_conflict": monthly["legacy_label"] == "月刃格"
        and branch != blade.get(day),
        "month_in_groups": [g for g in groups if "month" in g["positions"]],
        "selection_status": "requires_school_review",
        "intra_month_duty": {
            "status": "not_adjudicated",
            "selected_stem": None,
            "rule_profile": None,
            "source_reference": build_month_duty_reference(pillars),
            "scope": "月支、本气、取格与节后人元司令不是同一字段。仅凭四柱不能恢复节后天数；有出生时刻时另读同次calendar_context.bazi_month_boundary的民用比较瞬间与未取整经过秒数，仍不据未采用的分日表改写旺衰。",
        },
        "scope": "并列保留本气、透干、会支与禄刃资格；旧取格标签不是成格结论，劫财本气不自动等于阳刃。",
    }
    positional = _financial_seal_positions(pillars, gods)
    passage = build_passage_evidence(pillars, assessment)
    return {
        "method_id": "bazi_position_prerequisites_v2",
        "rulesets": deepcopy([*RULESETS, FROM_CHILD_SOURCE]),
        "ten_gods": gods,
        "star_occurrences": build_star_occurrences(gods),
        "element_presence": build_element_presence(pillars),
        "bureau_season_reference": build_bureau_season_reference(pillars, assessment),
        "visible_stems": stems,
        "relations": relations,
        "group_relations": groups,
        "month_command": month,
        "seasonal_reference": seasonal_climate_god(
            pillars["day"][0], pillars["month"][1], dict(pillars)
        ),
        "classical_root_profile": build_classical_root_profile(dict(pillars)),
        "classical_routes": build_classical_routes(pillars, gods, month),
        "candidate_selection": build_candidate_selection(pillars, monthly),
        "from_child_reference": build_from_child_reference(pillars),
        "natal_hidden_carriers": build_natal_hidden_carriers(pillars),
        "force_components": build_force_components(pillars, assessment, gods),
        "classical_passage": passage,
        "classical_passage_relations": build_passage_relation_context(
            passage, assessment, pillars=pillars
        ),
        "financial_seal_positions": positional,
        "structure_checks": _structure_checks(gods, month, strength or {}),
        "strength_context": strength or {},
        "limitations": [
            "同字根、同五行根和十二长生分列；根的存在不等于有力，阴长生不伪造藏干。",
            "关系成立不直接等于合化、合去、开库、失根或破格；不在此层改写原局五行。",
            "未以现代加权计数裁定原典的旺、根深或制化适当；未裁定条件保留 unknown。",
        ],
    }


def _financial_seal_positions(
    pillars: Pillars, gods: Dict[str, List[Dict[str, Any]]]
) -> List[Dict[str, Any]]:
    """Expose exact 财印 positions, including separation and competing 合."""
    wealth = [e for g in ("正财", "偏财") for e in gods[g] if e["location"] == "天干"]
    seals = [e for g in ("正印", "偏印") for e in gods[g] if e["location"] == "天干"]
    rows = []
    for w in wealth:
        for s in seals:
            a, b = w["pillar"], s["pillar"]
            lo, hi = sorted([ORDER.index(a), ORDER.index(b)])
            rows.append(
                {
                    "wealth_position": a,
                    "seal_position": b,
                    "stems": [w["stem"], s["stem"]],
                    "distance": hi - lo,
                    "intervening_positions": list(ORDER[lo + 1 : hi]),
                    "wealth_controls_seal_element": DESTRUCTION_CYCLE[
                        STEM_ELEMENTS[w["stem"]][0]
                    ]
                    == STEM_ELEMENTS[s["stem"]][0],
                    "stem_combination": any(
                        r["level"] == "stem" for r in _pair_relations(a, b, pillars)
                    ),
                    "adjudication": "position_observation_only",
                    "source_ref": "ziping_prerequisites_v1:positions",
                }
            )
    return rows


def _structure_checks(
    gods: Dict[str, List[Dict[str, Any]]],
    month: Dict[str, Any],
    strength: Dict[str, Any],
) -> List[Dict[str, Any]]:
    specs = [
        (
            "food_generates_wealth",
            "食神生财",
            ("食神",),
            ("正财", "偏财"),
            "food_wealth",
            True,
        ),
        ("hurt_with_seal", "伤官佩印", ("伤官",), ("正印", "偏印"), "hurt_seal", False),
        ("food_controls_killer", "食神制杀", ("七杀",), ("食神",), "formation", False),
        (
            "killer_generates_seal",
            "杀印相生",
            ("七杀",),
            ("正印", "偏印"),
            "formation",
            False,
        ),
        (
            "officer_with_wealth_seal",
            "正官财印相辅",
            ("正官",),
            ("正印", "偏印", "正财", "偏财"),
            "positions",
            False,
        ),
    ]

    def positions(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [
            {k: v for k, v in e.items() if k not in ("roots", "growth_phase_roots")}
            for e in entries
        ]

    checks = []
    for key, label, anchors, helpers, source, visible_required in specs:
        month_anchors = {
            "food_generates_wealth": ("食神",),
            "hurt_with_seal": ("伤官",),
            "food_controls_killer": ("食神", "七杀"),
            "killer_generates_seal": ("七杀", "正印", "偏印"),
            "officer_with_wealth_seal": ("正官",),
        }[key]
        anchor_hits = [e for g in anchors for e in gods[g]]
        helper_hits = [e for g in helpers for e in gods[g]]
        visible_helpers = [e for e in helper_hits if e["location"] == "天干"]
        conditions: List[Dict[str, Any]] = [
            {
                "id": "anchor_present",
                "status": "matched" if anchor_hits else "not_matched",
                "evidence": positions(anchor_hits),
            },
            {
                "id": "helper_present",
                "status": "matched" if helper_hits else "not_matched",
                "evidence": positions(helper_hits),
            },
            {
                "id": "month_command_anchor",
                "status": (
                    "matched"
                    if month["selected_god"]["ten_god"] in month_anchors
                    else "not_matched"
                ),
                "scope": "核对本次已选择的月令格局用神；本气候选与实际选择分开，不以同盘出现替代月令锚点。",
            },
            {
                "id": "helper_root_present",
                "status": (
                    "matched"
                    if any(e["roots"] for e in helper_hits)
                    else (
                        "unknown"
                        if any(e["growth_phase_roots"] for e in helper_hits)
                        else "not_matched"
                    )
                ),
                "required": key in ("food_generates_wealth", "hurt_with_seal"),
                "scope": "核对藏干同五行根；仅见长生等而无藏干根时保留流派复核，不判无根；不裁定印根深、财根有效或未受损。",
            },
        ]
        if visible_required:
            conditions.append(
                {
                    "id": "wealth_visible",
                    "status": "matched" if visible_helpers else "not_matched",
                    "evidence": positions(visible_helpers),
                }
            )
        if key == "officer_with_wealth_seal":
            for role, names in (
                ("wealth", ("正财", "偏财")),
                ("seal", ("正印", "偏印")),
            ):
                conditions.append(
                    {
                        "id": role + "_present",
                        "status": (
                            "matched" if any(gods[g] for g in names) else "not_matched"
                        ),
                    }
                )
        conditions.extend(
            [
                {
                    "id": "strength_and_relative_force",
                    "status": "unknown",
                    "model_observation": strength,
                    "scope": "工程强弱仅作旁证；不等同原典身强食旺、伤旺身弱、印根深等裁定。",
                },
                {
                    "id": "obstruction_and_rescue",
                    "status": "unknown",
                    "scope": "合绊争合、财印位置、偏印夺食、财滋杀等须合参，关系存在不自动判破或判救。",
                },
            ]
        )
        applicable = bool(anchor_hits and helper_hits)
        checks.append(
            {
                "id": key,
                "label": label,
                "status": (
                    "not_applicable"
                    if not applicable
                    else (
                        "prerequisite_not_met"
                        if any(
                            c["status"] == "not_matched" and c.get("required", True)
                            for c in conditions
                        )
                        else "pending_adjudication"
                    )
                ),
                "formation_status": "not_adjudicated",
                "conditions": conditions,
                "source_ref": f"ziping_prerequisites_v1:{source}",
                "formalization": "FateBridge 有限必要条件审查 v1；不把所有命式归入该路，也不认证成格。",
            }
        )
    return checks


TOPICS = {
    "career": (
        ("正官", "七杀", "正印", "偏印", "食神", "伤官", "正财", "偏财"),
        ("month",),
        "职责、输出与支持的传统类比；不能判职业高度或实际能力。",
    ),
    "wealth": (
        ("正财", "偏财", "食神", "伤官", "比肩", "劫财"),
        (),
        "财星、财源与分配线索；不能判资产、回款或投资收益。",
    ),
    "education": (
        ("正印", "偏印", "食神", "伤官", "正官", "七杀"),
        ("month",),
        "学习支持、表达与规范线索；不能判智力、学历或录取结果。",
    ),
    "personality": (
        tuple(g.value for g in TenGod),
        (),
        "盘内结构差异；不是心理测量或人格诊断。",
    ),
    "health": ((), (), "仅盘内五行与传统文化分类；不作健康、生理或疾病推断。"),
    "relatives": (
        ("偏财", "正印", "比肩", "劫财"),
        ("year", "month"),
        "命主视角的父母、手足传统对应；不能判亲人实际状况、人数或亲疏。",
    ),
    "marriage": (
        (),
        ("day",),
        "命主视角的星宫线索；不能代替双方互动，也不判婚姻成败。",
    ),
    "romance": (
        (),
        ("day",),
        "命主视角的关系线索；不能判他人心意、忠诚或所谓正缘身份。",
    ),
    "children": (
        (),
        ("hour",),
        "命主视角的子女星宫；不判生育能力、数量、孩子性别或生育时间。",
    ),
}


def build_topic_evidence(
    natal: Dict[str, Any],
    pillars: Pillars,
    topic: str,
    gender: Optional[str],
    dayun: Optional[Tuple[str, str]],
    liunian: Optional[Tuple[str, str]],
) -> Dict[str, Any]:
    from fatebridge.utils.data import normalize_gender

    focus, palaces, scope = TOPICS[topic]
    norm_gender = normalize_gender(gender)
    selection = "topic_correspondence"
    selection_alternatives: Dict[str, List[str]] = {}
    if topic in ("marriage", "romance", "children"):
        male = ("正官", "七杀") if topic == "children" else ("正财", "偏财")
        female = ("食神", "伤官") if topic == "children" else ("正官", "七杀")
        selection_alternatives = {"male": list(male), "female": list(female)}
        focus = (
            male
            if norm_gender == "male"
            else female if norm_gender == "female" else male + female
        )
        selection = (
            "gendered_traditional_correspondence"
            if norm_gender in ("male", "female")
            else "unselected_gender_alternatives"
        )
    temporal = {
        n: p for n, p in (("dayun", dayun), ("liunian", liunian)) if p is not None
    }
    layers: List[Dict[str, Any]] = []
    for name, pillar in temporal.items():
        incoming = {"day": pillars["day"], name: pillar}
        entries = [
            e for e in iter_pillar_gods(incoming, pillars["day"][0]) if e.pillar == name
        ]
        relations = [
            r
            for n in ORDER
            for r in _pair_relations(name, n, {**pillars, name: pillar})
        ]
        groups = [
            g
            for g in _group_relations({**pillars, name: pillar})
            if name in g["positions"]
        ]
        layers.append(
            {
                "layer": name,
                "pillar": "".join(pillar),
                "stars": [
                    {
                        "stem": e.char,
                        "location": e.location,
                        "ten_god": e.ten_god.value,
                        "in_topic": e.ten_god.value in focus,
                    }
                    for e in entries
                ],
                "natal_relations": relations,
                "group_relations": groups,
                "palace_hits": [
                    r
                    for r in relations
                    if r["level"] == "branch" and r["positions"][1] in palaces
                ],
            }
        )
    first_stars = []
    for god in focus:
        entries = natal["ten_gods"][god]
        if not entries:
            continue
        first_stars.append(
            {
                "ten_god": god,
                "visible_in": [e["pillar"] for e in entries if e["location"] == "天干"],
                "hidden_in": list(
                    dict.fromkeys(
                        e["pillar"] for e in entries if e["location"] == "地支藏干"
                    )
                ),
            }
        )
        if len(first_stars) == 2:
            break
    first_view = {
        "selection_basis": selection,
        "selection_policy": "按专题声明顺序摘录最多两种已见星，不表示主导或排名；完整星位和前提见depth视图。",
        "natal_stars": first_stars,
        "timing": [
            {
                "layer": layer["layer"],
                "pillar": layer["pillar"],
                "topic_stars": list(
                    dict.fromkeys(e["ten_god"] for e in layer["stars"] if e["in_topic"])
                ),
                "palace_relation_count": len(layer["palace_hits"]),
            }
            for layer in layers
        ],
    }
    return {
        "topic": topic,
        "first_view": first_view,
        "scope": scope,
        "selection_basis": selection,
        "selection_alternatives": selection_alternatives,
        "stars": {g: natal["ten_gods"][g] for g in focus},
        "palaces": {
            n: {
                "pillar": "".join(pillars[n]),
                "relations": [
                    r
                    for r in natal["relations"]
                    if r["level"] == "branch" and n in r["positions"]
                ],
            }
            for n in palaces
        },
        "timing": {
            "scope": "目标日期有效大运／流年柱的结构触点；不是全年扫描，也不判事件必发生或吉凶。",
            "pillar_carriers": [
                describe_timing_carrier(f"timing.{name}", *pillar, pillars)
                for name, pillar in temporal.items()
            ],
            "carrier_source": dict(CARRIER_SOURCE),
            "carrier_scope": CARRIER_SCOPE,
            "hidden_target_reference": hidden_target_reference(),
            "hidden_target_carriers": [
                describe_temporal_hidden_carrier(f"timing.{name}", *pillar)
                for name, pillar in temporal.items()
            ],
            "layers": layers,
            "between_layers": (
                _pair_relations("dayun", "liunian", temporal)
                if len(temporal) == 2
                else []
            ),
            "combined_groups": [
                g
                for g in _group_relations({**pillars, **temporal})
                if any(n in temporal for n in g["positions"])
            ],
        },
        "source_ref": "fatebridge_position_topic_v1",
        "limitations": [
            "未见相关星只表示该盘未列出，不推断现实关系不存在；计数不等于力量。",
            "所有星、宫与时间触点均属于命主单盘；实际能力、亲属与双方互动须独立资料。",
        ],
    }
