"""A selected explicit tomb rule and an unadopted, disputed literal reading.

The opening sentence and the named Wang Zhang enumeration are kept separate.
The former is a textual candidate, not another certified school or an option
to choose after observing an outcome. Only the latter drives formal matches.
"""

from typing import Any

SOURCE = "https://zh.wikisource.org/w/index.php?oldid=625946"
PROFILE_ID = "yanyi_vol2_wangzhang_tombs_v1"
SELECTED_TOMBS = {"乙": "坤", "丙": "乾", "丁": "艮"}
LITERAL_PROSE_CANDIDATE = {"乙": "乾", "丙": "乾", "丁": "乾"}


def describe_wonder_tombs() -> dict[str, Any]:
    return {
        "id": PROFILE_ID,
        "title": "卷二王璋三奇入墓明确列举",
        "source": SOURCE,
        "section": "卷二·三奇入墓·王璋所列",
        "scan_pages": [33],
        "selected_stem_trigrams": dict(SELECTED_TOMBS),
        "selection_policy": "fixed_named_enumeration_not_selected_by_match_or_outcome",
        "unadopted_literal_candidate": {
            "id": "yanyi_vol2_opening_sentence_literal_candidate",
            "section": "卷二·三奇入墓·此乃乙丙丁奇临六宫在戌句",
            "stem_trigrams": dict(LITERAL_PROSE_CANDIDATE),
            "adopted": False,
            "status": "literal_reading_and_source_priority_unresolved",
        },
        "source_priority_resolved": False,
        "variant_note": "同段王璋明确列乙坤、丙乾、丁艮；段首句可字面读为三奇临乾六戌宫，其释读及优先关系待校勘。候选仅对照、未采纳，不因哪种更吉或更易匹配而换法。",
        "whole_book_conformance_established": False,
    }


def palace_wonder_tombs(trigram: str, heaven_stems: list[str]) -> dict[str, Any]:
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
        raise ValueError("三奇入墓须读取实际外八宫及有效天盘主干、寄干")
    observed = [s for s in heaven_stems if s in SELECTED_TOMBS]
    selected = [s for s in observed if SELECTED_TOMBS[s] == trigram]
    candidate = [s for s in observed if LITERAL_PROSE_CANDIDATE[s] == trigram]
    return {
        "profile_id": PROFILE_ID,
        "trigram": trigram,
        "observed_wonder_stems": observed,
        "selected_matched_stems": selected,
        "unadopted_literal_candidate_matched_stems": candidate,
        "candidate_adopted": False,
        "disputed_stems_at_this_palace": [
            s for s in observed if (s in selected) != (s in candidate)
        ],
        "source_priority_resolved": False,
        "source": SOURCE,
        "source_scan_pages": [33],
        "scope": "heaven_wonder_stem_in_palace_including_hosted_stems_not_literal_hour_tomb",
        "interpretation_limit": "正式匹配仅据王璋所列；另句字面候选未采纳。本宫两法恰同不证明全书已统一，未按候选正式输出也不证明该候选结构不存在。",
        "outcome_inference_allowed": False,
    }
