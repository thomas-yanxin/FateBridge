"""Boundary tests for source-scoped, non-compass interior relationships."""

from copy import deepcopy
from types import SimpleNamespace
from typing import get_args

import pytest
from pydantic import ValidationError

from fatebridge.core.fengshui.interior_inputs import (
    RELATION_ROLES,
    SUPPORTED_INTERIOR_ROLES,
    InteriorRelation,
    InteriorRelationKind,
    validate_relation_references,
)
from fatebridge.core.fengshui.interior_rules import (
    analyze_interior_relations,
    interior_relation_provenance,
)

KINDS = list(get_args(InteriorRelationKind))


def relation(kind="mirror_faces_bed", present=True, basis="user_confirmed", **kwargs):
    return InteriorRelation(
        **{
            "relation_id": "r1",
            "kind": kind,
            "source_object_id": "source",
            "target_object_id": "target",
            "present": present,
            "observation_basis": basis,
            "evidence": "逐一核对实际对象及关系，不从标签猜测",
            **kwargs,
        }
    )


def analyze(relations, constraints=()):
    return analyze_interior_relations(
        SimpleNamespace(interior_relations=relations), constraints
    )


@pytest.mark.parametrize("kind", KINDS)
def test_every_registered_predicate_is_reviewable_without_a_compass(kind):
    fact = relation(kind)
    source_role, target_role = RELATION_ROLES[kind]
    validate_relation_references(
        [fact], {"source": {source_role}, "target": {target_role}}, {}
    )
    result = analyze([fact])
    assert result["status"] == "complete"
    assert result["missing_inputs"] == []
    assert result["rule_coverage_counts"] == {
        "supported": 1,
        "confirmed_unsupported": 0,
        "unknown": 0,
    }
    finding = result["findings"][0]
    assert finding["status"] == "authored_caution"
    assert finding["predicate"] and finding["exceptions"]
    assert finding["source_ids"] == result["rule_trace"][0]["source_ids"]
    assert all(a["status"] != "ready" for a in result["action_options"])
    for action in result["action_options"] + finding["action_options"]:
        assert action["action_basis"] == (
            "conditional_candidate_to_change_the_sourced_relation_not_a_guaranteed_cure"
        )


@pytest.mark.parametrize("kind", KINDS)
def test_confirmed_absence_is_covered_without_inventing_actions_or_overall_suitability(
    kind,
):
    result = analyze([relation(kind, present=False)])
    assert result["status"] == "complete"
    assert result["findings"][0]["status"] == "not_present"
    assert result["findings"][0]["interpretation"] is None
    assert result["action_options"] == []
    assert result["rule_trace"][0]["predicate_present"] is False


@pytest.mark.parametrize("present", [True, False, None])
def test_all_photo_relations_remain_candidates(present):
    result = analyze([relation(present=present, basis="image_observed")])
    assert result["status"] == "partial"
    assert result["findings"][0]["status"] == "candidate_only"
    assert result["rule_trace"][0]["predicate_confirmed"] is False
    assert result["rule_trace"][0]["predicate_present"] is None
    assert result["missing_inputs"] == [
        "environmental_context.interior_relations.r1.confirmation"
    ]
    assert result["action_options"] == []
    assert result["rule_coverage_counts"]["unknown"] == 1


def test_explicit_unknown_needs_relation_confirmation_without_requiring_direction():
    result = analyze([relation(present=None, basis="measured")])
    assert result["findings"][0]["status"] == "needs_confirmation"
    assert result["missing_inputs"] == [
        "environmental_context.interior_relations.r1.present"
    ]
    assert result["rule_coverage_status"] == "needs_confirmation"


@pytest.mark.parametrize("kind", KINDS)
def test_photo_caution_can_be_explained_conditionally_without_certifying_an_action(
    kind,
):
    result = analyze([relation(kind, basis="image_observed")])
    finding = result["findings"][0]
    conditional = finding["conditional_interpretation"]
    assert conditional["interpretation"]
    assert conditional["rule_id"] == finding["rule_id"]
    assert conditional["source_ids"] == finding["source_ids"]
    assert finding["interpretation"] is None
    assert finding["status"] == "candidate_only"
    assert finding["action_options"] == result["action_options"] == []
    assert result["status"] == "partial" and result["missing_inputs"]


@pytest.mark.parametrize("present", [False, None])
def test_photo_absence_or_unknown_does_not_create_a_conditional_caution(present):
    finding = analyze([relation(present=present, basis="image_observed")])["findings"][
        0
    ]
    assert finding["conditional_interpretation"] is None


def test_photo_conditional_suggestions_respect_both_endpoints_action_constraints():
    constraints = [
        SimpleNamespace(object_id=object_id, can_relocate=False, can_rotate=False)
        for object_id in ["source", "target"]
    ]
    finding = analyze([relation(basis="image_observed")], constraints)["findings"][0]
    assert finding["conditional_interpretation"]["interpretation"]
    assert finding["conditional_interpretation"]["suggestions"] == []


