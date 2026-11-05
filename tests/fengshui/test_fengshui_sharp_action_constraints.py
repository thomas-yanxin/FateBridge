"""Legacy corner observations only authorize actions on the known target seat."""

from itertools import product

import pytest

from fatebridge.services.fengshui import assess


def request(*, relocate=None, add=None, basis="user_confirmed", observed=True):
    return {
        "scene": "workstation",
        "methods": [],
        "form_observations": [
            {
                "object_id": "desk",
                "purpose": "desk",
                "entrance_visible": True,
                "entrance_direct_line": False,
                "solid_backing": True,
                "sharp_corner_points_at_user": observed,
                "observation_basis": basis,
                "evidence": "独立观察实际座位；未识别尖角来源对象",
            }
        ],
        "layout_constraints": [
            {
                "object_id": "desk",
                "can_relocate": relocate,
                # Rotating the desk does not grant permission to move the
                # unidentified source object or to add a plant.
                "can_rotate": True,
                "can_add_items": add,
                "evidence": "分别确认座位搬位与新增许可",
            }
        ],
    }


def review(inputs):
    result = assess(**inputs)
    form = result["layout_analysis"]["form_analysis"]["findings"][0]
    check = next(
        c for c in form["checks"] if c["criterion"] == "sharp_corner_points_at_user"
    )
    return result, form, check


@pytest.mark.parametrize("relocate,add", list(product([None, False, True], repeat=2)))
def test_each_corner_action_obeys_its_own_target_permission(relocate, add):
    result, _, check = review(request(relocate=relocate, add=add))
    actions = {a["action"]: a for a in check["action_options"]}
    assert set(actions) == {"relocate_target_seat", "add_leafy_screen"}
    for name, value, operation, permission_field in (
        ("relocate_target_seat", relocate, "location", "can_relocate"),
        ("add_leafy_screen", add, "add_items", "can_add_items"),
    ):
        action = actions[name]
        assert action["object_id"] == "desk"
        assert action["required_operations"] == [operation]
        assert action["permission_status"] == (
            "unknown" if value is None else "allowed" if value else "blocked"
        )
        assert action["action_status"] == (
            "blocked" if value is False else "conditional_option"
        )
        assert action["rule_id"] == check["rule_id"]
        assert action["source_ids"] == ["F4"]
        assert (
            action["scope"] == "known_target_seat_only_not_unidentified_corner_source"
        )
        if value is False:
            assert action["pending_confirmations"] == []
        else:
            assert action["conditions"] and action["pending_confirmations"]
            permission_pending = [
                p
                for p in action["pending_confirmations"]
                if p["reason"] == "confirm_action_permission"
            ]
            assert bool(permission_pending) is (value is None)
            if permission_pending:
                assert permission_pending[0]["path"].endswith(permission_field)
            assert all(
                p["object_id"] == "desk"
                and p["action_id"] == action["action_id"]
                and p["required_for"] == "optional_action"
                for p in action["pending_confirmations"]
            )
    assert check["finding"] == "opposes_rule"
    assert "本观察未标识尖角来源对象" in check["adjustment"]
    assert check["action_status"] == (
        "blocked" if relocate is False and add is False else "conditional_option"
    )
    assert check["pending_confirmations"] == [
        p for a in check["action_options"] for p in a["pending_confirmations"]
    ]
    counts = result["coverage"]["analysis_progress"]["action_counts"]
    blocked = sum(value is False for value in (relocate, add))
    assert counts == {
        "ready": 0,
        "conditional": 2 - blocked,
        "candidate": 0,
        "blocked": blocked,
    }
    assert result["coverage"]["analysis_progress"]["assessment_complete"] is True


def test_all_known_target_actions_blocked_do_not_ask_for_unknown_source_permission():
    result, _, check = review(request(relocate=False, add=False))
    assert check["action_status"] == "blocked"
    assert check["pending_confirmations"] == []
    progress = result["coverage"]["analysis_progress"]
    assert progress["pending_confirmations"] == []
    assert progress["action_readiness"] == "blocked"
    assert progress["optional_action_count"] == 2
    assert all(a["object_id"] == "desk" for a in check["action_options"])


@pytest.mark.parametrize("relocate,add", [(None, None), (True, False), (False, False)])
def test_photo_uncertainty_remains_even_when_actions_have_explicit_permissions(
    relocate, add
):
    result, form, check = review(
        request(relocate=relocate, add=add, basis="image_observed")
    )
    assert form["finding"] == "needs_confirmation"
    assert check["candidate_only"] is True
    assert result["coverage"]["analysis_progress"]["assessment_complete"] is False
    assert all(
        a["action_status"] in {"candidate_only", "blocked"}
        for a in check["action_options"]
    )
    assert any(
        "user_or_measurement_confirmation" in p
        for p in result["layout_analysis"]["missing_inputs"]
    )
    if relocate is False and add is False:
        assert check["action_status"] == "blocked"
        assert check["pending_confirmations"] == []
    else:
        assert check["action_status"] == "candidate_only"


def test_no_constraint_is_unknown_and_never_makes_either_action_ready():
    inputs = request()
    inputs.pop("layout_constraints")
    _, _, check = review(inputs)
    assert all(
        a["permission_status"] == "unknown"
        and a["action_status"] == "conditional_option"
        for a in check["action_options"]
    )


@pytest.mark.parametrize("observed", [False, None])
def test_false_and_unknown_observations_do_not_invent_corner_actions(observed):
    result = assess(**request(relocate=False, add=False, observed=observed))
    checks = result["layout_analysis"]["form_analysis"]["findings"][0]["checks"]
    corners = [c for c in checks if c["criterion"] == "sharp_corner_points_at_user"]
    if observed is None:
        assert corners == []
    else:
        assert corners[0]["finding"] == "matches_rule"
        assert "action_options" not in corners[0]
    assert result["coverage"]["analysis_progress"]["action_counts"] == {
        "ready": 0,
        "conditional": 0,
        "candidate": 0,
        "blocked": 0,
    }


@pytest.mark.parametrize("purpose", ["bed", "stove"])
def test_legacy_corner_rule_does_not_expand_beyond_the_sourced_desk_scope(purpose):
    inputs = request()
    inputs["form_observations"][0]["purpose"] = purpose
    result = assess(**inputs)
    checks = result["layout_analysis"]["form_analysis"]["findings"][0]["checks"]
    assert all(c["criterion"] != "sharp_corner_points_at_user" for c in checks)


def test_other_form_criteria_keep_their_existing_permission_behavior():
    inputs = request(relocate=False, add=False, observed=False)
    inputs["form_observations"][0]["entrance_direct_line"] = True
    result = assess(**inputs)
    checks = result["layout_analysis"]["form_analysis"]["findings"][0]["checks"]
    entrance = next(c for c in checks if c["criterion"] == "entrance_direct_line")
    assert entrance["action_status"] == "blocked"
    assert entrance["pending_confirmations"] == []
    assert "action_options" not in entrance
