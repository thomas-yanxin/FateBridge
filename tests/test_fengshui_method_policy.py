"""Method priority never supplies facts or blends personal chart domains."""

import asyncio
from copy import deepcopy

import pytest

from fatebridge.core.fengshui.method_details import (
    method_details,
    method_reference_provenance,
    reference_data,
)
from fatebridge.core.fengshui.method_policy import method_policy, select_methods
from fatebridge.core.fengshui.models import AssessRequest
from fatebridge.core.fengshui.output import Ruleset
from fatebridge.services.fengshui import assess
from tests.fixtures.fengshui import payload


def all_layers(scene="workstation"):
    return {
        "scene": scene,
        "house": {"sitting_trigram": "坎"},
        "occupants": [
            {
                "subject_id": "user",
                "effective_birth_year": 1990,
                "gender_convention": "male",
            }
        ],
        "placements": [
            {"object_id": "desk", "purpose": "desk", "location_direction": "N"}
        ],
        "features": [
            {
                "object_id": "feature",
                "direction": "N",
                "classification": "sand",
                "classification_basis": "user_confirmed",
                "evidence": "独立确认的环境资料",
            }
        ],
        "effective_year": 2026,
    }


@pytest.mark.parametrize("scene", ["workstation", "shared_rental", "home"])
def test_automatic_scene_methods_expand_flying_stars_then_jinsuo_then_bazhai(scene):
    req = AssessRequest.model_validate(all_layers(scene))
    assert req.selected_methods == ["annual_stars", "jinsuo", "bazhai"]
    policy = method_policy(req, explicit_methods=False)
    assert [row["method"] for row in policy["method_priority"]] == [
        "nine_palace_flying_stars",
        "jinsuo",
        "bazhai",
    ]
    assert policy["selected_family_order"] == [
        "nine_palace_flying_stars",
        "jinsuo",
        "bazhai",
    ]
    assert (
        policy["priority_meaning"] == "review_order_not_compensation_or_combined_score"
    )
    assert policy["selection_mode"] == "input_driven_default"


@pytest.mark.parametrize(
    "explicit", [[], ["bazhai"], ["jinsuo", "annual_stars", "bazhai"]]
)
def test_explicit_selection_and_order_are_authoritative(explicit):
    inputs = {**all_layers(), "methods": explicit}
    req = AssessRequest.model_validate(inputs)
    assert req.selected_methods == explicit
    assert (
        method_policy(req, explicit_methods=True)["selected_method_order"] == explicit
    )
    assert select_methods(inputs) == explicit
    policy = method_policy(req, explicit_methods=True)
    for priority in policy["method_priority"]:
        selected_layers = [m for m in explicit if m in priority["engine_layers"]]
        assert priority["selected_engine_layers"] == selected_layers
        if not selected_layers:
            assert priority["selection_status"] == "reference_only_not_selected"
            assert priority["judgment_scope"] == "no_calculation_or_physical_judgment"


def test_no_date_or_historical_inputs_are_created_to_satisfy_priority():
    inputs = all_layers()
    del inputs["effective_year"]
    req = AssessRequest.model_validate(inputs)
    assert req.selected_methods == ["jinsuo", "bazhai"]
    assert req.effective_year is None and req.query_at is None and req.xuankong is None
    policy = method_policy(req)
    assert policy["method_priority"][0]["method"] == "nine_palace_flying_stars"
    assert policy["fact_availability"]["annual_reference_supplied"] is False
    assert policy["fact_availability"]["natal_inputs_supplied"] is False


def test_real_natal_inputs_precede_annual_without_merging_their_dates():
    inputs = all_layers()
    inputs["xuankong"] = payload("xuankong_natal")
    del inputs["house"]
    req = AssessRequest.model_validate(inputs)
    assert req.selected_methods == [
        "xuankong_natal",
        "annual_stars",
        "jinsuo",
        "bazhai",
    ]
    earlier = assess(**inputs)
    later = assess(**{**inputs, "effective_year": 2027})
    assert earlier["layers"]["xuankong_natal"] == later["layers"]["xuankong_natal"]
    assert earlier["layers"]["annual_stars"] != later["layers"]["annual_stars"]


