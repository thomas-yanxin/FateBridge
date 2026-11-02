"""Month-specific source paths, with presence and effective force kept apart.

The selected 子平真诠 distinguishes 印用食伤 from 伤官佩印 and
杀用印 from 伤官用杀印. Neither a fixed priority nor co-occurrence
adjudicates these paths. This module never changes the strength calculation.
"""

from copy import deepcopy
from typing import Any, Dict, List, Mapping, NamedTuple, Optional, Tuple

from fatebridge.core.classical import determine_monthly_structure
from fatebridge.core.classical_roots import SOURCE as ROOT_SOURCE
from fatebridge.core.classical_stages import YANG_BLADE_SEATS
from fatebridge.utils.data import iter_pillar_gods

SOURCE = {
    **ROOT_SOURCE,
    "id": "ziping_month_path_conditions_v1",
    "title": "秘本子平真诠·论用神、成败救应及各格取用条件",
    "pdf_pages": [
        26,
        27,
        28,
        29,
        30,
        31,
        32,
        73,
        74,
        79,
        80,
        81,
        83,
        84,
        85,
        86,
        89,
        90,
    ],
    "printed_pages": [
        17,
        18,
        19,
        20,
        21,
        22,
        23,
        64,
        65,
        70,
        71,
        72,
        74,
        75,
        76,
        77,
        80,
        81,
    ],
}
Pillars = Mapping[str, Tuple[str, str]]
WEALTH = ("正财", "偏财")
SEAL = ("正印", "偏印")
OUTPUT = ("食神", "伤官")


class PathSpec(NamedTuple):
    id: str
    label: str
    month_gods: Tuple[str, ...]
    helpers: Tuple[Tuple[str, ...], ...]
    force_conditions: Tuple[str, ...]
    pages: Tuple[int, ...]
    month_kind: str = "ordinary"
    observed_check: Optional[str] = None


