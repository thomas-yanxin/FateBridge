"""Source-specific temporal roots remain separate from effective root force."""

from copy import deepcopy

import pytest
from pydantic import ValidationError

from fatebridge.core.output_timing import TimingInteractions
from fatebridge.core.timing_interactions import analyze_timing_interactions
from fatebridge.core.timing_roots import timing_root_snapshot_lines

NATAL = dict(
    zip(("year", "month", "day", "hour"), map(tuple, "甲子 丙寅 甲辰 壬戌".split()))
)


@pytest.mark.parametrize(
    "pillar,kind,hidden,weight",
    [
        ("甲寅", "lu_root", ["甲"], "heavy"),
        ("乙卯", "yang_blade_root", ["乙"], "heavy"),
        ("乙亥", "yang_growth_root", ["甲"], "heavy"),
        ("己未", "storage_root", ["乙"], "light"),
        ("戊辰", "residual_root", ["乙"], "light"),
        ("甲申", "no_root_in_this_profile", [], "not_ranked_by_this_rule"),
    ],
)
def test_day_master_in_timing_branch_uses_selected_source_root_kind(
    pillar, kind, hidden, weight
):
    result = analyze_timing_interactions(
        NATAL, {"liunian": dict(zip(("stem", "branch"), pillar))}
    )
    TimingInteractions.model_validate(result)
    context = result["root_context"]
    row = context["day_master_roots"][0]
    assert row["stem_node_id"] == "natal.day"
    assert row["branch_node_id"] == "timing.liunian"
    root = row["classification"]
    assert (
        root["kind"],
        root["matching_hidden_stems"],
        root["source_weight_class"],
    ) == (kind, hidden, weight)
    assert context["month_command_node_id"] == "natal.month"
    assert context["effective_force_status"] == "not_adjudicated"


def test_yin_growth_is_a_reference_and_cannot_invent_a_hidden_root():
    natal = {**NATAL, "day": ("丁", "巳")}
    result = analyze_timing_interactions(
        natal, {"dayun": {"stem": "丁", "branch": "酉"}}
    )
    row = result["root_context"]["day_master_roots"][0]["classification"]
    assert row["kind"] == "yin_growth_reference"
    assert row["matching_hidden_stems"] == [] and row["hidden_element_present"] is False
    assert row["source_weight_class"] == "light_textual_reference"
    assert "阴长生" in "".join(timing_root_snapshot_lines(result["root_context"]))


def test_a_clash_is_linked_to_the_root_without_erasing_its_physical_stem():
    result = analyze_timing_interactions(
        NATAL, {"liunian": {"stem": "甲", "branch": "申"}}
    )
    row = next(
        r
        for r in result["root_context"]["timing_stem_natal_roots"]
        if r["branch_node_id"] == "natal.month"
    )
    assert row["classification"]["kind"] == "lu_root"
    assert row["classification"]["matching_hidden_stems"] == ["甲"]
    lookup = {r["id"]: r for r in result["relations"]}
    assert any(
        lookup[i]["rule_id"] == "branch_clash" for i in row["branch_relation_ids"]
    )
    assert row["classification"]["effect_status"] == "root_effect_not_adjudicated"


def test_repeated_seats_and_multiple_stem_references_keep_physical_node_ids():
    natal = {**NATAL, "year": ("甲", "寅")}
    timing = {
        "dayun": {"stem": "甲", "branch": "子"},
        "liunian": {"stem": "甲", "branch": "午"},
    }
    original = deepcopy((natal, timing))
    context = analyze_timing_interactions(natal, timing)["root_context"]
    for node in ("timing.dayun", "timing.liunian"):
        roots = [
            r for r in context["timing_stem_natal_roots"] if r["stem_node_id"] == node
        ]
        assert len(roots) == 4
        assert {
            r["branch_node_id"]
            for r in roots
            if r["classification"]["kind"] == "lu_root"
        } == {"natal.year", "natal.month"}
    assert (natal, timing) == original


@pytest.mark.parametrize(
    "fault",
    [
        "wrong_stem",
        "wrong_branch",
        "unknown_node",
        "unrelated_relation",
        "unrelated_branch",
    ],
)
def test_output_rejects_root_receipts_rebound_to_other_nodes(fault):
    result = analyze_timing_interactions(
        NATAL, {"liunian": {"stem": "庚", "branch": "申"}}
    )
    row = result["root_context"]["day_master_roots"][0]
    if fault == "wrong_stem":
        row["classification"]["stem"] = "乙"
    elif fault == "wrong_branch":
        row["classification"]["branch"] = "寅"
    elif fault == "unknown_node":
        row["branch_node_id"] = "timing.unread"
    elif fault == "unrelated_relation":
        row["branch_relation_ids"] = [
            next(
                r["id"]
                for r in result["relations"]
                if r["rule_id"] == "stem_overcoming"
            )
        ]
    else:
        row = next(
            r
            for r in result["root_context"]["timing_stem_natal_roots"]
            if r["branch_node_id"] == "natal.month"
        )
        row["branch_relation_ids"] = [
            next(
                r["id"]
                for r in result["relations"]
                if r["rule_id"] == "triple_combination"
            )
        ]
    with pytest.raises(ValidationError, match="根|节点"):
        TimingInteractions.model_validate(result)


def test_partial_projection_does_not_require_unread_nodes_or_relations():
    result = analyze_timing_interactions(
        NATAL, {"liunian": {"stem": "甲", "branch": "申"}}
    )
    TimingInteractions.model_validate({"root_context": result["root_context"]})
    TimingInteractions.model_validate(
        {
            "root_context": result["root_context"],
            "nodes": [{"stem": "甲"}],
            "relations": [{"rule_id": "branch_clash"}],
        }
    )
    empty = analyze_timing_interactions(NATAL, {})["root_context"]
    assert empty["day_master_roots"] == empty["timing_stem_natal_roots"] == []


def test_returned_source_pages_do_not_mutate_the_shared_root_source():
    first = analyze_timing_interactions(NATAL, {})["root_context"]
    first["source"]["pdf_pages"].append(999)
    second = analyze_timing_interactions(NATAL, {})["root_context"]
    assert second["source"]["pdf_pages"] == [22, 23]
