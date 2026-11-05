"""Measured layouts: analytic geometry, independent proposals and real transports."""

import asyncio
import json
from copy import deepcopy
from pathlib import Path

import pytest
from fastmcp import Client
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from fatebridge.cli import run
from fatebridge.core.fengshui.models import AssessRequest
from fatebridge.core.fengshui.output import FengshuiOutput
from fatebridge.core.fengshui.spatial_geometry import direction_support
from fatebridge.core.fengshui.spatial_inputs import SpatialScene
from fatebridge.core.fengshui.spatial_layout import prepare_spatial_request
from fatebridge.core.fengshui.spatial_scene import evaluate_geometry
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.fengshui import assess
from tests.fengshui.test_fengshui_surfaces import (
    mcp_call,
    rest_client,
    without_transport,
)


def measured_request(*, search=False, charts=False):
    request = json.loads(
        Path("docs/examples/fengshui-workstation-measured.json").read_text()
    )
    scene = request["workstation_layout"]["scene"]
    scene["desktops"][0]["items"][0]["healthy"] = dict(
        value=True, observation_basis="user_confirmed", evidence="独立确认状态良好"
    )
    if not search:
        request["workstation_layout"].pop("search")
    if charts:
        template = json.loads(
            Path("docs/examples/fengshui-workstation-activity.json").read_text()
        )
        request["methods"] = ["xuankong_natal", "annual_stars", "monthly_stars"]
        request["xuankong"] = template["xuankong"]
        request["effective_year"] = 2026
        request["monthly"] = dict(effective_solar_year=2026, solar_month_number=3)
        request["workstation_layout"].update(
            evaluation_period=9,
            evaluation_period_evidence="独立评价运，不改变2004年竣工宅盘",
            timeliness_ruleset_id="wang_zhongzhou_timeliness_v1",
        )
    return request


def measured_result(request):
    return assess(**request)["layout_analysis"]["workstation_layout_analysis"]


def body(object_id, kind, x, y, width, depth, bottom, top, blocks=False):
    return dict(
        object_id=object_id,
        kind=kind,
        footprint=dict(
            center=dict(x=x, y=y), width_m=width, depth_m=depth, rotation_degrees=0
        ),
        bottom_m=bottom,
        top_m=top,
        blocks_view=blocks,
    )


def test_analytic_geometry_and_distinct_desktop_frames():
    result = assess(**measured_request())
    FengshuiOutput.model_validate(result)
    branch = result["layout_analysis"]["workstation_layout_analysis"]
    geometry = branch["geometry"]
    seat = geometry["seats"][0]
    assert seat["position"]["x"] == 0
    assert seat["position"]["y"] == pytest.approx(0.2)
    assert seat["backing_distance_m"] == pytest.approx(2.2)
    assert seat["form"]["entrance_visible"] is True
    assert seat["form"]["entrance_direct_line"] is False
    assert geometry["physically_feasible"] is True
    item = geometry["desktop_placements"][0]
    assert item["zone"] == "far_left" and item["compass_directions"] == ["NW"]
    comparisons = {c["rule_id"]: c for c in branch["rule_comparisons"]}
    assert comparisons["desktop_bagua_btb_v1.career_abundance_plant"]["matches"] is True
    assert comparisons["wofs_desktop_compass_v1.plant_southeast"]["matches"] is False
    assert result["status"] == "complete"


def test_complete_search_retains_every_rejection_and_tradeoff():
    branch = measured_result(measured_request(search=True))
    search = branch["search"]
    assert search["enumeration_complete"] is True
    assert search["evaluated_count"] == 12
    assert len(search["receipts"]) == 12
    assert search["rejected_count"] == 8
    assert len({row["candidate_id"] for row in search["receipts"]}) == 12
    assert any(
        "desktop_operating_zone_clear" in reason
        for row in search["receipts"]
        for reason in row["blocking_reasons"]
    )
    assert any(
        "inside_room" in reason
        for row in search["receipts"]
        for reason in row["blocking_reasons"]
    )
    # BTB far-left and WOFS compass-SE are competing authored rules in this
    # orientation. The solver preserves their tradeoff without inventing a sum.
    assert len(search["frontier_candidate_ids"]) >= 2
    assert all(
        row["status"] == "ready"
        for row in search["receipts"]
        if not row["blocking_reasons"]
    )