SPECS = (
    PathSpec(
        "officer_wealth",
        "官格财生官",
        ("正官",),
        (WEALTH,),
        ("财官力量适当", "刑冲破害与救应"),
        (26, 28),
    ),
    PathSpec(
        "officer_seal",
        "官格印护官",
        ("正官",),
        (SEAL,),
        ("财印位置及作用", "伤官与印的相对力量", "官杀混杂与去留"),
        (26, 27, 28, 30),
    ),
    PathSpec(
        "wealth_output",
        "财格食伤生财",
        WEALTH,
        (OUTPUT,),
        ("身能任财", "财与食伤根力", "比劫及官杀影响"),
        (26, 28),
    ),
    PathSpec(
        "wealth_officer",
        "财格生官护财",
        WEALTH,
        (("正官",),),
        ("身财官相对力量", "财官根力与损伤"),
        (26, 28),
    ),
    PathSpec(
        "wealth_seal",
        "财格佩印",
        WEALTH,
        (SEAL,),
        ("财印位置两不相克", "财印及日主相对力量"),
        (28,),
    ),
    PathSpec(
        "seal_officer",
        "印格用官",
        SEAL,
        (("正官",),),
        ("身与印各自轻重", "官印作用与损伤"),
        (27, 28),
    ),
    PathSpec(
        "seal_killer",
        "印格用杀",
        SEAL,
        (("七杀",),),
        ("身印轻重", "杀印相生效力", "印浅身轻时的食伤影响"),
        (73,),
    ),
    PathSpec(
        "seal_output",
        "印格用食伤",
        SEAL,
        (OUTPUT,),
        ("身强印旺才可泄身", "印浅身轻时不能套用", "食伤与印相对力量"),
        (28, 73),
    ),
    PathSpec(
        "seal_wealth",
        "印格用财",
        SEAL,
        (WEALTH,),
        ("印重身强才可抑太过", "印根深浅与财的力量", "印轻财重时不能套用"),
        (74,),
    ),
    PathSpec(
        "food_wealth",
        "食神格生财",
        ("食神",),
        (WEALTH,),
        ("身强食旺", "财根与任财能力", "枭印与财的作用"),
        (28,),
    ),
    PathSpec(
        "food_killer",
        "食神格制杀",
        ("食神",),
        (("七杀",),),
        ("身食杀相对力量", "财印的护食或夺食作用"),
        (27, 28),
    ),
    PathSpec(
        "killer_food",
        "杀格用食神",
        ("七杀",),
        (("食神",),),
        ("杀旺食强且身健", "制杀不能太过", "财印对食杀的作用"),
        (79, 80, 81),
    ),
    PathSpec(
        "killer_seal",
        "杀格用印",
        ("七杀",),
        (SEAL,),
        ("杀印有情", "身轻杀重与印的生化效力", "食神及财对印的作用"),
        (79, 80, 81),
    ),
    PathSpec(
        "killer_blade",
        "杀格用阳刃",
        ("七杀",),
        (),
        ("日主刃杀相对力量", "财印及食神对杀刃的作用"),
        (80, 81),
        observed_check="blade_present",
    ),
    PathSpec(
        "hurt_wealth",
        "伤官格生财",
        ("伤官",),
        (WEALTH,),
        ("身强而财有根", "伤官与财的相对力量", "寒暖与财印条件"),
        (28, 83),
    ),
    PathSpec(
        "hurt_seal",
        "伤官格佩印",
        ("伤官",),
        (SEAL,),
        ("伤官旺而身稍弱", "印根深且力量适当", "财印作用与位置"),
        (28, 83, 84),
    ),
    PathSpec(
        "hurt_killer_seal",
        "伤官格用杀印",
        ("伤官",),
        (("七杀",), SEAL),
        ("伤多身弱", "杀生印帮身制伤的效力", "财是否损印"),
        (84,),
    ),
    PathSpec(
        "hurt_wealth_seal",
        "伤官格兼用财印",
        ("伤官",),
        (WEALTH, SEAL),
        ("财印干头两清而不相碍", "财太旺或印太重时的调停", "身伤财印相对力量"),
        (83, 84),
    ),
    PathSpec(
        "hurt_officer",
        "金水伤官用官",
        ("伤官",),
        (("正官",),),
        (
            "寒暖调候与身官相对力量",
            "财印辅助的实际作用",
            "官伤能否两清",
            "官杀并透时须干头取清",
        ),
        (84, 85),
        observed_check="metal_water_officer",
    ),
    PathSpec(
        "hurt_wealth_officer",
        "伤官以财通官",
        ("伤官",),
        (WEALTH, ("正官",)),
        (
            "财通伤官与官的实际力量及位置",
            "财旺生官的实际通关效力",
            "身伤财官及变格兼格条件",
        ),
        (85,),
    ),
    PathSpec(
        "blade_officer",
        "阳刃格用官",
        ("劫财",),
        (("正官",),),
        ("官根与制刃效力", "财印及食伤的具体作用"),
        (26, 86),
        month_kind="blade",
    ),
    PathSpec(
        "blade_killer",
        "阳刃格用杀",
        ("劫财",),
        (("七杀",),),
        ("刃杀相对力量", "财印及食伤的具体作用", "合杀与去留"),
        (26, 86),
        month_kind="blade",
    ),
    PathSpec(
        "peer_wealth",
        "禄劫另取财",
        ("比肩", "劫财"),
        (WEALTH,),
        ("透干会支的取用条件", "身财相对力量", "比劫及食伤官杀的作用"),
        (27, 89, 90),
        month_kind="peer",
    ),
    PathSpec(
        "peer_officer",
        "禄劫另取官杀",
        ("比肩", "劫财"),
        (("正官", "七杀"),),
        ("透干会支的取用条件", "身与官杀相对力量", "财印食伤的作用"),
        (27, 89, 90),
        month_kind="peer",
    ),
    PathSpec(
        "peer_output",
        "禄劫另取食伤",
        ("比肩", "劫财"),
        (OUTPUT,),
        ("透干会支的取用条件", "身与食伤相对力量", "财印及官杀的作用"),
        (27, 89, 90),
        month_kind="peer",
    ),
)