def test_raw_legacy_default_and_form_only_selection_remain_compatible():
    assert AssessRequest().selected_methods == ["bazhai", "jinsuo", "annual_stars"]
    form = {
        "object_id": "desk",
        "purpose": "desk",
        "observation_basis": "user_confirmed",
        "evidence": "形态独立确认",
        "entrance_visible": True,
    }
    assert AssessRequest(form_observations=[form]).selected_methods == []
    assert (
        AssessRequest(scene="workstation", form_observations=[form]).selected_methods
        == []
    )
    assert (
        method_policy(AssessRequest(scene="workstation"))["supplemental_rules"][
            "desktop_btb"
        ]
        == "explicit_surface_ruleset_only_not_a_main_method"
    )


def test_context_alone_is_not_legacy_three_method_request():
    assert select_methods({"environmental_context": {}}) == []


def test_environment_layers_ignore_birth_conventions_and_never_invent_location():
    inputs = all_layers()
    inputs["methods"] = ["annual_stars", "jinsuo"]
    inputs["placements"] = [
        {
            "object_id": "desk",
            "purpose": "desk",
            "facing_direction": "N",
            "facing_role": "desk_facing",
        }
    ]
    before = assess(**inputs)
    changed = deepcopy(inputs)
    changed["occupants"][0].update(
        effective_birth_year=2000, gender_convention="female"
    )
    after = assess(**changed)
    assert before["layers"] == after["layers"]
    assert before["layout_analysis"]["placement_findings"] == []
    assert (
        "placements.desk.location_direction"
        in before["layout_analysis"]["missing_inputs"]
    )
    policy = method_policy(AssessRequest.model_validate(inputs))
    assert policy["fact_availability"]["provided_location_object_ids"] == []
    for method in ("nine_palace_flying_stars", "jinsuo"):
        assert policy["domains"][method]["primary_subject"] == "objective_environment"
        assert (
            "personal_bazi_favorable_elements"
            in policy["domains"][method]["excluded_inputs"]
        )
    assert (
        policy["domains"]["bazhai"]["primary_subject"]
        == "person_minggua_and_house_relation"
    )


