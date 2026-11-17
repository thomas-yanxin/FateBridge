"""Planar geometry and explicit height intervals; no Feng Shui verdicts."""

from dataclasses import dataclass
from fractions import Fraction
from math import hypot, lcm

from shapely import affinity, get_coordinates
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import nearest_points

from .spatial_angles import (
    DIRECTIONS,
    Angle,
    CompassDirection,
    _atan_degrees,
    _sin_cos_degrees,
    angular_offset,
    angular_radius,
    compose_degrees,
    direction_support,
)
from .spatial_inputs import PlanPoint, PlanPolygon, PlanPose, PlanRectangle, PlanSegment

# Numerical roundoff only. This is not a sourced distance or auspiciousness rule.
AREA_EPSILON = 1e-12


@dataclass(frozen=True)
class GeometryFrame:
    """Internal working frame; public degree floats are presentation only."""

    center: PlanPoint
    rotation_degrees: Fraction


@dataclass(frozen=True)
class GeometryRectangle(GeometryFrame):
    width_m: float
    depth_m: float


def point_xy(point: PlanPoint) -> Point:
    return Point(point.x, point.y)


def polygon_xy(polygon: PlanPolygon) -> Polygon:
    return Polygon([(p.x, p.y) for p in polygon.vertices])


def rectangle_xy(rectangle: PlanRectangle | GeometryRectangle) -> Polygon:
    shape = box(
        -rectangle.width_m / 2,
        -rectangle.depth_m / 2,
        rectangle.width_m / 2,
        rectangle.depth_m / 2,
    )
    sine, cosine = _sin_cos_degrees(rectangle.rotation_degrees)
    return affinity.affine_transform(
        shape,
        [cosine, sine, -sine, cosine, rectangle.center.x, rectangle.center.y],
    )


def transform_point(local: PlanPoint, frame: PlanPose | GeometryFrame) -> PlanPoint:
    sine, cosine = _sin_cos_degrees(frame.rotation_degrees)
    return PlanPoint(
        x=frame.center.x + local.x * cosine + local.y * sine,
        y=frame.center.y - local.x * sine + local.y * cosine,
    )


def transform_rectangle(
    local: PlanRectangle | GeometryRectangle, frame: PlanPose | GeometryFrame
) -> GeometryRectangle:
    return GeometryRectangle(
        center=transform_point(local.center, frame),
        rotation_degrees=compose_degrees(
            local.rotation_degrees, frame.rotation_degrees
        ),
        width_m=local.width_m,
        depth_m=local.depth_m,
    )


def inverse_point(world: PlanPoint, frame: PlanPose | GeometryFrame) -> PlanPoint:
    sine, cosine = _sin_cos_degrees(frame.rotation_degrees)
    x, y = world.x - frame.center.x, world.y - frame.center.y
    return PlanPoint(
        x=x * cosine - y * sine,
        y=x * sine + y * cosine,
    )


def segment_xy(segment: PlanSegment) -> LineString:
    return LineString(
        [(segment.start.x, segment.start.y), (segment.end.x, segment.end.y)]
    )


def point_on_segment(point: PlanPoint, segment: PlanSegment) -> bool:
    """Exact closed membership, including the segment's endpoints."""
    ax, ay = (
        Fraction(segment.start.x) - Fraction(point.x),
        Fraction(segment.start.y) - Fraction(point.y),
    )
    bx, by = (
        Fraction(segment.end.x) - Fraction(point.x),
        Fraction(segment.end.y) - Fraction(point.y),
    )
    return ax * by == ay * bx and ax * bx + ay * by <= 0


def heading(start: PlanPoint, end: PlanPoint) -> Fraction | None:
    """Clockwise from +y; a coincident point pair has no direction.

    Subtract original coordinates exactly, then reduce about the nearest axis
    or diagonal before evaluating atan. A tiny deviation remains a small
    argument instead of disappearing into a rounded quarter-turn.
    """
    dx, dy = Fraction(end.x) - Fraction(start.x), Fraction(end.y) - Fraction(start.y)
    if dx == dy == 0:
        return None
    if abs(dy) >= abs(dx):
        base, ratio = (0 if dy > 0 else 180), dx / dy
    else:
        base, ratio = (90 if dx > 0 else 270), -dy / dx
    if abs(ratio) > Fraction(1, 2):
        sign = 1 if ratio > 0 else -1
        base += sign * 45
        ratio = (ratio - sign) / (1 + sign * ratio)
    return compose_degrees(base, _atan_degrees(ratio))