def test_each_generated_pose_matches_fresh_standalone_request():
    request = measured_request(search=True, charts=True)
    branch = measured_result(request)
    for candidate in branch["search"]["candidates"]:
        row = next(
            r
            for r in branch["search"]["receipts"]
            if r["candidate_id"] == candidate["candidate_id"]
        )
        fresh = deepcopy(request)
        fresh["workstation_layout"].pop("search")
        for object_id, pose in row["poses"].items():
            for obj in fresh["workstation_layout"]["scene"]["bodies"]:
                if obj["object_id"] == object_id:
                    obj["footprint"].update(pose)
            for desktop in fresh["workstation_layout"]["scene"]["desktops"]:
                for item in desktop["items"]:
                    if item["object_id"] == object_id:
                        item["footprint"].update(pose)
        standalone = measured_result(fresh)
        assert candidate["geometry"] == standalone["geometry"]
        assert candidate["readings"] == standalone["readings"]
        assert candidate["rule_comparisons"] == standalone["rule_comparisons"]


def test_turn_recomputes_backing_entry_and_items_instead_of_reusing_them():
    request = measured_request(search=True)
    branch = measured_result(request)
    turned = next(
        c
        for c in branch["search"]["candidates"]
        if c["geometry"]["seats"][0]["plan_facing_degrees"] == 180
    )
    seat = turned["geometry"]["seats"][0]
    assert seat["form"]["entrance_visible"] is False
    assert seat["form"]["solid_backing"] is False
    # Desktop local far-left remains far-left while its compass sector turns.
    plant = turned["geometry"]["desktop_placements"][0]
    assert plant["zone"] == "far_left" and plant["compass_directions"] == ["SE"]


@pytest.mark.parametrize("basis,error", [("image_observed", 0), ("measured", 0.03)])
def test_uncertain_geometry_cannot_become_confirmed_placements_or_ready(basis, error):
    request = measured_request(search=True)
    request["workstation_layout"]["scene"].update(
        observation_basis=basis, coordinate_uncertainty_m=error
    )
    model = AssessRequest.model_validate(request)
    normalized, _ = prepare_spatial_request(model, model.workstation_layout.scene)
    assert normalized.placements == []
    result = measured_result(request)
    assert result["geometry"]["candidate_only"] is True
    assert not any(row["status"] == "ready" for row in result["search"]["receipts"])
    assert result["status"] == "partial"


def test_uncertain_compass_retains_all_sector_readings_without_changing_house_period():
    request = measured_request(charts=True)
    request["workstation_layout"]["scene"]["compass"].update(
        y_axis_bearing_degrees=22.5, uncertainty_degrees=0.1
    )
    result = assess(**request)
    branch = result["layout_analysis"]["workstation_layout_analysis"]
    assert branch["geometry"]["seats"][0]["location_directions"] == ["N", "NE"]
    assert {r["direction"] for r in branch["readings"]} == {"N", "NE"}
    assert all(r["candidate_only"] for r in branch["readings"])
    assert all(
        r["historical_period_number"] == 8 and r["evaluation_period_number"] == 9
        for r in branch["readings"]
    )
    for reading in branch["readings"]:
        for method, key in (
            ("annual_stars", "annual_star_number"),
            ("monthly_stars", "monthly_star_number"),
        ):
            assert (
                reading["time_layer_references"][method]
                == result["layers"][method]["palaces"][reading["direction"]][key]
            )
    assert branch["status"] == "partial"


@pytest.mark.parametrize(
    "bearing,radius,expected",
    [
        (0, 0, ["N"]),
        (22.5, 0, ["NE"]),
        (22.5, 0.01, ["N", "NE"]),
        (359.9, 0.2, ["N"]),
        (0, 180, ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]),
    ],
)
def test_exact_direction_cells_and_closed_error_support(bearing, radius, expected):
    assert direction_support(bearing, radius) == expected


