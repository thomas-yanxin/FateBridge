"""Exhaustive finite layouts with independent constraints and Pareto receipts."""

import json
from itertools import product

from pydantic import JsonValue, TypeAdapter

from .models import AssessRequest
from .spatial_geometry import angular_delta, movement_distance, transform_point
from .spatial_inputs import PlanPose
from .spatial_layout import (
    SceneAssessment,
    evaluate_measured_candidate,
    geometry_output,
)
from .spatial_outputs import MeasuredSearchOutput, SearchReceipt
from .spatial_scene import posed_scene, scene_poses


def _dominates(left: SearchReceipt, right: SearchReceipt) -> bool:
    # An unknown or candidate rule is incomparable, not an invented good score.
    keys = left.rule_dimensions.keys() | right.rule_dimensions.keys()
    if any(
        left.rule_dimensions.get(k) is None or right.rule_dimensions.get(k) is None
        for k in keys
    ):
        return False
    before = [left.changed_object_count, left.movement_m, left.rotation_degrees]
    after = [right.changed_object_count, right.movement_m, right.rotation_degrees]
    for key in sorted(keys):
        lvalue, rvalue = left.rule_dimensions[key], right.rule_dimensions[key]
        if lvalue is not None and rvalue is not None:
            before.append(lvalue)
            after.append(rvalue)
    return all(l <= r for l, r in zip(before, after)) and any(
        l < r for l, r in zip(before, after)
    )