@pytest.mark.parametrize("present", [1, 0, "true", "false", "yes"])
def test_relation_does_not_coerce_truth(present):
    with pytest.raises(ValidationError):
        relation(present=present)


def test_present_is_required_and_extra_personal_chart_fields_are_rejected():
    payload = relation().model_dump()
    del payload["present"]
    with pytest.raises(ValidationError):
        InteriorRelation.model_validate(payload)
    with pytest.raises(ValidationError):
        InteriorRelation.model_validate(
            {**relation().model_dump(), "bazi_element": "木"}
        )


@pytest.mark.parametrize(
    "field", ["relation_id", "source_object_id", "target_object_id", "evidence"]
)
def test_identifiers_and_evidence_must_be_nonblank(field):
    with pytest.raises(ValidationError):
        relation(**{field: "  "})


def test_endpoint_identity_and_reference_roles_are_explicit():
    with pytest.raises(ValidationError):
        relation(target_object_id="source")
    with pytest.raises(ValueError, match="未知对象"):
        validate_relation_references([relation()], {"source": {"mirror"}}, {})
    with pytest.raises(ValueError, match="必须明确具有角色 bed"):
        validate_relation_references(
            [relation()], {"source": {"mirror"}, "target": {"desk"}}, {}
        )
    # A generic door purpose cannot become the main entry from a suggestive label.
    with pytest.raises(ValueError, match="main_entry_door"):
        validate_relation_references(
            [relation("main_entry_door_faces_bathroom_door")],
            {"source": {"door"}, "target": {"bathroom_door"}},
            {},
        )


def test_multiple_explicit_roles_are_independent_and_duplicate_facts_are_rejected():
    first = relation("sharp_corner_points_at_desk")
    roles = {"source": {"desk", "sharp_corner"}, "target": {"desk"}}
    validate_relation_references([first], roles, {})
    with pytest.raises(ValueError, match="relation_id"):
        validate_relation_references([first, first], roles, {})
    with pytest.raises(ValueError, match="种类及端点"):
        validate_relation_references(
            [first, first.model_copy(update={"relation_id": "r2"})], roles, {}
        )


def test_bed_corner_rule_requires_a_pillar_and_does_not_generalize_furniture_corners():
    fact = relation("pillar_corner_points_at_bed")
    with pytest.raises(ValueError, match="pillar_corner"):
        validate_relation_references(
            [fact], {"source": {"sharp_corner", "desk"}, "target": {"bed"}}, {}
        )
    validate_relation_references(
        [fact], {"source": {"pillar_corner"}, "target": {"bed"}}, {}
    )
    with pytest.raises(ValidationError):
        relation("sharp_corner_points_at_bed")
    finding = analyze([fact])["findings"][0]
    assert "实体柱角" in finding["predicate"]
    assert any("家具尖角不在本条来源覆盖内" in item for item in finding["exceptions"])


@pytest.mark.parametrize(
    "kind", ["bed_headboard_against_toilet_wall", "stove_back_against_toilet_wall"]
)
def test_toilet_wall_relation_requires_the_fixture_side_not_any_bathroom_partition(
    kind,
):
    finding = analyze([relation(kind)])["findings"][0]
    assert "便器所在位置的共墙" in finding["predicate"]
    assert any("任意卫生间隔墙" in item for item in finding["exceptions"])


def test_horizontal_relation_uses_level_not_interior_courtyard_floor_id():
    fact = relation("sharp_corner_points_at_desk")
    roles = {"source": {"sharp_corner"}, "target": {"desk"}}
    floors = {
        "source": SimpleNamespace(
            level=1, floor_id="courtyard", space_kind="courtyard"
        ),
        "target": SimpleNamespace(level=1, floor_id="inside", space_kind="interior"),
    }
    validate_relation_references([fact], roles, floors)
    floors["target"].level = 2
    with pytest.raises(ValueError, match="不能跨"):
        validate_relation_references([fact], roles, floors)
    validate_relation_references(
        [fact.model_copy(update={"present": False})], roles, floors
    )
    validate_relation_references(
        [fact.model_copy(update={"observation_basis": "image_observed"})], roles, floors
    )


@pytest.mark.parametrize("source_level,target_level", [(1, 1), (1, 2)])
def test_bed_above_stove_requires_known_vertical_order_only_when_asserted(
    source_level, target_level
):
    fact = relation("bed_above_stove")
    roles = {"source": {"bed"}, "target": {"stove"}}
    floors = {"source": {"level": source_level}, "target": {"level": target_level}}
    with pytest.raises(ValueError, match="必须高于"):
        validate_relation_references([fact], roles, floors)
    validate_relation_references(
        [fact.model_copy(update={"present": False})], roles, floors
    )
    validate_relation_references(
        [fact.model_copy(update={"present": None})], roles, floors
    )
    validate_relation_references(
        [fact], roles, {"source": {"level": 2}, "target": {"level": 1}}
    )
    # Directly confirmed vertical alignment need not fabricate named floor spaces.
    validate_relation_references([fact], roles, {})