@pytest.mark.parametrize(
    "bottom,top,visible", [(0, 1, True), (0, 1.5, False), (2, 2.5, True)]
)
def test_visibility_uses_height_not_only_plan_overlap(bottom, top, visible):
    request = measured_request()
    scene = request["workstation_layout"]["scene"]
    scene["bodies"].append(
        body("screen", "screen", 0.95, 1.6, 1.2, 0.2, bottom, top, True)
    )
    result = measured_result(request)
    assert result["geometry"]["seats"][0]["form"]["entrance_visible"] is visible


def test_beam_projection_is_independent_of_floor_collision():
    request = measured_request()
    request["workstation_layout"]["scene"]["bodies"].append(
        body("beam", "beam", 0, 0.2, 0.8, 0.4, 2.5, 2.8)
    )
    geometry = measured_result(request)["geometry"]
    assert geometry["seats"][0]["form"]["exposed_beam_over_user"] is True
    assert geometry["physically_feasible"] is True


def test_concave_room_does_not_accept_rectangle_inside_only_bounding_box():
    request = measured_request()
    scene = request["workstation_layout"]["scene"]
    scene["boundary"]["vertices"] = [
        dict(x=-3, y=-3),
        dict(x=3, y=-3),
        dict(x=3, y=0),
        dict(x=0, y=0),
        dict(x=0, y=3),
        dict(x=-3, y=3),
    ]
    geometry = measured_result(request)["geometry"]
    assert any(
        c["check_id"] == "inside_room" and c["passed"] is False
        for c in geometry["checks"]
    )
    assert geometry["physically_feasible"] is False


def test_missing_inventory_is_unknown_and_blocks_only_execution():
    request = measured_request(search=True)
    scene = request["workstation_layout"]["scene"]
    scene["inventory_confirmed"] = False
    scene["solid_backing_segments"] = []
    result = measured_result(request)
    assert result["geometry"]["seats"][0]["form"]["solid_backing"] is None
    assert any(
        row["status"] == "conditional_option" for row in result["search"]["receipts"]
    )
    assert not any(row["status"] == "ready" for row in result["search"]["receipts"])


def test_no_rule_is_not_an_adverse_rule_or_reason_to_request_compass():
    request = measured_request()
    scene = request["workstation_layout"]["scene"]
    scene.pop("compass")
    item = scene["desktops"][0]["items"][0]
    item.update(representation="other")
    item.pop("healthy")
    result = measured_result(request)
    rules = [c for c in result["rule_comparisons"] if c["object_id"] == "plant"]
    assert rules and all(c["status"] == "not_covered" for c in rules)
    assert not any("rules.plant" in p for p in result["missing_inputs"])


def test_health_is_independent_of_live_plant_identity_and_location():
    request = measured_request()
    item = request["workstation_layout"]["scene"]["desktops"][0]["items"][0]
    item.pop("healthy")
    result = measured_result(request)
    placement = next(
        c
        for c in result["rule_comparisons"]
        if c["rule_id"] == "desktop_bagua_btb_v1.career_abundance_plant"
    )
    assert placement["matches"] is True and placement["status"] == "needs_confirmation"
    item["healthy"] = dict(
        value=False, observation_basis="user_confirmed", evidence="明确枯萎"
    )
    changed = measured_result(request)
    assert any(
        c["status"] == "opposes_application_condition"
        for c in changed["rule_comparisons"]
    )


def test_denied_permissions_and_attached_locked_item_are_preserved():
    request = measured_request(search=True)
    request["layout_constraints"][0].update(can_relocate=False, can_rotate=False)
    request["layout_constraints"][1].update(can_relocate=False, can_rotate=False)
    search = measured_result(request)["search"]
    assert len(search["receipts"]) == 12
    assert len([r for r in search["receipts"] if r["status"] == "ready"]) == 1
    assert any(
        "attached_locked_item" in reason
        for row in search["receipts"]
        for reason in row["blocking_reasons"]
    )