def search_measured_layouts(
    original: AssessRequest, layers: dict[str, JsonValue]
) -> MeasuredSearchOutput:
    spatial = original.workstation_layout
    if spatial is None or spatial.search is None:
        raise ValueError("search_measured_layouts requires explicit finite domains")
    scene, search = spatial.scene, spatial.search
    initial = scene_poses(scene)
    permissions = {
        constraint.object_id: constraint for constraint in original.layout_constraints
    }
    domains = [
        [
            PlanPose(center=position, rotation_degrees=rotation)
            for position in d.positions
            for rotation in d.rotations_degrees
        ]
        for d in spatial.resolved_domains
    ]
    receipts: list[SearchReceipt] = []
    frontier: list[tuple[SearchReceipt, SceneAssessment]] = []
    for index, values in enumerate(product(*domains)):
        poses = {
            domain.object_id: value for domain, value in zip(search.domains, values)
        }
        candidate_scene = posed_scene(scene, poses)
        assessment = evaluate_measured_candidate(original, candidate_scene, layers)
        blocked: list[str] = []
        pending: list[str] = []
        changed, distance, rotation = 0, 0.0, 0.0
        for object_id, pose in poses.items():
            displacement = movement_distance(initial[object_id], pose)
            turn = abs(
                angular_delta(
                    pose.rotation_degrees, initial[object_id].rotation_degrees
                )
            )
            changed += int(displacement != 0 or turn != 0)
            distance += displacement
            rotation += turn
            permission = permissions.get(object_id)
            for kind, required in (
                ("can_relocate", displacement != 0),
                ("can_rotate", turn != 0),
            ):
                if not required:
                    continue
                value = getattr(permission, kind) if permission is not None else None
                if value is False:
                    blocked.append(f"permission:{object_id}:{kind}")
                elif value is None:
                    pending.append(f"layout_constraints.{object_id}.{kind}")
        before_bodies = {b.object_id: b for b in scene.bodies}
        after_bodies = {b.object_id: b for b in candidate_scene.bodies}
        for desktop, after_desktop in zip(scene.desktops, candidate_scene.desktops):
            for item, after_item in zip(desktop.items, after_desktop.items):
                permission = permissions.get(item.object_id)
                old_desk = before_bodies[desktop.desk_id].footprint
                new_desk = after_bodies[desktop.desk_id].footprint
                before_center = transform_point(item.footprint.center, old_desk)
                after_center = transform_point(after_item.footprint.center, new_desk)
                for kind, value, required in (
                    (
                        "can_relocate",
                        permission.can_relocate if permission is not None else None,
                        before_center != after_center,
                    ),
                    (
                        "can_rotate",
                        permission.can_rotate if permission is not None else None,
                        angular_delta(
                            old_desk.rotation_degrees + item.footprint.rotation_degrees,
                            new_desk.rotation_degrees
                            + after_item.footprint.rotation_degrees,
                        )
                        != 0,
                    ),
                ):
                    if not required:
                        continue
                    if value is False:
                        blocked.append(f"attached_locked_item:{item.object_id}:{kind}")
                    elif value is None:
                        pending.append(f"layout_constraints.{item.object_id}.{kind}")
        blocked.extend(
            f"geometry:{check.check_id}:{','.join(check.object_ids)}"
            for check in assessment.geometry.checks
            if check.passed is False
        )
        pending.extend(
            f"geometry:{check.check_id}:{','.join(check.object_ids)}"
            for check in assessment.geometry.checks
            if check.passed is None
        )
        for seat in assessment.geometry.seats:
            observed = seat.form
            checks = dict(
                entrance_visible=observed.entrance_visible if observed else None,
                no_entry_direct_line=(
                    not observed.entrance_direct_line
                    if observed and observed.entrance_direct_line is not None
                    else None
                ),
                no_passage_direct_line=(
                    not observed.passage_direct_line
                    if observed and observed.passage_direct_line is not None
                    else None
                ),
                no_overhead_beam=(
                    not observed.exposed_beam_over_user
                    if observed and observed.exposed_beam_over_user is not None
                    else None
                ),
                solid_backing=observed.solid_backing if observed else None,
                no_sharp_corner=(
                    not observed.sharp_corner_points_at_user
                    if observed and observed.sharp_corner_points_at_user is not None
                    else None
                ),
            )
            for key in search.required_checks:
                if checks[key] is False:
                    blocked.append(f"required_check:{seat.desk_id}:{key}")
                elif checks[key] is None:
                    pending.append(f"workstation_layout.scene.{seat.desk_id}.{key}")
        if not scene.inventory_confirmed:
            pending.append("workstation_layout.scene.inventory_confirmed")
        candidate_id = f"spatial-{index + 1:04d}"
        receipt = SearchReceipt(
            candidate_id=candidate_id,
            poses={
                key: TypeAdapter(dict[str, JsonValue]).validate_python(
                    value.model_dump(mode="json")
                )
                for key, value in poses.items()
            },
            physically_feasible=assessment.geometry.physically_feasible,
            status=(
                "blocked"
                if blocked
                else (
                    "candidate_only"
                    if assessment.geometry.candidate_only
                    else "conditional_option" if pending else "ready"
                )
            ),
            blocking_reasons=list(dict.fromkeys(blocked)),
            pending_confirmations=list(dict.fromkeys(pending)),
            rule_dimensions={
                json.dumps(
                    [c.object_id, c.rule_id, c.instance_id], ensure_ascii=False
                ): (
                    None
                    if c.matches is None
                    or c.candidate_only
                    or c.status == "needs_confirmation"
                    else int(not c.matches or c.application_conditions_met is False)
                )
                for c in assessment.comparisons
                if c.status != "not_covered"
            },
            changed_object_count=changed,
            movement_m=distance,
            rotation_degrees=rotation,
        )
        receipts.append(receipt)
        if blocked:
            continue
        if not any(_dominates(other, receipt) for other, _ in frontier):
            frontier = [
                (other, state)
                for other, state in frontier
                if not _dominates(receipt, other)
            ]
            frontier.append((receipt, assessment))
    frontier.sort(
        key=lambda pair: (
            pair[0].changed_object_count,
            pair[0].movement_m,
            pair[0].rotation_degrees,
            pair[0].candidate_id,
        )
    )
    for receipt, _ in frontier:
        receipt.pareto_frontier = True
    selected = frontier[: search.max_results]
    candidates = []
    for receipt, assessment in selected:
        action_records = []
        for object_id, pose_values in receipt.poses.items():
            pose = PlanPose.model_validate(pose_values)
            before = initial[object_id]
            displacement = movement_distance(before, pose)
            turn = angular_delta(pose.rotation_degrees, before.rotation_degrees)
            if displacement == 0 and turn == 0:
                continue
            parent_desktop = next(
                (
                    desktop
                    for desktop in scene.desktops
                    if any(item.object_id == object_id for item in desktop.items)
                ),
                None,
            )
            action_records.append(
                dict(
                    object_id=object_id,
                    coordinate_frame=(
                        f"desktop:{parent_desktop.desk_id}"
                        if parent_desktop
                        else scene.frame_id
                    ),
                    from_pose=dict(
                        center=before.center.model_dump(mode="json"),
                        rotation_degrees=before.rotation_degrees,
                    ),
                    to_pose=pose.model_dump(mode="json"),
                    movement_m=displacement,
                    rotation_degrees=turn,
                    status=receipt.status,
                )
            )
        candidates.append(
            TypeAdapter(dict[str, JsonValue]).validate_python(
                dict(
                    candidate_id=receipt.candidate_id,
                    poses=receipt.poses,
                    actions=action_records,
                    geometry=geometry_output(assessment).model_dump(mode="json"),
                    readings=[r.model_dump(mode="json") for r in assessment.readings],
                    rule_comparisons=[
                        c.model_dump(mode="json") for c in assessment.comparisons
                    ],
                    missing_inputs=assessment.missing_inputs,
                    layout_analysis=assessment.legacy_layout,
                    status=receipt.status,
                    decision_scope="executable_geometry_and_individual_rules_not_universal_auspiciousness",
                )
            )
        )
    rejected = sum(r.status == "blocked" for r in receipts)
    return MeasuredSearchOutput(
        status="complete",
        evaluated_count=len(receipts),
        rejected_count=rejected,
        feasible_count=len(receipts) - rejected,
        frontier_candidate_ids=[r.candidate_id for r, _ in frontier],
        returned_candidate_ids=[r.candidate_id for r, _ in selected],
        omitted_frontier_count=len(frontier) - len(selected),
        enumeration_complete=True,
        resolved_domains=spatial.resolved_domains,
        selection_policy="independent_rule_dimensions_and_minimal_changes_pareto_no_weighted_fengshui_score",
        receipts=receipts,
        candidates=candidates,
    )
