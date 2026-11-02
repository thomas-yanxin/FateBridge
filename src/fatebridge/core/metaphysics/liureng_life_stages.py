"""Ten-stem stages under 探原's explicit 阳顺阴逆 convention.

This author's 戊己 starts and yin direction differ from five-phase Liu Ren
tables. The identity of this rule is part of every result, never inferred
from the independently selected noble-start profile.
"""

from __future__ import annotations

from typing import Any

from fatebridge.core.metaphysics.ren_sources import TANYUAN_SCAN_SHA256, TANYUAN_SOURCE

from ...utils.data import EARTHLY_BRANCHES

STAGES = (
    "长生",
    "沐浴",
    "冠带",
    "临官",
    "帝旺",
    "衰",
    "病",
    "死",
    "墓",
    "绝",
    "胎",
    "养",
)
STARTS = dict(zip("甲乙丙丁戊己庚辛壬癸", "亥午寅酉寅酉巳子申卯"))


def life_stage_cycle(day_stem: str) -> dict[str, str]:
    if day_stem not in STARTS:
        raise ValueError("十二运需要有效日干")
    start = EARTHLY_BRANCHES.index(STARTS[day_stem])
    direction = 1 if day_stem in "甲丙戊庚壬" else -1
    return {
        branch: STAGES[((i - start) * direction) % 12]
        for i, branch in enumerate(EARTHLY_BRANCHES)
    }


def build_life_stages(day_stem: str, sky_by_earth: dict[str, str]) -> dict[str, Any]:
    cycle = life_stage_cycle(day_stem)
    branches = set(EARTHLY_BRANCHES)
    if set(sky_by_earth) != branches or set(sky_by_earth.values()) != branches:
        raise ValueError("十二运需要完整且不重复的天地盘")
    offsets = {
        (EARTHLY_BRANCHES.index(sky) - EARTHLY_BRANCHES.index(earth)) % 12
        for earth, sky in sky_by_earth.items()
    }
    if len(offsets) != 1:
        raise ValueError("天地盘须按同一支序顺布")
    by_stage = {stage: branch for branch, stage in cycle.items()}
    earth_by_sky = {sky: earth for earth, sky in sky_by_earth.items()}
    placements = []
    for name, sky, required_earth in (
        ("墓乘长生", by_stage["墓"], by_stage["长生"]),
        ("长生乘墓", by_stage["长生"], by_stage["墓"]),
    ):
        earth = earth_by_sky[sky]
        placements.append(
            {
                "name": name,
                "sky_branch": sky,
                "earth_branch": earth,
                "required_earth_branch": required_earth,
                "sky_stage": cycle[sky],
                "earth_stage": cycle[earth],
                "matched": earth == required_earth,
            }
        )
    return {
        "ruleset_id": "tanyuan_ten_stem_life_stages_v1",
        "source_title": "大六壬探原·卷下论断篇·论墓（长生沐浴等附）",
        "source_url": TANYUAN_SOURCE,
        "source_sha256": TANYUAN_SCAN_SHA256,
        "original_pdf_pages": [93, 94],
        "day_stem": day_stem,
        "direction": "顺" if day_stem in "甲丙戊庚壬" else "逆",
        "changsheng_branch": by_stage["长生"],
        "linguan_branch": by_stage["临官"],
        "tomb_branch": by_stage["墓"],
        "stage_by_branch": cycle,
        "placements": placements,
        "scope": "仅采用探原十干阳顺阴逆、戊己随丙丁的十二运定位；不与五行水土同宫口径混用，独立于所选贵人表。病死墓绝是传统阶段名，不是疾病、生死或现实结局判断；空亡不抹掉支位阶段，阶段亦不取消空亡，不换算旺衰总分或概率。",
    }
