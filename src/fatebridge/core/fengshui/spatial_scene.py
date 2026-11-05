"""Evaluate measured scenes. Observations are compiled only from stated geometry."""

from itertools import combinations
from math import asin, degrees, hypot
from typing import Literal

from shapely.geometry import LineString, Polygon, box

from .layout_inputs import FormObservation
from .spatial_geometry import (
    AREA_EPSILON,
    DIRECTIONS,
    angular_delta,
    corner_points_at,
    direction_support,
    entrance_visible,
    heading,
    point_xy,
    polygon_xy,
    ray_xy,
    rear_backing_distance,
    rectangle_xy,
    segment_xy,
    swept_segment,
    transform_point,
    transform_rectangle,
)
from .spatial_inputs import (
    CompassDirection,
    PlanPoint,
    PlanPose,
    PlanRectangle,
    PlanSegment,
    RelativePosition,
    SpatialScene,
)
from .spatial_outputs import (
    DesktopPlacement,
    EvaluatedGeometry,
    GeometryCheck,
    SeatGeometry,
)
from .spatial_visibility import evaluate_screens


def posed_scene(scene: SpatialScene, poses: dict[str, PlanPose]) -> SpatialScene:
    return scene.model_copy(
        update=dict(
            bodies=[
                (
                    body.model_copy(
                        update=dict(
                            footprint=body.footprint.model_copy(
                                update=dict(
                                    center=poses[body.object_id].center,
                                    rotation_degrees=poses[
                                        body.object_id
                                    ].rotation_degrees,
                                )
                            )
                        )
                    )
                    if body.object_id in poses
                    else body
                )
                for body in scene.bodies
            ],
            desktops=[
                desktop.model_copy(
                    update=dict(
                        items=[
                            (
                                item.model_copy(
                                    update=dict(
                                        footprint=item.footprint.model_copy(
                                            update=dict(
                                                center=poses[item.object_id].center,
                                                rotation_degrees=poses[
                                                    item.object_id
                                                ].rotation_degrees,
                                            )
                                        )
                                    )
                                )
                                if item.object_id in poses
                                else item
                            )
                            for item in desktop.items
                        ]
                    )
                )
                for desktop in scene.desktops
            ],
        )
    )


def scene_poses(scene: SpatialScene) -> dict[str, PlanRectangle]:
    return {body.object_id: body.footprint for body in scene.bodies} | {
        item.object_id: item.footprint
        for desktop in scene.desktops
        for item in desktop.items
    }


def location_support(scene: SpatialScene, anchor: PlanPoint) -> list[CompassDirection]:
    compass = scene.compass
    if compass is None:
        return []
    distance = hypot(
        anchor.x - compass.sector_origin.x, anchor.y - compass.sector_origin.y
    )
    if distance <= scene.coordinate_uncertainty_m:
        return []
    radius = min(
        180,
        compass.uncertainty_degrees
        + degrees(asin(scene.coordinate_uncertainty_m / distance)),
    )
    return direction_support(
        heading(compass.sector_origin, anchor) + compass.y_axis_bearing_degrees, radius
    )


def relative_opening_positions(
    observer: PlanPoint, facing: float, segment: PlanSegment
) -> list[RelativePosition]:
    start, end = heading(observer, segment.start), heading(observer, segment.end)
    width = angular_delta(end, start)
    cells = direction_support(start + width / 2 - facing, abs(width) / 2)
    positions: tuple[RelativePosition, ...] = (
        "front",
        "front_right",
        "right",
        "back_right",
        "back",
        "back_left",
        "left",
        "front_left",
    )
    return [positions[DIRECTIONS.index(cell)] for cell in cells]


