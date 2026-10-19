"""Source-derived scope invariants across charts, facts and real transports."""

import asyncio
import json
from copy import deepcopy

import pytest
from fastmcp import Client
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from fatebridge.cli import run
from fatebridge.core.fengshui.models import AssessRequest
from fatebridge.core.fengshui.output import FengshuiOutput
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.fengshui import assess
from tests.fixtures.fengshui import payload
from tests.test_fengshui_material_facts import material_request
from tests.test_fengshui_surfaces import mcp_call, rest_client, without_transport


def condition(value=True, basis="user_confirmed"):
    return dict(
        value=value,
        observation_basis=basis,
        evidence="独立观察该事实，不由动作许可推定",
    )


def activity_request(activity="work", direction="N"):
    return dict(
        scene="workstation",
        methods=["xuankong_natal"],
        xuankong=payload("xuankong_natal"),
        placements=[
            dict(object_id="desk", purpose="desk", location_direction=direction)
        ],
        environmental_context=dict(
            workstation_review=dict(
                activities=[
                    dict(
                        ruleset_id="workstation_activity_authored_v1",
                        object_id="desk",
                        activity=activity,
                        observation_basis="user_confirmed",
                        evidence="用户说明实际活动",
                    )
                ]
            )
        ),
    )


def barrier_request(operation="relocate"):
    relation = dict(
        ruleset_id="afsi_entry_barrier_v1",
        relation_id="entry-seat",
        entrance_id="entry",
        desk_id="desk",
        barrier_id="screen",
        barrier_kind="screen",
        operation=operation,
        observation_basis="user_confirmed",
        evidence="实际屏风独立确认",
        entry_line_through_user=condition(),
        barrier_between_entry_and_user=condition(),
        **{
            key: condition()
            for key in [
                "entrance_view_maintained",
                "circulation_clear",
                "operating_space_clear",
                "physically_feasible",
            ]
        },
    )
    return dict(
        methods=[],
        environmental_context=dict(
            objects=[
                dict(
                    object_id="entry",
                    kind="opening",
                    purpose="door",
                    label="入口",
                    evidence="实际房间入口",
                ),
                dict(
                    object_id="desk",
                    kind="furniture",
                    purpose="desk",
                    label="桌",
                    evidence="实际坐者工位",
                ),
                dict(
                    object_id="screen",
                    kind="furniture",
                    label="隔挡",
                    evidence="实际屏风",
                ),
            ],
            workstation_review=dict(entry_barriers=[relation]),
        ),
        layout_constraints=[
            dict(object_id="screen", can_relocate=True, evidence="允许移动屏风"),
            dict(object_id="desk", can_add_items=True, evidence="允许新增"),
        ],
    )


def material_application_request(material="water", use="water_remedy", **conditions):
    request = material_request(element_use=use)
    fact = request["environmental_context"]["material_facts"][0]
    fact["material"] = material
    fact["application"] = dict(
        ruleset_id="afsi_application_conditions_v1", **conditions
    )
    if material == "living_plant":
        fact["plant_alive"] = True
    return request


def review(request):
    return assess(**request)["layout_analysis"]["workstation_analysis"]


@pytest.mark.parametrize("activity", ["work", "study"])
def test_activity_role_across_all_palaces_and_facing_changes(activity):
    # The independent source expectation is the facing ROLE, not a fixed number.
    for direction in ("N", "NE", "E", "SE", "S", "SW", "W", "NW"):
        request = activity_request(activity, direction)
        result = assess(**request)
        finding = result["layout_analysis"]["workstation_analysis"]["findings"][0]
        assert finding["selected_star_role"] == "facing"
        for candidate in finding["candidates"]:
            chart = next(
                c
                for c in result["layers"]["xuankong_natal"]["candidates"]
                if c["candidate_id"] == candidate["candidate_id"]
            )
            assert (
                candidate["selected_star_number"]
                == chart["palaces"][direction]["facing_star_number"]
            )
            assert (
                candidate["mountain_star_number"]
                == chart["palaces"][direction]["mountain_star_number"]
            )
        for facing in ("N", "SE", "W"):
            changed = deepcopy(request)
            changed["placements"][0].update(
                facing_direction=facing, facing_role="desk_facing"
            )
            assert review(changed) == result["layout_analysis"]["workstation_analysis"]
        assert finding["overall_auspiciousness"] == "not_produced"
        assert result["layout_analysis"]["workstation_analysis"]["action_options"] == []


