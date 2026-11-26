"""Host-callable nested inputs preserve shared contracts and validation."""

import asyncio
from itertools import product
from typing import Optional

import pytest
from fastmcp import Client, FastMCP
from fastmcp.utilities.json_schema import dereference_refs
from jsonschema import Draft202012Validator
from pydantic import BaseModel, Field, ValidationError

from fatebridge.application.examples import example_input
from fatebridge.application.tool_spec import ToolSpec
from fatebridge.core.fengshui.models import Placement
from fatebridge.core.requests.astrology import (
    AstroChartRequest,
    AstroRelativeFlatRequest,
)
from fatebridge.core.schema_cache import model_schema
from fatebridge.mcp_server import _register_mcp_tools, create_mcp_app
from fatebridge.services.tool_catalog import CATALOG
from tests.support.transports import (
    cached_mcp_app,
    call_calculation,
    capability_contracts,
    describe_capability,
)


def test_every_mcp_input_preserves_canonical_constraints_and_examples() -> None:
    async def fetch():
        async with Client(cached_mcp_app()) as client:
            return await capability_contracts(client)

    tools = asyncio.run(fetch())
    for spec in CATALOG:
        if spec.mcp_name is None:
            continue
        else:
            pass
        published = tools[spec.tool_name]["input_schema"]
        canonical = model_schema(spec.request_model)
        Draft202012Validator.check_schema(published)
        assert published == canonical, spec.key
        example = example_input(spec)
        if example is not None:
            Draft202012Validator(published).validate(example)
        else:
            pass
    assess = dereference_refs(tools["fengshui_assess"]["input_schema"])["properties"]
    placement = assess["placements"]["items"]
    assert placement["type"] == "object" and "$ref" not in placement
    assert set(placement["required"]) == {"object_id", "purpose"}
    assert "至少提供位置或朝向" in placement["description"]
    assert placement["allOf"]  # Cross-field rules survive nested MCP publication.
    forms = assess["form_observations"]["items"]
    assert forms["properties"]["purpose"]["enum"] == ["bed", "desk", "stove"]
    assert "无需罗盘" in forms["description"]


@pytest.mark.parametrize(
    "year, error_type",
    [
        (0, "greater_than_equal"),
        (1899, None),
        (2101, None),
        (10000, "less_than_equal"),
    ],
)
def test_western_birth_year_has_local_calendar_bounds(
    year: int, error_type: str | None
) -> None:
    birth = {
        "birth_year": year,
        "birth_month": 5,
        "birth_day": 15,
        "birth_hour": 12,
        "birth_timezone": "UTC",
        "birth_longitude": 0,
        "birth_latitude": 0,
    }
    reference = {**birth, "birth_year": 2000}
    flat = {
        f"{side}_{field}": value
        for side, party in {"inner": reference, "outer": birth}.items()
        for field, value in party.items()
    }
    cases = (
        (AstroChartRequest, birth, ("birth_year",)),
        (AstroRelativeFlatRequest, flat, ("outer_birth_year",)),
    )
    for model, payload, expected_path in cases:
        validator = Draft202012Validator(model_schema(model))
        assert validator.is_valid(payload) is (error_type is None)
        if error_type is None:
            model.model_validate(payload)
        else:
            with pytest.raises(ValidationError) as exc:
                model.model_validate(payload)
            assert [(err["loc"], err["type"]) for err in exc.value.errors()] == [
                (expected_path, error_type)
            ]


def test_recursive_input_falls_back_to_valid_refs_and_remains_callable() -> None:
    class Node(BaseModel):
        value: int = Field(ge=0, description="Non-negative node value")
        child: Optional["Node"] = None

    Node.model_rebuild()

    class Request(BaseModel):
        node: Node

    def bind(request):
        return lambda: {"node": request.node.model_dump()}, (), {}

    spec = ToolSpec(
        key="recursive",
        request_model=Request,
        bind=bind,
        summary="Recursive input",
        operation_label_zh="测试",
        family="test",
    )
    app = FastMCP("recursive contract", dereference_schemas=False)
    _register_mcp_tools(app, [spec])

    async def call():
        async with Client(app) as client:
            schema = (await describe_capability(client, spec.tool_name))["input_schema"]
            Draft202012Validator.check_schema(schema)
            assert "$defs" in schema  # cycles remain finite valid references
            good = {"node": {"value": 2, "child": {"value": 1}}}
            Draft202012Validator(schema).validate(good)
            result = await call_calculation(client, "recursive", good)
            assert result.structured_content["node"]["child"]["value"] == 1
            invalid = await call_calculation(
                client, "recursive", {"node": {"value": -1}}, raise_on_error=False
            )
            assert invalid.is_error

    asyncio.run(call())