def test_display_limit_does_not_change_frontier_or_discard_receipts():
    request = measured_request(search=True)
    full = measured_result(request)["search"]
    request["workstation_layout"]["search"]["max_results"] = 1
    limited = measured_result(request)["search"]
    assert limited["frontier_candidate_ids"] == full["frontier_candidate_ids"]
    assert limited["receipts"] == full["receipts"]
    assert len(limited["candidates"]) == 1
    assert limited["omitted_frontier_count"] == len(full["frontier_candidate_ids"]) - 1


def test_sand_water_requires_explicit_classification_and_moves_to_new_sector():
    request = measured_request(search=True)
    request.pop("methods")
    scene = request["workstation_layout"]["scene"]
    scene["bodies"][0]["sand_water"] = dict(
        classification="sand",
        observation_basis="user_confirmed",
        evidence="独立确认，不能从桌子高度猜",
    )
    request["workstation_layout"]["search"]["domains"] = [
        dict(
            object_id="desk",
            positions=[dict(x=0, y=1), dict(x=0, y=-2)],
            rotations_degrees=[0],
        )
    ]
    result = assess(**request)
    assert result["layers"]["jinsuo"]["feature_findings"][0]["direction"] == "N"
    for candidate in result["layout_analysis"]["workstation_layout_analysis"]["search"][
        "candidates"
    ]:
        finding = candidate["layout_analysis"]["environment_adjustments"][0]
        expected = candidate["geometry"]["seats"][0]["location_directions"][0]
        assert finding["direction"] == expected and finding["classification"] == "sand"


@pytest.mark.parametrize(
    "mutation",
    [
        "boolean_number",
        "numeric_string",
        "wrong_entry",
        "duplicate_id",
        "bad_polygon",
        "parallel_entry",
        "unknown_rule",
        "duplicate_pose",
        "oversized_domain",
        "dual_placement",
        "north_mismatch",
    ],
)
def test_invalid_scene_rejected_at_shared_request_boundary(mutation):
    request = measured_request(search=True, charts=True)
    scene = request["workstation_layout"]["scene"]
    if mutation == "boolean_number":
        scene["bodies"][0]["top_m"] = True
    elif mutation == "numeric_string":
        scene["bodies"][0]["top_m"] = "0.75"
    elif mutation == "wrong_entry":
        scene["seats"][0]["entrance_id"] = "desk"
    elif mutation == "duplicate_id":
        scene["desktops"][0]["items"][0]["object_id"] = "desk"
    elif mutation == "bad_polygon":
        scene["boundary"]["vertices"] = [
            dict(x=0, y=0),
            dict(x=1, y=1),
            dict(x=0, y=1),
            dict(x=1, y=0),
        ]
    elif mutation == "parallel_entry":
        scene["openings"][0]["inward_degrees"] = 90
    elif mutation == "unknown_rule":
        scene["desktops"][0]["ruleset_ids"] = ["all_fengshui"]
    elif mutation == "duplicate_pose":
        request["workstation_layout"]["search"]["domains"][0]["rotations_degrees"] = [
            0,
            360,
        ]
    elif mutation == "oversized_domain":
        request["workstation_layout"]["search"]["domains"] = [
            dict(
                object_id=name,
                positions=[dict(x=i, y=0) for i in range(30)],
                rotations_degrees=list(range(16)),
            )
            for name in ("desk", "plant")
        ]
    elif mutation == "dual_placement":
        request["placements"] = [
            dict(object_id="desk", purpose="desk", location_direction="N")
        ]
    elif mutation == "north_mismatch":
        scene["compass"]["north_reference"] = "true"
    with pytest.raises(ValidationError):
        AssessRequest.model_validate(request)