@pytest.mark.parametrize("activity", ["meditation", "storage", "mixed", "unknown"])
def test_non_work_uses_never_borrow_bed_or_door_rules(activity):
    result = review(activity_request(activity))
    finding = result["findings"][0]
    assert finding["selected_star_role"] is None
    assert finding["coverage_reason"] == (
        "unknown_activity" if activity == "unknown" else "activity_rule_not_implemented"
    )
    assert bool(result["missing_inputs"]) is (activity == "unknown")


def test_activity_explanation_survives_unknown_location_external_forms_and_execution():
    request = activity_request()
    request["placements"][0] = dict(
        object_id="desk",
        purpose="desk",
        facing_direction="W",
        facing_role="desk_facing",
    )
    result = assess(**request)
    finding = result["layout_analysis"]["workstation_analysis"]["findings"][0]
    assert finding["selected_star_role"] == "facing" and finding["candidates"] == []
    assert finding["status"] == "candidate_only"
    assert "placements.desk.location_direction" in finding["missing_inputs"]
    assert (
        result["coverage"]["analysis_progress"]["interpretation_status"]
        != "insufficient_evidence"
    )
    known = assess(**activity_request())
    assert known["layout_analysis"]["workstation_analysis"]["status"] == "complete"
    assert not known["layout_analysis"]["workstation_analysis"]["missing_inputs"]


def test_independent_version_keeps_old_interpretation_and_candidate_uncertainty():
    request = activity_request()
    request["xuankong"]["interpretation"] = dict(
        current_period_number=9, period_evidence="显式评价九运"
    )
    request["xuankong"]["house"]["facing_degrees"] = 355.5
    result = assess(**request)
    finding = result["layout_analysis"]["workstation_analysis"]["findings"][0]
    assert len(finding["candidates"]) > 1
    assert all(c["candidate_only"] for c in finding["candidates"])
    assert (
        result["layers"]["xuankong_natal"]["interpretation"]["candidates"][0][
            "placement_findings"
        ][0]["status"]
        == "unsupported"
    )
    assert all(
        c["timeliness"] in {"current", "not_current"} for c in finding["candidates"]
    )
    request["environmental_context"]["workstation_review"]["activities"][0][
        "space_mixed_use"
    ] = condition()
    mixed = review(request)["findings"][0]
    assert (
        mixed["mixed_use_review"]["value"]
        and mixed["overall_auspiciousness"] == "not_produced"
    )


def test_photographic_activity_never_becomes_confirmed_or_rotates_by_birth():
    request = activity_request()
    request["environmental_context"]["workstation_review"]["activities"][0][
        "observation_basis"
    ] = "image_observed"
    first = review(request)
    request["occupants"] = [
        dict(
            subject_id="unrelated",
            effective_birth_year=1977,
            gender_convention="female",
        )
    ]
    assert review(request) == first
    assert first["findings"][0]["status"] == "candidate_only"
    assert not first["non_btb_desktop_reference"]["placement_rules_enabled"]


@pytest.mark.parametrize("operation", ["retain", "relocate", "add"])
def test_barrier_gate_uses_actual_geometry_and_operation_permissions(operation):
    request = barrier_request(operation)
    assert review(request)["action_options"][0]["status"] == "ready"
    constrained = deepcopy(request)
    target = 1 if operation == "add" else 0
    field = "can_add_items" if operation == "add" else "can_relocate"
    constrained["layout_constraints"][target][field] = False
    action = review(constrained)["action_options"][0]
    assert action["status"] == ("ready" if operation == "retain" else "blocked")
    if operation != "retain":
        assert action["pending_confirmations"] == []
    request["environmental_context"]["workstation_review"]["entry_barriers"][0][
        "barrier_between_entry_and_user"
    ] = condition(False)
    assert review(request)["action_options"][0]["status"] != "ready"


@pytest.mark.parametrize(
    "field",
    [
        "entry_line_through_user",
        "barrier_between_entry_and_user",
        "entrance_view_maintained",
        "circulation_clear",
        "operating_space_clear",
        "physically_feasible",
    ],
)
def test_each_photo_fact_is_independent_and_cannot_make_action_ready(field):
    request = barrier_request()
    relation = request["environmental_context"]["workstation_review"]["entry_barriers"][
        0
    ]
    relation[field] = condition(True, "image_observed")
    assert review(request)["action_options"][0]["status"] != "ready"


