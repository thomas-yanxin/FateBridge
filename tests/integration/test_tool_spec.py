"""Transport-agnostic tool_spec helpers (shared by REST/MCP/CLI)."""

import asyncio

import pytest
from fastmcp import Client, FastMCP
from pydantic import BaseModel

from fatebridge.application.bindings import bind_kwargs
from fatebridge.application.execution import invoke_validated_service
from fatebridge.application.projection import project_fields
from fatebridge.application.tool_spec import ToolSpec
from fatebridge.mcp_server import _register_mcp_tools
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.utils.errors import ParameterError


class _Empty(BaseModel):
    pass


def test_request_service_drift_is_not_silently_ignored() -> None:
    class Request(BaseModel):
        value: int
        new_option: bool = True

    def service(value):
        return {"value": value}

    spec = _spec(service, bind=bind_kwargs(service))
    with pytest.raises(TypeError, match="new_option"):
        invoke_validated_service(spec, Request(value=1))


def _spec(service, **overrides):
    base = dict(
        name="t",
        bind=lambda req: (service, (), {}),
        request_model=_Empty,
        summary="",
        operation_label_zh="测试",
        family="",
    )
    base.update(overrides)
    return ToolSpec(**base)


def test_project_fields_keeps_subset_and_always_run_metadata() -> None:
    payload = {
        "analysis_type": "x",
        "detailed_analysis": {"big": "blob"},
        "run_metadata": {"run_id": "r"},
    }
    out = project_fields(payload, ["analysis_type"])
    assert set(out) == {"analysis_type", "run_metadata"}
    assert out["run_metadata"]["run_id"] == "r"


def test_project_fields_none_or_empty_is_identity() -> None:
    payload = {"a": 1, "b": 2}
    assert project_fields(payload, None) == payload
    assert project_fields(payload, []) == payload


def test_project_fields_rejects_unknown_keys_with_available_options() -> None:
    payload = {"a": 1, "b": 2, "run_metadata": {}}
    with pytest.raises(ParameterError) as exc_info:
        project_fields(payload, ["a", "no_such_key"])
    assert exc_info.value.issues == [
        {
            "path": "no_such_key",
            "code": "unknown_projection_path",
            "constraints": {"available": ["a", "b", "run_metadata"]},
        }
    ]


def _nested_payload():
    return {
        "analysis_type": "八字命盘",
        "bazi_birth": {
            "day_master": {"stem": "壬", "strength": "弱"},
            "favorable_elements": ["金", "水"],
            "element_distribution": {"木": 44.0, "水": 20.0},
            "ten_gods": {"big": "blob"},
            "shensha": [1, 2, 3],
        },
        "summary": "summary-text",
        "run_metadata": {"run_id": "r"},
    }


def test_project_fields_dotted_prunes_into_subtree() -> None:
    out = project_fields(
        _nested_payload(),
        ["bazi_birth.day_master", "bazi_birth.favorable_elements"],
    )
    assert set(out) == {"bazi_birth", "run_metadata"}
    assert set(out["bazi_birth"]) == {"day_master", "favorable_elements"}
    assert out["bazi_birth"]["day_master"] == {"stem": "壬", "strength": "弱"}


def test_project_fields_mixes_dotted_and_top_level() -> None:
    out = project_fields(_nested_payload(), ["summary", "bazi_birth.day_master"])
    assert set(out) == {"summary", "bazi_birth", "run_metadata"}
    assert out["summary"] == "summary-text"
    assert set(out["bazi_birth"]) == {"day_master"}


def test_project_fields_whole_parent_overrides_dotted_regardless_of_order() -> None:
    payload = _nested_payload()
    a = project_fields(payload, ["bazi_birth", "bazi_birth.day_master"])
    b = project_fields(payload, ["bazi_birth.day_master", "bazi_birth"])
    assert a["bazi_birth"] == payload["bazi_birth"]
    assert b["bazi_birth"] == payload["bazi_birth"]


def test_project_fields_unknown_subkey_fails_strictly() -> None:
    with pytest.raises(ParameterError) as exc_info:
        project_fields(_nested_payload(), ["bazi_birth.no_such_sub"])
    issue = exc_info.value.issues[0]
    assert issue["path"] == "bazi_birth.no_such_sub"
    assert issue["code"] == "unknown_projection_path"
    assert "day_master" in issue["constraints"]["available"]


def test_project_fields_dotted_into_scalar_fails_strictly() -> None:
    with pytest.raises(ParameterError) as exc_info:
        project_fields(_nested_payload(), ["summary.foo"])
    assert exc_info.value.issues == [
        {"path": "summary.foo", "code": "non_object_projection_path"}
    ]


def _call_mcp(spec, arguments, **options):
    server = FastMCP("test")
    _register_mcp_tools(server, [spec])

    async def call():
        async with Client(server) as client:
            return await client.call_tool(
                "run_calculation",
                {"tool": spec.name, "arguments": arguments, **options},
                raise_on_error=False,
            )

    return asyncio.run(call())


def test_mcp_threads_fields_to_projection() -> None:
    result = _call_mcp(
        _spec(lambda: {"selected": 1, "other": 2}),
        {},
        fields=["selected"],
    )
    assert not result.is_error
    assert set(result.structured_content) == {"selected", "run_metadata"}


def test_invoke_validated_service_preserves_domain_result_and_error() -> None:
    for payload in (
        {"a": 1},
        {"error": "boom", "error_code": "validation_error", "retryable": False},
    ):
        assert invoke_validated_service(_spec(lambda: payload), _Empty()) == payload


def test_mcp_preserves_binding_value_error_message() -> None:
    def _raising_bind(req):
        raise ValueError("bad input")

    spec = _spec(lambda: {}, bind=_raising_bind)
    result = _call_mcp(spec, {})
    assert result.is_error
    assert result.structured_content["status_code"] == 400
    assert result.structured_content["error_code"] == "validation_error"
    assert result.structured_content["error"] == "bad input"


def test_mcp_invalid_date_renders_error_end_to_end() -> None:
    # Complete civil dates are now rejected by shared request validation.
    spec = next(spec for spec in CATALOG if spec.name == "bazi_wealth")
    result = _call_mcp(
        spec,
        dict(
            birth_year=1990,
            birth_month=2,
            birth_day=31,
            birth_hour=10,
            gender="male",
            dayun_pillar="壬戌",
        ),
    )
    assert result.is_error
    assert result.structured_content["status_code"] == 422


def test_mcp_arguments_are_separate_from_delivery_controls() -> None:
    class Request(BaseModel):
        fields: list[str]

    spec = ToolSpec(
        name="field_calculation",
        bind=bind_kwargs(lambda fields: {"selection": fields, "other": 2}),
        request_model=Request,
        summary="",
        operation_label_zh="",
        family="",
    )
    result = _call_mcp(spec, {"fields": ["domain"]}, fields=["selection"])
    assert not result.is_error
    assert result.structured_content["selection"] == ["domain"]
    assert "other" not in result.structured_content