def test_reference_provenance_separates_user_requirements_classics_and_authored_prompts():
    provenance = method_reference_provenance()
    Ruleset.model_validate(provenance)
    sources = {source["source_id"]: source for source in provenance["sources"]}
    assert sources["EXPERT_20261015"]["kind"] == "user_supplied_expert_requirements"
    assert sources["SHUOGUA_PRIMARY"]["kind"] == "primary_text_transcription"
    assert (
        sources["FATEBRIDGE_OBSERVATION_REFERENCE"]["kind"]
        == "authored_observation_reference"
    )
    assert sources["EXPERT_20261015"]["url"] == ""

    def check_ids(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key == "source_ids":
                    assert set(item) <= set(sources)
                else:
                    check_ids(item)
        elif isinstance(value, list):
            for item in value:
                check_ids(item)

    check_ids(method_details())
    check_ids(reference_data("policy"))


def test_fixed_palaces_are_distinct_from_visiting_stars_and_center_has_no_role():
    details = method_details()
    assert details["status"] == "reference_only"
    assert len(details["palaces"]) == len(details["star_elements"]) == 9
    assert details["palaces"]["N"]["fixed_palace_element"] == "水"
    annual = assess(methods=["annual_stars"], effective_year=2026)["layers"][
        "annual_stars"
    ]
    assert annual["palaces"]["N"]["annual_star"]["element"] == "金"
    center = details["palaces"]["C"]
    assert center["fixed_palace_trigram"] is None and center["family_role"] is None
    assert center["occupation_reference"]["status"] == "not_covered"


def test_reference_filter_preserves_family_order_and_does_not_fabricate_career_tables():
    assert list(
        method_details(["jinsuo", "annual_stars", "xuankong_natal"])["methods"]
    ) == ["jinsuo", "nine_palace_flying_stars"]
    assert method_details([])["methods"] == {}
    details = method_details()
    known_roles = {
        direction
        for direction, reference in details["palaces"].items()
        if reference["occupation_reference"]["status"] == "limited_classical_role"
    }
    assert known_roles == {"NE", "SE", "W", "NW"}
    assert all(
        candidate["classification"] == "requires_confirmation"
        for candidate in details["sand_water_reference"]["candidate_observations"]
    )


def test_reference_callers_cannot_mutate_shared_registry():
    details = method_details()
    details["palaces"]["N"]["fixed_palace_element"] = "火"
    details["methods"].clear()
    details["ruleset"]["sources"].clear()
    fresh = method_details()
    assert fresh["palaces"]["N"]["fixed_palace_element"] == "水"
    assert len(fresh["methods"]) == 3
    assert fresh["ruleset"]["sources"]


@pytest.mark.parametrize("typed", [False, True])
def test_automatic_selection_includes_independent_candidate_features(typed):
    from fatebridge.core.fengshui.models import AssessRequest, LayoutAlternative
    from tests.test_fengshui_planning import proposal_request

    inputs = proposal_request()
    inputs.pop("methods")
    candidate = inputs["layout_alternatives"][0]
    candidate["features"] = [
        {
            "object_id": candidate["object_id"],
            "direction": candidate["placement"]["location_direction"],
            "classification": "sand",
            "classification_basis": "user_confirmed",
            "evidence": "独立确认候选新位置砂水",
        }
    ]
    if typed:
        inputs["layout_alternatives"] = [LayoutAlternative.model_validate(candidate)]
    assert "jinsuo" in AssessRequest.model_validate(inputs).selected_methods


@pytest.mark.parametrize("scene", ["workstation", "shared_rental"])
def test_preferred_method_availability_is_separate_from_complete_bazhai(scene):
    inputs = all_layers(scene)
    inputs.pop("features")
    inputs.pop("effective_year")
    result = assess(**inputs)
    assert list(result["layers"]) == ["bazhai"]
    assert result["coverage"]["requested_analysis_status"] == "complete"
    assert result["coverage"]["analysis_progress"]["assessment_complete"] is True
    policy = result["method_policy"]
    assert policy["priority_review_status"] == "partial"
    assert policy["priority_missing_methods"] == ["nine_palace_flying_stars", "jinsuo"]
    assert policy["priority_missing_inputs"]
    assert (
        "optional_preferred_method_review"
        in policy["priority_missing_inputs_required_for"]
    )
    for row in policy["method_priority"][:2]:
        assert row["not_selected_reason"] == "automatic_missing_inputs"
        assert row["available_engine_layers"] == []
        assert all(
            layer["availability"] == "not_computed"
            for layer in row["layer_availability"]
        )
    assert policy["method_priority"][2]["available_engine_layers"] == ["bazhai"]


@pytest.mark.parametrize("scene", ["workstation", "shared_rental"])
def test_explicitly_excluded_methods_do_not_request_more_inputs(scene):
    inputs = all_layers(scene)
    inputs.update(methods=["bazhai"])
    inputs.pop("features")
    inputs.pop("effective_year")
    policy = assess(**inputs)["method_policy"]
    assert policy["priority_review_status"] == "complete"
    assert policy["priority_missing_methods"] == policy["priority_missing_inputs"] == []
    assert all(
        row["not_selected_reason"] == "explicitly_excluded"
        for row in policy["method_priority"][:2]
    )
    empty = assess(scene=scene, methods=[])["method_policy"]
    assert empty["priority_review_status"] == "not_requested"
    assert empty["priority_missing_methods"] == empty["priority_missing_inputs"] == []


def test_local_priority_is_not_imposed_on_home_reference_scope():
    inputs = all_layers("home")
    inputs.pop("features")
    inputs.pop("effective_year")
    policy = assess(**inputs)["method_policy"]
    assert policy["priority_scope"] == "main_method_reference"
    assert policy["priority_review_status"] == "not_requested"
    assert policy["priority_missing_methods"] == policy["priority_missing_inputs"] == []
    assert (
        policy["method_priority"][0]["not_selected_reason"]
        == "automatic_missing_inputs"
    )


def test_availability_does_not_certify_unresolved_historical_chart_from_input_presence():
    natal = payload("xuankong_natal")
    natal["house"]["facing_degrees"] = 7.5
    result = assess(scene="workstation", methods=["xuankong_natal"], xuankong=natal)
    policy = result["method_policy"]
    flying = policy["method_priority"][0]
    historical = next(
        row
        for row in flying["layer_availability"]
        if row["engine_layer"] == "xuankong_natal"
    )
    assert historical["input_presence_sufficient"] is True
    assert historical["availability"] == "computed_partial"
    assert historical["calculation_status"] == "partial"
    assert (
        "xuankong_natal.unambiguous_bearing" in historical["calculation_missing_inputs"]
    )
    assert flying["available_engine_layers"] == []
    assert policy["priority_review_status"] == "partial"
    assert policy["priority_missing_methods"] == ["nine_palace_flying_stars"]


def test_method_policy_never_computes_unselected_or_unprovided_result_layers(
    monkeypatch,
):
    def forbidden(*args, **kwargs):
        raise AssertionError("availability must reuse results without calculating")

    monkeypatch.setattr("fatebridge.core.fengshui.annual.annual_stars", forbidden)
    monkeypatch.setattr("fatebridge.core.fengshui.xuankong.xuankong_natal", forbidden)
    monkeypatch.setattr("fatebridge.core.fengshui.jinsuo.jinsuo", forbidden)
    req = AssessRequest.model_validate(all_layers())
    policy = method_policy(req, explicit_methods=False)
    assert policy["priority_review_status"] == "not_assessed"
    assert policy["priority_missing_methods"] == []
    for priority in policy["method_priority"]:
        assert priority["available_engine_layers"] == []
        assert all(
            row["availability"] == "not_computed"
            for row in priority["layer_availability"]
        )


def test_sand_water_availability_records_current_and_candidate_inputs_separately():
    from tests.test_fengshui_planning import proposal_request

    inputs = proposal_request()
    inputs.pop("methods")
    candidate = inputs["layout_alternatives"][0]
    candidate["features"] = [
        {
            "object_id": candidate["object_id"],
            "direction": candidate["placement"]["location_direction"],
            "classification": "sand",
            "classification_basis": "user_confirmed",
            "evidence": "候选独立砂水确认，不冒充现状特征",
        }
    ]
    req = AssessRequest.model_validate(inputs)
    policy = method_policy(req, explicit_methods=False)
    jinsuo = policy["method_priority"][1]["layer_availability"][0]
    current, proposed = jinsuo["input_scopes"]
    assert current["scope"] == "current_environment"
    assert current["input_presence_status"] == "missing_inputs"
    assert proposed["scope"] == "candidate_environment"
    assert proposed["candidate_id"] == candidate["candidate_id"]
    assert proposed["input_presence_status"] == "required_inputs_present_not_computed"
    assert jinsuo["availability"] == "not_computed"


@pytest.mark.parametrize(
    "classification,expected", [("sand", "complete"), ("unknown", "partial")]
)
def test_real_candidate_availability_never_upgrades_current_missing_environment(
    classification, expected
):
    from tests.test_fengshui_planning import proposal_request

    inputs = proposal_request()
    inputs.pop("methods")
    inputs["scene"] = "workstation"
    candidate = inputs["layout_alternatives"][0]
    candidate["features"] = [
        {
            "object_id": candidate["object_id"],
            "direction": candidate["placement"]["location_direction"],
            "classification": classification,
            "classification_basis": "user_confirmed",
            "evidence": "只用于候选独立判断，不替现状补观察",
        }
    ]
    result = assess(**inputs)
    policy = result["method_policy"]
    jinsuo = policy["method_priority"][1]
    assert jinsuo["available_engine_layers"] == []
    assert jinsuo["available_engine_layers_scope"] == "current_calculation_only"
    assert jinsuo["layer_availability"][0]["availability"] == "computed_partial"
    assert policy["priority_review_status"] == "partial"
    assert policy["priority_missing_methods"] == ["jinsuo"]
    reviews = policy["priority_review_by_scope"]
    assert reviews["current"]["priority_review_status"] == "partial"
    planned = reviews["candidates"][0]
    assert planned["candidate_id"] == candidate["candidate_id"]
    assert planned["priority_review_status"] == expected
    if expected == "complete":
        assert jinsuo["available_candidate_engine_layers"][
            candidate["candidate_id"]
        ] == ["jinsuo"]
        assert planned["priority_missing_methods"] == []
    else:
        assert (
            jinsuo["available_candidate_engine_layers"][candidate["candidate_id"]] == []
        )
        assert planned["priority_missing_methods"] == ["jinsuo"]
    calculation = jinsuo["layer_availability"][0]["candidate_calculations"][0]
    assert calculation["scope"] == "candidate_calculation"
    assert calculation["calculation_status"] == expected


def test_candidate_input_presence_is_not_a_computed_availability_without_result_records():
    from tests.test_fengshui_planning import proposal_request

    inputs = proposal_request()
    inputs["scene"] = "workstation"
    inputs["methods"] = ["annual_stars"]
    req = AssessRequest.model_validate(inputs)
    current = {"annual_stars": {"status": "complete", "missing_inputs": []}}
    policy = method_policy(req, explicit_methods=True, layer_results=current)
    assert policy["priority_review_status"] == "complete"
    flying = policy["method_priority"][0]
    candidate_id = inputs["layout_alternatives"][0]["candidate_id"]
    assert flying["available_candidate_engine_layers"][candidate_id] == []
    assert (
        policy["priority_review_by_scope"]["candidates"][0]["priority_review_status"]
        == "not_assessed"
    )


@pytest.mark.parametrize("provided_null", [False, True])
def test_auto_selection_survives_validation_dump_and_service_binding(provided_null):
    inputs = all_layers()
    inputs.pop("features")
    inputs.pop("effective_year")
    if provided_null:
        inputs["methods"] = None
    request = AssessRequest.model_validate(inputs)
    assert request.methods is None
    assert request.selected_methods == ["bazhai"]
    dumped = request.model_dump()
    assert dumped["methods"] is None
    result = assess(**dumped)
    assert list(result["layers"]) == ["bazhai"]
    assert result["method_policy"]["selection_mode"] == "input_driven_default"
    assert result["method_policy"]["priority_review_status"] == "partial"
    assert result["method_policy"]["priority_missing_methods"] == [
        "nine_palace_flying_stars",
        "jinsuo",
    ]
    assert all(
        row["not_selected_reason"] == "automatic_missing_inputs"
        for row in result["method_policy"]["method_priority"][:2]
    )


@pytest.mark.parametrize("provided_null", [False, True])
def test_actual_mcp_default_and_materialized_null_keep_automatic_priority(
    provided_null,
):
    from fastmcp import Client

    from fatebridge.mcp_server import create_mcp_app

    inputs = all_layers("shared_rental")
    inputs.pop("features")
    inputs.pop("effective_year")
    if provided_null:
        inputs["methods"] = None

    async def call():
        async with Client(create_mcp_app()) as client:
            tool = next(
                t for t in await client.list_tools() if t.name == "fengshui_assess"
            )
            assert (
                tool.model_dump(by_alias=True)["inputSchema"]["properties"]["methods"][
                    "default"
                ]
                is None
            )
            return await client.call_tool(
                "fengshui_assess",
                {
                    **inputs,
                    "fields": ["method_policy", "coverage.method_priority_review"],
                    "strict_fields": True,
                    "include_snapshot_text": False,
                    "response_char_limit": 0,
                },
            )

    result = asyncio.run(call())
    assert not result.is_error
    body = result.structured_content
    assert body["method_policy"]["selection_mode"] == "input_driven_default"
    assert (
        body["coverage"]["method_priority_review"]["priority_review_status"]
        == "partial"
    )
    assert body["coverage"]["method_priority_review"]["priority_missing_methods"] == [
        "nine_palace_flying_stars",
        "jinsuo",
    ]
