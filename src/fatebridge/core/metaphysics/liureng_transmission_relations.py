"""探原's transmission relationships, separate from transmission selection."""

from __future__ import annotations

from typing import Any

from fatebridge.core.metaphysics.liureng_relation_tables import GOD_ELEMENTS
from fatebridge.core.metaphysics.ren_sources import TANYUAN_SCAN_SHA256, TANYUAN_SOURCE

from ...utils.data import EARTHLY_BRANCHES
from .common import (
    ELEMENT_CONTROLS,
    ELEMENT_GENERATES,
    SEXAGENARY_INDEX,
    branch_element_text,
    kongwang_for_ganzhi,
    liuqin_against_day,
    stem_element_text,
)
from .liureng_course_conditions import course_conditions
from .liureng_life_stages import life_stage_cycle
from .liureng_ordered_patterns import ordered_transmission_patterns

# Literal phase attributes in PDF86. Do not borrow Jin Kou's inherent stems:
# this witness has 玄武癸亥 and 天后壬子, with the same water phase.
TRINES = (("寅午戌", "火"), ("申子辰", "水"), ("巳酉丑", "金"), ("亥卯未", "木"))
RULE_NAMES = (
    ("birth_to_tomb", "初生末墓"),
    ("tomb_to_birth", "初墓末生"),
    ("final_controls_initial", "末克初"),
    ("control_chain", "干初中末递克"),
    ("all_branch_empty", "三传支神皆旬空"),
    ("initial_middle_empty", "初中空而末实"),
    ("middle_final_empty", "中末空而初实"),
    ("chao_zhi", "朝枝格条件"),
    ("chao_ri", "朝日格条件"),
)


def phase_relation(left: str, right: str) -> str:
    if left == right:
        return "比和"
    if ELEMENT_GENERATES[left] == right:
        return "生"
    if ELEMENT_GENERATES[right] == left:
        return "受生"
    return "克" if ELEMENT_CONTROLS[left] == right else "受克"


def transmission_relations(
    *,
    day_ganzhi: str,
    lessons: list[dict[str, Any]],
    transmissions: dict[str, Any],
    month_branch: str | None = None,
) -> dict[str, Any]:
    if day_ganzhi not in SEXAGENARY_INDEX:
        raise ValueError("三传关系需要有效日干支")
    day = stem_element_text(day_ganzhi[0])
    empty = kongwang_for_ganzhi(day_ganzhi)[:2]
    stages = life_stage_cycle(day_ganzhi[0])
    rows = []
    for position in ("initial", "middle", "final"):
        item = transmissions[position]
        branch, god, earth = item["branch"], item["god"], item["earth_branch"]
        if (
            branch not in EARTHLY_BRANCHES
            or earth not in EARTHLY_BRANCHES
            or god not in GOD_ELEMENTS
        ):
            raise ValueError("三传关系的支神、地盘或天将无效")
        element, god_element = branch_element_text(branch), GOD_ELEMENTS[god]
        relation = phase_relation(god_element, element)
        rows.append(
            dict(
                position=position,
                branch=branch,
                element=element,
                god=god,
                god_element=god_element,
                god_to_spirit=relation,
                war=(
                    "外战"
                    if relation == "克"
                    else "内战" if relation == "受克" else None
                ),
                earth_branch=earth,
                earth_element=branch_element_text(earth),
                spirit_to_seat=phase_relation(element, branch_element_text(earth)),
                day_relation=liuqin_against_day(day, element),
                day_stem_life_stage=stages[branch],
                xun_kong=branch in empty,
            )
        )
    a, b, c = rows
    upper = {int(l["index"]): l["upper_branch"] for l in lessons}
    if set(upper) != {1, 2, 3, 4} or len(lessons) != 4:
        raise ValueError("三传关系需要完整且不重复的四课")
    branches = [r["branch"] for r in rows]
    flags = {
        "birth_to_tomb": a["day_stem_life_stage"] == "长生"
        and c["day_stem_life_stage"] == "墓",
        "tomb_to_birth": a["day_stem_life_stage"] == "墓"
        and c["day_stem_life_stage"] == "长生",
        "final_controls_initial": ELEMENT_CONTROLS[c["element"]] == a["element"],
        "control_chain": ELEMENT_CONTROLS[day] == a["element"]
        and ELEMENT_CONTROLS[a["element"]] == b["element"]
        and ELEMENT_CONTROLS[b["element"]] == c["element"],
        "all_branch_empty": all(r["xun_kong"] for r in rows),
        "initial_middle_empty": a["xun_kong"] and b["xun_kong"] and not c["xun_kong"],
        "middle_final_empty": b["xun_kong"] and c["xun_kong"] and not a["xun_kong"],
        "chao_zhi": a["branch"] == upper[1] and c["branch"] == upper[3],
        "chao_ri": a["branch"] == upper[3] and c["branch"] == upper[1],
    }
    trines = []
    for members, element in TRINES:
        seen = [v for v in members if v in branches]
        complete = len(seen) == 3
        trines.append(
            dict(
                branches=list(members),
                present_branches=seen,
                missing_branches=[v for v in members if v not in branches],
                nominal_element=element,
                branches_complete=complete,
                nominal_day_relation=(
                    liuqin_against_day(day, element) if complete else None
                ),
                transformation_confirmed=None,
            )
        )
        if month_branch is not None:
            from .liureng_trine_seasonal import nominal_seasonal_evidence

            trines[-1]["nominal_seasonal_evidence"] = (
                nominal_seasonal_evidence(month_branch, element) if complete else None
            )
    return dict(
        ruleset_id="liuren_tanyuan_transmission_relations_v1",
        source_url=TANYUAN_SOURCE,
        source_sha256=TANYUAN_SCAN_SHA256,
        original_pdf_pages=[80, 81, 82, 86, 92],
        day_ganzhi=day_ganzhi,
        day_element=day,
        rows=rows,
        rules=[dict(id=i, name=n, matched=flags[i]) for i, n in RULE_NAMES],
        matched_rule_ids=[i for i, _ in RULE_NAMES if flags[i]],
        origin_destinations_coincide=upper[1] == upper[3],
        trines=trines,
        named_structures=ordered_transmission_patterns(branches),
        course_conditions=course_conditions(day_ganzhi, transmissions),
        all_transmissions_in_lesson_uppers=set(branches) <= set(upper.values()),
        all_transmissions_in_day_branch_uppers=set(branches) <= {upper[1], upper[3]},
        two_branch_empty=sum(r["xun_kong"] for r in rows) == 2,
        solid_transmission_has_sky_god=any(
            not r["xun_kong"] and r["god"] == "天空" for r in rows
        ),
        any_transmission_has_sky_god=any(r["god"] == "天空" for r in rows),
        equivalent_three_empty_adjudicated=None,
        comprehensive_judgement=None,
        complete_classical_conformance=False,
        scope="天将固有五行、三传支神本五行及地盘承座分层。内外战按神将两五行比较；断日六亲仍取支神，不以天将固有五行或三合名义局体替换。初末生墓采用已声明的探原十干十二运。朝枝朝日按干上、支上神比较，同位可同时满足，未设优先。三合支齐只列名义局体对日干关系，合化未定；如珠走盘、两空见天空的完整裁定及综合吉凶未完成，不据结构给现实结果或应期。",
    )