def test_new_branch_matches_real_rest_mcp_cli_and_strict_projection(
    monkeypatch, tmp_path, capsys
):
    request = measured_request(search=True, charts=True)
    fields = [
        "layout_analysis.workstation_layout_analysis",
        "coverage.analysis_progress",
        "rulesets",
        "rule_trace",
    ]
    controls = dict(
        fields=fields,
        strict_fields=True,
        include_snapshot_text=False,
        response_char_limit=0,
    )
    rest = rest_client(monkeypatch).post(
        "/api/fengshui/assess", json=request, params=controls
    )
    protocol = asyncio.run(mcp_call("assess", {**request, **controls}))
    path = tmp_path / "measured-workstation.json"
    path.write_text(json.dumps(request))
    assert (
        run(
            [
                "fengshui_assess",
                "--request-file",
                str(path),
                "--fields",
                *fields,
                "--strict-fields",
                "--no-include-snapshot-text",
                "--response-char-limit",
                "0",
            ]
        )
        == 0
    )
    cli = json.loads(capsys.readouterr().out)
    assert rest.status_code == 200, rest.text
    assert not protocol.is_error
    assert (
        without_transport(rest.json())
        == without_transport(protocol.structured_content)
        == without_transport(cli)
    )
    Draft202012Validator(FengshuiOutput.model_json_schema()).validate(cli)


@pytest.mark.parametrize(
    "field",
    [
        "layout_analysis.workstation_layout_analysis.geometry.seats",
        "layout_analysis.workstation_layout_analysis.search.receipts",
    ],
)
def test_nested_projection_retains_typed_new_evidence(monkeypatch, field):
    request = measured_request(search=True)
    rest = rest_client(monkeypatch).post(
        "/api/fengshui/assess",
        json=request,
        params=dict(
            fields=[field],
            strict_fields=True,
            include_snapshot_text=False,
            response_char_limit=0,
        ),
    )
    assert rest.status_code == 200, rest.text
    FengshuiOutput.model_validate(rest.json())


def test_wide_entrance_visibility_is_not_forced_into_midpoint_direction():
    request = measured_request()
    entry = request["workstation_layout"]["scene"]["openings"][0]
    entry.update(
        segment=dict(start=dict(x=2, y=-3), end=dict(x=2, y=1)), inward_degrees=270
    )
    result = assess(**request)
    FengshuiOutput.model_validate(result)
    seat = result["layout_analysis"]["workstation_layout_analysis"]["geometry"][
        "seats"
    ][0]
    assert seat["form"]["entrance_visible"] is True
    assert seat["form"]["entrance_position"] is None
    # atan2(2, 0.8) = 68.2 degrees: inside the declared 80-degree
    # front field of view, but in the right 45-degree directional cell.
    assert "right" in seat["entrance_relative_positions"]
    assert "back_right" in seat["entrance_relative_positions"]


def test_head_clearance_is_not_eye_clearance():
    request = measured_request()
    request["workstation_layout"]["scene"]["bodies"].append(
        body("beam", "beam", 0, 0.2, 0.8, 0.4, 1.3, 2.8)
    )
    geometry = measured_result(request)["geometry"]
    assert geometry["physically_feasible"] is False
    assert any(
        c["check_id"] == "seat_collision_free" and c["passed"] is False
        for c in geometry["checks"]
    )


def test_barrier_geometry_reaches_existing_afsi_rule_and_recomputes_after_move():
    request = measured_request(search=True)
    scene = request["workstation_layout"]["scene"]
    scene["openings"][0]["segment"] = dict(
        start=dict(x=-0.4, y=3), end=dict(x=0.4, y=3)
    )
    scene["bodies"].append(body("screen", "screen", 0, 2, 0.6, 0.1, 0, 0.8, True))
    request["layout_constraints"].append(
        dict(
            object_id="screen",
            can_relocate=True,
            can_rotate=True,
            evidence="允许移动实际隔挡",
        )
    )
    request["workstation_layout"]["search"]["domains"] = [
        dict(
            object_id="screen",
            positions=[dict(x=0, y=2), dict(x=1, y=2)],
            rotations_degrees=[0],
        )
    ]
    result = assess(**request)
    FengshuiOutput.model_validate(result)
    branch = result["layout_analysis"]["workstation_layout_analysis"]
    barrier = next(
        c
        for c in branch["rule_comparisons"]
        if c["rule_id"] == "afsi_entry_barrier_v1.entry_line_barrier"
    )
    assert barrier["matches"] is True
    assert barrier["instance_id"]
    rows = branch["search"]["receipts"]
    key = next(key for key in rows[0]["rule_dimensions"] if "afsi_entry_barrier" in key)
    assert rows[0]["rule_dimensions"][key] == 0
    assert rows[1]["rule_dimensions"][key] == 1
    assert any(r["ruleset_id"] == "afsi_entry_barrier_v1" for r in result["rulesets"])


