"""Independent geometric controls for generated domains and display shadows."""

import asyncio
import json
from copy import deepcopy

import pytest
from pydantic import ValidationError

from fatebridge.application.execution import OutputContractError, validate_output
from fatebridge.cli import run
from fatebridge.core.fengshui.models import AssessRequest
from fatebridge.core.fengshui.output import FengshuiOutput
from fatebridge.core.fengshui.spatial_geometry import transform_point
from fatebridge.core.fengshui.spatial_inputs import PlanPoint, PlanPose, SpatialScene
from fatebridge.core.fengshui.spatial_scene import evaluate_geometry
from fatebridge.services.fengshui import assess
from fatebridge.services.tool_catalog import CATALOG
from tests.fengshui.test_fengshui_measured_workstation import (
    body,
    measured_request,
    measured_result,
)
from tests.fengshui.test_fengshui_surfaces import (
    mcp_call,
    rest_client,
    without_transport,
)


def screen_request():
    request = measured_request()
    scene = request["workstation_layout"]["scene"]
    scene.pop("compass")
    scene["openings"] = []
    scene["solid_backing_segments"] = []
    scene["bodies"] = [body("desk", "desk", 0, 0, 2, 1, 0, 0.75)]
    scene["seats"][0].update(offset=dict(x=0, y=-2), entrance_id=None)
    scene["seats"][0]["operating_zone"]["center"] = dict(x=0, y=-2)
    scene["desktops"] = [
        dict(
            desk_id="desk",
            ruleset_ids=[],
            items=[
                dict(
                    object_id="display",
                    footprint=dict(center=dict(x=0, y=0), width_m=0.8, depth_m=0.1),
                    height_m=0.8,
                    blocks_view=True,
                    representation="other",
                    representation_basis="measured",
                    evidence="Synthetic display; no placement prescription",
                    screen=dict(
                        center=dict(x=0, y=0),
                        front_degrees=180,
                        width_m=0.8,
                        height_m=0.6,
                        bottom_above_desktop_m=0.2,
                        required_visible=True,
                    ),
                )
            ],
        )
    ]
    request["layout_constraints"] = [
        dict(
            object_id="display",
            can_relocate=True,
            can_rotate=True,
            evidence="Synthetic explicit permission",
        )
    ]
    return request


def screen_geometry(request):
    return evaluate_geometry(
        SpatialScene.model_validate(request["workstation_layout"]["scene"])
    )


def test_chartless_complete_output_requires_present_map_but_allows_empty_layers():
    request = screen_request()
    result = assess(**request)
    spec = next(s for s in CATALOG if s.key == "fengshui_assess")
    assert result["layers"] == {}
    validate_output(spec, result, request=AssessRequest.model_validate(request))
    for changed in ("missing", "null"):
        broken = deepcopy(result)
        if changed == "missing":
            broken.pop("layers")
        else:
            broken["layers"] = None
        with pytest.raises(OutputContractError):
            validate_output(spec, broken)
    # Wire projections may legitimately omit the map after full validation.
    FengshuiOutput.model_validate({"coverage": result["coverage"]})


@pytest.mark.parametrize("replacement", [{}, {"xuankong_natal": None}])
def test_nonempty_declared_chart_layers_cannot_disappear_in_complete_result(
    replacement,
):
    request = measured_request(charts=True)
    result = assess(**request)
    spec = next(s for s in CATALOG if s.key == "fengshui_assess")
    assert result["coverage"]["implemented_layers"]
    result["layers"] = replacement
    with pytest.raises(OutputContractError):
        validate_output(spec, result)


def test_thin_blocker_between_sample_rays_has_exact_projected_area():
    request = screen_request()
    scene = request["workstation_layout"]["scene"]
    scene["bodies"].append(body("thin", "pillar", 0.1, -1, 0.1, 0.1, 0, 2, True))
    observation = screen_geometry(request).screen_visibility[0]
    # Horizontal extrema .05/.1.05 and .15/.95 at depth 1, projected to depth 2.
    width = 2 * (0.15 / 0.95 - 0.05 / 1.05)
    assert observation.model_visible_fraction == pytest.approx(1 - width / 0.8)
    assert observation.blocking_object_ids == ["thin"]
    assert observation.unobstructed is False
    assert observation.front_facing and observation.in_horizontal_view


@pytest.mark.parametrize(
    "center_y,bottom,top", [(1, 0, 2), (-3, 0, 2), (-1, 0, 0.8), (-1, 1.7, 2)]
)
def test_behind_display_behind_eye_or_outside_vertical_rays_cannot_occlude(
    center_y, bottom, top
):
    request = screen_request()
    request["workstation_layout"]["scene"]["bodies"].append(
        body("irrelevant", "pillar", 0, center_y, 0.1, 0.1, bottom, top, True)
    )
    observation = screen_geometry(request).screen_visibility[0]
    assert observation.model_visible_fraction == 1
    assert observation.blocking_object_ids == []