def test_absent_entry_line_needs_no_barrier_action_or_execution_followup():
    request = barrier_request()
    relation = request["environmental_context"]["workstation_review"]["entry_barriers"][
        0
    ]
    relation["entry_line_through_user"] = condition(False)
    relation["barrier_between_entry_and_user"] = condition(None)
    result = review(request)
    assert result["findings"][0]["status"] == "not_indicated"
    assert result["action_options"] == [] and result["missing_inputs"] == []


def test_material_conditions_separate_eligibility_dosage_and_action():
    for moving in (None, False, True):
        request = material_application_request(
            water_clean=condition(), proportionate_to_space=condition()
        )
        if moving is not None:
            request["environmental_context"]["material_facts"][0]["application"][
                "water_moving"
            ] = condition(moving)
        finding = assess(**request)["layout_analysis"]["material_analysis"]["findings"][
            0
        ]
        app = finding["application_analysis"]
        assert finding["material_eligibility"] == "conditional_material_match"
        assert app["status"] == (
            "needs_confirmation"
            if moving is None
            else "conditions_reviewed" if moving else "conditions_not_met"
        )
        assert (
            app["placement_suitability"] == "not_assessed"
            and app["action_status"] != "ready"
        )
        assert "quantitative_dosage_or_sufficiency" in app["unassessed_dimensions"]
    metal = material_application_request(
        "metal", "metal_remedy", metal_exposed=condition()
    )
    finding = assess(**metal)["layout_analysis"]["material_analysis"]["findings"][0]
    assert finding["application_analysis"]["status"] == "needs_confirmation"
    assert finding["application_analysis"]["source_disagreements"][0]["source_ids"] == [
        "A2",
        "K5",
    ]


def test_computed_target_binding_is_separate_from_location_and_material_name():
    request = material_application_request(
        water_clean=condition(),
        water_moving=condition(),
        proportionate_to_space=condition(),
    )
    request.update(
        methods=["annual_stars"],
        effective_year=2026,
        placements=[dict(object_id="desk", purpose="desk", location_direction="N")],
        element_adjustments=[
            dict(
                request_id="goal",
                object_id="desk",
                target_method="annual_stars",
                goal="drain",
                evidence="明确选择泄耗目标",
            )
        ],
    )
    request["environmental_context"]["orientation"] = dict(
        direction_confirmed=True,
        north_reference="magnetic",
        floorplan_alignment_confirmed=True,
        center_confirmed=True,
        evidence="独立确认参考北与分宫",
    )
    request["environmental_context"]["material_facts"][0]["application"][
        "target_request_id"
    ] = "goal"
    app = assess(**request)["layout_analysis"]["material_analysis"]["findings"][0][
        "application_analysis"
    ]
    assert app["target_binding"]["status"] == "bound_to_computed_target"
    assert app["target_binding"]["location_confirmed"] is False
    request["element_adjustments"][0]["goal"] = "support"
    app = assess(**request)["layout_analysis"]["material_analysis"]["findings"][0][
        "application_analysis"
    ]
    assert app["target_binding"]["status"] == "element_mismatch"


def test_all_moved_barrier_ends_require_fresh_same_relation():
    for object_id in ("entry", "desk", "screen"):
        request = barrier_request()
        request["layout_constraints"] = [
            dict(object_id=object_id, can_relocate=True, evidence="只许可目标对象搬位")
        ]
        fresh = deepcopy(request["environmental_context"])
        fresh["objects"].extend(
            [
                dict(
                    object_id="other-entry",
                    kind="opening",
                    purpose="door",
                    label="另一个实际入口",
                    evidence="独立确认",
                ),
                dict(
                    object_id="other-desk",
                    kind="furniture",
                    purpose="desk",
                    label="另一实际书桌",
                    evidence="独立确认",
                ),
            ]
        )
        new_relation = fresh["workstation_review"]["entry_barriers"][0]
        new_relation["desk_id" if object_id == "entry" else "entrance_id"] = (
            "other-desk" if object_id == "entry" else "other-entry"
        )
        request["layout_alternatives"] = [
            dict(
                candidate_id="move",
                object_id=object_id,
                changes=["location"],
                environmental_context=fresh,
                physically_feasible=True,
                evidence="候选可容纳",
            )
        ]
        candidate = assess(**request)["layout_analysis"]["alternatives_analysis"][
            "findings"
        ][0]
        assert candidate["status"] == "candidate_only"
        assert any("entry_barriers" in m for m in candidate["missing_inputs"])