def test_reexpressing_plan_in_rotated_frame_preserves_physical_results():
    request = measured_request()
    original = measured_result(request)
    changed = deepcopy(request)
    scene = changed["workstation_layout"]["scene"]
    points = list(scene["boundary"]["vertices"])
    points += [b["footprint"]["center"] for b in scene["bodies"]]
    points += [
        p
        for o in scene["openings"]
        for p in (o["segment"]["start"], o["segment"]["end"])
    ]
    points += [
        p
        for segment in scene["solid_backing_segments"]
        for p in (segment["start"], segment["end"])
    ]
    points += [scene["compass"]["sector_origin"]]
    for point in points:
        point["x"], point["y"] = point["y"], -point["x"]
    for item in scene["bodies"]:
        item["footprint"]["rotation_degrees"] += 90
    for opening in scene["openings"]:
        opening["inward_degrees"] += 90
    scene["compass"]["y_axis_bearing_degrees"] -= 90
    result = measured_result(changed)
    assert (
        result["geometry"]["physically_feasible"]
        == original["geometry"]["physically_feasible"]
    )
    before, after = original["geometry"]["seats"][0], result["geometry"]["seats"][0]
    assert before["location_directions"] == after["location_directions"]
    for key in ("entrance_visible", "entrance_direct_line", "solid_backing"):
        assert before["form"][key] == after["form"][key]
    assert result["rule_comparisons"] == original["rule_comparisons"]


def test_source_ids_resolve_and_snapshot_includes_measured_actions():
    result = assess(**measured_request(search=True, charts=True))
    sources = {
        source["source_id"]
        for ruleset in result["rulesets"]
        for source in ruleset.get("sources", [])
    }
    branch = result["layout_analysis"]["workstation_layout_analysis"]
    assert all(set(c["source_ids"]) <= sources for c in branch["rule_comparisons"])
    assert all(set(r["source_ids"]) <= sources for r in branch["readings"])
    assert (
        "实测工位" in result["snapshot_text"]
        and "有限布局搜索" in result["snapshot_text"]
    )
    assert any(c["actions"] for c in branch["search"]["candidates"])
    assert all(
        a["coordinate_frame"].startswith(("desktop:", "synthetic-office-plan"))
        for c in branch["search"]["candidates"]
        for a in c["actions"]
    )


def test_default_budget_pages_reconstruct_same_run_search_without_recomputation(
    monkeypatch, tmp_path
):
    import fatebridge.api as api
    from fatebridge.application import result_delivery as delivery
    from tests.support.result_delivery import reconstruct

    store = delivery.ResultStore(tmp_path / "measured-results")
    monkeypatch.setattr(delivery, "RESULT_STORE", store)
    monkeypatch.setattr(api, "RESULT_STORE", store)

    async def native():
        async with Client(create_mcp_app(scenarios="onda-fengshui")) as client:
            result = await client.call_tool(
                "fengshui_assess",
                {
                    **measured_request(search=True, charts=True),
                    "include_snapshot_text": False,
                },
            )
            assert not result.is_error
            ref = result.structured_content["result_delivery"]
            manifest = json.loads(
                (await client.read_resource(ref["manifest_uri"]))[0].text
            )
            assert (
                manifest["run_metadata"]["run_id"]
                == result.structured_content["run_metadata"]["run_id"]
            )
            original = reconstruct(store, ref["result_id"])
            branch = original["layout_analysis"]["workstation_layout_analysis"]
            assert branch["search"]["evaluated_count"] == 12
            assert len(branch["search"]["receipts"]) == 12
            assert (
                original["run_metadata"]["run_id"] == manifest["run_metadata"]["run_id"]
            )

    asyncio.run(native())


