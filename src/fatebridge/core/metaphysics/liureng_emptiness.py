"""探原's earth/sky empty conditions, without an effective-empty verdict.

The 壬申 example expressly preserves sky 亥's emptiness while exempting
the day stem's earth seat. Neither a role exception nor a seat exception
rewrites the two unassigned branches of the divination day's xun.
"""

from __future__ import annotations

from typing import Any

from fatebridge.core.metaphysics.common import (
    SEXAGENARY_INDEX,
    kongwang_for_ganzhi,
    xun_head_for_ganzhi,
)
from fatebridge.core.metaphysics.liureng_transmissions import STEM_HOUSES
from fatebridge.utils.data import EARTHLY_BRANCHES


def emptiness_evidence(
    *,
    day_ganzhi: str,
    year_branch: str,
    month_branch: str,
    month_general_branch: str,
    hour_branch: str,
    sky_by_earth: dict[str, str],
) -> dict[str, Any]:
    if day_ganzhi not in SEXAGENARY_INDEX:
        raise ValueError("六壬空亡依据需要有效日干支")
    branches = set(EARTHLY_BRANCHES)
    if (
        any(
            v not in branches
            for v in (year_branch, month_branch, month_general_branch, hour_branch)
        )
        or set(sky_by_earth) != branches
        or set(sky_by_earth.values()) != branches
    ):
        raise ValueError("六壬空亡依据需要有效年月时支、月将和完整天地盘")
    offsets = {
        (EARTHLY_BRANCHES.index(sky) - EARTHLY_BRANCHES.index(earth)) % 12
        for earth, sky in sky_by_earth.items()
    }
    expected_offset = (
        EARTHLY_BRANCHES.index(month_general_branch)
        - EARTHLY_BRANCHES.index(hour_branch)
    ) % 12
    if offsets != {expected_offset}:
        raise ValueError("六壬空亡依据的天地盘与月将加时不一致")
    empty = kongwang_for_ganzhi(day_ganzhi)[:2]
    house = STEM_HOUSES[day_ganzhi[0]]
    roles = (
        ("太岁", year_branch),
        ("月建", month_branch),
        ("月将", month_general_branch),
    )
    evidence = dict(
        ruleset_id="liuren_tanyuan_empty_scope_v3",
        source_title="大六壬探原·卷下论空亡（所选条件）",
        original_pdf_pages=[84, 85],
        year_fate_placement_pdf_pages=[70, 71, 72, 73],
        day_ganzhi=day_ganzhi,
        xun_head=xun_head_for_ganzhi(day_ganzhi),
        empty_branches=list(empty),
        day_stem_house=house,
        year_branch=year_branch,
        month_building_branch=month_branch,
        month_general_branch=month_general_branch,
        hour_branch=hour_branch,
        hour_branch_xun_kong=hour_branch in empty,
        role_conditions=[
            dict(
                role=name,
                branch=branch,
                branch_xun_kong=branch in empty,
                xunkong_exception_applies=branch in empty,
            )
            for name, branch in roles
        ],
        rows=[
            dict(
                earth_branch=earth,
                sky_branch=sky_by_earth[earth],
                sky_xun_kong=sky_by_earth[earth] in empty,
                earth_xun_kong=earth in empty,
                earth_is_day_stem_house=earth == house,
                earth_stem_house_exception=earth in empty and earth == house,
                sky_authority_roles=[
                    name for name, branch in roles if branch == sky_by_earth[earth]
                ],
                sky_authority_xunkong_exception=sky_by_earth[earth] in empty
                and any(branch == sky_by_earth[earth] for _, branch in roles),
                effective_empty=None,
            )
            for earth in EARTHLY_BRANCHES
        ],
        seasonal_true_half_empty_status="not_adjudicated",
        filling_clashing_status="role_exceptions_only",
        comprehensive_judgement=None,
        complete_classical_conformance=False,
        scope="天盘本空与地盘落底空分列。日干寄地盘本空，依本节例外不作空论；天盘本空支为太岁、月建或月将，命中该角色填实。探原卷上规定行年、本命干支均书地盘；卷下年命值空不以空论，依此合读在其书地盘位判该例外，不把上神当年命地盘位。未知年命只影响地盘本空且未被其他已知例外覆盖的位置。各例外不改本空、旬遁、三传本空或坐空；真空半空、其他填实冲实及综合有效空亡仍未裁定。",
    )
    apply_year_fate_emptiness(evidence, natal=None, annual=None)
    return evidence


def apply_year_fate_emptiness(
    evidence: dict[str, Any], *, natal: str | None, annual: str | None
) -> None:
    """Apply the 卷下 exception at the 卷上 earth positions on the same board."""
    placements = {"natal": natal, "annual": annual}
    complete = natal is not None and annual is not None
    evidence["year_fate_earth_branches"] = placements
    evidence["nianming_status"] = (
        "calculated"
        if complete
        else (
            "partial"
            if natal is not None or annual is not None
            else "inputs_not_available"
        )
    )
    for row in evidence["rows"]:
        roles = [
            role for role, branch in placements.items() if branch == row["earth_branch"]
        ]
        exempt = row["earth_xun_kong"] and bool(roles)
        row.update(
            earth_year_fate_roles=roles,
            earth_year_fate_xunkong_exception=(
                exempt if exempt or not row["earth_xun_kong"] or complete else None
            ),
            earth_xunkong_after_seat_and_year_fate=(
                False
                if not row["earth_xun_kong"]
                or row["earth_stem_house_exception"]
                or exempt
                else True if complete else None
            ),
        )
