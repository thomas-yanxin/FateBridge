"""Planar geometry and explicit height intervals; no Feng Shui verdicts."""

from fractions import Fraction
from math import atan2, cos, degrees, fmod, hypot, radians, remainder, sin

from shapely import affinity
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import nearest_points

from .spatial_inputs import (
    CompassDirection,
    PlanPoint,
    PlanPolygon,
    PlanPose,
    PlanRectangle,
    PlanSegment,
)

DIRECTIONS: tuple[CompassDirection, ...] = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")
# Numerical roundoff only. This is not a sourced distance or auspiciousness rule.
AREA_EPSILON = 1e-12


def _sin_cos_degrees(angle: float) -> tuple[float, float]:
    angle = remainder(angle, 360)
    if angle == 0:
        return 0.0, 1.0
    if angle == 90:
        return 1.0, 0.0
    if angle == -90:
        return -1.0, 0.0
    if abs(angle) == 180:
        return 0.0, -1.0
    value = radians(angle)
    return sin(value), cos(value)


def point_xy(point: PlanPoint) -> Point:
    return Point(point.x, point.y)


def polygon_xy(polygon: PlanPolygon) -> Polygon:
    return Polygon([(p.x, p.y) for p in polygon.vertices])


def rectangle_xy(rectangle: PlanRectangle) -> Polygon:
    shape = box(
        -rectangle.width_m / 2,
        -rectangle.depth_m / 2,
        rectangle.width_m / 2,
        rectangle.depth_m / 2,
    )
    return affinity.translate(
        affinity.rotate(
            shape, -remainder(rectangle.rotation_degrees, 360), origin=(0, 0)
        ),
        rectangle.center.x,
        rectangle.center.y,
    )


def transform_point(local: PlanPoint, frame: PlanPose) -> PlanPoint:
    sine, cosine = _sin_cos_degrees(frame.rotation_degrees)
    return PlanPoint(
        x=frame.center.x + local.x * cosine + local.y * sine,
        y=frame.center.y - local.x * sine + local.y * cosine,
    )


def transform_rectangle(local: PlanRectangle, frame: PlanPose) -> PlanRectangle:
    return local.model_copy(
        update=dict(
            center=transform_point(local.center, frame),
            rotation_degrees=fmod(local.rotation_degrees, 360)
            + fmod(frame.rotation_degrees, 360),
        )
    )


def inverse_point(world: PlanPoint, frame: PlanPose) -> PlanPoint:
    return transform_point(
        PlanPoint(x=world.x - frame.center.x, y=world.y - frame.center.y),
        PlanPose(center=PlanPoint(x=0, y=0), rotation_degrees=-frame.rotation_degrees),
    )


def segment_xy(segment: PlanSegment) -> LineString:
    return LineString(
        [(segment.start.x, segment.start.y), (segment.end.x, segment.end.y)]
    )


def heading(start: PlanPoint, end: PlanPoint) -> float:
    return degrees(atan2(end.x - start.x, end.y - start.y)) % 360


def ray_xy(start: PlanPoint, bearing: float, reach: float) -> LineString:
    sine, cosine = _sin_cos_degrees(bearing)
    return LineString(
        [
            (start.x, start.y),
            (start.x + reach * sine, start.y + reach * cosine),
        ]
    )


def swept_segment(segment: PlanSegment, bearing: float, reach: float) -> Polygon:
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


def angular_delta(left: float, right: float) -> float:
    return (left - right + 180) % 360 - 180


def direction_support(bearing: float, radius: float) -> list[CompassDirection]:
    """Closed uncertainty interval; an exact point uses left-closed cells."""
    center = Fraction(bearing) % 360
    if radius == 0:
        return [DIRECTIONS[int((center + Fraction(45, 2)) // 45) % 8]]
    lower, upper = center - Fraction(radius), center + Fraction(radius)
    return [
        direction
        for i, direction in enumerate(DIRECTIONS)
        if any(
            max(lower, i * 45 - Fraction(45, 2) + turn * 360)
            <= min(upper, i * 45 + Fraction(45, 2) + turn * 360)
            for turn in (-1, 0, 1)
        )
    ]


def entrance_visible(
    observer: PlanPoint,
    facing: float,
    half_angle: float,
    entrance: PlanSegment,
    blockers: list[Polygon | LineString],
    reach: float,
) -> bool:
    """Test angular cells bounded by all obstacle vertices, not pixel sampling.

    A positive-width visible part of the opening must remain in the declared
    field of view. Heights have already selected the opaque blockers.
    """
    target = segment_xy(entrance)
    source = point_xy(observer)
    critical = {-half_angle, half_angle}
    vertices = [entrance.start, entrance.end]
    for blocker in blockers:
        coordinates = (
            blocker.exterior.coords if isinstance(blocker, Polygon) else blocker.coords
        )
        vertices.extend(PlanPoint(x=x, y=y) for x, y in coordinates)
    for vertex in vertices:
        delta = angular_delta(heading(observer, vertex), facing)
        if -half_angle < delta < half_angle:
            critical.add(delta)
    angles = sorted(critical)
    for left, right in zip(angles, angles[1:]):
        ray = ray_xy(observer, facing + (left + right) / 2, reach)
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


def rear_backing_distance(
    observer: PlanPoint, facing: float, segments: list[PlanSegment], reach: float
) -> float | None:
    ray, source = ray_xy(observer, facing + 180, reach), point_xy(observer)
    distances = [
        source.distance(hit)
        for segment in segments
        if not (hit := ray.intersection(segment_xy(segment))).is_empty
    ]
    return min(distances) if distances else None


def corner_points_at(rectangle: PlanRectangle, target: Polygon, reach: float) -> bool:
    for x, y in list(rectangle_xy(rectangle).exterior.coords)[:-1]:
        corner = PlanPoint(x=x, y=y)
        if ray_xy(corner, heading(rectangle.center, corner), reach).intersects(target):
            return True
    return False


def movement_distance(before: PlanPose, after: PlanPose) -> float:
    return hypot(after.center.x - before.center.x, after.center.y - before.center.y)
