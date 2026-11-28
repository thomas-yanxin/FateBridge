"""Two-person BaZi compatibility engine: cross-chart relations, 纳音, 鸳鸯合, 喜用互补, 神煞互照."""

from __future__ import annotations

from typing import Any, Mapping

from fatebridge.core.bazi.relations import (
    BRANCH_BREAKS,
    BRANCH_HIDDEN_COMBINATIONS,
    group_relations,
    pair_relations,
)
from fatebridge.core.bazi.shensha import (
    GU_CHEN_TARGETS,
    GUA_SU_TARGETS,
    HONG_LUAN_TARGETS,
    PEACH_BLOSSOM_TARGETS,
    TIAN_XI_TARGETS,
    TIAN_YI_TABLES,
)
from fatebridge.utils.data import (
    BRANCH_COMBINATIONS,
    BRANCH_CONFLICTS,
    BRANCH_HIDDEN_STEMS,
    DESTRUCTION_CYCLE,
    GENERATION_CYCLE,
    STEM_COMBINATIONS,
    STEM_ELEMENTS,
    Element,
    get_nayin,
    get_ten_god,
    kongwang_for_ganzhi,
)

Pillars = Mapping[str, tuple[str, str]]
ORDER = ("year", "month", "day", "hour")

_NAYIN_ELEMENT_CHAR = {
    "金": Element.METAL,
    "木": Element.WOOD,
    "水": Element.WATER,
    "火": Element.FIRE,
    "土": Element.EARTH,
}
_STEM_COMB_SET = {frozenset((a, b)) for a, b, _ in STEM_COMBINATIONS}


def cross_chart_relations(first: Pillars, second: Pillars) -> dict[str, Any]:
    """Cross-chart pairs (incl. 六破, 暗合, partial punishments), triples, half-triples, and arch pairs."""
    charts = {"person1": first, "person2": second}
    pillars = {
        f"{role}.{pos}": natal[pos] for role, natal in charts.items() for pos in ORDER
    }
    pair_facts = [
        row
        for left in ORDER
        for right in ORDER
        for row in pair_relations(f"person1.{left}", f"person2.{right}", pillars)
    ]
    for source, (stem, _) in pillars.items():
        source_element = STEM_ELEMENTS[stem][0]
        for target, (other_stem, _) in pillars.items():
            if source.split(".")[0] == target.split(".")[0]:
                continue
            if DESTRUCTION_CYCLE[source_element] == STEM_ELEMENTS[other_stem][0]:
                pair_facts.append(
                    {
                        "kind": "天干相克",
                        "level": "stem",
                        "positions": [source, target],
                        "characters": [stem, other_stem],
                        "distance": None,
                        "effect_status": "relation_only",
                    }
                )

    groups = group_relations(pillars)
    for relation in groups:
        roles = sorted({pos.split(".")[0] for pos in relation["positions"]})
        relation["source_scope"] = "cross_person" if len(roles) == 2 else roles[0]
        relation["natal_matches"] = [
            role
            for role, natal in charts.items()
            if set(relation["branches"]) <= {b for _, b in natal.values()}
        ]

    # Preserve directional_punishments summary for consumers
    directional_punishments = [
        {
            "source": row["positions"][0],
            "target": row["positions"][1],
            "branches": row["characters"],
        }
        for row in pair_facts
        if row["kind"] in {"三刑(半)", "子卯刑"}
    ]

    return {
        "pairs": pair_facts,
        "groups": groups,
        "directional_punishments": directional_punishments,
    }


def analyze_nayin_compatibility(first: Pillars, second: Pillars) -> dict[str, Any]:
    """Compare Year-pillar (年命) 纳音五行."""
    p1_ny = get_nayin(*first["year"])
    p2_ny = get_nayin(*second["year"])
    e1 = _NAYIN_ELEMENT_CHAR[p1_ny[-1]]
    e2 = _NAYIN_ELEMENT_CHAR[p2_ny[-1]]
    if e1 == e2:
        rel = "比和"
    elif GENERATION_CYCLE[e1] == e2:
        rel = "person1生person2"
    elif GENERATION_CYCLE[e2] == e1:
        rel = "person2生person1"
    elif DESTRUCTION_CYCLE[e1] == e2:
        rel = "person1克person2"
    else:
        rel = "person2克person1"
    return {
        "person1_year_nayin": p1_ny,
        "person1_nayin_element": e1.value,
        "person2_year_nayin": p2_ny,
        "person2_nayin_element": e2.value,
        "relation": rel,
    }