def test_corner_disagreements_do_not_cancel_wofs_rule_or_claim_consensus():
    result = assess(
        methods=[],
        form_observations=[
            dict(
                object_id="desk",
                purpose="desk",
                sharp_corner_points_at_user=True,
                observation_basis="user_confirmed",
                evidence="实体家具角直指实际坐者",
            )
        ],
    )
    check = next(
        c
        for c in result["layout_analysis"]["form_analysis"]["findings"][0]["checks"]
        if c["criterion"] == "sharp_corner_points_at_user"
    )
    assert check["finding"] == "opposes_rule"
    assert check["method_disagreements"][0]["source_ids"] == ["W1", "J1"]
    assert any(
        r["ruleset_id"] == "workstation_source_boundaries_v1"
        for r in result["rulesets"]
    )


@pytest.mark.parametrize(
    "factory", [activity_request, barrier_request, material_application_request]
)
def test_new_branches_match_rest_mcp_cli_and_strict_projection(
    monkeypatch, tmp_path, capsys, factory
):
    request = factory()
    branch = (
        "material_analysis"
        if factory == material_application_request
        else "workstation_analysis"
    )
    fields = [
        "layout_analysis." + branch,
        "coverage.analysis_progress",
        "rulesets",
        "rule_trace",
    ]
    controls = dict(fields=fields, strict_fields=True, include_snapshot_text=False)
    response = rest_client(monkeypatch).post(
        "/api/fengshui/assess", json=request, params=controls
    )
    protocol = asyncio.run(mcp_call("assess", {**request, **controls}))
    path = tmp_path / "request.json"
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
            ]
        )
        == 0
    )
    cli = json.loads(capsys.readouterr().out)
    assert response.status_code == 200, response.text
    assert not protocol.is_error
    assert (
        without_transport(response.json())
        == without_transport(protocol.structured_content)
        == without_transport(cli)
    )
    Draft202012Validator(FengshuiOutput.model_json_schema()).validate(cli)


def test_published_schema_rejects_unknown_rules_and_strict_boolean_facts():
    async def check():
        async with Client(create_mcp_app(scenarios="onda-fengshui")) as client:
            schema = next(
                t.model_dump(by_alias=True)["inputSchema"]
                for t in await client.list_tools()
                if t.name == "fengshui_assess"
            )
            for factory in (
                activity_request,
                barrier_request,
                material_application_request,
            ):
                Draft202012Validator(schema).validate(factory())
            bad = barrier_request()
            bad["environmental_context"]["workstation_review"]["entry_barriers"][0][
                "entry_line_through_user"
            ]["value"] = "true"
            assert list(Draft202012Validator(schema).iter_errors(bad))
            with pytest.raises(ValidationError):
                AssessRequest.model_validate(bad)
            bad = activity_request()
            bad["environmental_context"]["workstation_review"]["activities"][0][
                "ruleset_id"
            ] = "wofs_desktop_auto"
            assert list(Draft202012Validator(schema).iter_errors(bad))

    asyncio.run(check())


@pytest.mark.parametrize(
    "bad_kind",
    [
        "unknown_target",
        "wrong_desk",
        "wrong_barrier",
        "duplicate_relation",
        "wrong_material",
    ],
)
def test_invalid_references_rejected_identically_by_three_transports(
    monkeypatch, tmp_path, capsys, bad_kind
):
    request = barrier_request()
    context = request["environmental_context"]
    relation = context["workstation_review"]["entry_barriers"][0]
    if bad_kind == "wrong_desk":
        relation["desk_id"] = "entry"
    elif bad_kind == "wrong_barrier":
        relation["barrier_id"] = "missing"
    elif bad_kind == "duplicate_relation":
        context["workstation_review"]["entry_barriers"].append(deepcopy(relation))
    else:
        request = material_application_request()
        fact = request["environmental_context"]["material_facts"][0]
        if bad_kind == "unknown_target":
            fact["application"]["target_request_id"] = "unknown"
        else:
            fact["application"]["metal_exposed"] = condition()
    response = rest_client(monkeypatch).post("/api/fengshui/assess", json=request)
    protocol = asyncio.run(mcp_call("assess", request))
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(request))
    assert run(["fengshui_assess", "--request-file", str(path)]) == 1
    cli = json.loads(capsys.readouterr().out)
    assert response.status_code == 422 and protocol.is_error
    assert (
        response.json()["issues"]
        == protocol.structured_content["issues"]
        == cli["issues"]
    )


