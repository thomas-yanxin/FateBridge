"""Three-surface parity (REST/MCP/CLI), include/default_omit delivery, latency, and budget tests."""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any, cast

import pytest
from fastmcp import Client

import fatebridge.mcp_server as mcp
from fatebridge.application.examples import example_input
from fatebridge.application.execution import execute_with_receipt
from fatebridge.application.response_delivery import deliver_response
from fatebridge.cli import run
from fatebridge.core.execution_context import ExecutionOptions
from fatebridge.core.schema_cache import model_schema
from fatebridge.services.tool_catalog import CATALOG
from tests.fixtures.fengshui import payload
from tests.support.fengshui_transports import SPECS, mcp_call
from tests.support.mcp_result_assertions import without_transport
from tests.support.transports import rest_client

AS_OF = "2026-10-12T12:00:00+08:00"

STANDALONE_TOOLS = (
    "fengshui_directions",
    "fengshui_minggua",
    "fengshui_bazhai",
    "fengshui_jinsuo",
    "fengshui_annual_stars",
    "fengshui_monthly_stars",
    "fengshui_xuankong_house_chart",
)

LIGHT_STANDALONE_TOOLS = (
    "fengshui_directions",
    "fengshui_minggua",
    "fengshui_jinsuo",
    "fengshui_annual_stars",
    "fengshui_monthly_stars",
    "fengshui_xuankong_house_chart",
)

TARGETED_INCLUDES: dict[str, list[str]] = {
    "directions": ["layers.directions.directions"],
    "minggua": ["layers.minggua.time_context"],
    "bazhai": ["conflicts"],
    "jinsuo": ["layers.jinsuo.twenty_four_mountains"],
    "annual_stars": ["layers.annual_stars.time_context.timing"],
    "monthly_stars": ["layers.monthly_stars.daily_stars.palaces"],
    "xuankong_natal": ["layers.xuankong_natal.chart.structure.classical_patterns"],
    "assess": ["layout_analysis.element_relationships"],
}


def _assert_isomorphic_subset(subset: object, full: object, *, path: str = "") -> None:
    if isinstance(subset, dict) and isinstance(full, dict):
        for key, value in subset.items():
            if path == "run_metadata" and key == "omitted_fields":
                continue
            assert key in full, f"unexpected key {path}.{key} absent from full output"
            _assert_isomorphic_subset(
                value,
                full[key],
                path=f"{path}.{key}" if path else str(key),
            )
        return
    if isinstance(subset, list) and isinstance(full, list):
        assert len(subset) == len(full), f"length mismatch at {path}"
        for idx, (left, right) in enumerate(zip(subset, full)):
            _assert_isomorphic_subset(left, right, path=f"{path}[{idx}]")
        return
    assert subset == full, f"value mismatch at {path}: {subset!r} != {full!r}"


