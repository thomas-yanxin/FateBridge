"""Verify Sanshi default_omit budgets, isomorphism, omitted_fields, and output schemas."""

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

SANSHI_TOOLS = (
    "liuren_chart",
    "liuren_yearly_timing",
    "qimen",
    "taiyi",
    "jinkou",
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


@pytest.mark.parametrize("tool_name", SANSHI_TOOLS)
def test_sanshi_default_omit_isomorphic_and_within_10kb(tool_name: str) -> None:
    spec = next(entry for entry in CATALOG if entry.name == tool_name)
    req_data = dict(example_input(spec) or {})
    request = spec.request_model.model_validate(req_data)
    raw = execute_with_receipt(spec, request, options=ExecutionOptions(as_of=AS_OF))

    default_out = deliver_response(raw, spec=spec)
    full_out = deliver_response(raw, spec=spec, include=["*"])

    default_bytes = len(json.dumps(default_out, ensure_ascii=False).encode("utf-8"))
    assert default_bytes <= 10240, f"{tool_name} default payload is {default_bytes}B"
    assert default_out["run_metadata"].get("omitted_fields")
    assert "omitted_fields" not in full_out["run_metadata"]

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


def test_sanshi_optional_modes_stay_within_10kb_and_validate() -> None:
    by_name = {entry.name: entry for entry in CATALOG}
    opts = ExecutionOptions(as_of=AS_OF)

    # jinkou with birth_date omits heavy natal_course.course while keeping diurnal_evidence
    jinkou_spec = by_name["jinkou"]
    jinkou_req = jinkou_spec.request_model.model_validate(
        {**dict(example_input(jinkou_spec) or {}), "birth_date": "1990-05-01"}
    )
    jinkou_raw = execute_with_receipt(jinkou_spec, jinkou_req, options=opts)
    jinkou_default = deliver_response(jinkou_raw, spec=jinkou_spec)
    assert len(json.dumps(jinkou_default, ensure_ascii=False).encode("utf-8")) <= 10240
    assert "diurnal_evidence" in jinkou_default["jinkou"]["overview"]
    output_model_for("jinkou").model_validate(jinkou_default)

    # taiyi day/month/hour modes omit solar_anchors cleanly and stay <= 10 KiB
    taiyi_spec = by_name["taiyi"]
    taiyi_base = dict(example_input(taiyi_spec) or {})
    for mode in ("day", "month", "hour"):
        req = taiyi_spec.request_model.model_validate(
            {**taiyi_base, "calculation_mode": mode}
        )
        raw = execute_with_receipt(taiyi_spec, req, options=opts)
        out = deliver_response(raw, spec=taiyi_spec)
        assert len(json.dumps(out, ensure_ascii=False).encode("utf-8")) <= 10240
        output_model_for("taiyi").model_validate(out)
