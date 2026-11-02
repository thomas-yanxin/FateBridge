"""Exact general/eye co-location, supported by explicit classical annotations.

Wenchang/general 關 and Shiji/general 掩 have different subjects. Do not map
intercalary spirits into gate sectors, or turn these pairs into 四郭固/杜.
"""

from __future__ import annotations

from typing import Any

PROFILE = "wenchang_general_guan_shiji_general_yan_exact_palace_v1"
SOURCE = "https://zh.wikisource.org/wiki/太乙金鏡式經_(四庫全書本)/卷03"
ANNOTATIONS = (
    "https://zh.wikisource.org/wiki/欽定古今圖書集成/博物彙編/藝術典/第693卷",
    "https://zh.wikisource.org/wiki/欽定古今圖書集成/博物彙編/藝術典/第694卷",
)
SCOPE = (
    "将目同宫补证读法：文昌与四将为关，始击与四将为掩；只核精确同宫，"
    "间神不并入正宫。明钞关条未明列将目，版本范围不同；"
    "同阵两将互关、二目互关及四郭固杜组合未在此扩展中裁定，不由单条推出成败。"
)
GENERAL_FIELDS = {
    "main_general": "主大将",
    "main_vice_general": "主参将",
    "guest_general": "客大将",
    "guest_vice_general": "客参将",
}


def eye_general_relations(core: dict[str, Any]) -> list[dict[str, Any]]:
    """Read this same core; no ju exceptions, calendar work or recasting."""
    from fatebridge.core.metaphysics.taiyi_geometry import PALACES

    patterns = []
    for field, label in GENERAL_FIELDS.items():
        number = core[field]
        palace = PALACES[number]
        general = {"field": "core_board." + field, "value": number}
        if palace == core["wenchang_palace"]:
            patterns.append(
                {
                    "name": "关",
                    "subject": label,
                    "variant": f"{label}与文昌同宫",
                    "basis": [
                        general,
                        {"field": "wenchang_palace", "value": palace},
                    ],
                    "traditional_meaning": f"{label}{palace}与文昌{palace}同宫，命中将目关的空间条件",
                    "source": SOURCE + "#推闗法",
                    "supplementary_sources": list(ANNOTATIONS),
                    "relation_profile": PROFILE,
                    "scope": SCOPE,
                }
            )
        if palace == core["shiji"]:
            patterns.append(
                {
                    "name": "掩",
                    "subject": "始击",
                    "variant": f"始击掩{label}",
                    "basis": [
                        {"field": "core_board.shiji", "value": palace},
                        general,
                    ],
                    "traditional_meaning": f"始击{palace}与{label}{palace}同宫，命中始击掩将的空间条件",
                    "source": SOURCE + "#推掩法",
                    "supplementary_sources": list(ANNOTATIONS),
                    "relation_profile": PROFILE,
                    "scope": SCOPE,
                }
            )
    return patterns
