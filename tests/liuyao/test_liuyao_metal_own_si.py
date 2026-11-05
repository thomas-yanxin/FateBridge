"""Actual own-Si efficacy, independent roots and retained control conditions."""

import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core.liuyao_metal_change import PROFILE, own_si_context
from fatebridge.core.output_liuyao_conditions import StrengthActor
from fatebridge.core.output_liuyao_growth import GrowthConditions
from scripts.liuyao.build_profile import build_profile
from tests.liuyao.test_liuyao_conditions import conditional_case
from tests.liuyao.test_liuyao_metal_moving import cycle, read_path
from tests.liuyao.test_liuyao_roles import classical

BASE = Path(__file__).parents[1] / "fixtures/liuyao_metal_own_si_v35"
CASES = json.loads((BASE / "cases.json").read_text())["cases"]


def result_for(case):
    return conditional_case(
        {
            "base_code": case["gua_code"],
            "changed_code": case["changed_code"],
            "month_branch": case["month"],
            "day_ganzhi": case["day_ganzhi"],
            "focus_line": case["focus_line"],
        }
    )


def check(result, case):
    p = case["position"] - 1
    growth = result["growth_conditions"]["lines"][p]
    source = result["generation_conditions"]["sources"][p]
    assert growth["branch"] == case["branch"]
    assert source["condition_match"] is case["expected_generation_source"]
    own = growth.get("own_changed_si")
    if case.get("expected_applicable", True) is False:
        assert own is None
        return
    assert own["condition_match"] is case["expected_own_growth"]
    assert own["is_actual_moving"] is True and own["changed_branch"] == "巳"
    assert own["raw_back_relation"] == "克爻" and own["raw_back_control"] is True
    assert own["raw_outgoing_obstructions"]
    assert source["back_generation_condition"] is False
    assert read_path(result, own["source_path"]) == own
    assert result["growth_conditions"]["ruleset_id"] == PROFILE["ruleset_id"]
    assert result["growth_conditions"]["source_sha256"] == own["source_sha256"]
    for root in own["calendar_supports"]:
        actor = read_path(result, root["source_path"])
        assert (actor["location"], actor["branch"]) == (
            root["location"],
            root["branch"],
        )
    moving = own.get("moving_support")
    if moving:
        assert moving["excluded_target_position"] == case["position"]
        for candidate in moving["candidates"]:
            for step in candidate["root_proof"]:
                assert step["position"] != case["position"]
                assert step.get("source_position") != case["position"]
                assert (
                    read_path(result, step["source_path"])["branch"] == step["branch"]
                )
    qualified = False if case["expected_own_growth"] is True else None
    clash = result["clash_conditions"]["lines"][p]
    assert clash["back_control"] is True
    assert clash["qualified_back_control_condition"] is qualified
    assert clash["own_si_growth_source_path"] == own["source_path"]
    edge = next(
        e
        for e in result["interaction_edges"]
        if e["source_kind"] == "changed" and e["source_position"] == case["position"]
    )
    assert edge["relation"] == "克爻" and edge["target_position"] == case["position"]
    assert edge["qualified_back_control_condition"] is qualified
    assert edge["own_si_growth_source_path"] == own["source_path"]
    assert result["lines"][p]["outgoing_obstructions"] == (
        [] if qualified is False else ["本位金化巳的长生或回头克资格待审"]
    )
    strength = result["classical_assessment"]["lines"][p]["strength"]
    if qualified is False:
        assert not any(a["location"] == "changed" for a in strength["oppositions"])
        assert any(
            a["location"] == "changed" and a["harm_condition_match"] is False
            for a in strength["blocked_oppositions"]
        )
    if case.get("retain_month_control"):
        assert any(a["location"] == "month" for a in strength["oppositions"])
    if case.get("retain_day_control"):
        assert any(a["location"] == "day" for a in strength["oppositions"])
    if case.get("retain_visible_control"):
        assert any(
            a["location"] == "visible"
            and a["position"] == case["retain_visible_control"]
            for a in strength["oppositions"]
        )
    if case.get("changed_void"):
        assert (
            own["changed_void"] is True and own["changed_admission_condition"] is None
        )
    if case.get("changed_month_break"):
        assert (
            own["changed_month_break"] is True
            and own["changed_admission_condition"] is None
        )
    if case.get("retain_binding"):
        assert result["lines"][p]["binding_cues"]
    if case.get("retain_original_void"):
        assert source["status"] == "source_current_void_waits_for_filling"
    if case["id"] == "month-root-replaces-own-si-control":
        role = next(
            x
            for x in result["role_effects"]["lines"]
            if x["position"] == case["position"]
        )
        assert role["atom_values"]["injured_relation"] is True
        assert role["conditional_atom_values"]["injured_relation"] is False
        assert role["atom_values"]["back_generate"] is False
        assert role["conditional_atom_values"]["back_generate"] is False
    if case.get("expected_basis") == "moving":
        assert own["calendar_supports"] == [] and moving["condition_match"] is True
    elif case.get("expected_basis"):
        assert any(
            x["location"] == case["expected_basis"] for x in own["calendar_supports"]
        )
    assert all("_metal_own_si_growth" not in x for x in result["lines"])
    return own


