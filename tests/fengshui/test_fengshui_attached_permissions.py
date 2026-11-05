"""Actual motion of attached items requires its own explicit permission."""

import pytest

from fatebridge.services.fengshui import assess
from tests.fengshui.test_fengshui_rotation_invariance import payload_for
from tests.support.transports import SPECS, business, rest, surface_calls


def attached_request(kind, value, *, unchanged=False):
    request = payload_for(0, center_x=0, width=1.4)
    spatial = request["workstation_layout"]
    scene = spatial["scene"]
    scene["boundary"]["vertices"] = [
        {"x": -3, "y": -3},
        {"x": 3, "y": -3},
        {"x": 3, "y": 3},
        {"x": -3, "y": 3},
    ]
    scene["desktops"] = [
        {
            "desk_id": "desk",
            "items": [
                {
                    "object_id": "attached",
                    "footprint": {
                        "center": {"x": 0, "y": 0},
                        "width_m": 0.1,
                        "depth_m": 0.1,
                        "rotation_degrees": 0,
                    },
                    "height_m": 0.2,
                    "blocks_view": False,
                    "representation": "other",
                    "representation_basis": "user_confirmed",
                    "evidence": "Synthetic attached object, not a real site.",
                }
            ],
        }
    ]
    spatial["search"] = {
        "domains": [
            {
                "object_id": "desk",
                "positions": [
                    {
                        "x": 0.1 if kind == "can_relocate" and not unchanged else 0,
                        "y": 2,
                    }
                ],
                "rotations_degrees": [
                    360 if unchanged else 90 if kind == "can_rotate" else 0
                ],
            }
        ],
        "max_results": 1,
        "required_checks": [],
    }
    request["layout_constraints"] = [
        {
            "object_id": "desk",
            "can_relocate": True,
            "can_rotate": True,
            "evidence": "Synthetic explicit desk permission.",
        }
    ]
    if value != "missing":
        request["layout_constraints"].append(
            {
                "object_id": "attached",
                "can_relocate": False,
                "can_rotate": False,
                kind: value,
                "evidence": "Synthetic item permission, independent of the desk.",
            }
        )
    return request


def search_result(result):
    return result["layout_analysis"]["workstation_layout_analysis"]["search"]


@pytest.mark.parametrize("kind", ["can_relocate", "can_rotate"])
@pytest.mark.parametrize(
    "value,status",
    [
        (False, "blocked"),
        (None, "conditional_option"),
        (True, "ready"),
        ("missing", "conditional_option"),
    ],
)
def test_attached_actual_world_motion_preserves_three_permission_states(
    kind, value, status
):
    search = search_result(assess(**attached_request(kind, value)))
    (receipt,) = search["receipts"]
    assert receipt["physically_feasible"] is True
    assert receipt["status"] == status
    if value is False:
        assert receipt["blocking_reasons"] == [f"attached_locked_item:attached:{kind}"]
        assert search["candidates"] == []
    else:
        assert receipt["blocking_reasons"] == []
        (candidate,) = search["candidates"]
        assert candidate["status"] == status
        assert all(action["status"] == status for action in candidate["actions"])
    assert receipt["pending_confirmations"] == (
        [f"layout_constraints.attached.{kind}"]
        if value is None or value == "missing"
        else []
    )


@pytest.mark.parametrize("value", [False, None, "missing"])
def test_unchanged_attached_items_do_not_require_any_action_permission(value):
    search = search_result(
        assess(**attached_request("can_rotate", value, unchanged=True))
    )
    (receipt,) = search["receipts"]
    assert receipt["physically_feasible"] is True
    assert receipt["status"] == "ready"
    assert receipt["changed_object_count"] == 0
    assert receipt["blocking_reasons"] == receipt["pending_confirmations"] == []
    assert search["candidates"][0]["actions"] == []


@pytest.mark.parametrize("kind", ["can_relocate", "can_rotate"])
def test_unknown_attached_action_is_conditional_on_actual_three_transports(
    kind, surface_calls
):
    spec = SPECS["fengshui_assess"]
    payload = attached_request(kind, None)
    fields = ["layout_analysis"]
    response, protocol, code, cli = surface_calls(
        spec,
        payload,
        params={"fields": fields, "strict_fields": True},
        options={"fields": fields, "strict_fields": True},
        flags=("--fields", *fields, "--strict-fields"),
    )
    assert response.status_code == 200, response.text
    assert code == 0 and not protocol.is_error
    actual = business(response.json())
    assert actual == business(cli) == business(protocol.structured_content)
    (receipt,) = search_result(actual)["receipts"]
    assert receipt["status"] == "conditional_option"
    assert receipt["pending_confirmations"] == [f"layout_constraints.attached.{kind}"]