def test_evaluation_period_is_explicit_and_independent_of_natal_period():
    request = activity_request()
    assert all(
        c["timeliness"] == "unknown"
        for c in review(request)["findings"][0]["candidates"]
    )
    request["environmental_context"]["workstation_review"]["evaluation_period"] = dict(
        number=9, evidence="本次明确评价九运"
    )
    output = review(request)
    assert output["evaluation_period_context"]["source"] == "explicit_review"
    for c in output["findings"][0]["candidates"]:
        assert c["current_period_number"] == 9
        assert c["timeliness"] == (
            "current" if c["selected_star_number"] == 9 else "not_current"
        )
        assert c["overall_auspiciousness"] == "not_produced"
    request["xuankong"]["interpretation"] = dict(
        current_period_number=8, period_evidence="矛盾的八运"
    )
    with pytest.raises(ValidationError, match="评价运不得矛盾"):
        AssessRequest.model_validate(request)


@pytest.mark.parametrize(
    "material,use,conditions",
    [
        ("water", "water_remedy", {"water_clean": condition(False)}),
        ("metal", "metal_remedy", {"metal_exposed": condition(False)}),
    ],
)
def test_failed_application_condition_does_not_demand_remaining_observations(
    material, use, conditions
):
    result = assess(**material_application_request(material, use, **conditions))
    finding = result["layout_analysis"]["material_analysis"]["findings"][0]
    assert finding["application_analysis"]["status"] == "conditions_not_met"
    assert finding["application_analysis"]["missing_inputs"] == []
    assert result["coverage"]["analysis_progress"]["assessment_complete"]


def test_health_and_alive_are_distinct_and_photo_health_remains_candidate():
    request = material_application_request(
        "living_plant", "wood_remedy", plant_healthy=condition(True, "image_observed")
    )
    app = assess(**request)["layout_analysis"]["material_analysis"]["findings"][0][
        "application_analysis"
    ]
    assert app["status"] == "needs_confirmation"
    assert app["application_conditions"][0]["status"] == "candidate_only"
    assert "plant_healthy" in app["missing_inputs"][0]
    fact = request["environmental_context"]["material_facts"][0]
    fact["plant_alive"] = False
    fact["application"]["plant_healthy"] = condition()
    with pytest.raises(ValidationError, match="死亡植物"):
        AssessRequest.model_validate(request)


def test_ready_fresh_barrier_proposal_preserves_rule_identity_and_scope():
    request = barrier_request()
    fresh = deepcopy(request["environmental_context"])
    request["layout_alternatives"] = [
        dict(
            candidate_id="move",
            object_id="screen",
            changes=["location"],
            environmental_context=fresh,
            physically_feasible=True,
            evidence="独立确认候选的容纳及关系",
        )
    ]
    result = assess(**request)["layout_analysis"]["alternatives_analysis"]["findings"][
        0
    ]
    assert result["status"] == "ready"
    relation = result["workstation_analysis"]["findings"][0]
    assert relation["rule_id"] == "afsi_entry_barrier_v1.entry_line_barrier"
    assert result["rule_comparisons"][0]["method"] == "workstation_authored_review"
    assert not result["old_environmental_context_reused"]
    fresh["workstation_review"]["entry_barriers"][0]["circulation_clear"] = condition(
        False
    )
    result = assess(**request)["layout_analysis"]["alternatives_analysis"]["findings"][
        0
    ]
    action = result["workstation_analysis"]["action_options"][0]
    assert action["status"] == "blocked"
    assert "circulation_clear_not_met" in action["blocking_reasons"]
    assert result["status"] == "blocked"


