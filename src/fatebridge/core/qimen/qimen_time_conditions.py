"""The six literal hour stem/branch tomb pairs printed in Yanyi volume two.

This is a clock condition, distinct from a moving heaven stem in a tomb
palace. Jia's hidden instrument is never substituted for the literal hour.
"""

from typing import Any

from fatebridge.core.metaphysics.common import SEXAGENARY_INDEX

# Prose explicitly adds Ji-Chou after the five pairs named by the verse.
HOUR_BRANCH_TOMBS = {
    "丙戌": {"element": "火", "polarity": "阳", "verse_listed": True},
    "壬辰": {"element": "水", "polarity": "阳", "verse_listed": True},
    "丁丑": {"element": "火", "polarity": "阴", "verse_listed": True},
    "癸未": {"element": "水", "polarity": "阴", "verse_listed": True},
    "戊戌": {"element": "土", "polarity": "阳", "verse_listed": True},
    "己丑": {"element": "土", "polarity": "阴", "verse_listed": False},
}


def build_hour_branch_tomb(hour_ganzhi: str, *, source: str) -> dict[str, Any]:
    if hour_ganzhi not in SEXAGENARY_INDEX:
        raise ValueError("时干支入墓检查需要有效的六十甲子时柱")
    definition = HOUR_BRANCH_TOMBS.get(hour_ganzhi)
    return {
        "rule_id": "hour_branch_tomb",
        "scope": "yanyi_vol2_six_literal_hour_stem_branch_pairs",
        "hour_ganzhi": hour_ganzhi,
        "literal_stem": hour_ganzhi[0],
        "literal_branch": hour_ganzhi[1],
        "matched": definition is not None,
        "matched_definition": dict(definition) if definition is not None else None,
        "listed_pair_count": 6,
        "verse_list_count": 5,
        "verse_omission_is_not_prose_disagreement": True,
        "jia_hidden_instrument_substituted": False,
        "heaven_stem_palace_tomb_evaluated": False,
        "source": source,
        "source_section": "卷二·三奇入墓·时干支入墓六时",
        "source_scan_pages": [33],
        "evidence_paths": ["qimen.time_ganzhi", "four_pillars.hour"],
        "traditional_meaning": "原文列为传统时间禁忌，可作收束、受制的象义；不据此断现实失败、损失、人身或医疗后果。",
        "interpretation_limit": "只核所选正文六组字面时干支；未命中本表不等于所有入墓法均不存在，也不判断天盘时干落墓宫。",
        "outcome_inference_allowed": False,
    }
