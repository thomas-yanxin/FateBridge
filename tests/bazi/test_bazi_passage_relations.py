"""Preserve pending/partial events and physical carrier scope across entries."""

from copy import deepcopy

import pytest
from pydantic import ValidationError

from fatebridge.core.classical_passage import build_passage_evidence
from fatebridge.core.contracts.output_passage_relations import PassageRelationContext
from fatebridge.core.passage_relations import build_passage_relation_context


def controlled(assessment=None):
    # Synthetic supplied receipt; no civil birth instant or strength claim.
    pillars = dict(
        year=("甲", "辰"), month=("己", "卯"), day=("庚", "申"), hour=("乙", "酉")
    )
    if assessment is None:
        assessment = {
            "hidden_stem_ledger": [
                {
                    "pillar": "month",
                    "stem": "乙",
                    "element": "木",
                    "remaining_mass": 0.0,
                },
                {"pillar": "day", "stem": "庚", "element": "金", "remaining_mass": 1.0},
            ],
            "relations": [
                {
                    "kind": "天干合",
                    "positions": ["year", "month"],
                    "status": "day_master_or_contested_review",
                },
                {
                    "kind": "六冲",
                    "positions": ["month", "hour"],
                    "status": "active",
                    "root_multipliers": {"month": 0.0},
                },
            ],
        }
    else:
        pass
    passage = build_passage_evidence(pillars, assessment)
    return build_passage_relation_context(passage, assessment)


def test_visible_combination_does_not_bind_hidden_stems_and_zero_remaining_root_keeps_context() -> (
    None
):
    c = controlled()
    PassageRelationContext.model_validate(c)
    nodes = {n["node_id"]: n for n in c["nodes"]}
    assert nodes["year:stem:甲"]["visible_relation_refs"] == ["assessment.relations:0"]
    assert nodes["year:stem:甲"]["root_carrier_positions"] == ["month"]
    assert nodes["year:stem:甲"]["root_relation_refs"] == ["assessment.relations:1"]
    assert nodes["month:hidden:乙"]["visible_relation_refs"] == []
    assert nodes["month:hidden:乙"]["root_relation_refs"] == ["assessment.relations:1"]
    assert nodes["year:hidden:戊"]["root_relation_refs"] == []
    assert c["events"][1]["receipt"]["root_multipliers"]["month"] == 0.0
    assert c["effective_passage"] == "not_adjudicated"


def test_missing_and_supplied_empty_receipts_are_distinct_and_partial_reads_remain_valid() -> (
    None
):
    missing = controlled({})
    empty = controlled({"relations": [], "hidden_stem_ledger": []})
    assert missing["events"] is None and missing["source_relation_count"] is None
    assert empty["events"] == [] and empty["source_relation_count"] == 0
    assert missing["nodes"][0]["root_carrier_positions"] is None
    assert empty["nodes"][0]["root_carrier_positions"] == []
    for c in (missing, empty, controlled()):
        PassageRelationContext.model_validate(c)
        for key, value in c.items():
            PassageRelationContext.model_validate({key: value})
        for n in c["nodes"]:
            for key in n:
                PassageRelationContext.model_validate(
                    {"nodes": [{"node_id": n["node_id"], key: n[key]}]}
                )


def test_unknown_event_kind_is_retained_without_guessing_plane_or_effect() -> None:
    c = controlled(
        {
            "relations": [
                {
                    "kind": "未来未分类关系",
                    "positions": ["year", "month"],
                    "status": "pending_new_scope",
                }
            ]
        }
    )
    PassageRelationContext.model_validate(c)
    assert c["events"][0]["plane"] == "unclassified"
    assert c["unclassified_event_refs"] == ["assessment.relations:0"]
    assert c["effective_passage"] == "not_adjudicated"


def test_returned_receipts_do_not_share_mutable_event_objects_with_assessment() -> None:
    a = {
        "relations": [
            {
                "kind": "六冲",
                "positions": ["month", "hour"],
                "status": "active",
                "nested": {"value": 0},
            }
        ]
    }
    original = deepcopy(a)
    c = controlled(a)
    c["events"][0]["receipt"]["nested"]["value"] = 1
    assert a == original


@pytest.mark.parametrize("fault", range(11))
def test_suppressed_pending_conditions_wrong_planes_and_invented_effects_are_rejected(
    fault,
) -> None:
    c = controlled()
    if fault == 0:
        c["events"][0]["plane"] = "branch"
    elif fault == 1:
        c["events"].append(deepcopy(c["events"][0]))
    elif fault == 2:
        c["source_relation_count"] += 1
    elif fault == 3:
        c["events"][0]["id"] = "assessment.relations:9"
    elif fault == 4:
        c["nodes"][0]["visible_relation_refs"] = []
    elif fault == 5:
        c["nodes"][0]["root_relation_refs"] = []
    elif fault == 6:
        c["nodes"][1]["visible_relation_refs"] = ["assessment.relations:0"]
    elif fault == 7:
        c["nodes"][1]["root_carrier_positions"] = ["month"]
    elif fault == 8:
        c["effective_passage"] = "effective"
    elif fault == 9:
        c["relations_status"] = "not_supplied"
    else:
        c["nodes"].append(deepcopy(c["nodes"][0]))
    with pytest.raises(ValidationError):
        PassageRelationContext.model_validate(c)