def footprint_direction_support(
    footprint: Polygon,
    frame_bearing: Angle,
    coordinate_uncertainty: float,
    compass_uncertainty: float,
) -> list[CompassDirection]:
    """Angular support of a convex footprint and its translating error disc.

    The enlarged footprint is the convex hull of its vertex discs. When it
    excludes the origin, their angular extremes delimit the same visible arc.
    Reaching the origin retains the existing unbound all-directions policy.
    """
    points = [PlanPoint(x=x, y=y) for x, y in list(footprint.exterior.coords)[:-1]]
    vertices = [(Fraction(p.x), Fraction(p.y)) for p in points]
    crosses = []
    distances = []
    for (ax, ay), (bx, by) in zip(vertices, vertices[1:] + vertices[:1]):
        crosses.append(ax * by - ay * bx)
        dx, dy = bx - ax, by - ay
        projection = ax * dx + ay * dy
        length = dx * dx + dy * dy
        distances.append(
            ax * ax + ay * ay
            if projection >= 0
            else (
                bx * bx + by * by
                if -projection >= length
                else ax * ax + ay * ay - projection * projection / length
            )
        )
    if (
        sum(crosses) != 0
        and (all(v >= 0 for v in crosses) or all(v <= 0 for v in crosses))
    ) or min(distances) <= Fraction(coordinate_uncertainty) ** 2:
        return list(DIRECTIONS)
    origin = PlanPoint(x=0, y=0)
    base = heading(origin, points[0])
    assert base is not None
    intervals = []
    for point, (x, y) in zip(points, vertices):
        bearing = heading(origin, point)
        assert bearing is not None
        delta = angular_offset(bearing, base)
        radius = angular_radius(coordinate_uncertainty, x * x + y * y)
        intervals.append((delta - radius, delta + radius))
    lower = min(a for a, _ in intervals)
    upper = max(b for _, b in intervals)
    return direction_support(
        compose_degrees(base, (lower + upper) / 2, frame_bearing),
        min(Fraction(180), (upper - lower) / 2 + Fraction(compass_uncertainty)),
    )


def ray_xy(start: PlanPoint, bearing: Angle, reach: float) -> LineString:
    sine, cosine = _sin_cos_degrees(bearing)
    return LineString(
        [
            (start.x, start.y),
            (start.x + reach * sine, start.y + reach * cosine),
        ]
    )


def swept_segment(segment: PlanSegment, bearing: Angle, reach: float) -> Polygon:
    sine, cosine = _sin_cos_degrees(bearing)
    dx, dy = reach * sine, reach * cosine
    return Polygon(
        [
            (segment.start.x, segment.start.y),
            (segment.end.x, segment.end.y),
            (segment.end.x + dx, segment.end.y + dy),
            (segment.start.x + dx, segment.start.y + dy),
        ]
    )


def entrance_visible(
    observer: PlanPoint,
    facing: Angle,
    half_angle: float,
    entrance: PlanSegment,
    blockers: list[Polygon | LineString],
    reach: float,
) -> bool | None:
    """Test cells bounded by vertices and target/obstacle intersections.

    A positive-width visible part of the opening must remain in the declared
    field of view. Heights have already selected the opaque blockers.
    """
    if point_on_segment(observer, entrance):
        return None
    target = segment_xy(entrance)
    source = point_xy(observer)
    critical = {Fraction(-half_angle), Fraction(half_angle)}
    vertices = [entrance.start, entrance.end]
    for blocker in blockers:
        coordinates = (
            blocker.exterior.coords if isinstance(blocker, Polygon) else blocker.coords
        )
        vertices.extend(PlanPoint(x=x, y=y) for x, y in coordinates)
        vertices.extend(
            PlanPoint(x=x, y=y)
            for x, y in get_coordinates(blocker.intersection(target))
        )
    for vertex in vertices:
        bearing = heading(observer, vertex)
        if bearing is None:
            continue
        delta = angular_offset(bearing, facing)
        if -half_angle < delta < half_angle:
            critical.add(delta)
    angles = sorted(critical)
    for left, right in zip(angles, angles[1:]):
        ray = ray_xy(
            observer,
            compose_degrees(facing, (Fraction(left) + Fraction(right)) / 2),
            reach,
        )
        intersection = ray.intersection(target)
        if intersection.is_empty:
            continue
        distance = source.distance(nearest_points(source, intersection)[1])
        if distance > 0 and all(
            (hit := ray.intersection(blocker)).is_empty
            or source.distance(nearest_points(source, hit)[1]) >= distance
            for blocker in blockers
        ):
            return True
    return False