def test_candidate_preserves_query_period_without_reusing_activity_geometry():
    request = activity_request()
    request["environmental_context"]["workstation_review"]["evaluation_period"] = dict(
        number=9, evidence="本次评价运"
    )
    fresh = deepcopy(request["environmental_context"])
    del fresh["workstation_review"]["evaluation_period"]
    request["layout_constraints"] = [
        dict(object_id="desk", can_relocate=True, evidence="允许搬位")
    ]
    request["layout_alternatives"] = [
        dict(
            candidate_id="move",
            object_id="desk",
            changes=["location"],
            placement=dict(object_id="desk", purpose="desk", location_direction="E"),
            environmental_context=fresh,
            physically_feasible=True,
            evidence="新落宫独立确认",
        )
    ]
    candidate = assess(**request)["layout_analysis"]["alternatives_analysis"][
        "findings"
    ][0]
    assert candidate["workstation_analysis"]["evaluation_period_context"]["number"] == 9
    assert candidate["workstation_analysis"]["findings"][0]["location_direction"] == "E"
    fresh["workstation_review"]["evaluation_period"] = dict(
        number=8, evidence="不能借搬位改运"
    )
    with pytest.raises(ValidationError, match="不得更换本次评价运"):
        AssessRequest.model_validate(request)


def test_source_rules_resolve_and_references_never_enable_p3():
    from fatebridge.core.fengshui.workstation_sources import bundle, provenance

    data = bundle()
    for rule_id, rule in data["rules"].items():
        assert set(rule["source_ids"]) <= data["sources"].keys()
        assert rule_id.split(".")[0] in data["rulesets"]
    for ruleset_id in data["rulesets"]:
        p = provenance(ruleset_id)
        assert p["version"] == "1.0.0" and p["sources"]
        p["sources"].clear()
        assert provenance(ruleset_id)["sources"]
    for value in data["disagreements"].values():
        assert value["rule_id"] in data["rules"]
    for factory in (activity_request, barrier_request, material_application_request):
        result = assess(**factory())
        for trace in result["rule_trace"]:
            if trace.get("rule_id", "").split(".")[0] in data["rulesets"]:
                assert trace["rule_id"] in data["rules"]
                assert set(trace["source_ids"]) <= set(
                    data["rules"][trace["rule_id"]]["source_ids"]
                )
    assert data["non_btb_desktop_reference"]["status"] == "reference_only"
    assert data["non_btb_desktop_reference"]["placement_rules_enabled"] is False


@pytest.mark.parametrize("material", ["unknown", None])
def test_unknown_material_is_pending_identity_not_author_exclusion(material):
    request = material_application_request(material, "wood_remedy")
    fact = request["environmental_context"]["material_facts"][0]
    fact["colour"] = "green"  # Known colour cannot certify unknown material.
    result = assess(**request)["layout_analysis"]["material_analysis"]
    assert (
        result["findings"][0]["application_analysis"]["status"]
        == "needs_material_confirmation"
    )
    assert not result["findings"][0]["application_analysis"]["application_conditions"]
    assert all(
        "water_clean" not in p and "metal_exposed" not in p
        for p in result["missing_inputs"]
    )


def test_photo_dead_candidate_does_not_overrule_confirmed_health_fact():
    request = material_application_request(
        "living_plant", "wood_remedy", plant_healthy=condition()
    )
    fact = request["environmental_context"]["material_facts"][0]
    fact.update(plant_alive=False, observation_basis="image_observed")
    result = assess(**request)["layout_analysis"]["material_analysis"]
    assert result["status"] == "partial"
    assert result["findings"][0]["candidate_only"] is True


def test_material_application_facts_must_survive_a_real_barrier_move():
    request = barrier_request()
    request["environmental_context"]["material_facts"] = [
        dict(
            fact_id="screen-material",
            object_id="screen",
            material="metal",
            element_use="metal_remedy",
            observation_basis="user_confirmed",
            evidence="独立确认屏风材质",
            application=dict(
                ruleset_id="afsi_application_conditions_v1",
                metal_exposed=condition(),
                proportionate_to_space=condition(),
            ),
        )
    ]
    fresh = deepcopy(request["environmental_context"])
    del fresh["material_facts"][0]["application"]["metal_exposed"]
    request["layout_alternatives"] = [
        dict(
            candidate_id="move",
            object_id="screen",
            changes=["location"],
            environmental_context=fresh,
            physically_feasible=True,
            evidence="关系与容纳独立核对",
        )
    ]
    result = assess(**request)["layout_analysis"]["alternatives_analysis"]["findings"][
        0
    ]
    assert result["status"] == "candidate_only"
    assert any(
        p.endswith("application.metal_exposed") for p in result["missing_inputs"]
    )


