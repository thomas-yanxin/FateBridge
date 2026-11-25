"""Perspective area occlusion of declared vertical displays by opaque prisms.

Intersect each prism with the eye-to-display depth slab, then intersect the
display with its convex shadow cone. No point/ray sampling is used: a narrow
obstruction between the display's corners still contributes its projected area.
"""

from fractions import Fraction
from math import lcm

from shapely.geometry import Polygon, box
from shapely.ops import unary_union

from fatebridge.core.fengshui.spatial_angles import (
    _sin_cos_degrees,
    angular_offset,
    compose_degrees,
)
from fatebridge.core.fengshui.spatial_geometry import (
    AREA_EPSILON,
    heading,
    rectangle_xy,
    transform_point,
    transform_rectangle,
)
from fatebridge.core.fengshui.spatial_inputs import PlanPoint, SpatialScene
from fatebridge.core.fengshui.spatial_outputs import (
    GeometryCheck,
    ScreenVisibility,
    SeatGeometry,
)


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
    """Clip the exact prism cone; its silhouette planes contain prism edges.

    A magnitude tolerance can merge distinct faces of a thin prism and then
    remove the wrong half of the display. Keep side predicates and clipping
    rational; only the resulting planar coordinates return to binary64.
    """
    eye_x, eye_y = Fraction(eye.x), Fraction(eye.y)
    right_x, right_y = map(Fraction, right)
    forward_x, forward_y = map(Fraction, forward)
    clipped = [
        (
            (Fraction(x) - eye_x) * right_x + (Fraction(y) - eye_y) * right_y,
            (Fraction(x) - eye_x) * forward_x + (Fraction(y) - eye_y) * forward_y,
        )
        for x, y in list(footprint.exterior.coords)[:-1]
    ]
    depth = Fraction(distance)
    for boundary, direction in ((Fraction(0), 1), (depth, -1)):
        result: list[tuple[Fraction, Fraction]] = []
        for start, end in zip(clipped, clipped[1:] + clipped[:1]):
            before = direction * (start[1] - boundary)
            after = direction * (end[1] - boundary)
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
        clipped = list(dict.fromkeys(result))
    if len(clipped) < 2 or max(d for _, d in clipped) <= 0:
        return Polygon()
    low, high = Fraction(bottom) - Fraction(eye_height), Fraction(top) - Fraction(
        eye_height
    )
    vertices = [(u, z, d) for u, d in clipped for z in (low, high)]
    # One positive common scale preserves the cone and makes all side tests
    # integer determinants, without repeated rational arithmetic per edge.
    scale = lcm(*(value.denominator for point in vertices for value in point))
    rays = [
        (
            u.numerator * (scale // u.denominator),
            z.numerator * (scale // z.denominator),
            d.numerator * (scale // d.denominator),
        )
        for u, z, d in vertices
    ]
    lower, upper = rays[::2], rays[1::2]
    edges = list(zip(lower, upper))
    for layer in (lower, upper):
        edges.extend(zip(layer, layer[1:] + layer[:1]))
    polygon = [
        (Fraction(x), Fraction(y)) for x, y in list(display.exterior.coords)[:-1]
    ]
    for left, right_vertex in edges:
        a = left[1] * right_vertex[2] - left[2] * right_vertex[1]
        b = left[2] * right_vertex[0] - left[0] * right_vertex[2]
        c = left[0] * right_vertex[1] - left[1] * right_vertex[0]
        if a == b == c == 0:
            continue
        values = [a * u + b * z + c * d for u, z, d in rays]
        if not any(values):
            # All rays lie in one plane through the eye: zero projected area.
            return Polygon()
        if min(values) >= 0:
            pass
        elif max(values) <= 0:
            a, b, c = -a, -b, -c
        else:
            continue
        result = []
        for start, end in zip(polygon, polygon[1:] + polygon[:1]):
            before = a * start[0] + b * start[1] + c * depth
            after = a * end[0] + b * end[1] + c * depth
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
    return Polygon([(float(x), float(y)) for x, y in polygon])


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
            normal = compose_degrees(item_frame.rotation_degrees, screen.front_degrees)
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
                (bearing := heading(observer.position, endpoint)) is not None
                and abs(
                    angular_offset(
                        bearing,
                        compose_degrees(
                            desk.footprint.rotation_degrees, seat.facing_offset_degrees
                        ),
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
