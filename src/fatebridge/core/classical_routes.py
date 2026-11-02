"""Position-resolved routes from one declared edition of 子平真诠.

These operators establish observed 生/克/合 and selected-month prerequisites.
They do not replace the text's relative-force, formation or rescue judgments
with occurrence counts, nor declare every helper to be the decisive 相神.
"""

from itertools import product
from typing import Any, Dict, List, Mapping, Tuple

from fatebridge.core.classical_stages import STAGE_PROFILE_ID, twelve_life_stage
from fatebridge.utils.data import (
    DESTRUCTION_CYCLE,
    GENERATION_CYCLE,
    STEM_ELEMENTS,
)

Pillars = Mapping[str, Tuple[str, str]]
ORDER = ("year", "month", "day", "hour")
WEALTH = ("正财", "偏财")
SEAL = ("正印", "偏印")
PEER = ("比肩", "劫财")
COMBINATIONS = {frozenset(pair) for pair in ("甲己", "乙庚", "丙辛", "丁壬", "戊癸")}
SOURCE = {
    "id": "ziping_routes_v1",
    "author": "沈孝瞻",
    "title": "秘本子平真诠·成败救应、相神及食伤诸章",
    "edition": "国家图书馆藏本 NLC416-11jh010455-35296，上海世界图书馆发行",
    "source_url": "https://upload.wikimedia.org/wikipedia/commons/f/fe/NLC416-11jh010455-35296_%E5%AD%90%E5%B9%B3%E7%9C%9F%E8%A9%AE.pdf",
    "source_sha256": "71402a780b0351b54edf121a51bc4a4a4ce5896496c35b954563ee06f1a6f620",
    "formalization": "FateBridge 星位路径 v1；只裁定本条计算事实，未裁定全局成败。",
}


def star_id(pillar: str, location: str, stem: str) -> str:
    return f"{pillar}:{'stem' if location == '天干' else 'hidden'}:{stem}"