@pytest.mark.parametrize(
    "purpose,expected_role",
    [
        ("door", "door_facing"),
        ("bed", "headboard"),
        ("desk", "desk_facing"),
        ("stove", "fire_mouth"),
    ],
)
def test_placement_schema_and_runtime_preserve_cross_field_contract(
    purpose: str, expected_role: str
) -> None:
    validator = Draft202012Validator(model_schema(Placement))
    omitted = object()
    roles = [omitted, None, "door_facing", "headboard", "desk_facing", "fire_mouth"]
    for location, facing, role in product(
        [omitted, None, "NE"], [omitted, None, "W"], roles
    ):
        inputs = {"object_id": "object", "purpose": purpose}
        for field, value in [
            ("location_direction", location),
            ("facing_direction", facing),
            ("facing_role", role),
        ]:
            if value is not omitted:
                inputs[field] = value
            else:
                pass
        has_location = location is not omitted and location is not None
        has_facing = facing is not omitted and facing is not None
        has_role = role is not omitted and role is not None
        expected = (
            (has_location or has_facing)
            and has_facing == has_role
            and (not has_role or role == expected_role)
        )
        assert validator.is_valid(inputs) is expected, inputs
        try:
            Placement.model_validate(inputs)
            accepted = True
        except ValidationError:
            accepted = False
        assert accepted is expected, inputs


def test_published_mcp_schema_rejects_missing_role_for_every_supported_purpose() -> (
    None
):
    async def call():
        async with Client(cached_mcp_app(families="fengshui")) as client:
            tool = await describe_capability(client, "fengshui_assess")
            validator = Draft202012Validator(tool["input_schema"])
            for purpose, role in [
                ("door", "door_facing"),
                ("bed", "headboard"),
                ("desk", "desk_facing"),
                ("stove", "fire_mouth"),
            ]:
                placement = {
                    "object_id": purpose,
                    "purpose": purpose,
                    "facing_direction": "E",
                }
                inputs = {
                    "methods": ["bazhai"],
                    "analyze_layout": True,
                    "placements": [placement],
                }
                assert not validator.is_valid(inputs)
                invalid = await call_calculation(
                    client, "fengshui_assess", inputs, raise_on_error=False
                )
                assert invalid.is_error
                complete_pair = {
                    **inputs,
                    "placements": [{**placement, "facing_role": role}],
                }
                assert validator.is_valid(complete_pair)
                valid = await call_calculation(
                    client,
                    "fengshui_assess",
                    {**complete_pair, "response_char_limit": 0},
                    raise_on_error=False,
                )
                assert not valid.is_error
                assert (
                    valid.structured_content["layout_analysis"]["status"] == "partial"
                )
                assert (
                    valid.structured_content["layout_analysis"]["placement_findings"]
                    == []
                )

    asyncio.run(call())


def test_form_only_calls_need_no_compass_placeholder_and_invalid_layout_stays_rejected() -> (
    None
):
    async def call():
        async with Client(cached_mcp_app(families="fengshui")) as client:
            forms = {
                "methods": [],
                "form_observations": [
                    {
                        "object_id": "desk",
                        "purpose": "desk",
                        "entrance_visible": True,
                        "entrance_direct_line": False,
                        "solid_backing": True,
                        "observation_basis": "user_confirmed",
                        "evidence": "三项已确认",
                    }
                ],
                "include_snapshot_text": False,
            }
            valid = await call_calculation(
                client, "fengshui_assess", {**forms, "response_char_limit": 0}
            )
            assert (
                valid.structured_content["layout_analysis"]["form_analysis"]["status"]
                == "complete"
            )
            invalid = await call_calculation(
                client,
                "fengshui_assess",
                {**forms, "placements": [{"object_id": "desk", "purpose": "desk"}]},
                raise_on_error=False,
            )
            assert invalid.is_error
            assert invalid.structured_content["error_code"] == "validation_error"

    asyncio.run(call())


def test_city_only_career_call_remains_callable_without_explicit_solar_flag() -> None:
    async def call():
        async with Client(cached_mcp_app()) as client:
            result = await call_calculation(
                client,
                "bazi_career",
                {
                    "birth_year": 1990,
                    "birth_month": 5,
                    "birth_day": 15,
                    "birth_hour": 10,
                    "gender": "男",
                    "birth_place": "上海",
                    "as_of": "2026-10-16T12:00:00+08:00",
                    "fields": [
                        "career_analysis.evidence_chain.month_command.month_branch"
                    ],
                    "strict_fields": True,
                    "include_snapshot_text": False,
                },
            )
            assert not result.is_error
            evidence = result.structured_content["career_analysis"]["evidence_chain"]
            assert evidence["month_command"]["month_branch"] == "巳"

    asyncio.run(call())


@pytest.mark.parametrize("hour_input", [{}, {"birth_hour": None}])
def test_unknown_birth_hour_is_rejected_instead_of_fabricated(hour_input) -> None:
    async def call():
        async with Client(cached_mcp_app()) as client:
            result = await call_calculation(
                client,
                "bazi_career",
                {
                    "birth_year": 1990,
                    "birth_month": 5,
                    "birth_day": 15,
                    "birth_place": "上海",
                    **hour_input,
                },
                raise_on_error=False,
            )
            assert result.is_error
            assert "career_analysis" not in (result.structured_content or {})

    asyncio.run(call())
