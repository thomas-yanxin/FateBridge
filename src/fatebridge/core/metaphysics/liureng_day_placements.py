"""Literal day-stem/day-branch placements; houses locate, stems keep phase."""

from __future__ import annotations

from typing import Any

from fatebridge.core.metaphysics.liureng_day_placements_convention import CONVENTION
from fatebridge.core.metaphysics.ren_sources import TANYUAN_SCAN_SHA256, TANYUAN_SOURCE

from ...utils.data import EARTHLY_BRANCHES
from .common import (
    ELEMENT_CONTROLS,
    ELEMENT_GENERATES,
    SEXAGENARY_INDEX,
    branch_element_text,
    stem_element_text,
)
from .liureng_transmissions import STEM_HOUSES

RULES = (
    ("D01", "俯就", "干加枝受生", "stem_over_branch", "branch_generates_stem"),
    ("D02", "归福", "枝加干生干", "branch_over_stem", "branch_generates_stem"),
    ("D03", "脱我", "枝加干受生", "branch_over_stem", "stem_generates_branch"),
    ("D04", "历虚", "干加枝生枝", "stem_over_branch", "stem_generates_branch"),
    ("D05", "欺我", "枝加干尅干", "branch_over_stem", "branch_controls_stem"),
    ("D06", "取辱", "干加枝受尅", "stem_over_branch", "branch_controls_stem"),
    ("D07", "招夫", "枝加干受尅", "branch_over_stem", "stem_controls_branch"),
    ("D08", "赘婿", "干加枝尅枝", "stem_over_branch", "stem_controls_branch"),
    ("D09", "壮基", "枝加干比干", "branch_over_stem", "same_element"),
    ("D10", "培本", "干加枝比枝", "stem_over_branch", "same_element"),
    ("D11", "归合", "枝加干合干", "branch_over_stem", "harmony_unadjudicated"),
    ("D12", "求合", "干加枝合枝", "stem_over_branch", "harmony_unadjudicated"),
)


def placement_metadata() -> dict[str, Any]:
    return dict(
        ruleset_id="tanyuan_day_placements_v1",
        source_title="大六壬探原·论日干日枝、课体纲要",
        source_url=TANYUAN_SOURCE,
        source_sha256=TANYUAN_SCAN_SHA256,
        original_pdf_pages=[77, 78, 110],
        evaluations=[
            dict(
                id=i,
                name=n,
                condition=c,
                placement=p,
                relation=r,
                definition_adjudicated=r != "harmony_unadjudicated",
                **(
                    {"relation_matches": None, "matched": None}
                    if r == "harmony_unadjudicated"
                    else {}
                ),
            )
            for i, n, c, p, r in RULES
        ],
        evaluated_count=10,
        unresolved_count=2,
        unresolved_ids=["D11", "D12"],
        comprehensive_judgement=None,
        complete_classical_conformance=False,
        scope=(
            CONVENTION
            + "。干为我、支为彼是本书关系释读，不据名称判断他人意图、婚姻角色、现实成败或事件应期。"
            "原目录第五题曾保留损／欺异读，本层选书影欺我，不回写旧校勘。合干、合支的投影定义仍未裁，未知不作未命中。"
        ),
    )


def day_placement_patterns(
    day_ganzhi: str, sky_by_earth: dict[str, str]
) -> dict[str, Any]:
    if not isinstance(day_ganzhi, str) or day_ganzhi not in SEXAGENARY_INDEX:
        raise ValueError("干支加临条件需要有效占日干支")
    branches = set(EARTHLY_BRANCHES)
    if (
        not isinstance(sky_by_earth, dict)
        or set(sky_by_earth) != branches
        or any(
            not isinstance(v, str) or v not in branches for v in sky_by_earth.values()
        )
        or set(sky_by_earth.values()) != branches
        or len(
            {
                (EARTHLY_BRANCHES.index(s) - EARTHLY_BRANCHES.index(e)) % 12
                for e, s in sky_by_earth.items()
            }
        )
        != 1
    ):
        raise ValueError("干支加临条件需要完整顺布天地盘")
    stem, branch = day_ganzhi[0], day_ganzhi[1]
    house = STEM_HOUSES[stem]
    stem_phase, branch_phase = stem_element_text(stem), branch_element_text(branch)
    placements = dict(
        stem_over_branch=sky_by_earth[branch] == house,
        branch_over_stem=sky_by_earth[house] == branch,
    )
    relations = dict(
        branch_generates_stem=ELEMENT_GENERATES[branch_phase] == stem_phase,
        stem_generates_branch=ELEMENT_GENERATES[stem_phase] == branch_phase,
        branch_controls_stem=ELEMENT_CONTROLS[branch_phase] == stem_phase,
        stem_controls_branch=ELEMENT_CONTROLS[stem_phase] == branch_phase,
        same_element=stem_phase == branch_phase,
    )
    result = placement_metadata()
    for row in result["evaluations"]:
        row["placement_matches"] = placements[row["placement"]]
        if row["definition_adjudicated"]:
            row["relation_matches"] = relations[row["relation"]]
            row["matched"] = row["placement_matches"] and row["relation_matches"]
    result.update(
        day_ganzhi=day_ganzhi,
        day_stem_house=house,
        day_stem_element=stem_phase,
        day_branch_element=branch_phase,
        sky_by_earth=dict(sky_by_earth),
        placements=placements,
        element_relations=relations,
        matched_ids=[r["id"] for r in result["evaluations"] if r["matched"] is True],
    )
    return result


def day_placements_trace(evidence: dict[str, Any]) -> dict[str, Any]:
    return dict(
        rule_id="liuren.day_placement_patterns",
        source_url=evidence["source_url"],
        source_section=evidence["source_title"],
        result=evidence,
    )
