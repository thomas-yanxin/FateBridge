"""Presentation copies must not leak answers or hide unresolved pair branches."""

from copy import deepcopy

import pytest

from fatebridge.validation.sukuyo_semantic import semantic_calculation_view


def test_pair_export_copies_are_removed_while_all_candidate_relations_survive():
    source = {
        "reading_text": "NATIVE-ANSWER",
        "summary": "NATIVE-ANSWER",
        "snapshot_export": {
            "sections": [{"content": "NATIVE-ANSWER"}],
            "export_text": "NATIVE-ANSWER",
        },
        "snapshot_text": "NATIVE-ANSWER",
        "export_text": "NATIVE-ANSWER",
        "run_metadata": {"run_id": "metadata"},
        "person1": {"calendar_candidates": [{"day": 20}, {"day": 21}]},
        "person2": {"candidate_su27s": ["参", "毕"]},
        "pair": None,
        "candidate_relation_analysis": {
            "complete": False,
            "rows": [
                {"direction": "a_to_b", "role": "危"},
                {"direction": "b_to_a", "role": "成"},
            ],
        },
        "rulesets": {"source_passages": [{"text": "SOURCE-TEXT"}]},
        "validation": {"real_samples": 0},
        "future_domain_field": {"unfavorable_result": True},
    }
    before = deepcopy(source)
    view = semantic_calculation_view("sukuyo_compatibility", source)
    assert "NATIVE-ANSWER" not in str(view)
    assert set(view) == set(source) - {
        "reading_text",
        "summary",
        "snapshot_export",
        "snapshot_text",
        "export_text",
        "run_metadata",
    }
    assert view["candidate_relation_analysis"] == source["candidate_relation_analysis"]
    assert view["rulesets"] == source["rulesets"]
    assert view["future_domain_field"] == source["future_domain_field"]
    view["person1"]["calendar_candidates"].clear()
    assert source == before


def test_suzhan_projection_removes_nested_native_text_and_keeps_source_conditions():
    source = {
        "params": {"calendar_day_part": "first_half"},
        "sukuyo": {
            "reading_text": "NATIVE-ANSWER",
            "candidate_days": [
                {
                    "reading_text": "OTHER-NATIVE",
                    "source_passages": [{"text": "SOURCE-TEXT", "conditional": True}],
                }
            ],
        },
        "rulesets": {"unresolved": ["leap_priority"]},
        "snapshot_export": {"export_text": "NATIVE-ANSWER"},
        "physical_chart": {"evaluated_separately": True},
    }
    view = semantic_calculation_view("suzhan", source)
    assert "NATIVE" not in str(view)
    assert view["sukuyo"]["candidate_days"][0]["source_passages"] == [
        {"text": "SOURCE-TEXT", "conditional": True}
    ]
    assert view["params"] == source["params"] and view["rulesets"] == source["rulesets"]
    assert set(view) == {"params", "sukuyo", "rulesets"}
    assert source["sukuyo"]["reading_text"] == "NATIVE-ANSWER"


def test_unknown_tool_or_missing_required_suzhan_evidence_is_rejected():
    with pytest.raises(ValueError):
        semantic_calculation_view("other", {})
    with pytest.raises(KeyError):
        semantic_calculation_view("suzhan", {"params": {}, "rulesets": {}})
