"""Trace the literal You Nian operations and separate them from element relations."""

from typing import Any, Dict

from fatebridge.core.hexagram_relations import ELEMENT_CONTROLS, ELEMENT_GENERATES

# Cumulative top, middle, bottom, middle, top, middle, bottom changes.
# The operation count is different from the count of net changed lines.
_FLIPS = (3, 2, 1, 2, 3, 2, 1)
_MASKS = (0, 4, 6, 7, 5, 1, 3, 2)


def fuwei_element_context(source_prefix: str = "") -> Dict[str, Any]:
    return {
        "selected_clause": "伏位，左辅星，属木，小吉。",
        "selected_source_ids": [source_prefix + "S10"],
        "other_clause": "左辅右弼，随门而化。",
        "other_source_ids": [source_prefix + "S12"],
        "other_context_applied": False,
        "scope": "retain_text_context_difference_no_universal_fuwei_element_claim",
    }


def you_nian_trace(base_bits: int, target_bits: int) -> Dict[str, Any]:
    mask = base_bits ^ target_bits
    step = _MASKS.index(mask)
    changed = [line for line in (1, 2, 3) if mask & (1 << (line - 1))]
    return {
        "rule_id": "bazhai_sitting_v1.cumulative_you_nian_changes",
        "source_ids": ["S11"],
        "operation_count": step,
        "line_numbering": "bottom_1_middle_2_top_3",
        "cumulative_flip_sequence": list(_FLIPS[:step]),
        "net_changed_lines": changed,
        "net_changed_line_count": len(changed),
        "changed_line_mask": mask,
        "scope": "literal_change_sequence_not_elapsed_years_or_severity",
    }


def palace_star_relationship(
    palace_element: str, star_name: str, star_element: str
) -> Dict[str, Any]:
    if palace_element == star_element:
        code, label = "same_element", "宫星比和"
    elif ELEMENT_GENERATES[palace_element] == star_element:
        code, label = "palace_generates_star", "宫生星"
    elif ELEMENT_GENERATES[star_element] == palace_element:
        code, label = "star_generates_palace", "星生宫"
    elif ELEMENT_CONTROLS[palace_element] == star_element:
        code, label = "palace_controls_star", "宫克星"
    else:
        code, label = "star_controls_palace", "星克宫"
    result: Dict[str, Any] = {
        "rule_id": "bazhai_sitting_v1.palace_star_elements",
        "source_ids": ["S10", "S13"],
        "palace_element": palace_element,
        "star_element": star_element,
        "star_name": star_name,
        "relationship": code,
        "traditional_label": label,
        "element_policy": "selected_star_table_fixed_fuwei_wood",
        "scope": "directed_element_relation_only_no_whole_house_or_outcome_verdict",
    }
    if star_name == "伏位":
        result["source_context_variation"] = fuwei_element_context()
    return result