@pytest.mark.parametrize(
    "name",
    [
        "directions",
        "minggua",
        "bazhai",
        "jinsuo",
        "annual_stars",
        "monthly_stars",
        "xuankong_natal",
        "assess",
    ],
)
def test_three_surface_parity_default_full_and_include(
    name: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    spec = SPECS[name]
    inputs = payload(name)
    targeted = TARGETED_INCLUDES[name]

    modes: list[tuple[str, list[str] | None]] = [
        ("default", None),
        ("full", ["*"]),
        ("targeted", targeted),
    ]
    raw_by_mode: dict[str, dict[str, Any]] = {}

    for mode, include_items in modes:
        params: list[tuple[str, str]] = [("as_of", AS_OF)]
        mcp_req: dict[str, object] = {
            "tool": spec.name,
            "arguments": inputs,
            "as_of": AS_OF,
        }
        cli_flags: list[str] = ["--as-of", AS_OF]
        if include_items is not None:
            params.extend(("include", item) for item in include_items)
            mcp_req["include"] = include_items
            cli_flags.extend(["--include", *include_items])

        http = rest_client(monkeypatch).post(
            spec.rest_path,
            json=inputs,
            params=params,
        )
        assert http.status_code == 200, http.text

        async def _mcp(request_payload: dict[str, object] = mcp_req) -> Any:
            async with Client(mcp.app) as client:
                return await client.call_tool("run_calculation", request_payload)

        protocol = asyncio.run(_mcp())
        assert not protocol.is_error
        req_file = tmp_path / f"{name}_{mode}.json"
        req_file.write_text(json.dumps(inputs), encoding="utf-8")
        capsys.readouterr()
        code = run(
            [
                spec.name,
                "--request-file",
                str(req_file),
                *cli_flags,
            ]
        )
        assert code == 0
        cli_out = json.loads(capsys.readouterr().out)
        rest_json = http.json()
        mcp_json = protocol.structured_content
        assert (
            without_transport(rest_json)
            == without_transport(mcp_json)
            == without_transport(cli_out)
        )
        assert (
            rest_json["run_metadata"].get("omitted_fields")
            == mcp_json["run_metadata"].get("omitted_fields")
            == cli_out["run_metadata"].get("omitted_fields")
        )
        raw_by_mode[mode] = rest_json

    default_out = raw_by_mode["default"]
    full_out = raw_by_mode["full"]
    targeted_out = raw_by_mode["targeted"]

    assert "omitted_fields" not in full_out["run_metadata"]
    _assert_isomorphic_subset(
        without_transport(default_out), without_transport(full_out)
    )
    _assert_isomorphic_subset(
        without_transport(targeted_out), without_transport(full_out)
    )

    default_omitted = default_out["run_metadata"].get("omitted_fields", [])
    targeted_omitted = targeted_out["run_metadata"].get("omitted_fields", [])
    for item in targeted:
        assert item not in targeted_omitted
        if item in default_omitted:
            assert len(targeted_omitted) < len(default_omitted)


def test_invalid_projection_path_reports_constraints_available() -> None:
    res = asyncio.run(
        mcp_call(
            "directions",
            {
                "bearing_degrees": 0,
                "north_reference": "magnetic",
                "fields": ["layers.directions.nonexistent"],
            },
        )
    )
    assert res.is_error
    issue = res.structured_content["issues"][0]
    assert issue["code"] == "unknown_projection_path"
    assert "bearing" in issue["constraints"]["available"]


def test_invalid_include_path_reports_constraints_available_and_suggestions() -> None:
    res = asyncio.run(
        mcp_call(
            "directions",
            {
                "bearing_degrees": 0,
                "north_reference": "magnetic",
                "include": ["layers.directions.bearng"],
            },
        )
    )
    assert res.is_error
    issue = res.structured_content["issues"][0]
    assert issue["code"] == "unknown_projection_path"
    assert "bearing" in issue["constraints"]["available"]
    assert "bearing" in issue["constraints"]["suggestions"]


def test_include_and_fields_mutex_returns_422(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    spec = SPECS["directions"]
    inputs = payload("directions")

    http = rest_client(monkeypatch).post(
        spec.rest_path,
        json=inputs,
        params={"include": "*", "fields": "status"},
    )
    assert http.status_code == 422
    assert http.json()["issues"][0]["code"] == "conflicting_delivery_controls"

    mcp_res = asyncio.run(
        mcp_call(
            "directions",
            {**inputs, "include": ["*"], "fields": ["status"]},
        )
    )
    assert mcp_res.is_error
    assert (
        mcp_res.structured_content["issues"][0]["code"]
        == "conflicting_delivery_controls"
    )

    req_file = tmp_path / "mutex.json"
    req_file.write_text(json.dumps(inputs), encoding="utf-8")
    capsys.readouterr()
    code = run(
        [
            spec.name,
            "--request-file",
            str(req_file),
            "--include",
            "*",
            "--fields",
            "status",
        ]
    )
    assert code == 1
    cli_err = json.loads(capsys.readouterr().out)
    assert cli_err["status_code"] == 422
    assert cli_err["issues"][0]["code"] == "conflicting_delivery_controls"


def test_xuankong_evidence_views_via_include() -> None:
    spec = SPECS["xuankong_natal"]
    options = ExecutionOptions(as_of=AS_OF)
    req = spec.request_model.model_validate(
        {
            "house": {
                "object_id": "home",
                "facing_degrees": 64.5,
                "north_reference": "magnetic",
            },
            "period": {
                "basis": "construction_completion",
                "event_year": 2004,
                "evidence": "边界向与解盘测试",
            },
            "current_period_number": 9,
            "city_gate": {"reference_period_number": 9},
            "interpretation": {
                "timeliness_ruleset_id": "wang_zhongzhou_timeliness_v1",
                "host_guest_ruleset_id": "shen_2011_host_guest_v1",
                "fixed_lingzheng": {},
            },
        }
    )
    raw = execute_with_receipt(spec, req, options=options)

    default_out = cast(dict[str, Any], deliver_response(raw, spec=spec))
    assert (
        "palaces"
        not in default_out["layers"]["xuankong_natal"]["interpretation"]["candidates"][
            0
        ]
    )
    assert (
        "flight_details" not in default_out["layers"]["xuankong_natal"]["candidates"][0]
    )

    cand_out = cast(
        dict[str, Any],
        deliver_response(raw, spec=spec, include=["natal_candidates"]),
    )
    assert "flight_details" in cand_out["layers"]["xuankong_natal"]["candidates"][0]
    assert "timing" in cand_out["layers"]["xuankong_natal"]["period_context"]
    assert "layers.xuankong_natal.candidates.*.flight_details" not in cand_out[
        "run_metadata"
    ].get("omitted_fields", [])

    interp_out = cast(
        dict[str, Any],
        deliver_response(raw, spec=spec, include=["natal_interpretation"]),
    )
    assert (
        "palaces"
        in interp_out["layers"]["xuankong_natal"]["interpretation"]["candidates"][0]
    )
    assert "layers.xuankong_natal.interpretation.candidates.*.palaces" not in (
        interp_out["run_metadata"].get("omitted_fields", [])
    )


def test_wildcard_default_omit_over_empty_lists() -> None:
    options = ExecutionOptions(as_of=AS_OF)

    # Empty occupants=[] in fengshui_bazhai must not emit occupants.* in omitted_fields,
    # and explicitly including the declared wildcard pattern must succeed cleanly.
    bz_spec = SPECS["bazhai"]
    bz_req = bz_spec.request_model.model_validate(
        {
            "house": {
                "object_id": "home",
                "facing_degrees": 180,
                "north_reference": "magnetic",
            },
            "occupants": [],
            "placements": [],
        }
    )
    bz_raw = execute_with_receipt(bz_spec, bz_req, options=options)
    bz_default = cast(dict[str, Any], deliver_response(bz_raw, spec=bz_spec))
    bz_omitted = bz_default["run_metadata"]["omitted_fields"]
    assert "layers.bazhai.occupants.*.time_context.timing" not in bz_omitted
    assert "layers.bazhai.occupants.*.candidates.*.sectors" not in bz_omitted
    bz_inc = cast(
        dict[str, Any],
        deliver_response(
            bz_raw,
            spec=bz_spec,
            include=["layers.bazhai.occupants.*.candidates.*.sectors"],
        ),
    )
    assert bz_inc["layers"]["bazhai"]["occupants"] == []

    # Empty candidates=[] on uniquely resolved fengshui_xuankong_house_chart behaves identically.
    xk_spec = SPECS["xuankong_natal"]
    xk_req = xk_spec.request_model.model_validate(payload("xuankong_natal"))
    xk_raw = execute_with_receipt(xk_spec, xk_req, options=options)
    xk_default = cast(dict[str, Any], deliver_response(xk_raw, spec=xk_spec))
    xk_omitted = xk_default["run_metadata"]["omitted_fields"]
    assert "layers.xuankong_natal.candidates.*.flight_details" not in xk_omitted
    xk_inc = cast(
        dict[str, Any],
        deliver_response(
            xk_raw,
            spec=xk_spec,
            include=["layers.xuankong_natal.candidates.*.flight_details"],
        ),
    )
    assert xk_inc["layers"]["xuankong_natal"]["candidates"] == []


def test_latency_and_payload_and_schema_budgets() -> None:
    options = ExecutionOptions(as_of=AS_OF)
    for spec in [s for s in CATALOG if s.family == "fengshui"]:
        ex = example_input(spec)
        if ex is None:
            ex = {"query_at": "2026-02-04T12:00:00+08:00"}
        req = spec.request_model.model_validate(ex)
        svc_fn, pos, kw = spec.bind(req)
        svc_fn(*pos, **kw)
        t0 = time.perf_counter()
        for _ in range(25):
            svc_fn(*pos, **kw)
        svc_ms = (time.perf_counter() - t0) * 1000 / 25
        assert svc_ms < 3.0, f"{spec.name} too slow: {svc_ms:.2f} ms"

        raw = execute_with_receipt(spec, req, options=options)
        default_out = cast(dict[str, Any], deliver_response(raw, spec=spec))
        full_out = cast(dict[str, Any], deliver_response(raw, spec=spec, include=["*"]))

        _assert_isomorphic_subset(default_out, full_out)
        assert "omitted_fields" not in full_out["run_metadata"]
        omitted = default_out["run_metadata"].get("omitted_fields")
        if omitted:
            assert deliver_response(raw, spec=spec, include=omitted) == full_out
        else:
            assert "omitted_fields" not in default_out["run_metadata"]
            assert default_out == full_out

        default_kb = len(json.dumps(default_out, ensure_ascii=False).encode()) / 1024
        assert spec.output_model is not None
        out_schema_kb = (
            len(
                json.dumps(model_schema(spec.output_model), ensure_ascii=False).encode()
            )
            / 1024
        )
        assert out_schema_kb < 6.0, f"{spec.name} out schema {out_schema_kb:.1f}KB"
        assert default_kb <= 10.0, f"{spec.name} default {default_kb:.1f}KB"
        if spec.name in LIGHT_STANDALONE_TOOLS:
            assert default_kb < 4.5, f"{spec.name} default {default_kb:.1f}KB"

        for removed_key in (
            "rulesets",
            "source_catalog",
            "rule_trace",
            "source_citations",
            "conventions",
        ):
            assert removed_key not in full_out, f"{spec.name} full leaked {removed_key}"
            assert (
                removed_key not in default_out
            ), f"{spec.name} default leaked {removed_key}"
        for layer in full_out["layers"].values():
            assert "ruleset" not in layer
        for layer in default_out["layers"].values():
            assert "ruleset" not in layer

        if spec.name == "fengshui_assess":
            assert set(default_out) == {
                "analysis_type",
                "engine",
                "status",
                "layers",
                "palace_overlay",
                "layout_analysis",
                "coverage",
                "summary",
                "run_metadata",
            }
            assert set(full_out) == {
                "analysis_type",
                "engine",
                "status",
                "layers",
                "palace_overlay",
                "layout_analysis",
                "coverage",
                "conflicts",
                "summary",
                "run_metadata",
            }

        if spec.name in STANDALONE_TOOLS:
            full_kb = len(json.dumps(full_out, ensure_ascii=False).encode()) / 1024
            assert full_kb < 20.0, f"{spec.name} full {full_kb:.1f}KB"