def test_own_si_original_scan_and_frozen_cases():
    assert build_profile("metal_own_si") == PROFILE
    for name, digest in json.loads((BASE / "freeze.json").read_text())[
        "files_sha256"
    ].items():
        assert hashlib.sha256((BASE / name).read_bytes()).hexdigest() == digest
    assert len(CASES) == 11


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_actual_own_si_qualification_and_retained_conditions(case):
    check(result_for(case), case)


def test_pending_own_si_does_not_become_a_definite_route_blocker():
    case = next(c for c in CASES if c["id"] == "changed-si-void-remains-pending")
    result = result_for(case)
    route = next(
        x for x in result["routing_conditions"]["routes"] if x["positions"] == [4, 6, 5]
    )
    permission = next(x for x in route["conditions"] if x["id"] == "routing_permission")
    assert permission["matched"] is None and 6 not in route["obstructed_positions"]
    assert "routing_permission" in route["pending_conditions"]


@pytest.mark.parametrize(
    "case",
    json.loads((BASE / "post-implementation-geometry.json").read_text())["cases"],
    ids=lambda c: c["id"],
)
def test_second_legal_geometry_is_separately_labelled_engineering_coverage(case):
    for name, h in json.loads(
        (BASE / "post-implementation-freeze.json").read_text()
    ).items():
        assert hashlib.sha256((BASE / name).read_bytes()).hexdigest() == h
    result = classical(case)
    own = result["growth_conditions"]["lines"][4]["own_changed_si"]
    assert own["branch"] == "申" and own["condition_match"] is True
    if case.get("retain_month_break"):
        assert result["lines"][4]["monthly_strength"]["category"] == "月破"
        assert result["generation_conditions"]["sources"][4]["condition_match"] is None


@pytest.mark.parametrize(
    "anchor",
    [
        "none",
        "queried-metal",
        "calendar-fire",
        "source-false",
        "source-pending",
        "inactive-source",
    ],
)
def test_own_si_cannot_use_circular_or_unqualified_moving_roots(anchor):
    anchors = (
        {6: [dict(location="month", branch="丑")]}
        if anchor == "queried-metal"
        else {2: [dict(location="month", branch="午")]} if anchor != "none" else {}
    )
    args = cycle(anchors)
    args["lines"][5].update(change=True, changed_branch="巳")
    if anchor in ("source-false", "source-pending"):
        args["generation"]["sources"][0]["condition_match"] = (
            False if anchor == "source-false" else None
        )
    if anchor == "inactive-source":
        args["generation"]["sources"][0]["activity_condition_match"] = False
    own = own_si_context(
        args["lines"][5],
        dict(monthly_supported=False),
        "午",
        "乙卯",
        args["lines"],
        args["assessment"],
        args["generation"],
    )
    assert own["condition_match"] is (True if anchor == "calendar-fire" else None)


def test_own_si_leaf_projection_needs_no_sibling_fields():
    output = GrowthConditions.model_validate(
        {"lines": [{"own_changed_si": {"qualified_back_control_condition": None}}]}
    )
    assert output.lines[0].own_changed_si.qualified_back_control_condition is None


def test_own_si_calendar_proof_rejects_a_boolean_in_place_of_roots():
    with pytest.raises(ValidationError):
        GrowthConditions.model_validate(
            {"lines": [{"own_changed_si": {"calendar_supports": True}}]}
        )


@pytest.mark.parametrize(
    "payload", [{"harm_condition_match": "true"}, {"qualification_source_path": False}]
)
def test_strength_qualification_fields_have_strict_published_types(payload):
    with pytest.raises(ValidationError):
        StrengthActor.model_validate(payload)
