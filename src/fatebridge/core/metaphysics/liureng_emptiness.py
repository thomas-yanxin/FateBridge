"""探原's earth/sky empty conditions, without an effective-empty verdict.

The 壬申 example expressly preserves sky 亥's emptiness while exempting
the day stem's earth seat. Neither a role exception nor a seat exception
rewrites the two unassigned branches of the divination day's xun.
"""

from __future__ import annotations

from typing import Any

from fatebridge.core.metaphysics.ren_sources import TANYUAN_SCAN_SHA256, TANYUAN_SOURCE

from ...utils.data import EARTHLY_BRANCHES
from .common import SEXAGENARY_INDEX, kongwang_for_ganzhi, xun_head_for_ganzhi
from .liureng_transmissions import STEM_HOUSES


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
    return dict(
        ruleset_id="liuren_tanyuan_empty_scope_v1",
        source_url=TANYUAN_SOURCE,
        source_sha256=TANYUAN_SCAN_SHA256,
        source_title="大六壬探原·卷下论空亡（所选条件）",
        original_pdf_pages=[84, 85],
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
            dict(role=name, branch=branch, branch_xun_kong=branch in empty)
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
                effective_empty=None,
            )
            for earth in EARTHLY_BRANCHES
        ],
        nianming_status="not_adjudicated_in_this_excerpt",
        seasonal_true_half_empty_status="not_adjudicated",
        filling_clashing_status="not_adjudicated",
        comprehensive_judgement=None,
        complete_classical_conformance=False,
        scope="天盘本支旬空与地盘落底空分别保留。日干所寄地盘虽本空，本节不作空论；该局部例外不取消同名天盘支的本空。太岁、月建、月将列角色及本空条件，原文另有年命例外，本层未裁定其全部含义，不以分析年或行年代替。年月角色沿用本次四柱，月将沿用本次所选将；同支角色可并存。占时值空只列时支事实，不给现实成败断言。所列例外不改旬空两支、旬遁、原三传本空或坐空标志；真空半空、填实冲实、例外优先级及综合有效空亡仍未裁定。",
    )