def test_union_does_not_double_count_overlapping_shadows():
    request = screen_request()
    scene = request["workstation_layout"]["scene"]
    scene["bodies"].append(body("first", "pillar", 0.1, -1, 0.1, 0.1, 0, 2, True))
    one = screen_geometry(request).screen_visibility[0].model_visible_fraction
    scene["bodies"].append(body("second", "pillar", 0.1, -1, 0.1, 0.1, 0, 2, True))
    two = screen_geometry(request).screen_visibility[0]
    assert two.model_visible_fraction == one
    assert two.blocking_object_ids == ["first", "second"]


def test_lower_obstacle_can_occlude_display_without_covering_eye_height():
    request = screen_request()
    request["workstation_layout"]["scene"]["bodies"].append(
        body("low", "pillar", 0, -1, 1, 0.1, 0, 1.1, True)
    )
    observation = screen_geometry(request).screen_visibility[0]
    assert 0 < observation.model_visible_fraction < 1
    assert observation.blocking_object_ids == ["low"]


@pytest.mark.parametrize("angle", [0, 90, 180, 270, 37, -360, 720])
def test_display_shadow_is_invariant_under_rigid_plan_rotation(angle):
    request = screen_request()
    scene = request["workstation_layout"]["scene"]
    scene["bodies"].append(body("thin", "pillar", 0.1, -1, 0.1, 0.1, 0, 2, True))
    expected = screen_geometry(request).screen_visibility[0]
    frame = PlanPose(center=PlanPoint(x=0, y=0), rotation_degrees=angle)
    for b in scene["bodies"]:
        b["footprint"]["center"] = transform_point(
            PlanPoint.model_validate(b["footprint"]["center"]), frame
        ).model_dump()
        b["footprint"]["rotation_degrees"] += angle
    actual = screen_geometry(request).screen_visibility[0]
    assert actual.model_visible_fraction == pytest.approx(
        expected.model_visible_fraction, abs=1e-10
    )
    assert actual.blocking_object_ids == expected.blocking_object_ids
    assert actual.front_facing == expected.front_facing


def test_perspective_area_matches_independent_ray_box_intersection():
    request = screen_request()
    # Test an off-center, finite-height obstruction with partial vertical shadow.
    request["workstation_layout"]["scene"]["bodies"].append(
        body("box", "pillar", 0.07, -1.1, 0.13, 0.18, 0.9, 1.25, True)
    )
    fraction = screen_geometry(request).screen_visibility[0].model_visible_fraction
    blocked = 0
    resolution = 160
    for ix in range(resolution):
        for iz in range(resolution):
            target = (
                -0.4 + (ix + 0.5) * 0.8 / resolution,
                0,
                0.95 + (iz + 0.5) * 0.6 / resolution,
            )
            eye = (0, -2, 1.2)
            lower, upper = 0.0, 1.0
            for origin, end, lo, hi in zip(
                eye, target, (0.005, -1.19, 0.9), (0.135, -1.01, 1.25)
            ):
                delta = end - origin
                if delta == 0:
                    if not lo <= origin <= hi:
                        upper = -1
                        break
                else:
                    a, b = sorted(((lo - origin) / delta, (hi - origin) / delta))
                    lower, upper = max(lower, a), min(upper, b)
            blocked += lower <= upper
    assert fraction == pytest.approx(1 - blocked / resolution**2, abs=0.008)


def test_unknown_inventory_limits_positive_display_claim_and_search_readiness():
    request = screen_request()
    scene = request["workstation_layout"]["scene"]
    scene["inventory_confirmed"] = False
    request["workstation_layout"]["search"] = dict(
        domains=[
            dict(object_id="display", positions=[dict(x=0, y=0)], rotations_degrees=[0])
        ]
    )
    branch = measured_result(request)
    observation = branch["geometry"]["screen_visibility"][0]
    assert observation["unobstructed"] is None
    assert observation["model_visible_fraction"] == 1
    assert branch["status"] == "partial"
    (receipt,) = branch["search"]["receipts"]
    assert receipt["status"] == "conditional_option"
    assert any("screen_unobstructed" in p for p in receipt["pending_confirmations"])


@pytest.mark.parametrize("front,expected", [(0, False), (180, True), (540, True)])
def test_display_front_face_is_independent_of_seat_facing(front, expected):
    request = screen_request()
    request["workstation_layout"]["scene"]["desktops"][0]["items"][0]["screen"][
        "front_degrees"
    ] = front
    geometry = screen_geometry(request)
    assert geometry.screen_visibility[0].front_facing is expected
    assert (
        next(c for c in geometry.checks if c.check_id == "screen_front_facing").passed
        is expected
    )