def _ray_parameter(
    origin: tuple[Fraction, Fraction],
    vector: tuple[Fraction, Fraction],
    vertices: list[tuple[Fraction, Fraction]],
    reach_squared: Fraction,
) -> Fraction | None:
    """Nearest closed convex-set hit, with exact Euclidean finite reach.

    Vertices are ordered around the convex footprint, or describe a segment
    or point. A shared positive integer scale keeps half-plane signs exact.
    Bounding half-planes also delimit degenerate segments and point targets.
    """
    if not vertices:
        return None
    coordinates = (origin, vector, *vertices)
    scale = lcm(*(value.denominator for point in coordinates for value in point))
    (ox, oy), (vx, vy), *polygon = [
        (x.numerator * (scale // x.denominator), y.numerator * (scale // y.denominator))
        for x, y in coordinates
    ]
    xmin, xmax = min(p[0] for p in polygon), max(p[0] for p in polygon)
    ymin, ymax = min(p[1] for p in polygon), max(p[1] for p in polygon)
    bounds = [(vx, ox - xmin), (-vx, xmax - ox), (vy, oy - ymin), (-vy, ymax - oy)]
    edges = list(zip(polygon, polygon[1:] + polygon[:1]))
    area = sum(ax * by - ay * bx for (ax, ay), (bx, by) in edges)
    orientation = 1 if area >= 0 else -1
    for (ax, ay), (bx, by) in edges:
        dx, dy = bx - ax, by - ay
        bounds.append(
            (
                orientation * (dx * vy - dy * vx),
                orientation * (dx * (oy - ay) - dy * (ox - ax)),
            )
        )
    lower, upper = Fraction(0), None
    for slope, offset in bounds:
        if slope == 0:
            if offset < 0:
                return None
            continue
        bound = Fraction(-offset, slope)
        if slope > 0:
            lower = max(lower, bound)
        elif upper is None or bound < upper:
            upper = bound
        if upper is not None and upper < lower:
            return None
    if lower * lower * (vx * vx + vy * vy) <= reach_squared * scale * scale:
        return lower
    return None


def rear_backing_distance(
    observer: PlanPoint, facing: Angle, segments: list[PlanSegment], reach: float
) -> float | None:
    sine, cosine = _sin_cos_degrees(facing)
    origin = Fraction(observer.x), Fraction(observer.y)
    vector = Fraction(-sine), Fraction(-cosine)
    reach_squared = Fraction(reach) ** 2
    parameters = [
        parameter
        for segment in segments
        if (
            parameter := _ray_parameter(
                origin,
                vector,
                [
                    (Fraction(segment.start.x), Fraction(segment.start.y)),
                    (Fraction(segment.end.x), Fraction(segment.end.y)),
                ],
                reach_squared,
            )
        )
        is not None
    ]
    if not parameters:
        return None
    nearest = min(parameters)
    return hypot(float(nearest * vector[0]), float(nearest * vector[1]))


def corner_points_at(
    rectangle: PlanRectangle | GeometryRectangle, target: Polygon, reach: float
) -> bool:
    """Radial corner rays against the closed convex seated footprint."""
    sine_value, cosine_value = _sin_cos_degrees(rectangle.rotation_degrees)
    sine, cosine = Fraction(sine_value), Fraction(cosine_value)
    cx, cy = Fraction(rectangle.center.x), Fraction(rectangle.center.y)
    half_width, half_depth = (
        Fraction(rectangle.width_m) / 2,
        Fraction(rectangle.depth_m) / 2,
    )
    vertices = [(Fraction(x), Fraction(y)) for x, y in target.exterior.coords[:-1]]
    reach_squared = Fraction(reach) ** 2
    for x in (-half_width, half_width):
        for y in (-half_depth, half_depth):
            vx, vy = x * cosine + y * sine, -x * sine + y * cosine
            if (
                _ray_parameter((cx + vx, cy + vy), (vx, vy), vertices, reach_squared)
                is not None
            ):
                return True
    return False


def movement_distance(before: PlanPose, after: PlanPose) -> float:
    return hypot(after.center.x - before.center.x, after.center.y - before.center.y)