def test_measured_task_cards_are_published_and_choose_actual_fields():
    from fatebridge.application.examples import evidence_views
    from fatebridge.services.tool_catalog import CATALOG

    spec = next(s for s in CATALOG if s.key == "fengshui_assess")
    views = evidence_views(spec)
    assert "measured_workstation" in views and "measured_workstation_search" in views
    request = measured_request(search=True)
    for view in views.values():
        assert "rulesets" in view["fields"] and "rule_trace" in view["fields"]


def test_full_turn_is_an_identity_even_with_locked_attached_items():
    request = measured_request(search=True)
    request["workstation_layout"]["search"]["domains"] = [
        dict(object_id="desk", positions=[dict(x=0, y=1)], rotations_degrees=[360])
    ]
    request["layout_constraints"][0].update(can_rotate=False, can_relocate=False)
    request["layout_constraints"][1].update(can_rotate=False, can_relocate=False)
    search = measured_result(request)["search"]
    assert search["receipts"][0]["status"] == "ready"
    assert search["receipts"][0]["changed_object_count"] == 0
    assert search["candidates"][0]["actions"] == []


@pytest.mark.parametrize("on_axis", [False, True])
def test_host_guest_reference_does_not_expand_beyond_registered_axes(on_axis):
    request = measured_request(charts=True)
    request["xuankong"]["interpretation"] = dict(
        ruleset_id="xuankong_conditioned_v1",
        current_period_number=9,
        period_evidence="独立九运评价",
        host_guest_ruleset_id="shen_2011_host_guest_v1",
    )
    if on_axis:
        request["workstation_layout"]["scene"]["compass"]["sector_origin"] = dict(
            x=2, y=0.2
        )
    result = measured_result(request)
    reading = result["readings"][0]
    assert (reading["host_guest_reference"] is not None) is on_axis
    assert reading["host_guest_scope"] == (
        "existing_axis_operations_only_not_workstation_fortune"
        if on_axis
        else "outside_selected_source_axis_scope"
    )


def test_rectangle_envelope_does_not_confirm_a_sourced_sharp_corner():
    request = measured_request()
    pillar = body("pillar", "pillar", 1, 1.2, 0.4, 0.4, 0, 2, True)
    request["workstation_layout"]["scene"]["bodies"].append(pillar)
    assert (
        measured_result(request)["geometry"]["seats"][0]["form"][
            "sharp_corner_points_at_user"
        ]
        is None
    )
    pillar["has_sharp_corners"] = False
    assert (
        measured_result(request)["geometry"]["seats"][0]["form"][
            "sharp_corner_points_at_user"
        ]
        is False
    )
    pillar["has_sharp_corners"] = True
    assert (
        measured_result(request)["geometry"]["seats"][0]["form"][
            "sharp_corner_points_at_user"
        ]
        is True
    )


def test_period_condition_is_a_real_frontier_dimension_not_only_returned_text():
    request = measured_request(search=True, charts=True)
    request["workstation_layout"]["search"]["domains"] = [
        dict(
            object_id="desk",
            positions=[dict(x=0, y=1), dict(x=1, y=-1.8)],
            rotations_degrees=[0],
        )
    ]
    search = measured_result(request)["search"]
    assert search["rejected_count"] == 0
    assert len(search["frontier_candidate_ids"]) == 2
    key = next(
        k
        for k in search["receipts"][0]["rule_dimensions"]
        if "current_role_period_match" in k
    )
    # Original chart: N facing star 6, SE facing star 9, explicit period 9.
    assert search["receipts"][0]["rule_dimensions"][key] == 1
    assert search["receipts"][1]["rule_dimensions"][key] == 0
    assert {
        r["current_role_condition"] for c in search["candidates"] for r in c["readings"]
    } == {False, True}


