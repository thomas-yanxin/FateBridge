"""Shared deterministic stage and seat tables, independent of chart assembly."""

import hashlib
import json
from typing import Any, Dict, Tuple

from fatebridge.utils.data import EARTHLY_BRANCHES

TWELVE_STAGES: Tuple[str, ...] = (
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

# 阳干顺行、阴干逆行. A stage hit alone does not adjudicate a hidden root.
_CHANGSHENG_START: Dict[str, Tuple[str, int]] = {
    "甲": ("亥", +1),
    "丙": ("寅", +1),
    "戊": ("寅", +1),
    "庚": ("巳", +1),
    "壬": ("申", +1),
    "乙": ("午", -1),
    "丁": ("酉", -1),
    "己": ("酉", -1),
    "辛": ("子", -1),
    "癸": ("卯", -1),
}

LU_SEATS = dict(zip("甲乙丙丁戊己庚辛壬癸", "寅卯巳午巳午申酉亥子"))
YANG_BLADE_SEATS = dict(zip("甲丙戊庚壬", "卯午午酉子"))
STAGE_PROFILE_ID = "ten_stem_yang_forward_yin_reverse_fire_earth_v1"


def life_stage_profile() -> Dict[str, Any]:
    """Expose the table actually used; do not adjudicate roots or force."""
    lookup = {
        "branch_cycle": list(EARTHLY_BRANCHES),
        "stage_cycle": list(TWELVE_STAGES),
        "growth_starts": {
            stem: {"growth_branch": branch, "direction": direction}
            for stem, (branch, direction) in _CHANGSHENG_START.items()
        },
    }
    digest = hashlib.sha256(
        json.dumps(
            lookup, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()
    return {
        "profile_id": STAGE_PROFILE_ID,
        **lookup,
        "lookup_sha256": digest,
        "soil_convention": "戊随丙寅生、己随丁酉生；未选择戊申己卯等其他口径。",
        "source_basis": "implementation_lookup_with_selected_text_crosscheck",
        "sources": [
            {
                "title": "三命通會·卷二·論天干陰陽生死",
                "author": "明·萬民英",
                "edition": "欽定四庫全書本，浙江大学图书馆／CADAL06066038",
                "url": "https://archive.org/details/06066038.cn",
                "source_pdf_sha256": "af4a8ca65cc4dfdf63d6294adc7925a868214563d0d52664c7ba779b833db14a",
                "anchor_pdf_pages": {
                    "甲": [10],
                    "乙": [12],
                    "丙": [14],
                    "丁": [16],
                    "戊": [17, 18],
                    "己": [19, 20],
                    "庚": [21],
                    "辛": [23],
                    "壬": [25],
                    "癸": [27],
                },
                "soil_discussion_pdf_pages": [29, 30],
                "source_role": "所选十干生支；章内土之体用及争论保留，不认证全书只有此口径。",
            },
            {
                "title": "秘本子平真诠·论阴阳生死",
                "author": "沈孝瞻",
                "edition": "国家图书馆藏本，上海世界图书馆发行",
                "url": "https://upload.wikimedia.org/wikipedia/commons/f/fe/NLC416-11jh010455-35296_%E5%AD%90%E5%B9%B3%E7%9C%9F%E8%A9%AE.pdf",
                "source_pdf_sha256": "71402a780b0351b54edf121a51bc4a4a4ce5896496c35b954563ee06f1a6f620",
                "pdf_pages": [15, 16, 17],
                "source_role": "阴阳顺逆与阶段含义；不把阶段名等同实体藏干或有效根力。",
            },
        ],
        "independent_expert_review": "not_completed",
        "calculation_effect": "none_existing_values_only",
        "scope": "明示既有查表参数及有限原页对照，不新算旺衰，不认证原典全文唯一解释。阶段、本气藏干、根类、司令、身印承载与有效通关分别核对。",
    }


def twelve_life_stage(day_stem: str, branch: str) -> str:
    """Look up the stage; make no whole-chart strength or root-loss decision."""
    start_branch, direction = _CHANGSHENG_START[day_stem]
    steps = (
        (EARTHLY_BRANCHES.index(branch) - EARTHLY_BRANCHES.index(start_branch))
        * direction
    ) % 12
    return TWELVE_STAGES[steps]