def build_candidate_selection(
    pillars: Pillars, monthly: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Expose all modeled paths for this selected month, without choosing a winner."""
    monthly = monthly or determine_monthly_structure(dict(pillars), pillars["day"][0])
    selected = monthly["structure_god"]
    original = monthly["original_structure"]
    # PDF31–32 explicitly retains changes which do not lose the original 格.
    # Keep both bases without declaring a transformation or a 兼格 established.
    anchors = {"selected": selected, "original_main_qi": original}
    month_is_blade = monthly["selection_rule"] == "qualified_yang_blade_seat"
    stars: Dict[str, List[Dict[str, Any]]] = {}
    for entry in iter_pillar_gods(pillars, pillars["day"][0]):
        location = "stem" if entry.location == "天干" else "hidden"
        stars.setdefault(entry.ten_god.value, []).append(
            {
                "evidence_id": f"{entry.pillar}:{location}:{entry.char}",
                "pillar": entry.pillar,
                "location": entry.location,
                "stem": entry.char,
            }
        )
    rows = []
    for spec in SPECS:
        matching_anchors = [
            basis for basis, god in anchors.items() if god["ten_god"] in spec.month_gods
        ]
        if not matching_anchors:
            continue
        if (spec.month_kind == "blade" and not month_is_blade) or (
            spec.month_kind == "peer" and month_is_blade
        ):
            continue
        observations = []
        cautions = []
        for group in spec.helpers:
            refs = [s["evidence_id"] for god in group for s in stars.get(god, [])]
            observations.append(
                {
                    "id": "helper_presence:" + "/".join(group),
                    "status": "matched" if refs else "not_matched",
                    "star_refs": refs,
                    "scope": "实际透干或藏干出现；不是得力、透干或制化已成的结论。",
                }
            )
        if spec.observed_check == "blade_present":
            blade = YANG_BLADE_SEATS.get(pillars["day"][0])
            positions = [p for p, (_, b) in pillars.items() if b == blade]
            observations.append(
                {
                    "id": "five_yang_blade_position",
                    "status": "matched" if positions else "not_matched",
                    "positions": positions,
                    "scope": "杀格中借用阳刃的位置条件，不改称月刃格。",
                }
            )
        elif spec.observed_check == "metal_water_officer":
            from fatebridge.utils.data import STEM_ELEMENTS

            metal_water = STEM_ELEMENTS[pillars["day"][0]][0].value == "金" and any(
                STEM_ELEMENTS[anchors[basis]["stem"]][0].value == "水"
                for basis in matching_anchors
            )
            helper_refs = [
                s["evidence_id"] for god in (*WEALTH, *SEAL) for s in stars.get(god, [])
            ]
            hurt_visible = any(s["location"] == "天干" for s in stars.get("伤官", []))
            officer_visible = any(
                s["location"] == "天干" for s in stars.get("正官", [])
            )
            for key, value in (
                ("metal_day_water_month_god", metal_water),
                ("wealth_or_seal_present", bool(helper_refs)),
            ):
                observations.append(
                    {
                        "id": key,
                        "status": "matched" if value else "not_matched",
                        "scope": "所选正文的有限可观察条件；寒暖和有效力量仍未裁定。",
                        **(
                            {"star_refs": helper_refs}
                            if key == "wealth_or_seal_present"
                            else {}
                        ),
                    }
                )
            cautions.append(
                {
                    "id": "officer_hurt_both_revealed",
                    "status": (
                        "matched" if hurt_visible and officer_visible else "not_matched"
                    ),
                    "star_refs": [
                        s["evidence_id"]
                        for god in ("伤官", "正官")
                        for s in stars.get(god, [])
                        if s["location"] == "天干"
                    ],
                    "effect": "source_caution_only",
                    "scope": "PDF84–85对此作警语，不否定用官路径的存在；警语不作成格、现实结果或个人福祸的判断。",
                }
            )
        observed = all(c["status"] == "matched" for c in observations)
        rows.append(
            {
                "id": spec.id,
                "label": spec.label,
                "month_anchor_basis": matching_anchors,
                "status": (
                    "requires_force_adjudication"
                    if observed
                    else "observable_prerequisite_not_met"
                ),
                "observed_conditions": observations,
                **({"source_cautions": cautions} if cautions else {}),
                "force_conditions": [
                    {"condition": condition, "status": "unknown"}
                    for condition in spec.force_conditions
                ],
                "formation_status": "not_adjudicated",
                "source_ref": SOURCE["id"],
                "source_pdf_pages": list(spec.pages),
                **(
                    {
                        "scope": "原文化伤为财在此列为伤官—财—官路径参考，不改写原局五行或藏干，也不认证支局合化。"
                    }
                    if spec.id == "hurt_wealth_officer"
                    else {}
                ),
            }
        )
    return {
        "method_id": "month_path_conditions_v3",
        "source": deepcopy(SOURCE),
        "selected_month": {
            "branch": monthly["month_branch"],
            "label": monthly["label"],
            "stem": selected["stem"],
            "ten_god": selected["ten_god"],
            "selection_rule": monthly["selection_rule"],
            "selection_method": monthly["method_id"],
            "original_main_qi": {
                "stem": original["stem"],
                "ten_god": original["ten_god"],
            },
            "basis_status": (
                "original_and_selected_differ"
                if selected["ten_god"] != original["ten_god"]
                else "same_ten_god"
            ),
        },
        "paths": rows,
        "chosen_path_id": None,
        "adjudication_status": "not_adjudicated",
        "selection_status": (
            "requires_force_adjudication"
            if any(r["status"] == "requires_force_adjudication" for r in rows)
            else (
                "observable_prerequisites_not_met"
                if rows
                else "source_paths_not_modeled"
            )
        ),
        "scope": "并列月令本气与同次有限选择的取神路径，不以透干即抹去本气，也不认证变格或兼格。二十五条有限路径不是全书成败救应；未以十神共现、固定优先级、印比合计或计数代判相对力量，也未选定相神或全局喜忌。",
    }
