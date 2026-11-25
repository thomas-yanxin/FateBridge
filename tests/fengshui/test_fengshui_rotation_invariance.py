"""Analytic planar controls: full turns and exact right angles are identical."""

import math
from fractions import Fraction

import pytest

from fatebridge.core.fengshui.spatial_geometry import (
    ray_xy,
    rectangle_xy,
    swept_segment,
    transform_point,
    transform_rectangle,
)
from fatebridge.core.fengshui.spatial_inputs import (
    PlanPoint,
    PlanPose,
    PlanRectangle,
    PlanSegment,
)
from fatebridge.services.fengshui import assess
from tests.support.transports import SPECS, business, rest, surface_calls
from tests.unit_test.fixtures.fengshui_measured import rotation_payload as payload_for


@pytest.mark.parametrize("angle", [-1080, -720, -360, 0, 360, 720, 1080])
def test_full_turns_preserve_closed_rectangle_and_coordinate_operations(angle) -> None:
    frame = PlanPose(center=PlanPoint(x=1, y=2), rotation_degrees=angle)
    rectangle = PlanRectangle(**frame.model_dump(), width_m=2, depth_m=1)
    assert rectangle_xy(rectangle).bounds == (0, 1.5, 2, 2.5)
    seat = transform_point(PlanPoint(x=0, y=-1.2), frame)
    assert (seat.x, seat.y) == (1, 0.8)
    assert list(ray_xy(frame.center, angle, 2).coords) == [(1, 2), (1, 4)]
    opening = PlanSegment(start=PlanPoint(x=0, y=0), end=PlanPoint(x=2, y=0))
    swept = swept_segment(opening, angle, 1)
    assert swept.bounds == (0, 0, 2, 1)
    assert swept.area == 2


@pytest.mark.parametrize(
    "angle,point,ray_end",
    [
        (0, (1, 0), (0, 2)),
        (90, (0, -1), (2, 0)),
        (180, (-1, 0), (0, -2)),
        (270, (0, 1), (-2, 0)),
    ],
)
def test_exact_cardinal_components_keep_their_analytic_coordinates(
    angle: int, point, ray_end
) -> None:
    origin = PlanPoint(x=0, y=0)
    result = transform_point(
        PlanPoint(x=1, y=0), PlanPose(center=origin, rotation_degrees=angle)
    )
    assert (result.x, result.y) == point
    assert list(ray_xy(origin, angle, 2).coords) == [(0, 0), ray_end]


def test_two_finite_rotation_angles_compose_without_overflow() -> None:
    angle = 1e308
    rectangle = PlanRectangle(
        center=PlanPoint(x=0, y=0), width_m=1, depth_m=1, rotation_degrees=angle
    )
    combined = transform_rectangle(
        rectangle, PlanPose(center=PlanPoint(x=0, y=0), rotation_degrees=angle)
    )
    assert math.isfinite(combined.rotation_degrees)
    assert Fraction(combined.rotation_degrees) % 360 == (Fraction(angle) * 2) % 360


@pytest.mark.parametrize("angle,x,width", [(0, 1, 2), (720, 1, 2), (180, 0.25, 0.5)])
def test_analytic_closed_room_retains_desk_and_seat_on_its_boundary(
    angle: int, x: float | int, width: float | int
) -> None:
    result = assess(**payload_for(angle, x, width))
    geometry = result["layout_analysis"]["workstation_layout_analysis"]["geometry"]
    assert geometry["physically_feasible"] is True, geometry["checks"]
    assert all(check["passed"] is True for check in geometry["checks"])


@pytest.mark.parametrize("angle,x,width", [(720, 1, 2), (180, 0.25, 0.5)])
def test_rotation_boundary_facts_agree_on_actual_three_transports(
    angle: int, x: float | int, width: float | int, surface_calls
) -> None:
    spec = SPECS["fengshui_assess"]
    payload = payload_for(angle, x, width)
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
    assert (
        actual["layout_analysis"]["workstation_layout_analysis"]["geometry"][
            "physically_feasible"
        ]
        is True
    )
