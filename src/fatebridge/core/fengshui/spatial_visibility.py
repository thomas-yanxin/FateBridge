"""Perspective area occlusion of declared vertical displays by opaque prisms.

Intersect each prism with the eye-to-display depth slab, then intersect the
display with its convex shadow cone. No point/ray sampling is used: a narrow
obstruction between the display's corners still contributes its projected area.
"""

from itertools import combinations
from math import sqrt

from shapely.geometry import LineString, Polygon, box
from shapely.ops import unary_union

from .spatial_geometry import (
    AREA_EPSILON,
    _sin_cos_degrees,
    angular_delta,
    heading,
    rectangle_xy,
    transform_point,
    transform_rectangle,
)
from .spatial_inputs import PlanPoint, SpatialScene
from .spatial_outputs import GeometryCheck, ScreenVisibility, SeatGeometry


def _shadow(
    footprint: Polygon,
    bottom: float,
    top: float,
    eye: PlanPoint,
    eye_height: float,
    right: tuple[float, float],
    forward: tuple[float, float],
    distance: float,
    display: Polygon,
) -> Polygon:
    planar = Polygon(
        [
            (
                (x - eye.x) * right[0] + (y - eye.y) * right[1],
                (x - eye.x) * forward[0] + (y - eye.y) * forward[1],
            )
            for x, y in list(footprint.exterior.coords)[:-1]
        ]
    )
    xmin, _, xmax, _ = planar.bounds
    clipped = planar.intersection(box(xmin, 0, xmax, distance))
    if clipped.is_empty:
        return Polygon()
    if isinstance(clipped, Polygon):
        coordinates = list(clipped.exterior.coords)[:-1]
    elif isinstance(clipped, LineString):
        coordinates = list(clipped.coords)
    else:
        # Convex polygon/closed-slab intersection is convex and connected.
        return Polygon()
    if max(depth for _, depth in coordinates) <= 0:
        return Polygon()
    vertices = [
        (u, z - eye_height, depth) for u, depth in coordinates for z in (bottom, top)
    ]
    polygon = list(display.exterior.coords)[:-1]
    for left, right_vertex in combinations(vertices, 2):
        a = left[1] * right_vertex[2] - left[2] * right_vertex[1]
        b = left[2] * right_vertex[0] - left[0] * right_vertex[2]
        c = left[0] * right_vertex[1] - left[1] * right_vertex[0]
        length = sqrt(a * a + b * b + c * c)
        if length == 0:
            continue
        a, b, c = a / length, b / length, c / length
        values = [a * u + b * z + c * depth for u, z, depth in vertices]
        # A supporting plane contains every prism ray on the same side.
        if min(values) >= -1e-10:
            pass
        elif max(values) <= 1e-10:
            a, b, c = -a, -b, -c
        else:
            continue
        result = []
        for start, end in zip(polygon, polygon[1:] + polygon[:1]):
            before = a * start[0] + b * start[1] + c * distance
            after = a * end[0] + b * end[1] + c * distance
            if before >= 0:
                result.append(start)
            if (before >= 0) != (after >= 0):
                fraction = before / (before - after)
                result.append(
                    (
                        start[0] + fraction * (end[0] - start[0]),
                        start[1] + fraction * (end[1] - start[1]),
                    )
                )
        polygon = result
        if len(polygon) < 3:
            return Polygon()
    return Polygon(polygon)


def evaluate_screens(
    scene: SpatialScene, seats: list[SeatGeometry]
) -> tuple[list[ScreenVisibility], list[GeometryCheck]]:
    bodies = {b.object_id: b for b in scene.bodies}
    seat_inputs = {s.desk_id: s for s in scene.seats}
    seat_geometry = {s.desk_id: s for s in seats}
    blockers = [
        (b.object_id, rectangle_xy(b.footprint), b.bottom_m, b.top_m)
        for b in scene.bodies
        if b.blocks_view
    ]
    for desktop in scene.desktops:
        desk = bodies[desktop.desk_id]
        blockers.extend(
            (
                i.object_id,
                rectangle_xy(transform_rectangle(i.footprint, desk.footprint)),
                desk.top_m,
                desk.top_m + i.height_m,
            )
            for i in desktop.items
            if i.blocks_view
        )
    observations, checks = [], []
    for desktop in scene.desktops:
        desk = bodies[desktop.desk_id]
        for item in desktop.items:
            screen = item.screen
            if screen is None:
                continue
            seat, observer = (
                seat_inputs[desktop.desk_id],
                seat_geometry[desktop.desk_id],
            )
            item_frame = transform_rectangle(item.footprint, desk.footprint)
            center = transform_point(screen.center, item_frame)
            normal = item_frame.rotation_degrees + screen.front_degrees
            sine, cosine = _sin_cos_degrees(normal)
            right, forward = (cosine, -sine), (-sine, -cosine)
            depth = (center.x - observer.position.x) * forward[0] + (
                center.y - observer.position.y
            ) * forward[1]
            front_facing = depth > 0
            endpoints = [
                PlanPoint(
                    x=center.x + sign * screen.width_m / 2 * right[0],
                    y=center.y + sign * screen.width_m / 2 * right[1],
                )
                for sign in (-1, 1)
            ]
            in_view = all(
                abs(
                    angular_delta(
                        heading(observer.position, endpoint),
                        observer.plan_facing_degrees,
                    )
                )
                <= seat.view_half_angle_degrees
                for endpoint in endpoints
            )
            bottom = desk.top_m + screen.bottom_above_desktop_m
            center_u = (center.x - observer.position.x) * right[0] + (
                center.y - observer.position.y
            ) * right[1]
            display = box(
                center_u - screen.width_m / 2,
                bottom - seat.eye_height_m,
                center_u + screen.width_m / 2,
                bottom + screen.height_m - seat.eye_height_m,
            )
            shadows, ids = [], []
            if front_facing:
                for object_id, shape, low, high in blockers:
                    if object_id == item.object_id:
                        continue
                    shadow = _shadow(
                        shape,
                        low,
                        high,
                        observer.position,
                        seat.eye_height_m,
                        right,
                        forward,
                        depth,
                        display,
                    )
                    if shadow.area > AREA_EPSILON:
                        shadows.append(shadow)
                        ids.append(object_id)
            occluded = unary_union(shadows).area if shadows else 0.0
            fraction = (
                max(0.0, min(1.0, 1 - occluded / display.area)) if front_facing else 0.0
            )
            unobstructed = not ids if ids or scene.inventory_confirmed else None
            observation = ScreenVisibility(
                desk_id=desktop.desk_id,
                object_id=item.object_id,
                front_facing=front_facing,
                in_horizontal_view=in_view,
                model_visible_fraction=fraction,
                unobstructed=unobstructed,
                blocking_object_ids=ids,
                required_visible=screen.required_visible,
                candidate_only=scene.observation_basis == "image_observed"
                or scene.coordinate_uncertainty_m > 0,
            )
            observations.append(observation)
            if screen.required_visible:
                for check_id, passed in (
                    ("screen_front_facing", front_facing),
                    ("screen_in_horizontal_view", in_view),
                    ("screen_unobstructed", unobstructed),
                ):
                    checks.append(
                        GeometryCheck(
                            check_id=check_id,
                            object_ids=[desktop.desk_id, item.object_id],
                            passed=passed,
                        )
                    )
    return observations, checks