def test_grid_automatically_uses_scene_and_desktop_coordinate_frames():
    request = measured_request()
    request["workstation_layout"]["search"] = dict(
        domains=[
            dict(
                object_id="plant",
                grid=dict(origin=dict(x=0, y=0), step_x_m=0.5, step_y_m=0.3),
                rotations_degrees=[0, 180],
            )
        ]
    )
    branch = measured_result(request)
    search = branch["search"]
    (domain,) = search["resolved_domains"]
    assert domain["input_kind"] == "grid"
    assert domain["coordinate_frame"] == "desktop:desk"
    assert len(domain["positions"]) == 9
    assert search["evaluated_count"] == 18
    assert search["enumeration_complete"] is True
    # The center grid point is generated without caller-proposed positions.
    assert dict(x=0.0, y=0.0) in domain["positions"]
    # Every shown candidate agrees with a separate new request.
    for candidate in search["candidates"]:
        independent = deepcopy(request)
        independent["workstation_layout"].pop("search")
        independent["workstation_layout"]["scene"]["desktops"][0]["items"][0][
            "footprint"
        ].update(candidate["poses"]["plant"])
        assert candidate["geometry"] == measured_result(independent)["geometry"]


def test_grid_clips_centers_to_concave_region_then_audits_full_footprints():
    request = measured_request()
    scene = request["workstation_layout"]["scene"]
    scene["boundary"] = dict(
        vertices=[
            dict(x=0, y=0),
            dict(x=2, y=0),
            dict(x=2, y=1),
            dict(x=1, y=1),
            dict(x=1, y=2),
            dict(x=0, y=2),
        ]
    )
    request["workstation_layout"]["search"] = dict(
        domains=[
            dict(
                object_id="desk",
                grid=dict(origin=dict(x=0, y=0), step_x_m=1, step_y_m=1),
                rotations_degrees=[0],
            )
        ]
    )
    search = measured_result(request)["search"]
    (domain,) = search["resolved_domains"]
    assert len(domain["positions"]) == 8
    assert dict(x=2.0, y=2.0) not in domain["positions"]
    assert any(
        any("inside_room" in r for r in receipt["blocking_reasons"])
        for receipt in search["receipts"]
    )


def test_decimal_grid_boundary_is_inclusive_and_positions_are_not_silently_added():
    request = measured_request()
    request["workstation_layout"]["search"] = dict(
        domains=[
            dict(
                object_id="plant",
                grid=dict(
                    origin=dict(x=0, y=0),
                    step_x_m=0.1,
                    step_y_m=0.1,
                    center_region=dict(
                        vertices=[
                            dict(x=0, y=0),
                            dict(x=0.3, y=0),
                            dict(x=0.3, y=0.3),
                            dict(x=0, y=0.3),
                        ]
                    ),
                ),
                rotations_degrees=[0],
            )
        ]
    )
    search = measured_result(request)["search"]
    assert search["evaluated_count"] == 16
    (domain,) = search["resolved_domains"]
    assert dict(x=0.3, y=0.3) in domain["positions"]
    assert dict(x=-0.45, y=0.3) not in domain["positions"]


def test_display_measurement_uncertainty_remains_candidate_and_optional_visibility_is_not_hard_gate():
    request = screen_request()
    scene = request["workstation_layout"]["scene"]
    scene["coordinate_uncertainty_m"] = 0.01
    scene["desktops"][0]["items"][0]["screen"].update(
        front_degrees=0, required_visible=False
    )
    geometry = screen_geometry(request)
    (observation,) = geometry.screen_visibility
    assert observation.candidate_only and not observation.front_facing
    assert observation.model_visible_fraction == 0
    assert not any(c.check_id.startswith("screen_") for c in geometry.checks)


@pytest.mark.parametrize("bottom,expected", [(1.4, False), (1.55, True), (2, True)])
def test_tabletop_item_collides_with_overhead_body_using_world_height(bottom, expected):
    request = screen_request()
    request["workstation_layout"]["scene"]["bodies"].append(
        body("over-display", "beam", 0, 0, 1, 0.1, bottom, 3)
    )
    geometry = screen_geometry(request)
    collisions = [
        c
        for c in geometry.checks
        if c.check_id == "desktop_body_collision_free" and c.passed is False
    ]
    assert bool(collisions) is not expected