def evaluate_geometry(scene: SpatialScene) -> EvaluatedGeometry:
    boundary = polygon_xy(scene.boundary)
    xmin, ymin, xmax, ymax = boundary.bounds
    coordinates = [b.footprint.center for b in scene.bodies] + [
        p for o in scene.openings for p in (o.segment.start, o.segment.end)
    ]
    coordinates += [
        p
        for segment in scene.solid_backing_segments
        for p in (segment.start, segment.end)
    ]
    coordinates += [
        p
        for passage in scene.passages
        for p in (passage.centerline.start, passage.centerline.end)
    ]
    body_frames = {body.object_id: body.footprint for body in scene.bodies}
    coordinates += [
        transform_point(seat.offset, body_frames[seat.desk_id]) for seat in scene.seats
    ]
    reach = 4 * (
        hypot(xmax - xmin, ymax - ymin)
        + max((hypot(p.x - xmin, p.y - ymin) for p in coordinates), default=0)
        + 1
    )
    footprints = {b.object_id: rectangle_xy(b.footprint) for b in scene.bodies}
    bodies = {b.object_id: b for b in scene.bodies}
    checks: list[GeometryCheck] = []

    for body in scene.bodies:
        checks.append(
            GeometryCheck(
                check_id="inside_room",
                object_ids=[body.object_id],
                passed=boundary.covers(footprints[body.object_id]),
            )
        )
    for left, right in combinations(scene.bodies, 2):
        if min(left.top_m, right.top_m) <= max(left.bottom_m, right.bottom_m):
            continue
        area = footprints[left.object_id].intersection(footprints[right.object_id]).area
        checks.append(
            GeometryCheck(
                check_id="body_collision_free",
                object_ids=[left.object_id, right.object_id],
                passed=area <= AREA_EPSILON,
                measurement=area,
                unit="m2",
            )
        )
    clear_zones = [polygon_xy(zone) for zone in scene.keep_clear_zones]
    clear_zones += [
        segment_xy(p.centerline).buffer(p.width_m / 2, cap_style="flat")
        for p in scene.passages
    ]
    for body in scene.bodies:
        if body.kind == "beam":
            continue
        for index, zone in enumerate(clear_zones):
            checks.append(
                GeometryCheck(
                    check_id="keep_clear",
                    object_ids=[body.object_id, f"clear-zone:{index}"],
                    passed=footprints[body.object_id].intersection(zone).area
                    <= AREA_EPSILON,
                )
            )

    desktop_placements: list[DesktopPlacement] = []
    # Explicit height intervals are separate from Shapely's planar predicates.
    desktop_blockers: list[tuple[Polygon, float, float]] = []
    for desktop in scene.desktops:
        desk = bodies[desktop.desk_id]
        surface = box(
            -desk.footprint.width_m / 2,
            -desk.footprint.depth_m / 2,
            desk.footprint.width_m / 2,
            desk.footprint.depth_m / 2,
        )
        item_shapes = {
            item.object_id: rectangle_xy(item.footprint) for item in desktop.items
        }
        for item in desktop.items:
            shape = item_shapes[item.object_id]
            checks.append(
                GeometryCheck(
                    check_id="item_on_desktop",
                    object_ids=[desktop.desk_id, item.object_id],
                    passed=surface.covers(shape),
                )
            )
            world_shape = rectangle_xy(
                transform_rectangle(item.footprint, desk.footprint)
            )
            for obstacle in scene.bodies:
                if obstacle.object_id == desk.object_id or min(
                    desk.top_m + item.height_m, obstacle.top_m
                ) <= max(desk.top_m, obstacle.bottom_m):
                    continue
                checks.append(
                    GeometryCheck(
                        check_id="desktop_body_collision_free",
                        object_ids=[item.object_id, obstacle.object_id],
                        passed=world_shape.intersection(
                            footprints[obstacle.object_id]
                        ).area
                        <= AREA_EPSILON,
                    )
                )
            for index, protected in enumerate(desktop.protected_zones):
                checks.append(
                    GeometryCheck(
                        check_id="desktop_operating_zone_clear",
                        object_ids=[
                            item.object_id,
                            f"{desktop.desk_id}:protected:{index}",
                        ],
                        passed=shape.intersection(polygon_xy(protected)).area
                        <= AREA_EPSILON,
                    )
                )
            zones = []
            for row, prefix in enumerate(("near", "middle", "far")):
                for column, suffix in enumerate(("left", "center", "right")):
                    x = (
                        -desk.footprint.width_m / 2
                        + column * desk.footprint.width_m / 3
                    )
                    y = -desk.footprint.depth_m / 2 + row * desk.footprint.depth_m / 3
                    cell = box(
                        x,
                        y,
                        x + desk.footprint.width_m / 3,
                        y + desk.footprint.depth_m / 3,
                    )
                    if shape.intersection(cell).area > AREA_EPSILON:
                        zones.append(f"{prefix}_{suffix}")
            directions = []
            if scene.compass:
                distance = hypot(item.footprint.center.x, item.footprint.center.y)
                radius = (
                    hypot(item.footprint.width_m, item.footprint.depth_m) / 2
                    + scene.coordinate_uncertainty_m
                )
                directions = (
                    list(DIRECTIONS)
                    if distance <= radius
                    else direction_support(
                        heading(PlanPoint(x=0, y=0), item.footprint.center)
                        + desk.footprint.rotation_degrees
                        + scene.compass.y_axis_bearing_degrees,
                        min(
                            180,
                            scene.compass.uncertainty_degrees
                            + degrees(asin(radius / distance)),
                        ),
                    )
                )
            desktop_placements.append(
                DesktopPlacement(
                    desk_id=desktop.desk_id,
                    object_id=item.object_id,
                    zone=zones[0] if len(zones) == 1 else None,
                    zones=zones,
                    compass_directions=directions,
                    world_center=transform_point(item.footprint.center, desk.footprint),
                )
            )
            if item.blocks_view:
                desktop_blockers.append(
                    (
                        world_shape,
                        desk.top_m,
                        desk.top_m + item.height_m,
                    )
                )
        for left_item, right_item in combinations(desktop.items, 2):
            area = (
                item_shapes[left_item.object_id]
                .intersection(item_shapes[right_item.object_id])
                .area
            )
            checks.append(
                GeometryCheck(
                    check_id="desktop_item_collision_free",
                    object_ids=[left_item.object_id, right_item.object_id],
                    passed=area <= AREA_EPSILON,
                    measurement=area,
                    unit="m2",
                )
            )

    seats: list[SeatGeometry] = []
    occupied: dict[str, tuple[Polygon, Polygon]] = {}
    for seat in scene.seats:
        desk = bodies[seat.desk_id]
        position = transform_point(seat.offset, desk.footprint)
        facing = (desk.footprint.rotation_degrees + seat.facing_offset_degrees) % 360
        user = rectangle_xy(
            PlanRectangle(
                center=position,
                width_m=seat.body_width_m,
                depth_m=seat.body_depth_m,
                rotation_degrees=facing,
            )
        )
        operating = rectangle_xy(
            transform_rectangle(seat.operating_zone, desk.footprint)
        )
        occupied[seat.desk_id] = (user, operating)
        checks.extend(
            [
                GeometryCheck(
                    check_id="seat_inside_room",
                    object_ids=[seat.desk_id],
                    passed=boundary.covers(user),
                ),
                GeometryCheck(
                    check_id="operating_zone_inside_room",
                    object_ids=[seat.desk_id],
                    passed=boundary.covers(operating),
                ),
            ]
        )
        for body in scene.bodies:
            if body.bottom_m < seat.head_height_m:
                checks.extend(
                    [
                        GeometryCheck(
                            check_id="seat_collision_free",
                            object_ids=[seat.desk_id, body.object_id],
                            passed=user.intersection(footprints[body.object_id]).area
                            <= AREA_EPSILON,
                        ),
                        GeometryCheck(
                            check_id="operating_zone_clear",
                            object_ids=[seat.desk_id, body.object_id],
                            passed=operating.intersection(
                                footprints[body.object_id]
                            ).area
                            <= AREA_EPSILON,
                        ),
                    ]
                )
        blockers: list[Polygon | LineString] = [
            footprints[b.object_id]
            for b in scene.bodies
            if b.blocks_view and b.bottom_m <= seat.eye_height_m <= b.top_m
        ]
        blockers += [
            shape
            for shape, bottom, top in desktop_blockers
            if bottom <= seat.eye_height_m <= top
        ]
        entry = next(
            (o for o in scene.openings if o.object_id == seat.entrance_id), None
        )
        visible = direct = None
        entrance_position = None
        entry_positions: list[RelativePosition] = []
        barriers = []
        if entry and entry.inward_degrees is not None:
            midpoint = PlanPoint(
                x=(entry.segment.start.x + entry.segment.end.x) / 2,
                y=(entry.segment.start.y + entry.segment.end.y) / 2,
            )
            visible = entrance_visible(
                position,
                facing,
                seat.view_half_angle_degrees,
                entry.segment,
                blockers,
                reach,
            )
            direct = (
                swept_segment(entry.segment, entry.inward_degrees, reach)
                .intersection(user)
                .area
                > AREA_EPSILON
            )
            entry_positions = relative_opening_positions(
                position, facing, entry.segment
            )
            entrance_position = (
                entry_positions[0] if len(entry_positions) == 1 else None
            )
            line = LineString([(midpoint.x, midpoint.y), (position.x, position.y)])
            barriers = [
                b.object_id
                for b in scene.bodies
                if b.kind in {"plant", "screen"}
                and line.intersects(footprints[b.object_id])
                and not footprints[b.object_id].covers(point_xy(position))
            ]
        passage_direct = False
        for passage in scene.passages:
            # Extend only beyond the declared end; side traffic is not a clash.
            end = passage.centerline.end
            extended = ray_xy(end, heading(passage.centerline.start, end), reach)
            passage_direct |= (
                extended.buffer(passage.width_m / 2, cap_style="flat")
                .intersection(user)
                .area
                > AREA_EPSILON
            )
        beam = any(
            b.kind == "beam"
            and b.bottom_m >= seat.head_height_m
            and footprints[b.object_id].intersection(user).area > AREA_EPSILON
            for b in scene.bodies
        )
        pointing = [
            b
            for b in scene.bodies
            if b.object_id != seat.desk_id
            and b.bottom_m < seat.eye_height_m
            and corner_points_at(b.footprint, user, reach)
        ]
        sharp = (
            True
            if any(b.has_sharp_corners is True for b in pointing)
            else (
                None
                if any(b.has_sharp_corners is None for b in pointing)
                or not scene.inventory_confirmed
                else False
            )
        )
        backing = rear_backing_distance(
            position, facing, scene.solid_backing_segments, reach
        )
        windows = [o for o in scene.openings if o.kind == "window"]
        window = (
            next((o for o in windows if o.object_id == seat.window_id), None)
            if seat.window_id
            else windows[0] if len(windows) == 1 else None
        )
        window_position = None
        window_positions: list[RelativePosition] = []
        if window:
            midpoint = PlanPoint(
                x=(window.segment.start.x + window.segment.end.x) / 2,
                y=(window.segment.start.y + window.segment.end.y) / 2,
            )
            window_positions = relative_opening_positions(
                position, facing, window.segment
            )
            window_position = (
                window_positions[0] if len(window_positions) == 1 else None
            )
        observed = dict(
            object_id=seat.desk_id,
            purpose="desk",
            entrance_position=entrance_position,
            entrance_visible=(
                visible if scene.inventory_confirmed or visible is not True else None
            ),
            entrance_direct_line=direct,
            passage_direct_line=(
                passage_direct if passage_direct or scene.inventory_confirmed else None
            ),
            exposed_beam_over_user=beam if beam or scene.inventory_confirmed else None,
            sharp_corner_points_at_user=(
                sharp if sharp or scene.inventory_confirmed else None
            ),
            solid_backing=(
                (backing is not None)
                if backing is not None or scene.inventory_confirmed
                else None
            ),
            backing_distance_m=(
                backing if scene.observation_basis != "image_observed" else None
            ),
            window_position=window_position,
            observation_basis=scene.observation_basis,
            evidence=f"workstation_layout_v1:{scene.frame_id}; supplied geometry only; {scene.evidence}",
        )
        form = (
            FormObservation.model_validate(observed)
            if any(
                observed[key] is not None
                for key in (
                    "entrance_visible",
                    "entrance_direct_line",
                    "passage_direct_line",
                    "exposed_beam_over_user",
                    "sharp_corner_points_at_user",
                    "solid_backing",
                    "window_position",
                )
            )
            else None
        )
        locations = []
        facings = []
        binding: Literal[
            "confirmed", "candidate_only", "not_bound", "at_sector_origin"
        ] = "not_bound"
        if scene.compass:
            compass = scene.compass
            anchor = position if seat.sector_anchor == "seat" else desk.footprint.center
            distance = hypot(
                anchor.x - compass.sector_origin.x, anchor.y - compass.sector_origin.y
            )
            if distance <= scene.coordinate_uncertainty_m:
                binding = "at_sector_origin"
            else:
                locations = location_support(scene, anchor)
                binding = (
                    "confirmed"
                    if (
                        compass.chart_binding_confirmed
                        and len(locations) == 1
                        and scene.observation_basis != "image_observed"
                    )
                    else (
                        "candidate_only"
                        if compass.chart_binding_confirmed
                        else "not_bound"
                    )
                )
            facings = direction_support(
                facing + compass.y_axis_bearing_degrees, compass.uncertainty_degrees
            )
        seats.append(
            SeatGeometry(
                desk_id=seat.desk_id,
                subject_ids=seat.subject_ids,
                position=position,
                plan_facing_degrees=facing,
                sector_anchor=seat.sector_anchor,
                location_directions=locations,
                facing_directions=facings,
                chart_binding_status=binding,
                form=form,
                backing_distance_m=backing,
                barriers_between=barriers,
                entrance_relative_positions=entry_positions,
                window_relative_positions=window_positions,
            )
        )
    for (left_id, (left_user, left_operating)), (
        right_id,
        (right_user, right_operating),
    ) in combinations(occupied.items(), 2):
        checks.extend(
            [
                GeometryCheck(
                    check_id="seats_disjoint",
                    object_ids=[left_id, right_id],
                    passed=left_user.intersection(right_user).area <= AREA_EPSILON,
                ),
                GeometryCheck(
                    check_id="operating_zones_disjoint",
                    object_ids=[left_id, right_id],
                    passed=left_operating.intersection(right_operating).area
                    <= AREA_EPSILON,
                ),
                GeometryCheck(
                    check_id="other_seat_operating_zone_clear",
                    object_ids=[left_id, right_id],
                    passed=left_user.intersection(right_operating).area <= AREA_EPSILON
                    and right_user.intersection(left_operating).area <= AREA_EPSILON,
                ),
            ]
        )
    screen_visibility, screen_checks = evaluate_screens(scene, seats)
    checks.extend(screen_checks)
    return EvaluatedGeometry(
        seats=seats,
        checks=checks,
        desktop_placements=desktop_placements,
        candidate_only=scene.observation_basis == "image_observed"
        or scene.coordinate_uncertainty_m > 0,
        body_sectors={
            body.object_id: location_support(scene, body.footprint.center)
            for body in scene.bodies
        },
        screen_visibility=screen_visibility,
    )