def analyze_day_pillar_synergy(first: Pillars, second: Pillars) -> dict[str, Any]:
    """Detect 日柱天合地合 (鸳鸯合) and 天克地冲."""
    s1, b1 = first["day"]
    s2, b2 = second["day"]
    stem_comb = frozenset((s1, s2)) in _STEM_COMB_SET
    branch_comb = BRANCH_COMBINATIONS.get(b1) == b2
    yuanyang = stem_comb and branch_comb
    branch_clash = BRANCH_CONFLICTS.get(b1) == b2
    return {
        "person1_day_pillar": s1 + b1,
        "person2_day_pillar": s2 + b2,
        "stem_combination": stem_comb,
        "branch_six_harmony": branch_comb,
        "yuanyang_he": yuanyang,
        "branch_six_clash": branch_clash,
        "branch_six_harm": False,
        "branch_six_break": BRANCH_BREAKS.get(b1) == b2,
        "branch_hidden_harmony": frozenset((b1, b2)) in BRANCH_HIDDEN_COMBINATIONS,
        "tian_ke_di_chong": bool(
            branch_clash
            and STEM_ELEMENTS[s1][1] == STEM_ELEMENTS[s2][1]
            and (
                DESTRUCTION_CYCLE[STEM_ELEMENTS[s1][0]] == STEM_ELEMENTS[s2][0]
                or DESTRUCTION_CYCLE[STEM_ELEMENTS[s2][0]] == STEM_ELEMENTS[s1][0]
            )
        ),
    }


def analyze_element_complementarity(
    p1_useful: list[str],
    p1_avoid: list[str],
    p1_dist: dict[str, float],
    p2_useful: list[str],
    p2_avoid: list[str],
    p2_dist: dict[str, float],
) -> dict[str, Any]:
    """Measure mutual 喜用神 complementarity based on dominant elements (>20%)."""
    p1_strong = [e for e, pct in p1_dist.items() if pct >= 20.0]
    p2_strong = [e for e, pct in p2_dist.items() if pct >= 20.0]
    p2_supplies_p1 = [e for e in p1_useful if e in p2_strong]
    p1_supplies_p2 = [e for e in p2_useful if e in p1_strong]
    p2_hits_p1_avoid = [e for e in p1_avoid if e in p2_strong]
    p1_hits_p2_avoid = [e for e in p2_avoid if e in p1_strong]
    return {
        "person1_useful_elements": p1_useful,
        "person2_useful_elements": p2_useful,
        "person2_supports_person1_useful": p2_supplies_p1,
        "person1_supports_person2_useful": p1_supplies_p2,
        "person2_overlaps_person1_avoid": p2_hits_p1_avoid,
        "person1_overlaps_person2_avoid": p1_hits_p2_avoid,
        "mutual_useful_overlap": [e for e in p1_useful if e in p2_useful],
    }


def analyze_cross_shensha(first: Pillars, second: Pillars) -> dict[str, Any]:
    """Check cross-chart 神煞互照 (天乙, 桃花, 红鸾, 天喜, 孤辰寡宿, 空亡填实)."""

    def _one_way(src: Pillars, dst: Pillars) -> list[dict[str, Any]]:
        hits: list[dict[str, Any]] = []
        dst_branches = {pos: dst[pos][1] for pos in ORDER}
        s_day_stem, s_day_branch = src["day"]
        s_year_branch = src["year"][1]

        ty_targets = set(TIAN_YI_TABLES["standard"][s_day_stem])
        ty_pos = [pos for pos, b in dst_branches.items() if b in ty_targets]
        if ty_pos:
            hits.append({"star": "天乙贵人", "positions": ty_pos})

        hl_target = HONG_LUAN_TARGETS[s_year_branch]
        tx_target = TIAN_XI_TARGETS[s_year_branch]
        for label, t in (("红鸾", hl_target), ("天喜", tx_target)):
            pos = [p for p, b in dst_branches.items() if b == t]
            if pos:
                hits.append({"star": label, "positions": pos})

        peach_target = next(
            t
            for g, t in PEACH_BLOSSOM_TARGETS
            if s_year_branch in g or s_day_branch in g
        )
        peach_pos = [p for p, b in dst_branches.items() if b == peach_target]
        if peach_pos:
            hits.append({"star": "桃花", "positions": peach_pos})

        for label, table in (("孤辰", GU_CHEN_TARGETS), ("寡宿", GUA_SU_TARGETS)):
            t = table[s_year_branch]
            pos = [p for p, b in dst_branches.items() if b == t]
            if pos:
                hits.append({"star": label, "positions": pos})

        day_kw = set(kongwang_for_ganzhi(f"{s_day_stem}{s_day_branch}"))
        kw_pos = [p for p, b in dst_branches.items() if b in day_kw]
        if kw_pos:
            hits.append({"star": "空亡填实", "positions": kw_pos})
        return hits

    return {
        "person1_activated_by_person2": _one_way(first, second),
        "person2_activated_by_person1": _one_way(second, first),
    }


def compute_directional_ten_gods(first: Pillars, second: Pillars) -> dict[str, Any]:
    charts = {"person1": first, "person2": second}
    directional: dict[str, Any] = {}
    for source_role, target_role in (("person1", "person2"), ("person2", "person1")):
        target_day_stem = charts[target_role]["day"][0]
        directional[f"{source_role}_to_{target_role}"] = {
            "source": source_role,
            "target": target_role,
            "target_day_stem": target_day_stem,
            "stars": [
                {
                    "pillar": pos,
                    "stem": evidenced_stem,
                    "location": location,
                    "ten_god": get_ten_god(target_day_stem, evidenced_stem).value,
                }
                for pos, (stem, branch) in charts[source_role].items()
                for evidenced_stem, location in (
                    (stem, "天干"),
                    *((h, "地支藏干") for h in BRANCH_HIDDEN_STEMS[branch]),
                )
            ],
        }
    return directional