def test_star_pair_relationship_is_shared_mechanics_without_fortune_judgment():
    from fatebridge.core.divination import ELEMENT_CONTROLS, ELEMENT_GENERATES

    for direction in ("N", "E", "S", "W", "NE", "NW", "SE", "SW"):
        result = review(activity_request(direction=direction))
        for candidate in result["findings"][0]["candidates"]:
            pair = candidate["ordered_pair"]
            m, f = pair["mountain_element"], pair["facing_element"]
            expected = (
                "same_element"
                if m == f
                else (
                    "mountain_generates_facing"
                    if ELEMENT_GENERATES[m] == f
                    else (
                        "facing_generates_mountain"
                        if ELEMENT_GENERATES[f] == m
                        else (
                            "mountain_controls_facing"
                            if ELEMENT_CONTROLS[m] == f
                            else "facing_controls_mountain"
                        )
                    )
                )
            )
            assert pair["relationship"] == expected
            assert candidate["overall_auspiciousness"] == "not_produced"


def test_missing_engineering_fact_cannot_hide_behind_candidate_feasibility():
    request = barrier_request()
    fresh = deepcopy(request["environmental_context"])
    del fresh["workstation_review"]["entry_barriers"][0]["entrance_view_maintained"]
    request["layout_alternatives"] = [
        dict(
            candidate_id="move",
            object_id="screen",
            changes=["location"],
            environmental_context=fresh,
            physically_feasible=True,
            evidence="只确认容纳，不代替视野",
        )
    ]
    result = assess(**request)["layout_analysis"]["alternatives_analysis"]["findings"][
        0
    ]
    assert result["status"] == "conditional_option"
    assert result["calculation_status"] == "complete"
    assert any(
        p["path"].endswith("entrance_view_maintained")
        for p in result["pending_confirmations"]
    )


def test_default_budget_delivery_preserves_same_run_workstation_data(
    monkeypatch, tmp_path
):
    import fatebridge.api as api
    from fatebridge.application import result_delivery as delivery
    from tests.test_result_delivery import reconstruct

    store = delivery.ResultStore(tmp_path / "results")
    monkeypatch.setattr(delivery, "RESULT_STORE", store)
    monkeypatch.setattr(api, "RESULT_STORE", store)

    async def native():
        async with Client(create_mcp_app(scenarios="onda-fengshui")) as client:
            result = await client.call_tool(
                "fengshui_assess",
                {**activity_request(), "include_snapshot_text": False},
            )
            assert not result.is_error
            ref = result.structured_content["result_delivery"]
            assert ref["file_payload_path"] == "payload"
            manifest = json.loads(
                (await client.read_resource(ref["manifest_uri"]))[0].text
            )
            assert (
                manifest["run_metadata"]["run_id"]
                == result.structured_content["run_metadata"]["run_id"]
            )
            original = reconstruct(store, ref["result_id"])
            assert (
                original["run_metadata"]["run_id"] == manifest["run_metadata"]["run_id"]
            )
            branch = original["layout_analysis"]["workstation_analysis"]
            assert branch["findings"][0]["selected_star_role"] == "facing"
            assert (
                branch["non_btb_desktop_reference"]["placement_rules_enabled"] is False
            )
            assert any(
                r["ruleset_id"] == "workstation_activity_authored_v1"
                for r in original["rulesets"]
            )

    asyncio.run(native())


@pytest.mark.parametrize(
    "name,status",
    [
        ("fengshui-workstation-activity", "complete"),
        ("fengshui-entry-barrier", "complete"),
        ("fengshui-material-application", "partial"),
    ],
)
def test_published_workstation_examples_are_executable(name, status):
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "docs/examples" / (name + ".json")
    result = assess(**json.loads(path.read_text()))
    assert result["layout_analysis"]["status"] == status
    if name == "fengshui-workstation-activity":
        assert "向星" in result["snapshot_text"]
        assert "真实水装置需求" in result["snapshot_text"]
    if name == "fengshui-entry-barrier":
        assert "入口隔挡" in result["snapshot_text"]
    if name == "fengshui-material-application":
        assert "剂量、目标位置" in result["snapshot_text"]
