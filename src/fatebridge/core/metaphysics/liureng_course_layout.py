"""Necessary stage/god compatibility across explicit supported noble layouts.

The alternatives do not assert the current diurnal state or select transmissions.
A compatible pair may still never be selected by a given four-lesson board.
"""

from __future__ import annotations

import copy
from typing import Any

from ...utils.data import EARTHLY_BRANCHES
from .common import GUI_REN_SEQUENCE
from .liureng_life_stages import life_stage_cycle
from .ren_gods import GuirenProfile, noble_start

PROFILES: tuple[GuirenProfile, ...] = ("liuren_common_v1", "tanyuan_xieji_v1")
BASIS = {
    "ruleset_id": "tanyuan_supported_noble_layout_necessity_v1",
    "stage_subject": "day_stem",
    "noble_profiles": ["liuren_common_v1", "tanyuan_xieji_v1"],
    "diurnal_alternatives": [False, True],
    "direction_alternatives": ["顺", "逆"],
    "conditions_are_alternatives": True,
    "is_initial_transmission_guarantee": False,
    "unresolved_authorial_intent_ids": ["S05"],
    "authorial_intent_adjudicated": None,
    "original_conditions_rewritten": False,
    "source_reference_sha256": "08bb40a3de13ad607f3ceb059fa00bac322ecd15b77a83ef359e25845f52d245",
    "witnesses": [
        {
            "id": "zhuji_zhuji-1",
            "source_title": "毛志道《六壬经纬》",
            "edition": "清金阊书业堂刻本，诸暨图书馆藏",
            "source_url": "https://upload.wikimedia.org/wikipedia/commons/d/d1/ZJSLib-FLDB-2457-1_%E5%85%AD%E5%A3%AC%E7%B6%93%E7%B7%AF%E5%85%AD%E5%8D%B7_%E7%AC%AC%E4%B8%80%E5%86%8A.pdf",
            "source_sha256": "99f4362c0bee35adc3be6eb3a872aa24e418660ba9b7db57bcdca186463dab80",
            "original_pdf_pages": [31, 32, 33],
        },
        {
            "id": "zhuji_zhuji-2",
            "source_title": "毛志道《六壬经纬》",
            "edition": "清金阊书业堂刻本，诸暨图书馆藏",
            "source_url": "https://upload.wikimedia.org/wikipedia/commons/2/20/ZJSLib-FLDB-2457-2_%E5%85%AD%E5%A3%AC%E7%B6%93%E7%B7%AF%E5%85%AD%E5%8D%B7_%E7%AC%AC%E4%BA%8C%E5%86%8A.pdf",
            "source_sha256": "cc14c2876507f1a59e2fecfe6f5c7cd930d99b01f2ae13a9815f3cd3b709082d",
            "original_pdf_pages": [37, 38, 39, 40, 41, 79, 80, 81],
        },
        {
            "id": "gugong_gugong-419",
            "source_title": "毛志道《六壬经纬》",
            "edition": "故宫珍本丛刊419所收六壬经纬，目录标雍正刊本",
            "source_url": "https://upload.wikimedia.org/wikipedia/commons/9/94/GGZBCK419_%E5%BE%A1%E5%AE%9A%E5%8D%9C%E7%AD%AE%E7%B2%BE%E8%98%8A_%E5%85%AD%E5%A3%AC%E7%B6%93%E7%B7%AF_%E5%85%AD%E5%A3%AC%E7%B2%B9%E8%A8%80_%E5%85%AD%E5%A3%AC%E9%A1%9E%E8%81%9A.pdf",
            "source_sha256": "5bc1538f57153f26f1498061820d26ca016b5075cdaeabaadfe0f0ef3b077378",
            "original_pdf_pages": [10, 11, 53, 54, 55, 65, 66],
        },
    ],
    "scope": "只枚举两张声明贵人表、昼夜及顺逆的配将必要配置；候选支位集合不保证九宗取传选中，不是当前昼夜的另一次判定，也不作占事吉凶。崇位字面条件保留，原意未裁。",
}


def layout_compatibility_basis() -> dict[str, Any]:
    return copy.deepcopy(BASIS)


def pair_layout_necessity(day_stem: str, stage: str, god: str) -> dict[str, Any]:
    cycle = life_stage_cycle(day_stem)
    if stage not in cycle.values() or god not in GUI_REN_SEQUENCE:
        raise ValueError("配将必要条件需要有效十二运与天将")
    required_branch = next(b for b, s in cycle.items() if s == stage)
    rank = GUI_REN_SEQUENCE.index(god)
    candidates = set()
    for profile in PROFILES:
        for daylight in (False, True):
            start = EARTHLY_BRANCHES.index(noble_start(day_stem, daylight, profile))
            for direction in (1, -1):
                candidates.add(EARTHLY_BRANCHES[(start + direction * rank) % 12])
    return dict(
        required_stage_branch=required_branch,
        possible_god_branches=[b for b in EARTHLY_BRANCHES if b in candidates],
        compatible_in_any_supported_noble_layout=required_branch in candidates,
    )
