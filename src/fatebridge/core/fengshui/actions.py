"""Filter sourced actions by explicit permissions; never invent physical facts."""

from typing import Any

from fatebridge.core.fengshui.models import LayoutConstraint


def permission_state(
    constraint: LayoutConstraint | None, routes: list[list[str]]
) -> str:
    """Routes are alternatives; operations within each route are conjunctive."""
    states = []
    for route in routes:
        values = [
            (
                getattr(
                    constraint,
                    {
                        "location": "can_relocate",
                        "facing": "can_rotate",
                        "add_items": "can_add_items",
                    }[operation],
                )
                if constraint is not None
                else None
            )
            for operation in route
        ]
        states.append(
            "blocked"
            if False in values
            else "allowed" if all(v is True for v in values) else "unknown"
        )
    return (
        "allowed"
        if "allowed" in states
        else "unknown" if "unknown" in states else "blocked"
    )


def apply_permission(
    action: dict[str, Any],
    constraint: LayoutConstraint | None,
    routes: list[list[str]],
    *,
    status_key: str = "action_status",
) -> None:
    if constraint is None:
        return
    state = permission_state(constraint, routes)
    action["permission_status"] = state
    action["constraint_evidence"] = constraint.evidence
    if state == "blocked":
        action[status_key] = "blocked"
        action["pending_confirmations"] = []
        action["blocked_reason"] = "explicit_action_constraint"


def sharp_corner_target_actions(
    object_id: str,
    constraint: LayoutConstraint | None,
    *,
    candidate_only: bool,
    rule_id: str,
    source_ids: list[str],
) -> list[dict[str, Any]]:
    """Legacy observations identify the seat, never the corner's source object.

    Moving that unknown source needs an independently identified object and
    permission. Only seat relocation and adding a conditional screen can be
    checked against the known desk's permissions here.
    """
    choices = (
        (
            "relocate_target_seat",
            "location",
            "can_relocate",
            "verify_seat_clearance_and_corner_relation",
            ["新座位容纳、通行和操作空间已确认", "新位置尖角关系及入口视野须独立核对"],
        ),
        (
            "add_leafy_screen",
            "add_items",
            "can_add_items",
            "verify_leafy_screen_clearance_and_entrance_view",
            ["叶状植物屏障实际可容纳并能形成遮挡", "不遮挡入口视野、不妨碍操作及通行"],
        ),
    )
    actions = []
    for action_name, operation, permission_field, reason, conditions in choices:
        action_id = f"form:{object_id}:sharp_corner_points_at_user:{action_name}"
        permission = permission_state(constraint, [[operation]])
        pending = [
            {
                "path": (
                    f"layout_analysis.form_analysis.{object_id}."
                    f"sharp_corner_points_at_user.action_options.{action_name}"
                ),
                "reason": reason,
                "object_id": object_id,
                "action_id": action_id,
                "required_for": "optional_action",
            }
        ]
        if permission == "unknown":
            pending.insert(
                0,
                {
                    "path": f"layout_constraints.{object_id}.{permission_field}",
                    "reason": "confirm_action_permission",
                    "object_id": object_id,
                    "action_id": action_id,
                    "required_for": "optional_action",
                },
            )
        action = {
            "action_id": action_id,
            "action": action_name,
            "object_id": object_id,
            "required_operations": [operation],
            "action_status": (
                "candidate_only" if candidate_only else "conditional_option"
            ),
            "permission_status": permission,
            "optional": True,
            "pending_confirmations": pending,
            "conditions": list(conditions),
            "scope": "known_target_seat_only_not_unidentified_corner_source",
            "rule_id": rule_id,
            "source_ids": list(source_ids),
        }
        apply_permission(action, constraint, [[operation]])
        actions.append(action)
    return actions


FORM_ACTION_ROUTES = {
    "entrance_visible": [["location"], ["facing"]],
    "entrance_direct_line": [["location"]],
    "solid_backing": [["location"], ["add_items"]],
    "passage_direct_line": [["location"]],
    "exposed_beam_over_user": [["location"]],
    "window_to_side": [["location"], ["facing"]],
}