def test_mirror_actions_have_independent_permissions_and_no_ready_state():
    result = analyze(
        [relation()],
        [SimpleNamespace(object_id="source", can_relocate=False, can_rotate=True)],
    )
    actions = {item["operation"]: item for item in result["action_options"]}
    assert actions["location"]["status"] == "blocked"
    assert actions["location"]["pending_confirmations"] == []
    assert actions["facing"]["status"] == "conditional_option"
    assert actions["facing"]["permission_field"] == "can_rotate"
    assert actions["facing"]["pending_confirmations"] == [
        "independently_confirmed_candidate_relation_geometry",
        "independently_confirmed_candidate_physical_feasibility",
    ]
    assert result["missing_inputs"] == []  # Optional action review is separate.
    assert result["status"] == "complete"


def test_all_actions_blocked_stop_action_questions_and_do_not_move_structural_sources():
    fact = relation("exposed_beam_above_bed")
    result = analyze([fact], [SimpleNamespace(object_id="target", can_relocate=False)])
    assert result["findings"][0]["action_status"] == "blocked"
    assert result["action_options"][0]["object_id"] == "target"
    assert result["action_options"][0]["pending_confirmations"] == []
    assert result["missing_inputs"] == []
    for kind in ("pipe_above_stove", "exposed_beam_above_stove"):
        assert {
            a["object_id"] for a in analyze([relation(kind)])["action_options"]
        } == {"target"}
    for kind in ("bed_headboard_against_toilet_wall", "stove_back_against_toilet_wall"):
        assert {
            a["object_id"] for a in analyze([relation(kind)])["action_options"]
        } == {"source"}


def test_vertical_alternatives_do_not_share_permission_between_bed_and_stove():
    result = analyze(
        [relation("bed_above_stove")],
        [
            SimpleNamespace(object_id="source", can_relocate=True),
            SimpleNamespace(object_id="target", can_relocate=False),
        ],
    )
    assert [(a["object_id"], a["status"]) for a in result["action_options"]] == [
        ("source", "conditional_option"),
        ("target", "blocked"),
    ]


def test_main_entry_relation_has_no_invented_screen_or_door_reconstruction():
    result = analyze([relation("main_entry_door_faces_bathroom_door")])
    assert (
        result["findings"][0]["action_status"] == "no_registered_nonstructural_action"
    )
    assert result["action_options"] == []


def test_source_versions_and_mirror_disagreement_are_preserved_and_not_auto_selected():
    provenance = interior_relation_provenance()
    assert provenance["ruleset_id"] == "interior_authored_relations_v1"
    assert len(RELATION_ROLES) == len(KINDS) == 12
    assert len(SUPPORTED_INTERIOR_ROLES) == 11
    sources = {s["source_id"]: s for s in provenance["sources"]}
    for source in sources.values():
        assert source["author"] and source["source_version"] and source["locator"]
        assert source["url"].startswith("https://")
        assert source["retrieved_at"] == "2026-10-15"
        if source["evidence_excerpt"]:
            assert len(source["evidence_excerpt"].split()) < 25
    result = analyze([relation()])
    disagreement = result["findings"][0]["method_disagreements"][0]
    assert disagreement["source_id"] in sources
    assert disagreement["method"] == "BTB"
    assert disagreement["automatically_selected"] is False
    assert result["findings"][0]["status"] == "authored_caution"
    original = deepcopy(provenance)
    provenance["sources"][0]["author"] = "mutated"
    assert interior_relation_provenance() == original


def test_empty_scope_does_not_claim_assessment_and_dictionary_context_is_supported():
    assert analyze_interior_relations(None, [])["status"] == "not_requested"
    assert analyze([])["rulesets"] == []
    result = analyze_interior_relations({"relations": [relation().model_dump()]}, [])
    assert result["status"] == "complete"
    assert (
        result["action_options"][0]["pending_confirmations"][0]
        == "layout_constraints.source.can_relocate"
    )


def test_provenance_sources_meet_output_contract_and_keep_citable_locators():
    from fatebridge.core.fengshui.output import RuleSource

    required = {
        "title",
        "url",
        "kind",
        "scope",
        "source_version",
        "locator",
        "retrieved_at",
    }
    sources = interior_relation_provenance()["sources"]
    assert len(sources) == 6
    for source in sources:
        assert required <= source.keys()
        assert all(
            isinstance(source[key], str) and source[key].strip() for key in required
        )
        RuleSource.model_validate(source)
    assert sources[-1]["kind"] == "author_published_dissent"
