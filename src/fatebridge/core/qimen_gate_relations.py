"""Keep the verse's 门迫 predicate separate from four prose relation names."""

from typing import Any

from fatebridge.core.metaphysics.common import ELEMENT_CONTROLS, ELEMENT_GENERATES

SOURCE = "https://zh.wikisource.org/w/index.php?oldid=625940"
PROFILE_ID = "yanyi_vol2_gate_palace_relations_v1"
PALACE_ELEMENTS = {
    "坎": "水",
    "坤": "土",
    "震": "木",
    "巽": "木",
    "中": "土",
    "乾": "金",
    "兑": "金",
    "艮": "土",
    "离": "火",
}
DOOR_ELEMENTS = {
    "休门": "水",
    "生门": "土",
    "伤门": "木",
    "杜门": "木",
    "景门": "火",
    "死门": "土",
    "惊门": "金",
    "开门": "金",
}
PROSE_LABELS = {
    "door_controls_palace": "吉迫",
    "palace_controls_door": "凶迫",
    "door_generates_palace": "和",
    "palace_generates_door": "义",
    "same_element": None,
}
RELATION_TEXT = {
    "door_controls_palace": "门克宫",
    "palace_controls_door": "宫克门",
    "door_generates_palace": "门生宫",
    "palace_generates_door": "宫生门",
    "same_element": "门宫同五行",
}
# Only these exact door/palace observations are classified by this paragraph.
# In particular 景门 at 兑 is listed with 吉门 here, not certified globally.
PRINTED_EXAMPLES = {
    ("开门", "震"): "吉门被迫",
    ("休门", "离"): "吉门被迫",
    ("生门", "坎"): "吉门被迫",
    ("景门", "兑"): "吉门被迫",
    ("伤门", "坤"): "凶门被迫",
    ("伤门", "艮"): "凶门被迫",
    ("杜门", "坤"): "凶门被迫",
    ("杜门", "艮"): "凶门被迫",
    ("死门", "坎"): "凶门被迫",
    ("惊门", "震"): "凶门被迫",
    ("惊门", "巽"): "凶门被迫",
}


def describe_gate_relations() -> dict[str, Any]:
    return {
        "id": PROFILE_ID,
        "title": "卷二门宫生克；歌诀门迫与正文关系名分别保留",
        "source": SOURCE,
        "section": "卷二·门迫宫迫",
        "scan_pages": [34],
        "verse_door_pressure_relation": "door_controls_palace",
        "verse_palace_controls_door_is_door_pressure": False,
        "prose_labels_by_relation": dict(PROSE_LABELS),
        "same_element_named_in_selected_paragraph": False,
        "selection_policy": "fixed_parallel_source_naming_not_selected_by_outcome",
        "interpretation_limit": "吉迫、凶迫、和、义是本段关系名，不是现实吉凶或伦理评价；歌诀门迫为否不等于正文没有凶迫。景门只在所列兑宫例被归入吉门被迫，不推广成景门恒吉。",
        "whole_book_conformance_established": False,
    }


def gate_palace_relation(door: str, trigram: str) -> dict[str, Any]:
    if (
        type(door) is not str
        or door not in DOOR_ELEMENTS
        or type(trigram) is not str
        or trigram not in PALACE_ELEMENTS
        or trigram == "中"
    ):
        raise ValueError("门宫关系须使用实际八门与外八宫，不给中宫补门")
    d, p = DOOR_ELEMENTS[door], PALACE_ELEMENTS[trigram]
    if d == p:
        relation = "same_element"
    elif ELEMENT_CONTROLS[d] == p:
        relation = "door_controls_palace"
    elif ELEMENT_CONTROLS[p] == d:
        relation = "palace_controls_door"
    elif ELEMENT_GENERATES[d] == p:
        relation = "door_generates_palace"
    else:
        relation = "palace_generates_door"
    category = PRINTED_EXAMPLES.get((door, trigram))
    example = (
        None
        if category is None
        else {
            "door": door,
            "trigram": trigram,
            "category": category,
            "traditional_statement": (
                "吉事不成、不吉" if category == "吉门被迫" else "凶事尤甚"
            ),
            "scope": "literal_door_palace_observation_not_global_door_classification",
            "outcome_inference_allowed": False,
        }
    )
    return {
        "profile_id": PROFILE_ID,
        "door": door,
        "trigram": trigram,
        "door_element": d,
        "palace_element": p,
        "relation": relation,
        "relation_text": RELATION_TEXT[relation],
        "verse_door_pressure": relation == "door_controls_palace",
        "palace_restricts_door": relation == "palace_controls_door",
        "prose_label": PROSE_LABELS[relation],
        "prose_label_is_outcome_judgment": False,
        "same_element_named_in_selected_paragraph": False,
        "printed_example": example,
        "source": SOURCE,
        "source_scan_pages": [34],
        "interpretation_limit": "按实际生克方向读取。吉迫不表示吉利，门迫为否不排除正文凶迫；和、义不判断现实结果或人的品德。同五行本段未另命名，未补写为原文比和。",
        "outcome_inference_allowed": False,
    }