def test_unknown_application_condition_cannot_receive_a_satisfied_dimension():
    request = measured_request(search=True)
    request["workstation_layout"]["scene"]["desktops"][0]["items"][0].pop("healthy")
    search = measured_result(request)["search"]
    key = next(
        k
        for k in search["receipts"][0]["rule_dimensions"]
        if "career_abundance_plant" in k
    )
    assert search["receipts"][0]["rule_dimensions"][key] is None


def test_geometry_keeps_explicit_occupant_scope_for_house_and_person_rules():
    request = measured_request()
    request["methods"] = ["bazhai"]
    request["house"] = {"sitting_trigram": "坎"}
    request["occupants"] = [
        dict(subject_id="alice", effective_birth_year=1990, gender_convention="female"),
        dict(subject_id="bob", effective_birth_year=1990, gender_convention="male"),
    ]
    request["workstation_layout"]["scene"]["seats"][0]["subject_ids"] = ["alice"]
    result = assess(**request)
    findings = result["layers"]["bazhai"]["placement_findings"]
    assert {f["subject_id"] for f in findings if f["subject_kind"] == "occupant"} == {
        "alice"
    }
    request["workstation_layout"]["scene"]["seats"][0]["subject_ids"] = ["unknown"]
    with pytest.raises(ValidationError, match="subject_ids"):
        AssessRequest.model_validate(request)


def test_geometry_does_not_bypass_independent_floor_center_confirmation():
    request = measured_request()
    request["environmental_context"] = {
        "floors": [
            dict(
                floor_id="floor-1",
                level=1,
                object_ids=["desk"],
                observation_basis="user_confirmed",
                evidence="旧楼层清单，不能代替几何场景独立绑定",
            )
        ]
    }
    with pytest.raises(ValidationError, match="floors"):
        AssessRequest.model_validate(request)


def test_seated_right_is_relative_to_actual_user_not_desktop_center():
    request = measured_request()
    scene = request["workstation_layout"]["scene"]
    scene["seats"][0]["offset"]["x"] = -0.6
    scene["seats"][0]["operating_zone"]["center"]["x"] = -0.6
    desktop = scene["desktops"][0]
    desktop["ruleset_ids"] = ["wofs_desktop_compass_v1"]
    equipment = desktop["items"][0]
    equipment.update(representation="metal_office_equipment", height_m=0.1)
    equipment.pop("healthy")
    equipment["footprint"]["center"] = dict(x=-0.1, y=0.2)
    higher = deepcopy(equipment)
    higher.update(object_id="higher-left", representation="other", height_m=0.2)
    higher["footprint"].update(center=dict(x=-0.65, y=0.2), width_m=0.05, depth_m=0.05)
    desktop["items"].append(higher)
    rules = measured_result(request)["rule_comparisons"]
    finding = next(
        c
        for c in rules
        if c["rule_id"] == "wofs_desktop_compass_v1.same_desk_metal_equipment"
    )
    assert finding["matches"] is True


def test_btb_near_edge_rule_is_not_rotated_from_an_incompatible_real_seat():
    request = measured_request()
    request["workstation_layout"]["scene"]["seats"][0]["facing_offset_degrees"] = 180
    rules = measured_result(request)["rule_comparisons"]
    btb = next(
        c
        for c in rules
        if c["rule_id"] == "desktop_bagua_btb_v1.career_abundance_plant"
    )
    assert btb["matches"] is None and btb["status"] == "not_covered"


def test_backing_segment_does_not_invent_height_or_eye_occlusion():
    request = measured_request()
    scene = request["workstation_layout"]["scene"]
    scene["solid_backing_segments"].append(
        dict(start=dict(x=0.8, y=0.3), end=dict(x=0.8, y=2.3))
    )
    assert (
        measured_result(request)["geometry"]["seats"][0]["form"]["entrance_visible"]
        is True
    )
    scene["bodies"].append(body("opaque", "furniture", 0.8, 1.3, 0.1, 2, 0, 2, True))
    assert (
        measured_result(request)["geometry"]["seats"][0]["form"]["entrance_visible"]
        is False
    )
