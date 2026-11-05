"""Explicit author desktop rules over independent seated and compass frames."""

from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel

from .spatial_geometry import (
    angular_delta,
    inverse_point,
    rectangle_xy,
    transform_rectangle,
)
from .spatial_inputs import PlanPoint, PlanPose, SpatialScene
from .spatial_outputs import EvaluatedGeometry
from .spatial_reasoning import RuleComparison
from .spatial_sources import RegisteredRuleset, desktop_compass_rules
from .surface import surface_provenance


class BaguaEntry(BaseModel):
    rule_id: str
    goals: list[str]
    zone: str
    representations: list[str]
    source_ids: list[str]
    conditions: list[str]


class BaguaRules(BaseModel):
    entries: list[BaguaEntry]


@lru_cache(maxsize=1)
def _bagua_rules() -> BaguaRules:
    return BaguaRules.model_validate_json(
        (Path(__file__).parents[2] / "data/fengshui/desktop-bagua-v1.json").read_bytes()
    )


def desktop_rule_comparisons(
    scene: SpatialScene, geometry: EvaluatedGeometry
) -> tuple[list[RuleComparison], list[RegisteredRuleset]]:
    result: list[RuleComparison] = []
    rulesets = []
    bagua = None
    if any("desktop_bagua_btb_v1" in d.ruleset_ids for d in scene.desktops):
        bagua = _bagua_rules()
        rulesets.append(RegisteredRuleset.model_validate(surface_provenance()))
    positions = {p.object_id: p for p in geometry.desktop_placements}
    seats = {seat.desk_id: seat for seat in geometry.seats}
    uses = {seat.desk_id: seat for seat in scene.seats}
    desks = {body.object_id: body for body in scene.bodies}
    for desktop in scene.desktops:
        desk = desks[desktop.desk_id]
        seat = seats.get(desktop.desk_id)
        use = uses.get(desktop.desk_id)
        grid_frame_supported = (
            use is not None
            and use.offset.y <= -desk.footprint.depth_m / 2
            and angular_delta(use.facing_offset_degrees, 0) == 0
        )
        seated_x: dict[str, list[float]] = {}
        if seat is not None and any(
            item.representation == "metal_office_equipment" for item in desktop.items
        ):
            observer = PlanPose(
                center=seat.position, rotation_degrees=seat.plan_facing_degrees
            )
            for item in desktop.items:
                world = rectangle_xy(
                    transform_rectangle(item.footprint, desk.footprint)
                )
                seated_x[item.object_id] = [
                    inverse_point(PlanPoint(x=x, y=y), observer).x
                    for x, y in world.exterior.coords
                ]
        for item in desktop.items:
            position = positions[item.object_id]
            uncertain = (
                geometry.candidate_only or item.representation_basis == "image_observed"
            )
            for selected in desktop.ruleset_ids:
                records: list[RuleComparison] = []
                if selected == "desktop_bagua_btb_v1" and bagua:
                    for rule in bagua.entries:
                        if (
                            desktop.goal in rule.goals
                            and item.representation in rule.representations
                        ):
                            match = (
                                position.zone == rule.zone
                                if position.zone is not None and grid_frame_supported
                                else None
                            )
                            records.append(
                                RuleComparison(
                                    object_id=item.object_id,
                                    rule_id=rule.rule_id,
                                    source_ids=rule.source_ids,
                                    reference_frame="seated_desktop_nine_cells",
                                    matches=match,
                                    candidate_only=uncertain or match is None,
                                    status=(
                                        "pending"
                                        if grid_frame_supported
                                        else "not_covered"
                                    ),
                                    observed=position.zone,
                                    expected=rule.zone,
                                    conditions=(
                                        rule.conditions
                                        if grid_frame_supported
                                        else [
                                            "本版本只覆盖实际坐在已声明近沿并面向桌面远沿的参考系；不将其他实际坐者方位强套九格"
                                        ]
                                    ),
                                )
                            )
                elif selected == "wofs_desktop_compass_v1":
                    for compass_rule in desktop_compass_rules():
                        if item.representation != compass_rule.representation:
                            continue
                        directions = position.compass_directions
                        match = (
                            directions[0] == compass_rule.direction
                            if len(directions) == 1
                            else (
                                False
                                if directions
                                and compass_rule.direction not in directions
                                else None
                            )
                        )
                        records.append(
                            RuleComparison(
                                object_id=item.object_id,
                                rule_id=compass_rule.rule_id,
                                source_ids=compass_rule.source_ids,
                                reference_frame="desktop_compass_not_house_palace",
                                matches=match,
                                candidate_only=uncertain or match is None,
                                status="pending",
                                observed=",".join(directions) or None,
                                expected=compass_rule.direction,
                                conditions=[
                                    "保持入口及屏幕视野",
                                    "不侵占实际操作区",
                                    "植物/鲜花状态须独立核对，不由位置证明",
                                ],
                            )
                        )
                    if item.representation == "metal_office_equipment":
                        right = min(seated_x[item.object_id]) >= 0 if seat else None
                        higher_left = (
                            any(
                                max(seated_x[other.object_id]) <= 0
                                and other.height_m > item.height_m
                                for other in desktop.items
                            )
                            if seat
                            else None
                        )
                        match = right and higher_left if seat else None
                        records.append(
                            RuleComparison(
                                object_id=item.object_id,
                                rule_id="wofs_desktop_compass_v1.same_desk_metal_equipment",
                                source_ids=["W1"],
                                reference_frame="seated_right_with_higher_left_object",
                                matches=match,
                                candidate_only=uncertain or seat is None,
                                status="pending",
                                observed=f"right={right};higher_left={higher_left}",
                                expected="whole_equipment_right_and_higher_object_left",
                                conditions=[
                                    "只覆盖已确认金属办公设备，不类推手机或充电口",
                                    "不新增固定高度阈值",
                                ],
                            )
                        )
                if not records:
                    records.append(
                        RuleComparison(
                            object_id=item.object_id,
                            rule_id=f"{selected}.coverage",
                            source_ids=(
                                ["W1"]
                                if selected == "wofs_desktop_compass_v1"
                                else ["D1", "D2", "D3"]
                            ),
                            reference_frame=selected,
                            matches=None,
                            candidate_only=uncertain,
                            status="not_covered",
                            observed=item.representation,
                            conditions=[
                                "没有该物件的独立摆放规则；不按名称补五行或要求购买"
                            ],
                        )
                    )
                for record in records:
                    if record.status != "not_covered":
                        if item.representation in {"living_plant", "fresh_flowers"}:
                            record.application_conditions_met = (
                                item.healthy.value
                                if item.healthy
                                and item.healthy.observation_basis != "image_observed"
                                else None
                            )
                        else:
                            record.application_conditions_met = True
                        record.status = (
                            "needs_confirmation"
                            if (
                                record.candidate_only
                                or record.matches is None
                                or record.matches
                                and record.application_conditions_met is None
                            )
                            else (
                                "opposes_application_condition"
                                if record.application_conditions_met is False
                                else (
                                    "matches_rule" if record.matches else "opposes_rule"
                                )
                            )
                        )
                result.extend(records)
    return result, rulesets
