"""Explicit six-instrument identities with an unadjudicated source scope.

The legacy broad reading is retained provisionally. A narrower current-zhifu
reading is also calculated; the printed mao example distinguishes them.
Neither silently shrinking the rule nor claiming the broader reading is
certified resolves the wording's scope.
"""

from typing import Any

from fatebridge.core.metaphysics.common import SEXAGENARY_INDEX, xun_head_for_ganzhi

SOURCE = "https://zh.wikisource.org/w/index.php?oldid=625940"
PROFILE_ID = "yanyi_vol2_six_instrument_scope_v1"
# head: (concealed instrument, punished branch, Wang Zhang's named palace)
PUNISHMENT_BY_HEAD = {
    "甲子": ("戊", "卯", "震"),
    "甲戌": ("己", "未", "坤"),
    "甲申": ("庚", "寅", "艮"),
    "甲午": ("辛", "午", "离"),
    "甲辰": ("壬", "辰", "巽"),
    "甲寅": ("癸", "巳", "巽"),
}


def describe_punishment() -> dict[str, Any]:
    return {
        "id": PROFILE_ID,
        "title": "六仪落所刑宫广义暂定；并列本时直符候选",
        "source": SOURCE,
        "section": "卷二·六仪击刑·葛洪定义及王璋列宫",
        "scan_pages": [33, 34],
        "scope": "all_six_instruments_geometry_provisional",
        "definitions": [
            {
                "xun_head": head,
                "hidden_stem": stem,
                "punished_branch": branch,
                "trigram": gua,
            }
            for head, (stem, branch, gua) in PUNISHMENT_BY_HEAD.items()
        ],
        "other_instrument_geometry": "legacy_broad_matches_retained_provisionally",
        "selection_policy": "retain_legacy_broad_rule_pending_scope_adjudication_not_selected_by_outcome",
        "unresolved_example": {
            "id": "vol2-yang1-mao-punishment-scope",
            "source_branch": "卯",
            "source_claim": "六仪击刑",
            "status": "printed_example_distinguishes_unadjudicated_scope_readings",
            "broader_instrument_reading_adopted": True,
            "adoption_status": "provisional_not_source_certified",
            "narrow_current_zhifu_reading_adopted": False,
        },
        "source_scope_adjudicated": False,
        "whole_section_reconciled": False,
        "whole_book_conformance_established": False,
    }


def palace_punishment(
    hour_ganzhi: str, trigram: str, heaven_stems: list[str]
) -> dict[str, Any]:
    if type(hour_ganzhi) is not str or hour_ganzhi not in SEXAGENARY_INDEX:
        raise ValueError("六仪击刑须使用完整有效时柱，不以日旬或小时地支代替")
    if (
        not isinstance(trigram, str)
        or trigram not in set("坎坤震巽乾兑艮离")
        or not isinstance(heaven_stems, list)
        or not heaven_stems
        or any(
            type(s) is not str or s not in set("戊己庚辛壬癸丁丙乙")
            for s in heaven_stems
        )
    ):
        raise ValueError("六仪击刑须读取实际外八宫及有效天盘主干、寄干")
    # This helper validates the entire sexagenary token, not just its prefix.
    head = xun_head_for_ganzhi(hour_ganzhi)
    stem, branch, target = PUNISHMENT_BY_HEAD[head]
    observed = [
        {"xun_head": h, "hidden_stem": s, "punished_branch": b, "trigram": t}
        for h, (s, b, t) in PUNISHMENT_BY_HEAD.items()
        if s in heaven_stems and t == trigram
    ]
    return {
        "profile_id": PROFILE_ID,
        "hour_ganzhi": hour_ganzhi,
        "xun_head": head,
        "hidden_stem": stem,
        "punished_branch": branch,
        "required_trigram": target,
        "observed_trigram": trigram,
        "observed_heaven_stems": list(heaven_stems),
        "matched": bool(observed),
        "current_zhifu_matched": stem in heaven_stems and target == trigram,
        "current_zhifu_reading_adopted": False,
        "source_scope_adjudicated": False,
        "geometric_matches": observed,
        "non_current_geometric_stems": [
            r["hidden_stem"] for r in observed if r["xun_head"] != head
        ],
        "other_instrument_geometry_is_formal_match": True,
        "scope": "all_six_instruments_geometry_provisional",
        "source": SOURCE,
        "source_scan_pages": [33, 34],
        "whole_section_reconciled": False,
        "interpretation_limit": "暂定保留广义六仪落刑宫匹配，并列本时直符窄读。正文未明写仅本旬，卯时印例区分两种读法；范围未定，不认证任一读法为全书原法，不据击刑断现实灾祸。",
        "outcome_inference_allowed": False,
    }
