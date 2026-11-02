"""Crossed branch-Liuhe structure, with the source's shared-anchor exclusion."""

from __future__ import annotations

from typing import Any

from fatebridge.core.metaphysics.liureng_cross_harmony_convention import CONVENTION
from fatebridge.core.metaphysics.ren_sources import TANYUAN_SCAN_SHA256, TANYUAN_SOURCE

from ...utils.data import EARTHLY_BRANCHES
from .common import SEXAGENARY_INDEX
from .liureng_branch_relations import branch_pair_facts
from .liureng_transmissions import STEM_HOUSES

SOURCE = "https://zh.wikisource.org/w/index.php?oldid=763692&title=六壬大全_(四庫全書本)/卷09"
SOURCE_SHA = "78431acbfbd9d2f27dd65d5ec9e04e3921d6ded8896836f9b0e2b2b72a728127"


def cross_harmony_metadata() -> dict[str, Any]:
    return dict(
        ruleset_id="daquan_siku_bifa21_cross_harmony_v1",
        name="交车合",
        source_title="六壬大全（四库全书本）卷九·毕法赋第二十一法",
        source_url=SOURCE,
        source_sha256=SOURCE_SHA,
        source_revision=763692,
        source_kind="frozen_primary_transcription_not_scan_collated",
        witness_source_title="大六壬探原·论合、占卜一班录第八例",
        witness_source_url=TANYUAN_SOURCE,
        witness_source_sha256=TANYUAN_SCAN_SHA256,
        witness_pdf_pages=[91, 92, 155],
        definition="日干与支上神作六合，地支与干上神作六合；干支同宫五日排除",
        excluded_days=["甲寅", "庚申", "丁未", "己未", "癸丑"],
        comprehensive_judgement=None,
        complete_classical_conformance=False,
        scope=(
            CONVENTION
            + " 本层只识别交叉支位结构，十种交车子格及空亡、旺衰、合化等综合取用未裁；"
            "不从相合条件推出交易、诉讼、婚姻或其他现实结果。"
        ),
    )


def cross_harmony(day_ganzhi: str, sky_by_earth: dict[str, str]) -> dict[str, Any]:
    if not isinstance(day_ganzhi, str) or day_ganzhi not in SEXAGENARY_INDEX:
        raise ValueError("交车合条件需要有效占日干支")
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
        raise ValueError("交车合条件需要完整顺布天地盘")
    house, branch = STEM_HOUSES[day_ganzhi[0]], day_ganzhi[1]
    stem_upper, branch_upper = sky_by_earth[house], sky_by_earth[branch]
    pairs = [
        dict(
            id=ident,
            left_role=left_role,
            right_role=right_role,
            left_branch=left,
            right_branch=right,
            liuhe=branch_pair_facts(left, right)["liuhe"],
        )
        for ident, left_role, right_role, left, right in (
            ("stem_upper_to_day_branch", "干上神", "日支", stem_upper, branch),
            ("branch_upper_to_stem_house", "支上神", "日干寄宫支", branch_upper, house),
        )
    ]
    both = all(row["liuhe"] for row in pairs)
    distinct = house != branch
    return dict(
        **cross_harmony_metadata(),
        day_ganzhi=day_ganzhi,
        day_stem_house=house,
        day_branch=branch,
        stem_upper=stem_upper,
        branch_upper=branch_upper,
        sky_by_earth=dict(sky_by_earth),
        cross_pairs=pairs,
        distinct_anchors=distinct,
        both_cross_pairs=both,
        matched=distinct and both,
        exclusion_reason=None if distinct else "干支同宫（八专五日）",
    )


def cross_harmony_trace(evidence: dict[str, Any]) -> dict[str, Any]:
    return dict(
        rule_id="liuren.cross_harmony",
        source_url=evidence["source_url"],
        source_section=evidence["source_title"],
        result=evidence,
    )