def test_multiple_seats_and_declared_operating_zones_are_mutual_constraints():
    request = screen_request()
    scene = request["workstation_layout"]["scene"]
    scene["bodies"].append(body("desk-two", "desk", 2, 0, 1, 1, 0, 0.75))
    other = deepcopy(scene["seats"][0])
    other.update(desk_id="desk-two", offset=dict(x=-2, y=-2))
    other["operating_zone"]["center"] = dict(x=-2, y=-2)
    scene["seats"].append(other)
    geometry = screen_geometry(request)
    assert (
        next(c for c in geometry.checks if c.check_id == "seats_disjoint").passed
        is False
    )
    assert (
        next(
            c for c in geometry.checks if c.check_id == "operating_zones_disjoint"
        ).passed
        is False
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "both",
        "neither",
        "tiny_step",
        "empty",
        "combined_cap",
        "screen_height",
        "screen_width",
        "missing_seat",
    ],
)
def test_generated_and_display_input_boundaries_fail_explicitly(mutation):
    request = screen_request()
    layout = request["workstation_layout"]
    grid = dict(origin=dict(x=0, y=0), step_x_m=1, step_y_m=1)
    layout["search"] = dict(
        domains=[dict(object_id="desk", grid=grid, rotations_degrees=[0])]
    )
    if mutation == "both":
        layout["search"]["domains"][0]["positions"] = [dict(x=0, y=0)]
    elif mutation == "neither":
        layout["search"]["domains"][0].pop("grid")
    elif mutation == "tiny_step":
        grid["step_x_m"] = 0.00001
    elif mutation == "empty":
        grid.update(origin=dict(x=4, y=4), step_x_m=10, step_y_m=10)
    elif mutation == "combined_cap":
        grid.update(step_x_m=0.1, step_y_m=0.1)
        layout["search"]["domains"][0]["rotations_degrees"] = [0, 180]
    elif mutation == "screen_height":
        layout["scene"]["desktops"][0]["items"][0]["screen"]["height_m"] = 2
    elif mutation == "screen_width":
        layout["scene"]["desktops"][0]["items"][0]["screen"]["width_m"] = 2
    elif mutation == "missing_seat":
        layout["scene"]["seats"][0]["desk_id"] = "another"
    with pytest.raises(ValidationError):
        AssessRequest.model_validate(request)


def test_generated_screen_candidates_recompute_visibility_and_real_transports(
    monkeypatch, tmp_path, capsys
):
    request = screen_request()
    scene = request["workstation_layout"]["scene"]
    scene["bodies"].append(body("movable", "screen", 0.1, -1, 0.1, 0.1, 0, 2, True))
    request["layout_constraints"].append(
        dict(
            object_id="movable",
            can_relocate=True,
            can_rotate=True,
            evidence="Synthetic explicit permission",
        )
    )
    request["workstation_layout"]["search"] = dict(
        domains=[
            dict(
                object_id="movable",
                grid=dict(
                    origin=dict(x=0.1, y=-1),
                    step_x_m=1,
                    step_y_m=1,
                    center_region=dict(
                        vertices=[
                            dict(x=0, y=-1.1),
                            dict(x=1.2, y=-1.1),
                            dict(x=1.2, y=-0.9),
                            dict(x=0, y=-0.9),
                        ]
                    ),
                ),
                rotations_degrees=[0],
            )
        ]
    )
    controls = dict(
        fields=["layout_analysis.workstation_layout_analysis"],
        strict_fields=True,
        include_snapshot_text=False,
        response_char_limit=0,
    )
    rest = rest_client(monkeypatch).post(
        "/api/fengshui/assess", json=request, params=controls
    )
    assert rest.status_code == 200
    protocol = asyncio.run(mcp_call("assess", {**request, **controls}))
    path = tmp_path / "screen-grid.json"
    path.write_text(json.dumps(request))
    assert (
        run(
            [
                "fengshui_assess",
                "--request-file",
                str(path),
                "--fields",
                *controls["fields"],
                "--strict-fields",
                "--no-include-snapshot-text",
                "--response-char-limit",
                "0",
            ]
        )
        == 0
    )
    cli = json.loads(capsys.readouterr().out)
    assert (
        without_transport(rest.json())
        == without_transport(protocol.structured_content)
        == without_transport(cli)
    )
    branch = cli["layout_analysis"]["workstation_layout_analysis"]
    FengshuiOutput.model_validate(cli)
    assert branch["research_completion_status"] == "incomplete"
    assert any(r["status"] == "source_blocked" for r in branch["research_coverage"])
    search = branch["search"]
    assert search["evaluated_count"] == 2 and search["rejected_count"] == 1
    (candidate,) = search["candidates"]
    independent = deepcopy(request)
    independent["workstation_layout"].pop("search")
    independent["workstation_layout"]["scene"]["bodies"][1]["footprint"].update(
        candidate["poses"]["movable"]
    )
    assert candidate["geometry"] == measured_result(independent)["geometry"]
    assert candidate["geometry"]["screen_visibility"][0]["model_visible_fraction"] == 1