def build_classical_routes(
    pillars: Pillars,
    gods: Dict[str, List[Dict[str, Any]]],
    month: Dict[str, Any],
) -> Dict[str, Any]:
    """Return actual routes and their unresolved conditions, never a fitted grade."""
    selected = month["selected_god"]
    anchor_god = selected["ten_god"]
    specifications = (
        (
            "wealth_feeds_officer",
            "官格财生官",
            ("正官",),
            WEALTH,
            ("正官",),
            "生",
            [28, 39],
        ),
        (
            "seal_checks_hurt",
            "官格印制伤护官",
            ("正官",),
            SEAL,
            ("伤官",),
            "克",
            [30, 40],
        ),
        (
            "peer_combines_killer",
            "官格比劫合杀留官线索",
            ("正官",),
            PEER,
            ("七杀",),
            "合",
            [30, 39, 66],
        ),
        (
            "food_generates_wealth",
            "食神格生财",
            ("食神",),
            ("食神",),
            WEALTH,
            "生",
            [28, 76],
        ),
        (
            "wealth_checks_owl",
            "食神格财制枭护食",
            ("食神",),
            WEALTH,
            ("偏印",),
            "克",
            [30, 78],
        ),
        (
            "food_controls_killer",
            "食神制杀路径",
            ("食神", "七杀"),
            ("食神",),
            ("七杀",),
            "克",
            [28, 39, 77],
        ),
        (
            "hurt_generates_wealth",
            "伤官格生财",
            ("伤官",),
            ("伤官",),
            WEALTH,
            "生",
            [28, 82, 83],
        ),
        (
            "seal_checks_hurt_in_hurt_month",
            "伤官格佩印",
            ("伤官",),
            SEAL,
            ("伤官",),
            "克",
            [28, 83],
        ),
    )

    def stars(names: Tuple[str, ...]) -> List[Dict[str, Any]]:
        return [entry for name in names for entry in gods[name]]

    def ref(entry: Dict[str, Any]) -> str:
        return star_id(entry["pillar"], entry["location"], entry["stem"])

    def root_condition(entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        revealed = [e for e in entries if e["location"] == "天干"]
        return {
            "revealed_stars": [ref(e) for e in revealed],
            "with_hidden_root": [ref(e) for e in revealed if e["roots"]],
            "yin_growth_references": [
                {
                    "star_ref": ref(e),
                    "pillar": name,
                    "branch": pillars[name][1],
                }
                for e in revealed
                for name in ORDER
                if e["stem"] in "乙丁己辛癸"
                and twelve_life_stage(e["stem"], pillars[name][1]) == "长生"
            ],
            "effective_strength": "not_adjudicated",
        }

    routes = []
    for key, label, allowed, left_gods, right_gods, relation, pages in specifications:
        left, right = stars(left_gods), stars(right_gods)
        edges = []
        for a, b in product(left, right):
            if ref(a) == ref(b):
                continue
            ea, eb = STEM_ELEMENTS[a["stem"]][0], STEM_ELEMENTS[b["stem"]][0]
            if relation == "生":
                observed = GENERATION_CYCLE[ea] == eb
            elif relation == "克":
                observed = DESTRUCTION_CYCLE[ea] == eb
            else:
                observed = (
                    a["location"] == b["location"] == "天干"
                    and frozenset((a["stem"], b["stem"])) in COMBINATIONS
                )
            if not observed:
                continue
            distance = abs(ORDER.index(a["pillar"]) - ORDER.index(b["pillar"]))
            competitors = []
            if relation == "合":
                # Include the day stem in competition even though it is not a
                # counted ten-god occurrence. Do not pick an arbitrary partner.
                competitors = [
                    name
                    for name in ORDER
                    if name not in (a["pillar"], b["pillar"])
                    and (
                        frozenset((pillars[name][0], a["stem"])) in COMBINATIONS
                        or frozenset((pillars[name][0], b["stem"])) in COMBINATIONS
                    )
                ]
            edges.append(
                {
                    "from_star": ref(a),
                    "to_star": ref(b),
                    "relation": relation,
                    "position_distance": distance,
                    "both_revealed": a["location"] == b["location"] == "天干",
                    "other_matching_stem_positions": competitors,
                    "effect_status": (
                        "other_matching_stems_require_position_review"
                        if competitors
                        else "observed_relation_not_effect_adjudication"
                    ),
                }
            )
        helper_entries = (
            right if key in ("food_generates_wealth", "hurt_generates_wealth") else left
        )
        applicable = anchor_god in allowed
        routes.append(
            {
                "id": key,
                "label": label,
                "allowed_month_gods": list(allowed),
                "status": (
                    "not_applicable_to_selected_month"
                    if not applicable
                    else "observed_route" if edges else "relation_not_observed"
                ),
                "star_refs": list(dict.fromkeys(ref(e) for e in left + right)),
                "edges": edges,
                "helper_root_context": root_condition(helper_entries),
                "unresolved": [
                    "日主、用神与辅助星的相对力量",
                    "根损、合化、作用是否被阻及救应是否有效",
                    "是否为全局赖以成格的相神",
                ],
                "source_ref": "ziping_routes_v1",
                "source_pdf_pages": pages,
                "formation_status": "not_adjudicated",
            }
        )
    # 财与印隔位、同根月令是原文的不同观察，不能合成一句自动相战／不碍。
    positions = []
    for wealth, seal in product(stars(WEALTH), stars(SEAL)):
        if wealth["location"] != "天干" or seal["location"] != "天干":
            continue
        lo, hi = sorted((ORDER.index(wealth["pillar"]), ORDER.index(seal["pillar"])))
        positions.append(
            {
                "wealth_star": ref(wealth),
                "seal_star": ref(seal),
                "intervening_positions": list(ORDER[lo + 1 : hi]),
                "stem_combination": frozenset((wealth["stem"], seal["stem"]))
                in COMBINATIONS,
                "effect_status": "position_observation_not_automatic_conflict_or_rescue",
            }
        )
    common_roots = []
    for output, wealth in product(stars(("食神", "伤官")), stars(WEALTH)):
        if output["location"] != "天干" or wealth["location"] != "天干":
            continue
        for root_name in ORDER:
            left = [r for r in output["roots"] if r["pillar"] == root_name]
            right = [r for r in wealth["roots"] if r["pillar"] == root_name]
            if left and right:
                common_roots.append(
                    {
                        "output_star": ref(output),
                        "wealth_star": ref(wealth),
                        "root_pillar": root_name,
                        "root_branch": pillars[root_name][1],
                        "output_hidden_stems": [r["stem"] for r in left],
                        "wealth_hidden_stems": [r["stem"] for r in right],
                        "is_month_command": root_name == "month",
                        "effect_status": "shared_branch_root_not_equal_force",
                    }
                )
    return {
        "method_id": "ziping_position_routes_v1",
        "life_stage_profile_id": STAGE_PROFILE_ID,
        "source": dict(SOURCE),
        "selected_month_role": selected,
        "routes": routes,
        "wealth_seal_positions": positions,
        "output_wealth_shared_roots": common_roots,
        "metal_water_hurt_officer_context": (
            STEM_ELEMENTS[pillars["day"][0]][0].value == "金" and anchor_god == "伤官"
        ),
        "scope": "月令取用、星位关系与根的存在；相神须全局论成败，不由生克合或同根直接认证。金水伤官见官另审调候，不能一见官就判破。",
    }
