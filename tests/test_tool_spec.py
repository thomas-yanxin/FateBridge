"""Transport-agnostic tool_spec helpers (shared by REST/MCP/CLI)."""

import inspect

import pytest
from pydantic import BaseModel

from fatebridge.application.bindings import raw_invoke
from fatebridge.application.execution import execute_spec, invalid_input_result
from fatebridge.application.projection import project_fields
from fatebridge.application.tool_spec import ToolSpec
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.transports.mcp import _make_mcp_fn


class _Empty(BaseModel):
    pass


def test_request_service_drift_is_not_silently_ignored():
    class Request(BaseModel):
        value: int
        new_option: bool = True

    def service(value):
        return {"value": value}

    spec = _spec(service, bind=raw_invoke(service))
    with pytest.raises(TypeError, match="new_option"):
        execute_spec(spec, Request(value=1))


def _spec(service, **overrides):
    base = dict(
        key="t",
        bind=lambda req: (service, (), {}),
        request_model=_Empty,
        summary="",
        operation_label_zh="测试",
        family="",
    )
    base.update(overrides)
    return ToolSpec(**base)


def test_project_fields_keeps_subset_and_always_run_metadata():
    payload = {
        "analysis_type": "x",
        "detailed_analysis": {"big": "blob"},
        "run_metadata": {"run_id": "r"},
    }
    out = project_fields(payload, ["analysis_type"])
    assert set(out) == {"analysis_type", "run_metadata"}
    assert out["run_metadata"]["run_id"] == "r"


def test_project_fields_none_or_empty_is_identity():
    payload = {"a": 1, "b": 2}
    assert project_fields(payload, None) == payload
    assert project_fields(payload, []) == payload


def test_project_fields_warns_for_unknown_keys_without_changing_selected_data():
    payload = {"a": 1, "run_metadata": {}}
    out = project_fields(payload, ["a", "no_such_key"])
    assert set(out) == {"a", "run_metadata", "projection_warnings"}
    assert out["projection_warnings"] == [
        {"path": "no_such_key", "code": "unknown_projection_path"}
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
        "snapshot_text": "[起盘信息]...",
        "run_metadata": {"run_id": "r"},
    }


def test_project_fields_dotted_prunes_into_subtree():
    out = project_fields(
        _nested_payload(),
        ["bazi_birth.day_master", "bazi_birth.favorable_elements"],
    )
    # Top level keeps only the requested parent + run_metadata.
    assert set(out) == {"bazi_birth", "run_metadata"}
    # The parent is pruned to exactly the requested sub-keys (heavy ten_gods/shensha dropped).
    assert set(out["bazi_birth"]) == {"day_master", "favorable_elements"}
    assert out["bazi_birth"]["day_master"] == {"stem": "壬", "strength": "弱"}


def test_project_fields_mixes_dotted_and_top_level():
    out = project_fields(_nested_payload(), ["snapshot_text", "bazi_birth.day_master"])
    assert set(out) == {"snapshot_text", "bazi_birth", "run_metadata"}
    assert out["snapshot_text"] == "[起盘信息]..."
    assert set(out["bazi_birth"]) == {"day_master"}


def test_project_fields_whole_parent_overrides_dotted_regardless_of_order():
    # Asking for the whole parent AND a sub-path => keep the whole parent.
    payload = _nested_payload()
    a = project_fields(payload, ["bazi_birth", "bazi_birth.day_master"])
    b = project_fields(payload, ["bazi_birth.day_master", "bazi_birth"])
    assert a["bazi_birth"] == payload["bazi_birth"]
    assert b["bazi_birth"] == payload["bazi_birth"]


def test_project_fields_unknown_subkey_keeps_legacy_shape_and_warns():
    out = project_fields(_nested_payload(), ["bazi_birth.no_such_sub"])
    assert set(out) == {"bazi_birth", "run_metadata", "projection_warnings"}
    assert out["bazi_birth"] == {}
    assert out["projection_warnings"][0]["path"] == "bazi_birth.no_such_sub"


def test_project_fields_dotted_into_scalar_keeps_scalar():
    # A sub-path under a non-dict value just keeps that value (lenient, no crash).
    out = project_fields(_nested_payload(), ["snapshot_text.foo"])
    assert out["snapshot_text"] == "[起盘信息]..."
    assert out["projection_warnings"] == [
        {"path": "snapshot_text.foo", "code": "non_object_projection_path"}
    ]


def _fake_renderers():
    captured = {}

    def render_response(result, **kwargs):
        captured["result"] = result
        captured.update(kwargs)
        return "ok"

    def render_error(result, operation, **kwargs):
        captured["error_result"] = result
        return "err"

    return captured, render_response, render_error


def test_mcp_fn_exposes_fields_param_and_threads_it():
    spec = next(s for s in CATALOG if s.rest_path == "/api/cn/bazi/wealth")
    captured, render_response, render_error = _fake_renderers()
    fn = _make_mcp_fn(spec, render_response=render_response, render_error=render_error)

    assert "fields" in inspect.signature(fn).parameters

    fn(
        birth_year=1990,
        birth_month=6,
        birth_day=15,
        birth_hour=10,
        gender="male",
        dayun_pillar="壬戌",
        fields=["wealth_analysis"],
    )
    assert captured["fields"] == ["wealth_analysis"]


def test_execute_spec_preserves_domain_result_and_error():
    for payload in (
        {"a": 1},
        {"error": "boom", "error_code": "validation_error", "retryable": False},
    ):
        assert execute_spec(_spec(lambda: payload), _Empty()) == payload


def test_invalid_input_result_shape_mirrors_rest_400():
    spec = _spec(lambda: {}, rest_error_label="八字参数")
    out = invalid_input_result(spec)
    assert out["error"] == "无效的八字参数"
    assert out["status_code"] == 400
    assert out["error_code"] == "validation_error"
    assert out["retryable"] is False


def test_mcp_fn_renders_valueerror_as_clean_error():
    # M2: a ValueError raised during binding/validation must render via
    # render_error, not bubble a raw exception out of the MCP tool.
    def _raising_bind(req):
        raise ValueError("bad input")

    spec = _spec(lambda: {}, bind=_raising_bind)
    captured, render_response, render_error = _fake_renderers()
    fn = _make_mcp_fn(spec, render_response=render_response, render_error=render_error)
    assert fn() == "err"
    assert captured["error_result"]["status_code"] == 400
    assert captured["error_result"]["error_code"] == "validation_error"


def test_mcp_fn_invalid_date_renders_error_end_to_end():
    # Complete civil dates are now rejected by shared request validation.
    spec = next(s for s in CATALOG if s.rest_path == "/api/cn/bazi/wealth")
    captured, render_response, render_error = _fake_renderers()
    fn = _make_mcp_fn(spec, render_response=render_response, render_error=render_error)
    out = fn(
        birth_year=1990,
        birth_month=2,
        birth_day=31,
        birth_hour=10,
        gender="male",
        dayun_pillar="壬戌",
    )
    assert out == "err"
    assert captured["error_result"]["status_code"] == 422


def test_mcp_fn_reserved_field_clash_raises():
    class Bad(BaseModel):
        fields: list = []

    spec = ToolSpec(
        key="bad",
        bind=lambda req: (lambda: {}, (), {}),
        request_model=Bad,
        summary="",
        operation_label_zh="",
        family="",
    )
    _, render_response, render_error = _fake_renderers()
    with pytest.raises(ValueError):
        _make_mcp_fn(spec, render_response=render_response, render_error=render_error)
