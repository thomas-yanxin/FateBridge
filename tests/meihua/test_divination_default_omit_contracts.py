"""Verify Divination default_omit budgets, isomorphism, omitted_fields, and output schemas."""

from __future__ import annotations

import json

import pytest

from fatebridge.application.examples import evidence_views, example_input
from fatebridge.application.execution import execute_with_receipt
from fatebridge.application.projection import include_issues
from fatebridge.application.response_delivery import deliver_response
from fatebridge.core.execution_context import ExecutionOptions
from fatebridge.core.response_models import output_model_for
from fatebridge.services.tool_catalog import CATALOG

DIVINATION_TOOLS = (
    "gua_lookup",
    "meihua_time_cast",
    "meihua_cast",
    "combine_four_gua",
    "liuyao",
    "canping",
    "heluo",
    "suzhan",
    "sukuyo_compatibility",
    "interpret_astrology_dice",
    "sanshi_combined_chart",
)
AS_OF = "2026-10-22T12:00:00+08:00"


def _assert_subset(subset: object, superset: object, path: str = "") -> None:
    if isinstance(subset, dict):
        assert isinstance(superset, dict), f"{path}: expected dict"
        for key, value in subset.items():
            assert key in superset, f"{path}.{key} missing in full output"
            _assert_subset(value, superset[key], f"{path}.{key}")
    elif isinstance(subset, list):
        assert isinstance(superset, list) and len(subset) == len(
            superset
        ), f"{path}: list length mismatch"
        for index, (sub_item, super_item) in enumerate(
            zip(subset, superset, strict=True)
        ):
            _assert_subset(sub_item, super_item, f"{path}[{index}]")
    else:
        assert subset == superset, f"{path}: {subset!r} != {superset!r}"


@pytest.mark.parametrize("tool_name", DIVINATION_TOOLS)
def test_divination_default_omit_isomorphic_and_within_10kb(tool_name: str) -> None:
    spec = next(entry for entry in CATALOG if entry.name == tool_name)
    req_data = dict(example_input(spec) or {})
    if tool_name == "liuyao":
        req_data.setdefault("seed", 42)
    request = spec.request_model.model_validate(req_data)
    raw = execute_with_receipt(spec, request, options=ExecutionOptions(as_of=AS_OF))

    default_out = deliver_response(raw, spec=spec)
    full_out = deliver_response(raw, spec=spec, include=["*"])

    default_bytes = len(json.dumps(default_out, ensure_ascii=False).encode("utf-8"))
    assert default_bytes <= 10240, f"{tool_name} default payload is {default_bytes}B"
    assert "omitted_fields" not in full_out["run_metadata"]
    if spec.default_omit:
        assert default_out["run_metadata"].get("omitted_fields")
    else:
        assert "omitted_fields" not in default_out["run_metadata"]

    _assert_subset(
        {k: v for k, v in default_out.items() if k != "run_metadata"},
        {k: v for k, v in full_out.items() if k != "run_metadata"},
        tool_name,
    )

    model = output_model_for(tool_name)
    model.model_validate(default_out)
    model.model_validate(full_out)

    views = evidence_views(spec) or {}
    for view_name in views:
        issues = include_issues(
            raw, [view_name], views=views, default_omit=spec.default_omit
        )
        assert not issues, f"{tool_name} view {view_name} failed: {issues}"
        model.model_validate(deliver_response(raw, spec=spec, include=[view_name]))


def test_astrology_dice_with_sky_omits_chart_under_10kb_and_restores_on_include() -> (
    None
):
    spec = next(entry for entry in CATALOG if entry.name == "interpret_astrology_dice")
    req = spec.request_model.model_validate(
        {
            **dict(example_input(spec) or {}),
            "date": "2024-05-20",
            "time": "14:30",
            "timezone": "Asia/Shanghai",
            "latitude": 31.23,
            "longitude": 121.47,
        }
    )
    raw = execute_with_receipt(spec, req, options=ExecutionOptions(as_of=AS_OF))
    default_out = deliver_response(raw, spec=spec)
    assert len(json.dumps(default_out, ensure_ascii=False).encode("utf-8")) <= 10240
    assert "chart" not in default_out
    assert "chart" in default_out["run_metadata"]["omitted_fields"]

    sky_out = deliver_response(raw, spec=spec, include=["astronomical_context"])
    assert "chart" in sky_out
    model = output_model_for("interpret_astrology_dice")
    model.model_validate(default_out)
    model.model_validate(sky_out)
